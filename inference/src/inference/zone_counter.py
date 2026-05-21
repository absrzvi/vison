"""Per-zone occupancy counting with 1 Hz rate limit and threshold crossing detection.

No GStreamer or pipeline imports here — Rule 6.
All config from injected Settings — Rule 1 (no os.environ.get).

Event envelope is built via the canonical EventEnvelope Pydantic model in
oebb_shared.events.envelope — same shape as rtsp-ingest (E4-S3) post-f6d377c.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from oebb_shared.events import (
    EventEnvelope,
    EventType,
    OccupancyThresholdCrossedPayload,
    OccupancyUpdatePayload,
    VestibuleCongestionPayload,
)
from oebb_shared.http.retry import DEFAULT_RETRY

from inference.config import Settings
from inference.models import JourneyHolder, OccupancyState

log = structlog.get_logger(__name__)


class ZoneCounter:
    """Maintains per-car occupancy state and emits events to event-store."""

    def __init__(
        self,
        cameras: list[dict[str, Any]],
        settings: Settings,
        event_store_client: httpx.AsyncClient,
        journey_holder: JourneyHolder | None = None,
    ) -> None:
        self._settings = settings
        self._client = event_store_client
        # M13: journey_id may be updated at runtime by POST /context. Holder ties
        # outbound envelopes to the live trip without a container restart.
        self._journey_holder = journey_holder or JourneyHolder(
            journey_id=settings.journey_id
        )

        # Build per-car state from cameras config. Capacity is validated at startup;
        # capacity <= 0 is a config error and refuses to start.
        self._states: dict[str, OccupancyState] = {}
        for cam in cameras:
            car_id = str(cam["coach_id"])
            if car_id in self._states:
                continue
            cap_raw = cam.get("capacity", settings.occupancy_capacity_default)
            # M17: bool is a subclass of int — int(True)=1 would silently produce
            # capacity=1 and trip thresholds on a single person. Reject explicitly.
            if isinstance(cap_raw, bool):
                raise ValueError(
                    f"Invalid capacity for car_id={car_id!r}: bool {cap_raw!r}"
                )
            try:
                capacity = int(cap_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid capacity for car_id={car_id!r}: {cap_raw!r}"
                ) from exc
            if capacity <= 0:
                raise ValueError(
                    f"Capacity for car_id={car_id!r} must be > 0, got {capacity}"
                )
            self._states[car_id] = OccupancyState(
                car_id=car_id,
                capacity=capacity,
                zone=str(cam.get("zone", "interior")),
            )

        self._last_emit: dict[str, float] = {car_id: 0.0 for car_id in self._states}
        # (car_id, threshold) → last emitted direction ("rising"|"falling"|None)
        self._threshold_state: dict[tuple[str, float], str | None] = {}
        # M9: per-car in-flight flag — suppresses new emits while a previous
        # POST chain (retries included) is still draining. Prevents POST pile-up
        # and out-of-order envelopes during event-store outages.
        self._in_flight: dict[str, bool] = {car_id: False for car_id in self._states}
        # M4: per-car asyncio.Lock guards the state-mutation→POST critical section.
        # Without this, a second update() for the same car arriving during an await
        # can clobber occupancy_count/pct before _check_threshold reads prev_count.
        self._locks: dict[str, asyncio.Lock] = {
            car_id: asyncio.Lock() for car_id in self._states
        }

        # E4-S5: slip/fall detection — last bbox per (car_id, camera_id, track_id).
        # Keyed by camera_id (not car_id alone) so multi-camera-per-car doesn't clobber
        # tracks emitted by different cameras for the same coach.
        self._track_bboxes: dict[
            tuple[str, str], dict[int, tuple[float, float, float, float]]
        ] = {}
        # E4-S5: vestibule congestion rate-limit — one emit per vestibule per 10s
        self._vestibule_last_emit: dict[str, float] = {}

        # Build (car_id, camera_id) → zone lookup. Multi-camera-per-car: each camera
        # carries its own zone, so we can't fold to car_id alone.
        self._camera_zone: dict[tuple[str, str], str] = {
            (str(cam["coach_id"]), str(cam["camera_id"])): str(cam.get("zone", "interior"))
            for cam in cameras
        }

    def update_journey_id(self, journey_id: str) -> None:
        """Update the journey_id used for outbound envelopes (M13 — /context push)."""
        self._journey_holder.journey_id = journey_id

    async def update(
        self,
        car_id: str,
        detections: list[dict[str, Any]],
        camera_id: str | None = None,
    ) -> None:
        """Update zone counts from track IDs and emit events if rate allows.

        camera_id identifies the originating camera so slip/fall and vestibule
        emissions carry the right source identifier and tracks are scoped per
        camera (R7 — multi-camera-per-car).
        """
        if car_id not in self._states:
            return

        # C1 decision: rate-limit + _in_flight check run OUTSIDE the lock so
        # contending callers can skip without blocking for the full POST/retry chain.
        # The lock guards only state mutation (count/pct/tracks). POSTs happen outside.

        # M9: skip early if previous POST chain is still in flight. Checked before
        # acquiring the lock so a contending frame exits immediately without blocking
        # behind a 30s httpx retry timeout.
        if self._in_flight.get(car_id, False):
            log.warning("zone_counter.skip_in_flight", car_id=car_id)
            return

        # 1 Hz rate limit — checked outside the lock for the same reason.
        now = time.monotonic()
        if now - self._last_emit.get(car_id, 0.0) < 1.0:
            return

        # M4: lock guards state mutation only. Held briefly; no awaits inside.
        async with self._locks[car_id]:
            state = self._states[car_id]
            prev_count = state.occupancy_count

            # Count unique person track IDs. None ids are filtered (callback already drops
            # them; this is defence in depth).
            person_tracks: set[int] = {
                d["track_id"]
                for d in detections
                if d.get("label") == "person" and d.get("track_id") is not None
            }
            state.active_tracks = person_tracks
            state.occupancy_count = len(person_tracks)
            # Capacity is guaranteed > 0 by constructor.
            state.occupancy_pct = min(state.occupancy_count / state.capacity, 1.0)

            self._last_emit[car_id] = now
            self._in_flight[car_id] = True

        # POST and threshold check run outside the lock. _in_flight stays True for the
        # full async chain; any concurrent update() for this car hits the early-exit above.
        try:
            await self._post_occupancy_update(state)
            await self._check_threshold(car_id, prev_count, state.occupancy_count)
            await self._check_slip_fall(car_id, detections, camera_id=camera_id)
            # R5: vestibule person count is the subset whose centroid the callback
            # tagged as in the camera's vestibule polygon. If no detection carries
            # the tag (cameras.json without a vestibule_zone, or legacy callers),
            # fall back to the total person count so behaviour matches the old
            # "treat any door-camera person as vestibule" semantics.
            person_dets = [d for d in detections if d.get("label") == "person"]
            tagged = [d for d in person_dets if d.get("in_vestibule")]
            vestibule_person_count = (
                len(tagged)
                if any("in_vestibule" in d for d in person_dets)
                else len(person_dets)
            )
            await self._check_vestibule_congestion(
                car_id,
                vestibule_person_count,
                camera_id=camera_id,
            )
        finally:
            self._in_flight[car_id] = False

    @DEFAULT_RETRY
    async def _post_occupancy_update(self, state: OccupancyState) -> None:
        """Emit OCCUPANCY_UPDATE. confidence is omitted (None) until real aggregation
        from per-detection YOLO scores lands — schema's _drop_none serializer strips it.
        """
        payload = OccupancyUpdatePayload(
            car_id=state.car_id,
            zone=state.zone,
            occupancy_count=state.occupancy_count,
            occupancy_pct=state.occupancy_pct,
            capacity=state.capacity,
            confidence=None,
            service_tier=self._settings.service_tier,
        )
        envelope = self._build_envelope(
            EventType.OCCUPANCY_UPDATE,
            payload.model_dump(),
            severity="info",
        )
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()
        # E4-S9 AC10: fire-and-forget OCCUPANCY_UPDATE payload (NOT the wrapping
        # envelope) to fusion for closed-ledger reconciliation. Non-blocking.
        try:
            fresp = await self._client.post(
                f"{self._settings.fusion_url}/candidates/occupancy_update",
                json=payload.model_dump(mode="json"),
            )
            fresp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 — fire-forget
            log.warning(
                "zone_counter.fusion_unreachable",
                car_id=state.car_id,
                reason="fusion_unreachable",
                error=str(exc),
            )

    async def _check_threshold(
        self, car_id: str, prev_count: int, new_count: int
    ) -> None:
        """Count-based threshold crossing with symmetric deadband (P-M10).

        Threshold is converted to absolute people count using the car's capacity.
        Rising fires when count crosses ``threshold_count + deadband`` from below.
        Falling fires when count crosses ``threshold_count - deadband`` from above.
        The ±deadband zone in the middle is a stable region that does NOT emit.
        """
        state = self._states[car_id]
        threshold_pct = self._settings.occupancy_threshold_pct
        deadband = self._settings.occupancy_deadband_count
        threshold_count = threshold_pct * state.capacity
        rising_at = threshold_count + deadband
        falling_at = threshold_count - deadband

        key: tuple[str, float] = (car_id, threshold_pct)
        last_dir = self._threshold_state.get(key)

        if prev_count < rising_at <= new_count and last_dir != "rising":
            self._threshold_state[key] = "rising"
            await self._fire_threshold_event(car_id, "rising", threshold_pct)
        elif prev_count > falling_at >= new_count and last_dir != "falling":
            self._threshold_state[key] = "falling"
            await self._fire_threshold_event(car_id, "falling", threshold_pct)

    @DEFAULT_RETRY
    async def _fire_threshold_event(
        self, car_id: str, direction: str, threshold: float
    ) -> None:
        """Emit OCCUPANCY_THRESHOLD_CROSSED. Awaited (not fire-and-forget) so
        DEFAULT_RETRY and raise_for_status actually take effect.
        """
        state = self._states[car_id]
        payload = OccupancyThresholdCrossedPayload(
            car_id=car_id,
            zone=state.zone,
            threshold_pct=threshold,
            direction="rising" if direction == "rising" else "falling",
            occupancy_pct=state.occupancy_pct,
            occupancy_count=state.occupancy_count,
            capacity=state.capacity,
            service_tier=self._settings.service_tier,
        )
        envelope = self._build_envelope(
            EventType.OCCUPANCY_THRESHOLD_CROSSED,
            payload.model_dump(),
            severity="warning",
        )
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()

    async def _check_slip_fall(
        self,
        car_id: str,
        detections: list[dict[str, Any]],
        camera_id: str | None = None,
    ) -> None:
        """Detect slip/fall events from consecutive person bounding boxes.

        Tracks are keyed per (car_id, camera_id) so the same coach observed by
        multiple cameras doesn't share a single bbox map (R7).
        """
        # Use a sentinel "unknown" camera bucket for callers that don't supply one
        # (preserves backwards compat with tests that seed _track_bboxes by car_id).
        bucket_key = (car_id, camera_id or "unknown")
        car_bboxes = self._track_bboxes.setdefault(bucket_key, {})
        active_track_ids: set[int] = set()
        for det in detections:
            if det.get("label") != "person":
                continue
            track_id = det.get("track_id")
            bbox = det.get("bbox")
            if track_id is None or bbox is None:
                continue
            active_track_ids.add(track_id)
            prev = car_bboxes.get(track_id)
            if prev is not None:
                h1 = prev[3] - prev[1]
                h2 = bbox[3] - bbox[1]
                cy1 = (prev[1] + prev[3]) / 2.0
                cy2 = (bbox[1] + bbox[3]) / 2.0
                height_ratio = h2 / h1 if h1 > 0 else 1.0
                velocity = abs(cy2 - cy1)
                threshold = self._settings.slip_fall_height_collapse_threshold
                if (
                    height_ratio < (1.0 - threshold)
                    and velocity > self._settings.slip_fall_velocity_threshold
                ):
                    await self._post_slip_fall_candidate(
                        car_id=car_id,
                        track_id=track_id,
                        camera_id=camera_id or "unknown",
                    )
            car_bboxes[track_id] = bbox
        # F2: prune stale track entries for tracks that left frame
        for stale_id in list(car_bboxes.keys()):
            if stale_id not in active_track_ids:
                del car_bboxes[stale_id]

    @DEFAULT_RETRY
    async def _post_slip_fall_candidate(
        self, car_id: str, track_id: int, camera_id: str
    ) -> None:
        resp = await self._client.post(
            f"{self._settings.fusion_url}/candidates/alert_raised",
            json={
                "alert_type": "slip_fall",
                "car_id": car_id,
                "track_id": track_id,
                "camera_id": camera_id,
            },
        )
        resp.raise_for_status()

    async def _check_vestibule_congestion(
        self,
        car_id: str,
        person_count: int,
        camera_id: str | None = None,
    ) -> None:
        """Emit VESTIBULE_CONGESTION when door/vestibule zone exceeds threshold.

        Uses the source camera's zone when provided; falls back to a per-car
        lookup so callers without camera context (legacy tests) still resolve a
        zone. Multi-camera-per-car coaches need the per-camera path to avoid
        misattributing interior counts to a door camera's vestibule (R5/R7).
        """
        if camera_id is not None:
            zone = self._camera_zone.get((car_id, camera_id))
            if zone is None:
                return
        else:
            # Legacy fallback: pick any camera_id for this car. Returns "interior"
            # if no door/vestibule camera is configured.
            zone = next(
                (
                    z for (c_id, _), z in self._camera_zone.items() if c_id == car_id
                ),
                "interior",
            )
        if zone not in ("door", "vestibule"):
            return

        threshold = self._settings.vestibule_congestion_threshold
        score_threshold = self._settings.vestibule_congestion_score_threshold
        score = min(person_count / threshold, 1.0) if threshold > 0 else 0.0
        if score <= score_threshold:
            return

        vestibule_id = f"{car_id}-{zone}"
        now = time.monotonic()
        if now - self._vestibule_last_emit.get(vestibule_id, 0.0) < 10.0:
            return

        self._vestibule_last_emit[vestibule_id] = now
        payload = VestibuleCongestionPayload(
            car_id=car_id,
            vestibule_id=vestibule_id,
            congestion_score=round(score, 4),
            person_count=person_count,
            dwell_time_avg_s=0.0,
            threshold_score=score_threshold,
        )
        envelope = self._build_envelope(
            EventType.VESTIBULE_CONGESTION,
            payload.model_dump(),
            severity="warning",
        )
        await self._post_vestibule_congestion(envelope)

    @DEFAULT_RETRY
    async def _post_vestibule_congestion(self, envelope: EventEnvelope) -> None:
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()

    def _build_envelope(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        severity: str,
    ) -> EventEnvelope:
        # Cast severity to the canonical Literal at the boundary; envelope validates.
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
