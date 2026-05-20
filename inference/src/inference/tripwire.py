"""Gangway tripwire crossing detection — emits WAGON_EXIT and WAGON_ENTRY events.

One TripwireHandler instance per gangway camera. Gangway cameras bypass ZoneCounter
entirely; only TripwireHandler runs for zone: gangway-fwd / gangway-aft.

Threading model: process_frame() is sync (called from GStreamer streaming thread);
async work is scheduled onto the asyncio loop via run_coroutine_threadsafe, matching
the pattern in callback.py.

No os.environ.get() — all config via injected Settings (Rule 8).
No GStreamer or pipeline imports (Rule 6).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from typing import Any

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


@dataclass
class TripwireConfig:
    """Static configuration extracted from a gangway camera entry in cameras.json."""

    coach_from: str
    coach_to: str
    direction_axis: str
    tripwire_polygon: list[list[int]]  # list of [x, y] points forming the line


@dataclass
class _PendingExit:
    """State for a WAGON_EXIT that is awaiting a paired WAGON_ENTRY."""

    coach_from: str
    coach_to: str
    direction: str
    confidence: float
    orphan_handle: asyncio.TimerHandle | None = None


class TripwireHandler:
    """Detects persons crossing a gangway tripwire and emits WAGON_EXIT/ENTRY events.

    One instance per gangway camera. The handler tracks which side of the tripwire
    each track_id was last seen on; a side-change constitutes a crossing.
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

        self._config = TripwireConfig(
            coach_from=str(camera["coach_from"]),
            coach_to=str(camera["coach_to"]),
            direction_axis=str(camera.get("direction_axis", "x")),
            tripwire_polygon=[list(p) for p in tripwire_raw["tripwire_polygon"]],
        )
        self._camera_id = str(camera["camera_id"])
        self._camera_zone = zone
        self._settings = settings
        self._client = event_store_client
        self._loop_holder = loop_holder
        self._journey_holder = journey_holder

        # track_id → last observed side ("from" | "to" | None)
        self._last_side: dict[int, str | None] = {}
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
        self._last_side[track_id] = current_side

        if prev_side is None or prev_side == current_side:
            # No crossing yet
            return

        # Crossing detected
        direction = "forward" if prev_side == "from" else "backward"

        # Low-confidence suppression (AC4)
        if confidence is None or confidence < _CONFIDENCE_THRESHOLD:
            log.debug(
                "tripwire.low_confidence",
                camera_id=self._camera_id,
                track_id=track_id,
                confidence=confidence,
                reason="low_confidence",
            )
            return

        if self._camera_zone == "gangway-aft":
            # Receiving (entry) side — emit WAGON_ENTRY directly.
            # The exit was detected by the adjacent gangway-fwd camera; track_id
            # is the shared correlation key consumed by fusion's ledger (E4-S9).
            await self._emit_wagon_entry(
                track_id=track_id,
                coach_from=self._config.coach_from,
                coach_to=self._config.coach_to,
                direction=direction,
                confidence=confidence,
            )
        else:
            # gangway-fwd (exit) side — emit WAGON_EXIT and start orphan timer.
            await self._emit_wagon_exit(
                track_id=track_id,
                coach_from=self._config.coach_from,
                coach_to=self._config.coach_to,
                direction=direction,
                confidence=confidence,
            )
            # Schedule orphan timer (AC5)
            loop = asyncio.get_running_loop()
            # Capture values at schedule time to avoid stale-closure (E3 retro A3)
            _tid, _cfrom, _cto = track_id, self._config.coach_from, self._config.coach_to
            handle = loop.call_later(
                self._orphan_timeout_s,
                lambda: asyncio.ensure_future(
                    self._handle_orphaned_exit(_tid, _cfrom, _cto),
                    loop=loop,
                ),
            )
            self._pending_exits[track_id] = _PendingExit(
                coach_from=self._config.coach_from,
                coach_to=self._config.coach_to,
                direction=direction,
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

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    @DEFAULT_RETRY
    async def _emit_wagon_exit(
        self,
        track_id: int,
        coach_from: str,
        coach_to: str,
        direction: str,
        confidence: float,
    ) -> None:
        payload = WagonExitPayload(
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            direction=direction,  # type: ignore[arg-type]
            confidence=confidence,
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
            direction=direction,
        )

    @DEFAULT_RETRY
    async def _emit_wagon_entry(
        self,
        track_id: int,
        coach_from: str,
        coach_to: str,
        direction: str,
        confidence: float,
    ) -> None:
        payload = WagonEntryPayload(
            track_id=track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            camera_id=self._camera_id,
            direction=direction,  # type: ignore[arg-type]
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
            direction=direction,
        )

    async def _handle_orphaned_exit(
        self, track_id: int, coach_from: str, coach_to: str
    ) -> None:
        """Called when WAGON_EXIT has no matching WAGON_ENTRY within timeout (AC5)."""
        # Remove from pending (may already be gone if WAGON_ENTRY arrived just in time)
        self._pending_exits.pop(track_id, None)
        log.warning(
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
