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
        "model_versions": {"detector_arch": "yolox_s_leaky"},
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


@pytest.mark.unit
@respx.mock
async def test_resolve_car_id_consist_mapping_used_for_lookup() -> None:
    """R3: when payload.car_id is a consist index (e.g. "1"), door_obstruction
    must resolve it to the real car_id before looking up door_state.
    Code-review decision 1 (2026-05-20)."""
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        speed_kmh=10.0,
        door_state={"car-1:door-1A": "closed"},
        consist={"1": "car-1"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        # Inference posts car_id="1" (numeric index); consist resolves to "car-1".
        await door_obstruction_mod.handle(_payload(car_id="1"), ctx, gate, enricher)
    assert route.called
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["car_id"] == "car-1"


@pytest.mark.unit
@respx.mock
async def test_alert_carries_fused_basis_with_door_firmware() -> None:
    """Story 10-1 AC9: door obstruction alerts are fused-basis — camera score +
    upstream model_versions + door_sensor_firmware from context state."""
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260612",
        vehicle_id="OBB-TEST",
        speed_kmh=0.0,
        door_state={"car-1:door-1A": "closed"},
        door_firmware_version="fw-2.4.1",
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(confidence=0.77), ctx, gate, enricher)
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["confidence_basis"] == "fused"
    assert env.payload["confidence_score"] == pytest.approx(0.77)
    assert env.payload["model_versions"] == {
        "detector_arch": "yolox_s_leaky",
        "door_sensor_firmware": "fw-2.4.1",
    }


@pytest.mark.unit
@respx.mock
async def test_fused_firmware_defaults_to_unknown() -> None:
    """door_firmware_version defaults to 'unknown' until SNMP populates it."""
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260612",
        vehicle_id="OBB-TEST",
        speed_kmh=0.0,
        door_state={"car-1:door-1A": "closed"},
    )
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        gate = SuppressionGate(ctx, enricher)
        await door_obstruction_mod.handle(_payload(confidence=0.5), ctx, gate, enricher)
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["model_versions"]["door_sensor_firmware"] == "unknown"
