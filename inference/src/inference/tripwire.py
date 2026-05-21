"""Gangway tripwire crossing detection — emits WAGON_EXIT and WAGON_ENTRY events.

One TripwireHandler instance per gangway camera. Gangway cameras bypass ZoneCounter
entirely; only TripwireHandler runs for zone: gangway-fwd / gangway-aft.

Threading model: process_frame() is sync (called from GStreamer streaming thread);
async work is scheduled onto the asyncio loop via run_coroutine_threadsafe, matching
the pattern in callback.py.

No os.environ.get() — all config via injected Settings (Rule 8).
No GStreamer or pipeline imports (Rule 6).

Traversal semantics: events carry 'traversal: from_to | to_from' from the camera-frame
perspective. Train direction-of-travel is NOT computed at the edge — push-pull trains
reverse on return legs and the edge has no cab-active signal (Stadler SNMP OID TBD).
Runtime direction enrichment is deferred (see deferred-work.md W-traversal).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import structlog
from oebb_shared.events import (
    EventEnvelope,
    EventType,
    WagonEntryPayload,
    WagonExitPayload,
)
from oebb_shared.http.retry import DEFAULT_RETRY

from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder

log = structlog.get_logger(__name__)

_CONFIDENCE_THRESHOLD = 0.70
_DEFAULT_ORPHAN_TIMEOUT_S = 10.0
# Maximum number of track_ids retained in _last_side before oldest entries are pruned.
# Monotonically-increasing tracker ids accumulate over a journey; cap prevents unbounded growth.
_LAST_SIDE_MAX_SIZE = 2000


@dataclass
class TripwireConfig:
    """Static configuration extracted from a gangway camera entry in cameras.json."""

    coach_from: str
    coach_to: str
    direction_axis: str
    traversal: Literal["from_to", "to_from"]  # per-journey camera-frame orientation
    tripwire_polygon: list[list[int]]  # list of [x, y] points forming the line


@dataclass
class _PendingExit:
    """State for a WAGON_EXIT that is awaiting a paired WAGON_ENTRY."""

    coach_from: str
    coach_to: str
    traversal: str
    confidence: float
    orphan_handle: asyncio.TimerHandle | None = None


class TripwireHandler:
    """Detects persons crossing a gangway tripwire and emits WAGON_EXIT/ENTRY events.

    One instance per gangway camera. The handler tracks which side of the tripwire
    each track_id was last seen on; a side-change constitutes a crossing.

    Traversal field: "from_to" when centroid crossed from coach_from side to coach_to
    side; "to_from" for reverse crossing. train direction-of-travel is NOT inferred —
    push-pull operation invalidates static direction_axis assumptions.

    Orphan timer: armed only for from_to crossings on gangway-fwd. to_from crossings
    are emitted with expect_orphan=True and no timer (the aft handler will not see
    a matching WAGON_ENTRY for a reverse exit from fwd).
    """

    def __init__(
        self,
        camera: dict[str, Any],
        settings: Settings,
        event_store_client: httpx.AsyncClient,
        loop_holder: LoopHolder,
        journey_holder: JourneyHolder,
    ) -> None:
        zone = str(camera.get("zone", ""))
        if zone not in ("gangway-fwd", "gangway-aft"):
            raise RuntimeError(
                f"TripwireHandler requires zone gangway-fwd/aft, got {zone!r}"
            )

        tripwire_raw = camera.get("tripwire")
        if not tripwire_raw or "tripwire_polygon" not in tripwire_raw:
            raise RuntimeError(
                f"Camera {camera.get('camera_id')!r} has zone={zone!r} but "
                f"missing 'tripwire.tripwire_polygon' field"
            )

        # P7: validate all required config fields (AC1)
        for required in ("coach_from", "coach_to", "direction_axis"):
            if not camera.get(required):
                raise RuntimeError(
                    f"Camera {camera.get('camera_id')!r} has zone={zone!r} but "
                    f"missing required field '{required}'"
                )

        traversal_raw = str(camera.get("traversal", "from_to"))
        if traversal_raw not in ("from_to", "to_from"):
            raise RuntimeError(
                f"Camera {camera.get('camera_id')!r} has invalid traversal={traversal_raw!r}; "
                f"expected 'from_to' or 'to_from'"
            )

        self._config = TripwireConfig(
            coach_from=str(camera["coach_from"]),
            coach_to=str(camera["coach_to"]),
            direction_axis=str(camera["direction_axis"]),
            traversal=traversal_raw,  # type: ignore[arg-type]
            tripwire_polygon=[list(p) for p in tripwire_raw["tripwire_polygon"]],
        )
        self._camera_id = str(camera["camera_id"])
        self._camera_zone = zone
        self._settings = settings
        self._client = event_store_client
        self._loop_holder = loop_holder
        self._journey_holder = journey_holder

        # track_id → last observed side ("from" | "to")
        # Capped at _LAST_SIDE_MAX_SIZE to prevent unbounded growth over long journeys (P5).
        # P9: OrderedDict for LRU eviction — move_to_end on every write keeps
        # recently-active tracks safe; eviction prunes truly-oldest entries.
        self._last_side: OrderedDict[int, str] = OrderedDict()
        # track_id → pending exit state (waiting for paired WAGON_ENTRY)
        self._pending_exits: dict[int, _PendingExit] = {}

        # Allow tests to shorten the timeout
        self._orphan_timeout_s: float = _DEFAULT_ORPHAN_TIMEOUT_S

    # ------------------------------------------------------------------
    # Public sync entry point (called from GStreamer streaming thread)
    # ------------------------------------------------------------------

    def process_frame(
        self,
        track_id: int,
        bbox: tuple[float, float, float, float],
        confidence: float | None,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Schedule async crossing detection onto the asyncio loop.

        Called synchronously from OccupancyCallback.__call__ on the GStreamer
        streaming thread. Matches the run_coroutine_threadsafe pattern used
        throughout callback.py.
        """
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._handle_detection(track_id, bbox, confidence),
                loop,
            )
            fut.add_done_callback(self._on_done)
        except RuntimeError as exc:
            log.warning(
                "tripwire.schedule_during_shutdown",
                camera_id=self._camera_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Core async logic
    # ------------------------------------------------------------------

    async def _handle_detection(
        self,
        track_id: int,
        bbox: tuple[float, float, float, float],
        confidence: float | None,
    ) -> None:
        """Determine side of tripwire for this detection; emit events on crossing."""
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        current_side = self._centroid_side(cx, cy)

        prev_side = self._last_side.get(track_id)

        # P4: update _last_side ONLY after confidence gate so a low-conf frame
        # does not teleport side state (causing a phantom crossing on the next
        # high-conf frame from the original side).
        if prev_side is None or prev_side == current_side:
            # No crossing — update side unconditionally (first sight or no change).
            self._last_side[track_id] = current_side
            self._last_side.move_to_end(track_id)  # P9: LRU — keep recently-active at tail
            self._maybe_evict_last_side()
            return

        # Crossing detected — check confidence BEFORE committing side state.
        # Low-confidence suppression (AC4)
        if confidence is None or confidence < _CONFIDENCE_THRESHOLD:
            log.debug(
                "tripwire.low_confidence",
                camera_id=self._camera_id,
                track_id=track_id,
                confidence=confidence,
                reason="low_confidence",
            )
            # Do NOT update _last_side — track continues from prev_side.
            return

        # Commit side transition only after passing confidence gate.
        self._last_side[track_id] = current_side
        self._last_side.move_to_end(track_id)  # P9: LRU
        self._maybe_evict_last_side()

        # Compute traversal from camera-frame perspective.
        # "from_to" = centroid moved from coach_from side to coach_to side.
        # Camera config.traversal indicates per-journey mounting orientation
        # (not train travel direction — see module docstring).
        raw_traversal: Literal["from_to", "to_from"] = (
            "from_to" if prev_side == "from" else "to_from"
        )

        if self._camera_zone == "gangway-aft":
            # Receiving (entry) side — emit WAGON_ENTRY directly.
            # The exit was detected by the adjacent gangway-fwd camera; track_id
            # is the shared correlation key consumed by fusion's ledger (E4-S9).
            await self._emit_wagon_entry(
                track_id=track_id,
                coach_from=self._config.coach_from,
                coach_to=self._config.coach_to,
                traversal=raw_traversal,
                confidence=confidence,
            )
        else:
            # gangway-fwd (exit) side — emit WAGON_EXIT.
            # D2: to_from crossings on fwd camera cannot be reconciled by the aft
            # handler (it will not see a paired WAGON_ENTRY). Emit with
            # expect_orphan=True and skip the orphan timer to avoid phantom alerts.
            expect_orphan = raw_traversal == "to_from"

            # P10: cancel any prior orphan handle BEFORE awaiting the emit so a
            # concurrent second crossing for the same track_id cannot race the
            # pop-then-arm sequence (asyncio is single-threaded but a second
            # run_coroutine_threadsafe task can interleave at any await point).
            if not expect_orphan:
                prior = self._pending_exits.pop(track_id, None)
                if prior and prior.orphan_handle:
                    prior.orphan_handle.cancel()

            await self._emit_wagon_exit(
                track_id=track_id,
                coach_from=self._config.coach_from,
                coach_to=self._config.coach_to,
                traversal=raw_traversal,
                confidence=confidence,
                expect_orphan=expect_orphan,
            )

            if not expect_orphan:
                # Arm orphan timer AFTER emit succeeds (AC5).
                # P1/P2: prior handle already cancelled above.

                loop = asyncio.get_running_loop()
                # Capture values at schedule time to avoid stale-closure (E3 retro A3).
                # P3: use loop.create_task inside call_later instead of deprecated
                # asyncio.ensure_future(loop=loop) which was removed in Python 3.12.
                _tid = track_id
                _cfrom = self._config.coach_from
                _cto = self._config.coach_to

                handle = loop.call_later(
                    self._orphan_timeout_s,
                    lambda: loop.create_task(
                        self._handle_orphaned_exit(_tid, _cfrom, _cto)
                    ),
                )
                self._pending_exits[track_id] = _PendingExit(
                    coach_from=self._config.coach_from,
                    coach_to=self._config.coach_to,
                    traversal=raw_traversal,
                    confidence=confidence,
                    orphan_handle=handle,
                )

    def _centroid_side(self, cx: float, cy: float) -> str:
        """Determine which side of the tripwire the centroid (cx, cy) is on.

        The tripwire polygon is a directed polyline. Side is determined by the
        cross-product sign of the first segment vector vs the vector to the centroid.
        Returns "from" (coach_from side) or "to" (coach_to side).

        For a vertical line [[320,0],[320,480]]:
            cx < 320 → "from", cx >= 320 → "to"
        """
        poly = self._config.tripwire_polygon
        if len(poly) < 2:
            return "from"

        x1, y1 = float(poly[0][0]), float(poly[0][1])
        x2, y2 = float(poly[1][0]), float(poly[1][1])

        # Cross product of (segment vector) × (centroid vector from first point)
        cross = (x2 - x1) * (cy - y1) - (y2 - y1) * (cx - x1)
        return "from" if cross >= 0 else "to"

    def _maybe_evict_last_side(self) -> None:
        """Prune oldest entries when _last_side exceeds max size (P5)."""
        if len(self._last_side) > _LAST_SIDE_MAX_SIZE:
            # Remove oldest quarter to amortise eviction cost.
            evict_count = _LAST_SIDE_MAX_SIZE // 4
            to_evict = list(self._last_side.keys())[:evict_count]
            for k in to_evict:
                del self._last_side[k]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    @DEFAULT_RETRY
    async def _emit_wagon_exit(
        self,
        track_id: int,
        coach_from: str,
        coach_to: str,
        traversal: Literal["from_to", "to_from"],
        confidence: float,
        expect_orphan: bool = False,
    ) -> None:
        payload = WagonExitPayload(
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            traversal=traversal,
            confidence=confidence,
            expect_orphan=expect_orphan,
        )
        envelope = self._build_envelope(EventType.WAGON_EXIT, payload.model_dump(), "info")
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()
        log.info(
            "tripwire.wagon_exit",
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            traversal=traversal,
            expect_orphan=expect_orphan,
        )
        # E4-S9 AC10: fire-and-forget to fusion. Non-blocking — fusion-unreachable
        # is a WARNING log, not a retry or failure condition (deliberate: no
        # DEFAULT_RETRY here).
        try:
            fresp = await self._client.post(
                f"{self._settings.fusion_url}/candidates/wagon_exit",
                json=payload.model_dump(mode="json"),
            )
            fresp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — fire-forget
            log.warning(
                "tripwire.fusion_unreachable",
                kind="wagon_exit",
                track_id=track_id,
                reason="fusion_unreachable",
                error=str(exc),
            )

    @DEFAULT_RETRY
    async def _emit_wagon_entry(
        self,
        track_id: int,
        coach_from: str,
        coach_to: str,
        traversal: Literal["from_to", "to_from"],
        confidence: float,
    ) -> None:
        payload = WagonEntryPayload(
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            traversal=traversal,
            confidence=confidence,
        )
        envelope = self._build_envelope(EventType.WAGON_ENTRY, payload.model_dump(), "info")
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()
        log.info(
            "tripwire.wagon_entry",
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            traversal=traversal,
        )
        # E4-S9 AC10: fire-and-forget to fusion.
        try:
            fresp = await self._client.post(
                f"{self._settings.fusion_url}/candidates/wagon_entry",
                json=payload.model_dump(mode="json"),
            )
            fresp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — fire-forget
            log.warning(
                "tripwire.fusion_unreachable",
                kind="wagon_entry",
                track_id=track_id,
                reason="fusion_unreachable",
                error=str(exc),
            )

    async def _handle_orphaned_exit(
        self, track_id: int, coach_from: str, coach_to: str
    ) -> None:
        """Called when WAGON_EXIT has no matching WAGON_ENTRY within timeout (AC5).

        D3: This fires on every normal traversal because the aft handler does not
        cancel the fwd handler's pending entry (handlers are isolated by design).
        fusion's closed-ledger (E4-S9) is the authoritative reconciliation point.
        # TODO(E4-S9): remove or reclassify this signal once fusion emits orphan events.
        Logged at DEBUG (not WARNING) to avoid alert fatigue on normal crossings.
        """
        # Remove from pending (may already be gone if WAGON_ENTRY arrived just in time)
        self._pending_exits.pop(track_id, None)
        log.debug(
            "tripwire.orphaned_exit",
            camera_id=self._camera_id,
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            reason="orphaned_exit",
        )
        # Notify fusion so it can flag ledger as unreconciled
        try:
            resp = await self._client.post(
                f"{self._settings.fusion_url}/context",
                json={
                    "unreconciled_exit": {
                        "track_id": track_id,
                        "coach_from": coach_from,
                        "coach_to": coach_to,
                        "camera_id": self._camera_id,
                    }
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            log.warning(
                "tripwire.orphan_fusion_notify_failed",
                camera_id=self._camera_id,
                track_id=track_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_envelope(
        self, event_type: EventType, payload: dict[str, Any], severity: str
    ) -> EventEnvelope:
        sev: Any = severity
        return EventEnvelope(
            journey_id=self._journey_holder.journey_id,
            vehicle_id=self._settings.vehicle_id,
            event_type=event_type,
            severity=sev,
            source="inference",
            schema_version=self._settings.schema_version,
            payload=payload,
        )

    @staticmethod
    def _on_done(future: "concurrent.futures.Future[Any]") -> None:
        exc = future.exception()
        if exc is not None:
            log.warning("tripwire.scheduled_post_failed", error=str(exc))
