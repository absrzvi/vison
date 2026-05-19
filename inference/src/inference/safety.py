"""SafetyHandler — ramp deployment event emitter.

No os.environ.get() — Rule 8. All config from injected Settings.
"""
from __future__ import annotations

import httpx
import structlog
from oebb_shared.events import EventEnvelope, EventType, RampDeployedPayload
from oebb_shared.http.retry import DEFAULT_RETRY

from inference.config import Settings
from inference.models import JourneyHolder

log = structlog.get_logger(__name__)


class SafetyHandler:
    """Handles safety-related events that originate from context pushes.

    Holds the last known accessibility track_id per camera so that RAMP_DEPLOYED
    can carry triggered_by_track_id from the most recent ACCESSIBILITY_DETECTED.
    """

    def __init__(
        self,
        settings: Settings,
        event_store_client: httpx.AsyncClient,
        journey_holder: JourneyHolder,
    ) -> None:
        self._settings = settings
        self._client = event_store_client
        self._journey_holder = journey_holder
        # Populated by OccupancyCallback when a bicycle detection is emitted.
        self._last_track_ids: dict[str, str] = {}

    def update_last_track(self, camera_id: str, track_id: str) -> None:
        """Called by OccupancyCallback after a successful ACCESSIBILITY_DETECTED emit."""
        self._last_track_ids[camera_id] = track_id

    async def on_ramp_deployed(self, door_id: str, station_id: str) -> None:
        """Post RAMP_DEPLOYED to event-store when a ramp_deployed context push arrives."""
        triggered = next(iter(self._last_track_ids.values()), "unknown")
        payload = RampDeployedPayload(
            car_id=self._settings.vehicle_id,
            door_id=door_id or "unknown",
            triggered_by_track_id=triggered,
            deployed_by="auto",
            station_id=station_id or "unknown",
        )
        envelope = EventEnvelope(
            journey_id=self._journey_holder.journey_id,
            vehicle_id=self._settings.vehicle_id,
            event_type=EventType.RAMP_DEPLOYED,
            severity="warning",
            source="inference",
            schema_version=self._settings.schema_version,
            payload=payload.model_dump(),
        )
        await self._post_ramp_deployed(envelope)

    @DEFAULT_RETRY
    async def _post_ramp_deployed(self, envelope: EventEnvelope) -> None:
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()
