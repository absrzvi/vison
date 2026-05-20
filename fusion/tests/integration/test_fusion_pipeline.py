"""Synthetic end-to-end pipeline — AC12.

Drives: context push → door obstruction candidate (door closing) → assert
exactly one ALERT_RAISED envelope POSTed with source='fusion'. Then push
maintenance_mode=true and assert a second candidate is suppressed (no POST).
"""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from oebb_shared.events import EventEnvelope, EventType

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import build_app
from fusion.suppression import SuppressionGate


def _build_test_app() -> TestClient:
    settings = Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        journey_id="OBB-TEST_t1_20260520",
    )
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    http_client = httpx.AsyncClient()
    enricher = Enrichment(http_client, settings, ctx)
    gate = SuppressionGate(ctx, enricher)
    app = build_app(
        settings=settings, ctx=ctx, gate=gate, enricher=enricher, client=http_client
    )
    return TestClient(app)


@pytest.mark.integration
def test_pipeline_normal_then_suppressed() -> None:
    client = _build_test_app()

    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201, json={"data": {"stored": True}})
        )

        # 1. Push context: door closing on car-1:door-1A, train at 30 km/h.
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "speed_kmh": 30.0,
                "door_state": {"car-1:door-1A": "closing"},
            },
        )
        assert resp.status_code == 200

        # 2. Inference candidate → fusion → event-store.
        resp = client.post(
            "/candidates/door_obstruction",
            json={
                "car_id": "car-1",
                "door_id": "door-1A",
                "obstruction_type": "person",
                "track_id": "42",
                "camera_id": "C1_DOOR_01",
                "confidence": None,
                "door_state": "unknown",
            },
        )
        assert resp.status_code == 202
        assert route.call_count == 1

        body = route.calls.last.request.content.decode()
        env = EventEnvelope.model_validate_json(body)
        assert env.source == "fusion"
        assert env.event_type == EventType.ALERT_RAISED
        assert env.severity == "critical"  # speed > 0
        assert env.payload["alert_code"] == "door_obstruction"

        # 3. Maintenance mode on → second candidate suppressed.
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "speed_kmh": 30.0,
                "maintenance_mode": True,
                "door_state": {"car-1:door-1A": "closing"},
            },
        )
        assert resp.status_code == 200

        resp = client.post(
            "/candidates/door_obstruction",
            json={
                "car_id": "car-1",
                "door_id": "door-1A",
                "obstruction_type": "person",
                "track_id": "43",
                "camera_id": "C1_DOOR_01",
                "confidence": None,
                "door_state": "unknown",
            },
        )
        assert resp.status_code == 202
        # No new POST to event-store under suppression.
        assert route.call_count == 1


@pytest.mark.integration
def test_pipeline_slip_fall_with_station_approach_escalates() -> None:
    client = _build_test_app()

    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "speed_kmh": 5.0,
                "station_approach": True,
            },
        )
        assert resp.status_code == 200

        resp = client.post(
            "/candidates/alert_raised",
            json={
                "alert_type": "slip_fall",
                "car_id": "car-1",
                "track_id": "77",
                "camera_id": "C1_DOOR_01",
            },
        )
        assert resp.status_code == 202

        env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
        assert env.payload["priority"] == "escalated"
        assert env.payload["alert_code"] == "slip_fall"
        assert env.source == "fusion"


@pytest.mark.integration
def test_pipeline_depot_emits_journey_ended_once() -> None:
    client = _build_test_app()

    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "depot_mode": True,
            },
        )
        assert resp.status_code == 200
        assert route.call_count == 1
        env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
        assert env.event_type == EventType.JOURNEY_ENDED
        assert env.source == "fusion"

        # Second push with depot still true → no re-emit.
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "depot_mode": True,
            },
        )
        assert resp.status_code == 200
        assert route.call_count == 1


@pytest.mark.integration
def test_pipeline_ramp_deployed_with_recent_accessibility() -> None:
    client = _build_test_app()

    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )

        # 1. Inference notifies fusion of accessibility detection.
        resp = client.post(
            "/candidates/accessibility_detected",
            json={
                "car_id": "car-1",
                "zone": "door",
                "track_id": "acc-77",
                "assistance_type": ["wheelchair"],
                "camera_id": "C1_DOOR_01",
                "confidence": None,
                "near_door_id": "door-1A",
            },
        )
        assert resp.status_code == 202
        assert route.call_count == 0  # fusion does NOT re-emit ACCESSIBILITY_DETECTED

        # 2. Ramp deployed via context push.
        resp = client.post(
            "/context",
            json={
                "journey_id": "OBB-TEST_t1_20260520",
                "vehicle_id": "OBB-TEST",
                "ramp_deployed": True,
                "ramp_door_id": "door-1A",
                "ramp_station_id": "VIE-HBF",
                "door_state": {"car-1:door-1A": "open"},
            },
        )
        assert resp.status_code == 200
        assert route.call_count == 1

        env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
        assert env.event_type == EventType.RAMP_DEPLOYED
        assert env.payload["triggered_by_track_id"] == "acc-77"
        assert env.payload["station_id"] == "VIE-HBF"
        assert env.source == "fusion"
