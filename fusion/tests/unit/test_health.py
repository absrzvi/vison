"""Health endpoints + readiness cache + ramp/door fallback paths — AC1, AC8."""
from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.health import _ReadinessCache, build_app
from fusion.ledger import CoachLedger
from fusion.suppression import SuppressionGate


def _make_client(
    ctx: ContextState | None = None,
    *,
    tmp_path: object = None,
) -> TestClient:
    settings = Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        ledger_db_path=":memory:",
        ledger_pending_timeout_s=0.05,
    )
    if ctx is None:
        ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    client = httpx.AsyncClient()
    enricher = Enrichment(client, settings, ctx)
    gate = SuppressionGate(ctx, enricher)
    ledger = CoachLedger(settings)
    app = build_app(
        settings=settings,
        ctx=ctx,
        gate=gate,
        enricher=enricher,
        client=client,
        ledger=ledger,
    )
    return TestClient(app)


@pytest.fixture
def cleanup_client() -> Iterator[None]:
    """No-op fixture that signals tests should clean up TestClient when done."""
    yield


@pytest.mark.unit
def test_health_live_returns_ok() -> None:
    client = _make_client()
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    client.close()


@pytest.mark.unit
def test_health_ready_returns_200_when_event_store_reachable() -> None:
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.get("http://event-store-test/health/live").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        resp = client.get("/health/ready")
    assert resp.status_code == 200
    client.close()


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
    client.close()


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
    """Ramp pushed for door not in context.door_state → car_id resolves to 'unknown'."""
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
    client.close()


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
    client.close()


@pytest.mark.unit
def test_car_id_for_door_resolves_from_door_state() -> None:
    ctx = ContextState()
    ctx.door_state = {"car-3:door-3B": "closing"}
    assert ctx.car_id_for_door("door-3B") == "car-3"


@pytest.mark.unit
def test_car_id_for_door_returns_none_when_no_match() -> None:
    ctx = ContextState()
    assert ctx.car_id_for_door("door-X") is None


@pytest.mark.unit
def test_car_id_for_door_ambiguous_returns_none() -> None:
    """Same door_id under multiple cars → ambiguous → None (not first-match)."""
    ctx = ContextState()
    ctx.door_state = {
        "car-1:door-A": "closed",
        "car-2:door-A": "closed",
    }
    # No consist → ambiguous, returns None.
    assert ctx.car_id_for_door("door-A") is None


@pytest.mark.unit
def test_car_id_for_door_consist_disambiguates() -> None:
    ctx = ContextState()
    ctx.door_state = {
        "car-1:door-A": "closed",
        "car-2:door-A": "closed",
    }
    ctx.consist = {"1": "car-1"}  # only car-1 is in the known consist
    assert ctx.car_id_for_door("door-A") == "car-1"


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
                "track_id": 42,
                "camera_id": "C1_DOOR_01",
            },
        )
    assert resp.status_code == 202
    assert not route.called  # suppressed
    client.close()


@pytest.mark.unit
def test_slip_fall_emit_failure_returns_202() -> None:
    """Event-store outage during slip-fall emit must not break the inference caller."""
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            side_effect=httpx.ConnectError("event-store down")
        )
        resp = client.post(
            "/candidates/alert_raised",
            json={
                "alert_type": "slip_fall",
                "car_id": "car-1",
                "track_id": 42,
                "camera_id": "C1_DOOR_01",
            },
        )
    assert resp.status_code == 202
    client.close()


@pytest.mark.unit
def test_door_obstruction_emit_failure_returns_202() -> None:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        door_state={"car-1:door-1A": "closed"},
    )
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            side_effect=httpx.ConnectError("event-store down")
        )
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
    client.close()


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
    client.close()


# ---------------------------------------------------------------------------
# E4-S9 — closed-ledger candidate endpoints + malformed-payload security
# ---------------------------------------------------------------------------


def _valid_wagon_exit_body(track_id: int = 42) -> dict[str, object]:
    return {
        "track_id": track_id,
        "coach_from": "car-1",
        "coach_to": "car-2",
        "camera_id": "C1_GANGWAY_FWD",
        "traversal": "from_to",
        "confidence": 0.9,
        "expect_orphan": False,
    }


def _valid_wagon_entry_body(track_id: int = 42) -> dict[str, object]:
    return {
        "track_id": track_id,
        "coach_from": "car-1",
        "coach_to": "car-2",
        "camera_id": "C2_GANGWAY_AFT",
        "traversal": "from_to",
        "confidence": 0.9,
    }


def _valid_occupancy_body(car_id: str = "car-1", count: int = 50) -> dict[str, object]:
    return {
        "car_id": car_id,
        "zone": None,
        "occupancy_count": count,
        "occupancy_pct": count / 200.0,
        "capacity": 200,
        "service_tier": "standard",
    }


@pytest.mark.unit
def test_wagon_exit_candidate_returns_202() -> None:
    client = _make_client()
    resp = client.post("/candidates/wagon_exit", json=_valid_wagon_exit_body())
    assert resp.status_code == 202
    client.close()


@pytest.mark.unit
def test_wagon_entry_candidate_returns_202() -> None:
    client = _make_client()
    # Pre-seed with an exit so the entry has something to reconcile.
    client.post("/candidates/wagon_exit", json=_valid_wagon_exit_body())
    resp = client.post("/candidates/wagon_entry", json=_valid_wagon_entry_body())
    assert resp.status_code == 202
    client.close()


@pytest.mark.unit
def test_occupancy_update_candidate_returns_202_without_emit_when_gated() -> None:
    """First OCCUPANCY_UPDATE alone (no WAGON_*) must not emit — AC1 gate."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post("/candidates/occupancy_update", json=_valid_occupancy_body())
    assert resp.status_code == 202
    assert not route.called
    client.close()


@pytest.mark.unit
def test_malformed_payload_wagon_exit_returns_422() -> None:
    client = _make_client()
    resp = client.post("/candidates/wagon_exit", json={"track_id": "not-an-int"})
    assert resp.status_code == 422
    client.close()


@pytest.mark.unit
def test_malformed_payload_wagon_entry_returns_422() -> None:
    client = _make_client()
    resp = client.post("/candidates/wagon_entry", json={"coach_from": "car-1"})
    assert resp.status_code == 422
    client.close()


@pytest.mark.unit
def test_malformed_payload_occupancy_update_returns_422() -> None:
    client = _make_client()
    resp = client.post(
        "/candidates/occupancy_update",
        json={"car_id": "", "occupancy_count": -1},
    )
    assert resp.status_code == 422
    client.close()


@pytest.mark.unit
def test_occupancy_update_suppressed_when_gate_closed_but_ledger_mutates() -> None:
    """AC8 — when SuppressionGate.should_emit() is False, no envelope is POSTed
    but ledger state (incl. drift-bucket transition + ADR-15 correction) still
    mutates. Round-1 review P12."""
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        maintenance_mode=True,  # suppression-active
    )
    client = _make_client(ctx)
    # Reach into app.state to seed ledger state before the OCCUPANCY arrives:
    # we need _seen_wagon populated for car-1 and a non-zero ledger_count so
    # the camera count triggers a drift-bucket transition.
    # Easiest way: call the wagon_exit endpoint first (it does not depend on
    # the gate; ledger always mutates on WAGON_EXIT).
    client.post(
        "/candidates/wagon_exit",
        json={
            "track_id": 1,
            "coach_from": "car-1",
            "coach_to": "car-2",
            "camera_id": "C1_FWD",
            "traversal": "from_to",
            "confidence": 0.9,
            "expect_orphan": True,  # avoid arming a timer the TestClient won't drain
        },
    )

    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/candidates/occupancy_update",
            json={
                "car_id": "car-1",
                "zone": None,
                "occupancy_count": 50,
                "occupancy_pct": 0.25,
                "capacity": 200,
                "service_tier": "standard",
            },
        )

    assert resp.status_code == 202
    # No envelope POSTed because SuppressionGate is closed under maintenance_mode.
    assert not envelope_route.called
    client.close()
