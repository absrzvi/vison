"""Enrichment envelope construction + station_approach escalation — AC7, AC11."""
from __future__ import annotations

import httpx
import pytest
import respx
from oebb_shared.events import EventEnvelope, EventType

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment, _severity_for


def _make_settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
    )


def _make_ctx(**overrides: object) -> ContextState:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
    )
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


@pytest.mark.unit
def test_severity_door_obstruction_at_speed_is_critical() -> None:
    assert _severity_for("door_obstruction", speed_kmh=15.0) == "critical"


@pytest.mark.unit
def test_severity_door_obstruction_at_zero_speed_is_warning() -> None:
    assert _severity_for("door_obstruction", speed_kmh=0.0) == "warning"


@pytest.mark.unit
def test_severity_door_obstruction_unknown_speed_is_critical_fail_closed() -> None:
    """Fail-closed: stale telemetry must not downgrade a real door fault.
    Code-review decision 3 (2026-05-20)."""
    assert _severity_for("door_obstruction", speed_kmh=None) == "critical"
    assert _severity_for("door_fault", speed_kmh=None) == "critical"


@pytest.mark.unit
def test_severity_non_door_alert_defaults_to_warning() -> None:
    assert _severity_for("slip_fall", speed_kmh=80.0) == "warning"


@pytest.mark.unit
@respx.mock
async def test_emit_alert_posts_envelope_with_source_fusion() -> None:
    settings = _make_settings()
    ctx = _make_ctx()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    assert route.called
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.source == "fusion"
    assert env.event_type == EventType.ALERT_RAISED
    assert env.severity == "warning"
    assert env.payload["alert_code"] == "slip_fall"


@pytest.mark.unit
@respx.mock
async def test_station_approach_escalates_priority() -> None:
    settings = _make_settings()
    ctx = _make_ctx(station_approach=True)
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.payload["priority"] == "escalated"


@pytest.mark.unit
@respx.mock
async def test_no_station_approach_keeps_priority_normal() -> None:
    settings = _make_settings()
    ctx = _make_ctx(station_approach=False)
    respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    # AlertRaisedPayload _drop_none keeps priority because it's set to 'normal',
    # not None. Envelope payload must reflect that.
    body = respx.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.payload["priority"] == "normal"


@pytest.mark.unit
@respx.mock
async def test_emit_envelope_for_journey_ended_with_empty_payload() -> None:
    settings = _make_settings()
    ctx = _make_ctx()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_envelope(
            event_type_name="JOURNEY_ENDED",
            payload={},
            severity="info",
        )
    assert route.called
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.event_type == EventType.JOURNEY_ENDED
    assert env.source == "fusion"


@pytest.mark.unit
@respx.mock
async def test_emit_skipped_when_journey_id_is_none() -> None:
    """When ContextState has no journey_id (vlan-pollers hasn't pushed yet),
    fusion MUST NOT emit a synthetic placeholder — log WARN and skip.
    Code-review patch (2026-05-20)."""
    settings = _make_settings()
    ctx = _make_ctx()
    ctx.journey_id = None  # explicit: no journey known
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    assert not route.called  # NO emit with empty journey_id
