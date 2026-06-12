"""Contract test — replay the exact body shapes inference posts to fusion.

Story 4-5 locked the candidate POST contracts at:
- POST {fusion_url}/candidates/door_obstruction — DoorObstructionPayload with door_state='unknown'
- POST {fusion_url}/candidates/alert_raised      — {alert_type:'slip_fall', car_id, track_id (int), camera_id}

This test calls the fusion endpoints with those exact bodies and asserts 202.
If a shared payload field is renamed or a track_id type drifts without
coordination, this fails fast.

Code-review patch (2026-05-20): slip-fall ``track_id`` is now ``int`` to match
the actual integer hailotracker id inference emits at ``zone_counter.py:329``.
"""
from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fusion.comfort_index import ComfortIndexState
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import build_app
from fusion.ledger import CoachLedger
from fusion.suppression import SuppressionGate


def _settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        ledger_db_path=":memory:",
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = _settings()
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    http_client = httpx.AsyncClient()
    enricher = Enrichment(http_client, settings, ctx)
    gate = SuppressionGate(ctx, enricher)
    ledger = CoachLedger(settings)
    comfort = ComfortIndexState(settings)
    app = build_app(
        settings=settings, ctx=ctx, gate=gate, enricher=enricher, client=http_client,
        ledger=ledger, comfort=comfort,
    )
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        # httpx.AsyncClient instantiated outside an event loop has no resources
        # to release synchronously (TestClient owned the transport). Nothing
        # to await; ignore_resource_warnings filter set in pyproject suppresses
        # the close warning.
        del http_client


@pytest.mark.contract
def test_door_obstruction_candidate_with_unknown_door_state_accepted(client: TestClient) -> None:
    """Replay inference's exact payload from callback.py:282-312."""
    body = {
        "car_id": "car-1",
        "door_id": "door-1A",
        "obstruction_type": "person",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
        "confidence": None,
        "door_state": "unknown",
        "model_versions": {"detector_arch": "yolox_s_leaky"},
    }
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/door_obstruction", json=body)
    assert resp.status_code == 202
    assert resp.json() == {"received": True}


@pytest.mark.contract
def test_slip_fall_candidate_dict_shape_accepted(client: TestClient) -> None:
    """Replay inference's exact payload from zone_counter.py:320-333.

    ``track_id`` is ``int`` — matches the hailotracker integer id at the source.
    """
    body = {
        "alert_type": "slip_fall",
        "car_id": "car-1",
        "track_id": 42,
        "camera_id": "C1_DOOR_01",
    }
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 202


@pytest.mark.contract
def test_slip_fall_invalid_alert_type_returns_422(client: TestClient) -> None:
    body = {
        "alert_type": "unknown",
        "car_id": "car-1",
        "track_id": 42,
        "camera_id": "C1_DOOR_01",
    }
    resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 422


@pytest.mark.contract
def test_slip_fall_track_id_string_rejected(client: TestClient) -> None:
    """Type contract: track_id MUST be int (matches inference's int source).

    A string body should fail validation under Pydantic strict-ish int parsing.
    """
    body = {
        "alert_type": "slip_fall",
        "car_id": "car-1",
        "track_id": "not-a-number",
        "camera_id": "C1_DOOR_01",
    }
    resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 422


@pytest.mark.contract
def test_door_obstruction_invalid_body_returns_422(client: TestClient) -> None:
    body = {"car_id": "car-1"}  # missing required fields
    resp = client.post("/candidates/door_obstruction", json=body)
    assert resp.status_code == 422


@pytest.mark.contract
def test_context_push_extra_field_returns_422(client: TestClient) -> None:
    body = {"unknown_field": True}
    resp = client.post("/context", json=body)
    assert resp.status_code == 422
