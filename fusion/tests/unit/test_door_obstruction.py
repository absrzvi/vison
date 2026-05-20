"""Door obstruction correlation — AC5, AC6 (FR7, FR9)."""
from __future__ import annotations

import httpx
import pytest
import respx
from oebb_shared.events import DoorObstructionPayload, EventEnvelope

from fusion import door_obstruction as door_obstruction_mod
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.suppression import SuppressionGate


def _settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        journey_id="OBB-TEST_t1_20260520",
    )


def _payload(**overrides: object) -> DoorObstructionPayload:
    base = {
        "car_id": "car-1",
        "door_id": "door-1A",
        "obstruction_type": "person",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
        "confidence": None,
        "door_state": "unknown",
    }
    base.update(overrides)
    return DoorObstructionPayload(**base)  # type: ignore[arg-type]


@pytest.mark.unit
@respx.mock
async def test_closed_door_with_camera_obstruction_emits_alert() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        speed_kmh=0.0,
        door_state={"car-1:door-1A": "closed"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    assert route.called


@pytest.mark.unit
@respx.mock
async def test_open_door_discards_candidate() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        door_state={"car-1:door-1A": "open"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    assert not route.called


@pytest.mark.unit
@respx.mock
async def test_unknown_door_state_discards_candidate() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        # No door_state entry → returns 'unknown'.
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    assert not route.called


@pytest.mark.unit
@respx.mock
async def test_severity_critical_when_speed_above_zero() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        speed_kmh=25.0,
        door_state={"car-1:door-1A": "closing"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.severity == "critical"


@pytest.mark.unit
@respx.mock
async def test_severity_warning_when_speed_zero() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        speed_kmh=0.0,
        door_state={"car-1:door-1A": "closing"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.severity == "warning"


@pytest.mark.unit
@respx.mock
async def test_suppressed_candidate_not_posted() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        maintenance_mode=True,
        door_state={"car-1:door-1A": "closed"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(), ctx, gate, enricher)
    assert not route.called
