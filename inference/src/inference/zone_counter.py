"""Per-zone occupancy counting with 1 Hz rate limit and threshold crossing detection.

No GStreamer or pipeline imports here — Rule 6.
All config from injected Settings — Rule 1 (no os.environ.get).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from oebb_shared.events.types import EventType
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

        # Build per-car state from cameras config
        self._states: dict[str, OccupancyState] = {}
        self._zones: dict[str, str] = {}  # car_id → zone name
        for cam in cameras:
            car_id = str(cam["coach_id"])
            if car_id not in self._states:
                self._states[car_id] = OccupancyState(
                    car_id=car_id,
                    capacity=int(cam.get("capacity", settings.occupancy_capacity_default)),
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

        # Count unique person track IDs in zone
        person_tracks = {
            d["track_id"]
            for d in detections
            if d.get("label") == "person"
        }
        state.active_tracks = person_tracks
        state.occupancy_count = len(person_tracks)
        state.occupancy_pct = (
            state.occupancy_count / state.capacity if state.capacity > 0 else 0.0
        )

        # 1 Hz rate limit per car
        now = time.monotonic()
        if now - self._last_emit.get(car_id, 0.0) < 1.0:
            return
        self._last_emit[car_id] = now

        await self._post_occupancy_update(state)
        self._check_threshold(car_id, prev_pct, state.occupancy_pct)

    @DEFAULT_RETRY
    async def _post_occupancy_update(self, state: OccupancyState) -> None:
        payload = self.build_occupancy_payload(state, confidence=1.0)
        envelope = _build_envelope(EventType.OCCUPANCY_UPDATE, payload, self._settings)
        await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope,
        )

    def _check_threshold(self, car_id: str, prev_pct: float, new_pct: float) -> None:
        threshold = self._settings.occupancy_threshold_pct
        key: tuple[str, float] = (car_id, threshold)
        last_dir = self._threshold_state.get(key)

        if prev_pct < threshold <= new_pct and last_dir != "rising":
            self._threshold_state[key] = "rising"
            self._fire_threshold_event(car_id, "rising", threshold)
        elif prev_pct >= threshold > new_pct and last_dir != "falling":
            self._threshold_state[key] = "falling"
            self._fire_threshold_event(car_id, "falling", threshold)

    def _fire_threshold_event(self, car_id: str, direction: str, threshold: float) -> None:
        import asyncio

        state = self._states[car_id]
        payload = {
            "car_id": car_id,
            "direction": direction,
            "threshold_pct": threshold,
            "occupancy_pct": state.occupancy_pct,
        }
        envelope = _build_envelope(EventType.OCCUPANCY_THRESHOLD_CROSSED, payload, self._settings)
        # Fire-and-forget via asyncio — threshold events are best-effort
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    self._client.post(
                        f"{self._settings.event_store_url}/api/v1/events",
                        json=envelope,
                    )
                )
        except RuntimeError:
            log.warning("zone_counter.no_event_loop_for_threshold", car_id=car_id)

    @staticmethod
    def build_occupancy_payload(state: OccupancyState, confidence: float) -> dict[str, Any]:
        """Build OCCUPANCY_UPDATE payload dict with all required schema fields."""
        return {
            "car_id": state.car_id,
            "zone": state.zone,
            "occupancy_count": state.occupancy_count,
            "occupancy_pct": state.occupancy_pct,
            "capacity": state.capacity,
            "confidence": confidence,
            "service_tier": state.service_tier,
        }


def _build_envelope(
    event_type: EventType,
    payload: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "journey_id": settings.journey_id,
        "vehicle_id": settings.vehicle_id,
        "event_type": str(event_type),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "severity": "info",
        "source": "inference",
        "schema_version": settings.schema_version,
        "payload": payload,
    }
