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

    def update_journey_id(self, journey_id: str) -> None:
        """Update the journey_id used for outbound envelopes (M13 — /context push)."""
        self._journey_holder.journey_id = journey_id

    async def update(self, car_id: str, detections: list[dict[str, Any]]) -> None:
        """Update zone counts from track IDs and emit events if rate allows."""
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
