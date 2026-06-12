"""Story 10-1 AC8/AC10 — emit_alert confidence plumbing."""
from __future__ import annotations

import httpx
import pytest
import respx
from oebb_shared.events import EventEnvelope
from pydantic import ValidationError

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment

_MODEL_VERSIONS = {
    "detector_arch": "yolox_s_leaky",
    "detector_hef": "yolox_s_leaky.hef@ab12cd34ef56",
}


def _ctx() -> ContextState:
    return ContextState(
        journey_id="OBB-TEST_t1_20260612",
        vehicle_id="OBB-TEST",
        speed_kmh=0.0,
    )


def _settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
    )


@pytest.mark.unit
@respx.mock
async def test_emit_alert_requires_confidence_basis_keyword() -> None:
    """AC8: confidence_basis is keyword-only and required — omitting it is a
    TypeError at the call site (and a mypy --strict error at type-check time)."""
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, _settings(), _ctx())
        with pytest.raises(TypeError, match="confidence_basis"):
            await enricher.emit_alert(  # type: ignore[call-arg]
                alert_code="slip_fall",
                car_id="car-1",
                description="x",
            )


@pytest.mark.unit
@respx.mock
async def test_emit_alert_model_basis_carries_score_and_versions() -> None:
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, _settings(), _ctx())
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall",
            confidence_basis="model",
            confidence_score=0.83,
            model_versions=_MODEL_VERSIONS,
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["confidence_basis"] == "model"
    assert env.payload["confidence_score"] == pytest.approx(0.83)
    assert env.payload["model_versions"] == _MODEL_VERSIONS


@pytest.mark.unit
@respx.mock
async def test_emit_alert_sensor_basis_defaults() -> None:
    """Sensor-basis alerts carry score=None and empty versions without the
    caller passing them explicitly."""
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, _settings(), _ctx())
        await enricher.emit_alert(
            alert_code="door_fault",
            car_id="car-1",
            description="sensor-only",
            confidence_basis="sensor",
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["confidence_basis"] == "sensor"
    assert env.payload["confidence_score"] is None
    assert env.payload["model_versions"] == {}


@pytest.mark.unit
@respx.mock
async def test_emit_alert_fused_basis_two_sources() -> None:
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    fused = {**_MODEL_VERSIONS, "door_sensor_firmware": "fw-2.4.1"}
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, _settings(), _ctx())
        await enricher.emit_alert(
            alert_code="door_obstruction",
            car_id="car-1",
            description="fused",
            confidence_basis="fused",
            confidence_score=0.7,
            model_versions=fused,
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["confidence_basis"] == "fused"
    assert env.payload["model_versions"]["door_sensor_firmware"] == "fw-2.4.1"


@pytest.mark.unit
@respx.mock
async def test_emit_alert_invalid_combo_raises_before_post() -> None:
    """AC10: payload validation happens before any POST — no envelope leaves
    fusion with inconsistent confidence metadata."""
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, _settings(), _ctx())
        with pytest.raises(ValidationError):
            await enricher.emit_alert(
                alert_code="slip_fall",
                car_id="car-1",
                description="bad",
                confidence_basis="model",
                confidence_score=None,  # model basis requires a score
                model_versions=_MODEL_VERSIONS,
            )
    assert not route.called
