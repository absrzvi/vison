"""Envelope construction + POSTing — AC7, AC11.

Single severity decision point lives in ``_severity_for``. Single envelope
constructor lives in ``_build_envelope``. station_approach escalation lives in
``emit_alert``. Every outbound envelope has ``source='fusion'``.

Code-review patches (2026-05-20):
  * ``_severity_for`` fails CLOSED on unknown speed → ``critical`` (decision 3).
  * ``ctx.journey_id is None`` skips the emit with a WARN log instead of falling
    back to a config placeholder (decision against `Settings.journey_id`).
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

import httpx
import structlog
from oebb_shared.events import AlertRaisedPayload, EventEnvelope, EventType
from oebb_shared.http.retry import DEFAULT_RETRY

from fusion.config import Settings
from fusion.context_state import ContextState

log = structlog.get_logger(__name__)

Severity = Literal["critical", "warning", "info"]


def _severity_for(alert_code: str, speed_kmh: float | None) -> Severity:
    """FR9: speed-correlated door fault escalation lives here.

    Door-fault alerts at speed > 0 are ``critical``. At speed = 0 they are
    ``warning``. **Unknown speed** (``None``) is treated as ``critical`` — fail
    closed (code-review decision 3, 2026-05-20). All other alert codes default
    to ``warning``.
    """
    if alert_code in {"door_obstruction", "door_fault"}:
        if speed_kmh is None:
            # Fail-closed: stale telemetry on a moving train must not downgrade.
            return "critical"
        if speed_kmh > 0.0:
            return "critical"
        return "warning"
    return "warning"


class Enrichment:
    """Builds canonical EventEnvelopes and POSTs them to event-store."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        ctx: ContextState,
    ) -> None:
        self._client = client
        self._settings = settings
        self._ctx = ctx

    def _build_envelope(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        severity: Severity,
    ) -> EventEnvelope | None:
        """Construct an envelope or return ``None`` if no journey_id is known.

        Returning ``None`` is preferable to inventing a synthetic journey_id;
        the caller logs and skips.
        """
        if self._ctx.journey_id is None:
            log.warning(
                "enrichment.skip_no_journey_id",
                event_type=str(event_type),
                severity=severity,
            )
            return None
        return EventEnvelope(
            journey_id=self._ctx.journey_id,
            vehicle_id=self._ctx.vehicle_id or self._settings.vehicle_id,
            event_type=event_type,
            severity=severity,
            source="fusion",
            schema_version=self._settings.schema_version,
            payload=payload,
        )

    @DEFAULT_RETRY
    async def _post_envelope(self, envelope: EventEnvelope) -> None:
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()

    async def emit_alert(
        self,
        *,
        alert_code: str,
        car_id: str,
        description: str,
        zone: str | None = None,
    ) -> None:
        """Build + POST an ALERT_RAISED envelope.

        ADR-18 T3: when ctx.station_approach is true, priority='escalated'.
        Severity is determined by ``_severity_for`` (FR9 lives there).
        """
        severity = _severity_for(alert_code, self._ctx.speed_kmh)
        priority: Literal["escalated", "normal"] = (
            "escalated" if self._ctx.station_approach else "normal"
        )
        payload_model = AlertRaisedPayload(
            alert_id=str(uuid.uuid4()),
            alert_code=alert_code,
            car_id=car_id,
            zone=zone,
            description=description,
            priority=priority,
        )
        envelope = self._build_envelope(
            EventType.ALERT_RAISED,
            payload_model.model_dump(),
            severity,
        )
        if envelope is None:
            return
        await self._post_envelope(envelope)
        log.info(
            "enrichment.alert_emitted",
            alert_code=alert_code,
            car_id=car_id,
            severity=severity,
            priority=priority,
            station_approach=self._ctx.station_approach,
        )

    async def emit_envelope(
        self,
        *,
        event_type_name: str,
        payload: dict[str, Any],
        severity: Severity,
    ) -> None:
        """Generic emit for non-AlertRaised envelopes (RAMP_DEPLOYED, JOURNEY_ENDED)."""
        event_type = EventType(event_type_name)
        envelope = self._build_envelope(event_type, payload, severity)
        if envelope is None:
            return
        await self._post_envelope(envelope)
        log.info(
            "enrichment.envelope_emitted",
            event_type=event_type_name,
            severity=severity,
        )
