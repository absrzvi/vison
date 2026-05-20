"""SafetyHandler — ramp deployment event emitter.

No os.environ.get() — Rule 8. All config from injected Settings.

PoC simplification (R3 — 2026-05-20): ``car_id`` on the emitted RAMP_DEPLOYED
payload is sourced from ``settings.vehicle_id`` (whole train) rather than a
coach-level identifier. The vlan-pollers ``POST /context`` payload carries no
per-coach signal today; resolving this requires either an explicit
``ramp_car_id`` field on ``ContextPushModel`` or a ``door_id → car_id`` reverse
map from ``cameras.json``. Deferred until ZFR per-coach signals are available —
see ``_bmad-output/implementation-artifacts/deferred-work.md`` (2026-05-20).

R4 (2026-05-20): the per-camera ``_last_track_ids`` correlation has been removed.
The selection between concurrently-tracked accessibility events from multiple
cameras was arbitrary (first-inserted), and the additional ``update_last_track``
plumbing introduced a race between callback writes and ramp reads. We now emit
``triggered_by_track_id="unknown"`` unconditionally. Fusion (E4-S6) is the
correct place to correlate ACCESSIBILITY_DETECTED with RAMP_DEPLOYED.
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
    """Handles safety-related events originating from context pushes.

    Posts RAMP_DEPLOYED to event-store when ``POST /context`` carries
    ``ramp_deployed=True``. ``triggered_by_track_id`` is always ``"unknown"``
    on the inference side (see module docstring); downstream correlation is
    fusion's responsibility.
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

    async def on_ramp_deployed(self, door_id: str, station_id: str) -> None:
        """Post RAMP_DEPLOYED to event-store."""
        payload = RampDeployedPayload(
            car_id=self._settings.vehicle_id,  # R3 PoC simplification
            door_id=door_id or "unknown",
            triggered_by_track_id="unknown",  # R4: fusion correlates
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
