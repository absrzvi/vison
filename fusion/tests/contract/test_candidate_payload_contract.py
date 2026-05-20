"""Contract test — replay the exact body shapes inference posts to fusion.

Story 4-5 locked the candidate POST contracts at:
- POST {fusion_url}/candidates/door_obstruction — DoorObstructionPayload with door_state='unknown'
- POST {fusion_url}/candidates/alert_raised      — {alert_type:'slip_fall', car_id, track_id, camera_id}

This test calls the fusion endpoints with those exact bodies and asserts 202.
If a shared payload field is renamed without coordination, this fails fast.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import build_app
from fusion.suppression import SuppressionGate


def _settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        journey_id="OBB-TEST_t1_20260520",
    )


def _client_app() -> tuple[TestClient, dict[str, Any]]:
    settings = _settings()
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    http_client = httpx.AsyncClient()
    enricher = Enrichment(http_client, settings, ctx)
    gate = SuppressionGate(ctx, enricher)
    app = build_app(
        settings=settings, ctx=ctx, gate=gate, enricher=enricher, client=http_client
    )
    state = {"ctx": ctx, "settings": settings, "client": http_client}
    return TestClient(app), state


@pytest.mark.contract
def test_door_obstruction_candidate_with_unknown_door_state_accepted() -> None:
    """Replay inference's exact payload from callback.py:282-312."""
    body = {
        "car_id": "car-1",
        "door_id": "door-1A",
        "obstruction_type": "person",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
        "confidence": None,
        "door_state": "unknown",
    }
    client, _ = _client_app()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/door_obstruction", json=body)
    assert resp.status_code == 202
    assert resp.json() == {"received": True}


@pytest.mark.contract
def test_slip_fall_candidate_dict_shape_accepted() -> None:
    """Replay inference's exact payload from zone_counter.py:320-333."""
    body = {
        "alert_type": "slip_fall",
        "car_id": "car-1",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
    }
    client, _ = _client_app()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 202


@pytest.mark.contract
def test_slip_fall_invalid_alert_type_returns_422() -> None:
    body = {
        "alert_type": "unknown",
        "car_id": "car-1",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
    }
    client, _ = _client_app()
    resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 422


@pytest.mark.contract
def test_door_obstruction_invalid_body_returns_422() -> None:
    body = {"car_id": "car-1"}  # missing required fields
    client, _ = _client_app()
    resp = client.post("/candidates/door_obstruction", json=body)
    assert resp.status_code == 422


@pytest.mark.contract
def test_context_push_extra_field_returns_422() -> None:
    body = {"unknown_field": True}
    client, _ = _client_app()
    resp = client.post("/context", json=body)
    assert resp.status_code == 422
