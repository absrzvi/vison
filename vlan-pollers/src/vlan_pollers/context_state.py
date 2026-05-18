from __future__ import annotations

import dataclasses
from typing import Any

import httpx
import structlog
from oebb_shared.http.retry import DEFAULT_RETRY

from .models import AlarmEntry, ContextState, PisState

log = structlog.get_logger()

# Shared client — reused across all context pushes to avoid per-request TCP setup
_http_client = httpx.AsyncClient()


class ContextStateManager:
    """In-memory ContextState with delta-push to downstream containers.

    Rules:
    - Only pushes when state actually changes (delta-only).
    - Door-release pushes go to rtsp-ingest/context immediately.
    - Station-approach flag pushes go to fusion.
    - General context deltas push to both fusion and inference.
    """

    def __init__(
        self,
        fusion_url: str,
        inference_url: str,
        rtsp_ingest_url: str,
    ) -> None:
        self._state = ContextState()
        self._fusion_url = fusion_url
        self._inference_url = inference_url
        self._rtsp_ingest_url = rtsp_ingest_url

    @property
    def state(self) -> ContextState:
        return self._state

    async def update_journey(self, journey_id: str, trip_number: str, vehicle_id: str) -> None:
        changed = (
            self._state.journey_id != journey_id
            or self._state.trip_number != trip_number
            or self._state.vehicle_id != vehicle_id
        )
        if not changed:
            return
        self._state.journey_id = journey_id
        self._state.trip_number = trip_number
        self._state.vehicle_id = vehicle_id
        await self._push_context_delta()

    async def update_alarm(self, entry: AlarmEntry) -> None:
        existing = self._state.alarms.get(entry.alarm_id)
        if existing and dataclasses.asdict(existing) == dataclasses.asdict(entry):
            return
        self._state.alarms[entry.alarm_id] = entry
        await self._push_context_delta()

    async def update_speed(self, speed_kmh: float) -> None:
        if self._state.speed_kmh == speed_kmh:
            return
        self._state.speed_kmh = speed_kmh
        await self._push_context_delta()

    async def set_station_approach(self, active: bool) -> None:
        if self._state.station_approach == active:
            return
        self._state.station_approach = active
        await _post_with_retry(
            f"{self._fusion_url}/context",
            {"station_approach": active, "journey_id": self._state.journey_id},
        )

    async def set_door_release(self, car_id: str, door_id: str) -> None:
        # Keyed by (car_id, door_id) so multiple doors per car are tracked independently
        self._state.door_release[f"{car_id}:{door_id}"] = True
        await _post_with_retry(
            f"{self._rtsp_ingest_url}/context",
            {"event": "door_release", "car_id": car_id, "door_id": door_id},
        )

    async def update_pis(self, pis: PisState) -> None:
        if (
            self._state.pis.next_station == pis.next_station
            and self._state.pis.next_station_arrival_utc == pis.next_station_arrival_utc
        ):
            return
        self._state.pis = pis
        await self._push_context_delta()

    async def _push_context_delta(self) -> None:
        payload = _state_to_dict(self._state)
        for url in (self._fusion_url, self._inference_url):
            await _post_with_retry(f"{url}/context", payload)


def _state_to_dict(state: ContextState) -> dict[str, Any]:
    return {
        "journey_id": state.journey_id,
        "trip_number": state.trip_number,
        "vehicle_id": state.vehicle_id,
        "speed_kmh": state.speed_kmh,
        "station_approach": state.station_approach,
        "alarms": [dataclasses.asdict(a) for a in state.alarms.values()],
        "pis": dataclasses.asdict(state.pis),
    }


@DEFAULT_RETRY
async def _post_with_retry(url: str, payload: dict[str, Any]) -> None:
    r = await _http_client.post(url, json=payload, timeout=5.0)
    r.raise_for_status()
