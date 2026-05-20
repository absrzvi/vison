"""Health endpoints + readiness cache + ramp/door fallback paths — AC1, AC8."""
from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import _car_id_for_door, _ReadinessCache, build_app
from fusion.suppression import SuppressionGate


def _make_client(ctx: ContextState | None = None) -> TestClient:
    settings = Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        journey_id="OBB-TEST_t1_20260520",
    )
    if ctx is None:
        ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    client = httpx.AsyncClient()
    enricher = Enrichment(client, settings, ctx)
    gate = SuppressionGate(ctx, enricher)
    app = build_app(settings=settings, ctx=ctx, gate=gate, enricher=enricher, client=client)
    return TestClient(app)


@pytest.mark.unit
def test_health_live_returns_ok() -> None:
    client = _make_client()
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.unit
def test_health_ready_returns_200_when_event_store_reachable() -> None:
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.get("http://event-store-test/health/live").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        resp = client.get("/health/ready")
    assert resp.status_code == 200


@pytest.mark.unit
def test_health_ready_returns_503_when_event_store_unreachable() -> None:
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.get("http://event-store-test/health/live").mock(
            side_effect=httpx.ConnectError("nope")
        )
        resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "event_store_unreachable"


@pytest.mark.unit
async def test_readiness_cache_serves_cached_result_within_ttl() -> None:
    cache = _ReadinessCache(ttl_s=10.0)
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=False) as rmock:
            route = rmock.get("http://event-store-test/health/live").mock(
                return_value=httpx.Response(200)
            )
            r1 = await cache.is_ready(client, "http://event-store-test")
            r2 = await cache.is_ready(client, "http://event-store-test")
    assert r1 is True
    assert r2 is True
    assert route.call_count == 1  # second call served from cache


@pytest.mark.unit
def test_ramp_deployed_with_no_known_door_uses_unknown_car_id() -> None:
    """Ramp pushed for door not in context.door_state → _car_id_for_door returns 'unknown'."""
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/context",
            json={
                "ramp_deployed": True,
                "ramp_door_id": "door-9X",
                "ramp_station_id": "VIE-HBF",
            },
        )
    assert resp.status_code == 200


@pytest.mark.unit
def test_ramp_emit_failure_is_logged_not_raised() -> None:
    """If event-store POST fails, the /context handler still returns 200."""
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    ctx.note_accessibility("car-1", "door-1A", "trk-7")
    ctx.door_state["car-1:door-1A"] = "open"
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            side_effect=httpx.ConnectError("event-store down")
        )
        resp = client.post(
            "/context",
            json={
                "ramp_deployed": True,
                "ramp_door_id": "door-1A",
                "ramp_station_id": "VIE-HBF",
            },
        )
    assert resp.status_code == 200


@pytest.mark.unit
def test_car_id_for_door_resolves_from_door_state() -> None:
    ctx = ContextState()
    ctx.door_state = {"car-3:door-3B": "closing"}
    assert _car_id_for_door(ctx, "door-3B") == "car-3"


@pytest.mark.unit
def test_car_id_for_door_returns_unknown_when_no_match() -> None:
    ctx = ContextState()
    assert _car_id_for_door(ctx, "door-X") == "unknown"


@pytest.mark.unit
def test_slip_fall_suppressed_under_maintenance_returns_202() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        maintenance_mode=True,
    )
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/candidates/alert_raised",
            json={
                "alert_type": "slip_fall",
                "car_id": "car-1",
                "track_id": "42",
                "camera_id": "C1_DOOR_01",
            },
        )
    assert resp.status_code == 202
    assert not route.called  # suppressed


@pytest.mark.unit
def test_accessibility_candidate_endpoint_updates_ctx_only() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    client = _make_client(ctx)
    resp = client.post(
        "/candidates/accessibility_detected",
        json={
            "car_id": "car-1",
            "zone": "door",
            "track_id": "trk-99",
            "assistance_type": ["wheelchair"],
            "camera_id": "C1_DOOR_01",
            "confidence": None,
            "near_door_id": "door-1A",
        },
    )
    assert resp.status_code == 202
    assert ctx.find_recent_accessibility("car-1", "door-1A", window_s=60.0) == "trk-99"
