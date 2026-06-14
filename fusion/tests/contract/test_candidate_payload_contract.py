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

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from oebb_shared.events import EventEnvelope, EventType

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


@pytest.mark.contract
def test_real_targeted_pis_push_populates_scheduled_departure() -> None:
    """E10-S4 — real-producer contract: the EXACT targeted-push body vlan-pollers
    sends on a PIS update (vlan_pollers/context_state.py update_pis) must validate
    through fusion's ContextPushModel and land on ContextState.scheduled_departure.

    This bridges the producer→consumer wire that the unit tests previously bypassed:
    vlan-pollers POSTs a FLAT {scheduled_departure, journey_id} dict (NOT the nested
    `pis` object), which is the only shape fusion's extra='forbid' model accepts.
    Self-contained app so we hold the ctx reference to assert against.
    """
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
    wire_body = {
        "scheduled_departure": "2026-05-19T12:05:00Z",
        "journey_id": "OBB-TEST_t1_20260520",
    }
    with TestClient(app) as tc:
        resp = tc.post("/context", json=wire_body)
    assert resp.status_code == 200, resp.text
    assert ctx.scheduled_departure == "2026-05-19T12:05:00Z"
    del http_client


# ---------------------------------------------------------------------------
# Producer → shared-schema boundary (story 10-1 model_versions audit).
#
# The 202-only tests above cannot catch a broken model_versions invariant: the
# /candidates/* handlers are fail-safe (Pattern 3 — they return 202 even when
# AlertRaisedPayload construction raises). These tests capture the envelope
# fusion ACTUALLY POSTs to event-store and validate it against the real shared
# EventEnvelope, which transitively runs AlertRaisedPayload._validate_confidence.
# This is the contract that the landside ingest boundary (cloud-backend) enforces
# with HTTP 422 — so if fusion emits an alert that violates the per-basis
# model_versions floor, it would be rejected at ingest. These tests fail FAST in
# that case instead of letting a silently-dropped alert reach production.
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_slip_fall_emitted_envelope_validates_against_shared_schema(
    client: TestClient,
) -> None:
    """slip_fall is model-basis: model_versions must be non-empty. Inference may
    omit it; fusion's ``payload.model_versions or {...}`` fallback must keep it
    non-empty so the emitted ALERT_RAISED clears AlertRaisedPayload's
    model-basis invariant at the ingest boundary."""
    body = {
        "alert_type": "slip_fall",
        "car_id": "car-1",
        "track_id": 42,
        "camera_id": "C1_DOOR_01",
        # confidence + model_versions deliberately omitted — exercises fusion's
        # fail-safe fallback (zone_counter may post a legacy body without them).
    }
    with respx.mock(assert_all_called=True) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/alert_raised", json=body)
    assert resp.status_code == 202
    # Capture what fusion actually sent and validate it against the shared schema.
    sent = route.calls.last.request
    envelope = EventEnvelope.model_validate(json.loads(sent.content))
    assert envelope.event_type == EventType.ALERT_RAISED.value
    assert envelope.payload["confidence_basis"] == "model"
    # model-basis invariant: non-empty model_versions (the fallback supplied it).
    assert envelope.payload["model_versions"]


@pytest.mark.contract
def test_door_obstruction_emitted_envelope_validates_against_shared_schema(
    client: TestClient,
) -> None:
    """door_obstruction is fused-basis: model_versions must have >= 2 entries.
    Fusion joins the upstream detector provenance with the door-sensor firmware
    version — proving that join keeps the fused floor satisfied end-to-end."""
    body = {
        "car_id": "car-1",
        "door_id": "door-1A",
        "obstruction_type": "person",
        "track_id": "42",
        "camera_id": "C1_DOOR_01",
        "confidence": 0.88,
        "door_state": "unknown",
        "model_versions": {"detector_arch": "yolox_s_leaky"},
    }
    # ZFR-derived door state must be 'closing'/'closed' for the alert to emit.
    client.post(
        "/context",
        json={"door_state": {"car-1:door-1A": "closing"}},
    )
    with respx.mock(assert_all_called=True) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/door_obstruction", json=body)
    assert resp.status_code == 202
    sent = route.calls.last.request
    envelope = EventEnvelope.model_validate(json.loads(sent.content))
    assert envelope.event_type == EventType.ALERT_RAISED.value
    assert envelope.payload["confidence_basis"] == "fused"
    # fused-basis invariant: >= 2 model_versions entries (detector + door firmware).
    assert len(envelope.payload["model_versions"]) >= 2
