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

import math
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import httpx
import structlog
from oebb_shared.events import AlertRaisedPayload, EventEnvelope, EventType
from oebb_shared.events.envelope import TIMESTAMP_RE
from oebb_shared.http.retry import DEFAULT_RETRY

from fusion.config import Settings
from fusion.context_state import ContextState

log = structlog.get_logger(__name__)

Severity = Literal["critical", "warning", "info"]


def _seconds_to_departure(
    *,
    scheduled_departure: str | None,
    station_approach: bool,
    speed_kmh: float | None,
    now: datetime,
) -> int | None:
    """E10-S4: seconds until scheduled departure when pre-departure at a station.

    Returns a non-negative ``int`` only when the train is pre-departure
    (``station_approach`` true, or stopped with ``speed_kmh == 0``) AND
    ``scheduled_departure`` is a parseable ISO-UTC instant. Otherwise ``None``:
      - in-transit (moving, not flagged at a station) → ``None``;
      - empty / malformed / non-UTC departure (feed-degraded) → ``None`` (no raise);
      - stopped-but-overdue (speed branch only, departure already past) → ``None``.

    The full instant is parsed (not time-of-day), so a departure across the
    midnight boundary yields the correct positive delta (ADR-2 trap precedent).
    On the ``station_approach`` branch a past departure clamps to ``0`` (AC6b); on
    the speed-only branch a past departure means the train is overdue, not
    pre-departure, so it returns ``None`` (D1/AC2).
    """
    pre_departure = station_approach or speed_kmh == 0.0
    if not pre_departure:
        return None
    if not scheduled_departure or not TIMESTAMP_RE.fullmatch(scheduled_departure):
        return None
    sched = datetime.fromisoformat(scheduled_departure.replace("Z", "+00:00"))
    delta = math.floor((sched - now).total_seconds())
    if delta < 0 and not station_approach:
        return None
    return max(0, delta)


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
        *,
        timestamp: str | None = None,
    ) -> EventEnvelope | None:
        """Construct an envelope or return ``None`` if no journey_id is known.

        Returning ``None`` is preferable to inventing a synthetic journey_id;
        the caller logs and skips. ``timestamp`` lets the caller pin the envelope
        time to the same clock read used elsewhere (E10-S4: so ``t_fired`` and the
        ``seconds_to_departure`` delta derive from one instant); omitted → default.
        """
        if self._ctx.journey_id is None:
            log.warning(
                "enrichment.skip_no_journey_id",
                event_type=str(event_type),
                severity=severity,
            )
            return None
        fields: dict[str, Any] = dict(
            journey_id=self._ctx.journey_id,
            vehicle_id=self._ctx.vehicle_id or self._settings.vehicle_id,
            event_type=event_type,
            severity=severity,
            source="fusion",
            schema_version=self._settings.schema_version,
            payload=payload,
        )
        if timestamp is not None:
            fields["timestamp"] = timestamp
        return EventEnvelope(**fields)

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
        confidence_basis: Literal["model", "sensor", "fused"],
        zone: str | None = None,
        confidence_score: float | None = None,
        model_versions: dict[str, str] | None = None,
    ) -> None:
        """Build + POST an ALERT_RAISED envelope.

        ADR-18 T3: when ctx.station_approach is true, priority='escalated'.
        Severity is determined by ``_severity_for`` (FR9 lives there).

        E10-S1 AC8: confidence_basis is keyword-only and required — a handler
        that forgets it fails mypy --strict (and TypeError at runtime). The
        per-basis invariants are enforced by AlertRaisedPayload's validator
        BEFORE any POST (AC10 two-phase discipline: nothing leaves fusion with
        inconsistent confidence metadata).
        """
        # Snapshot context once, synchronously, before any await (the POST below) —
        # a concurrent /context push must not change the values mid-build.
        speed_kmh = self._ctx.speed_kmh
        station_approach = self._ctx.station_approach
        scheduled_departure = self._ctx.scheduled_departure
        # One clock read drives BOTH the seconds_to_departure delta and the envelope
        # timestamp (t_fired), so the KPI's in-time boundary (t_fired + seconds)
        # reconstructs from a single instant rather than two skewed reads (E10-S4 review).
        now = datetime.now(UTC)
        severity = _severity_for(alert_code, speed_kmh)
        priority: Literal["escalated", "normal"] = (
            "escalated" if station_approach else "normal"
        )
        seconds_to_departure = _seconds_to_departure(
            scheduled_departure=scheduled_departure,
            station_approach=station_approach,
            speed_kmh=speed_kmh,
            now=now,
        )
        # AC2: surface a degraded/skip path. Pre-departure but no derivable seconds
        # means the PIS feed was empty/unparseable or the train is overdue — log it so
        # a silently-None seconds_to_departure is observable (mirrors pis_poll_failed).
        if seconds_to_departure is None and (station_approach or speed_kmh == 0.0):
            log.warning(
                "enrichment.seconds_to_departure_unavailable",
                reason="pis_feed_degraded_or_overdue",
                scheduled_departure=scheduled_departure,
                car_id=car_id,
                recoverable=True,
            )
        payload_model = AlertRaisedPayload(
            alert_id=str(uuid.uuid4()),
            alert_code=alert_code,
            car_id=car_id,
            zone=zone,
            description=description,
            priority=priority,
            confidence_score=confidence_score,
            confidence_basis=confidence_basis,
            model_versions=model_versions if model_versions is not None else {},
            seconds_to_departure=seconds_to_departure,
        )
        envelope = self._build_envelope(
            EventType.ALERT_RAISED,
            payload_model.model_dump(),
            severity,
            timestamp=now.isoformat(timespec="microseconds").replace("+00:00", "Z"),
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
            station_approach=station_approach,
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
