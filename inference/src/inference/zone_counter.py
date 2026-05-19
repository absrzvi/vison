"""Per-zone occupancy counting with 1 Hz rate limit and threshold crossing detection.

No GStreamer or pipeline imports here — Rule 6.
All config from injected Settings — Rule 1 (no os.environ.get).

Event envelope is built via the canonical EventEnvelope Pydantic model in
oebb_shared.events.envelope — same shape as rtsp-ingest (E4-S3) post-f6d377c.
"""
from __future__ import annotations

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
from inference.models import OccupancyState

log = structlog.get_logger(__name__)


class ZoneCounter:
    """Maintains per-car occupancy state and emits events to event-store."""

    def __init__(
        self,
        cameras: list[dict[str, Any]],
        settings: Settings,
        event_store_client: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._client = event_store_client

        # Build per-car state from cameras config. Capacity is validated at startup;
        # capacity <= 0 is a config error and refuses to start.
        self._states: dict[str, OccupancyState] = {}
        for cam in cameras:
            car_id = str(cam["coach_id"])
            if car_id in self._states:
                continue
            cap_raw = cam.get("capacity", settings.occupancy_capacity_default)
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

    async def update(self, car_id: str, detections: list[dict[str, Any]]) -> None:
        """Update zone counts from track IDs and emit events if rate allows."""
        if car_id not in self._states:
            return

        state = self._states[car_id]
        prev_pct = state.occupancy_pct

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

        # 1 Hz rate limit per car.
        now = time.monotonic()
        if now - self._last_emit.get(car_id, 0.0) < 1.0:
            return
        self._last_emit[car_id] = now

        await self._post_occupancy_update(state)
        await self._check_threshold(car_id, prev_pct, state.occupancy_pct)

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
        self, car_id: str, prev_pct: float, new_pct: float
    ) -> None:
        threshold = self._settings.occupancy_threshold_pct
        key: tuple[str, float] = (car_id, threshold)
        last_dir = self._threshold_state.get(key)

        # Rising: <= on left side so prev_pct == threshold still triggers when we cross.
        if prev_pct <= threshold <= new_pct and prev_pct < new_pct and last_dir != "rising":
            self._threshold_state[key] = "rising"
            await self._fire_threshold_event(car_id, "rising", threshold)
        elif prev_pct >= threshold >= new_pct and prev_pct > new_pct and last_dir != "falling":
            self._threshold_state[key] = "falling"
            await self._fire_threshold_event(car_id, "falling", threshold)

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
            journey_id=self._settings.journey_id,
            vehicle_id=self._settings.vehicle_id,
            event_type=event_type,
            severity=sev,
            source="inference",
            schema_version=self._settings.schema_version,
            payload=payload,
        )
