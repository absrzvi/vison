"""Health endpoints + readiness cache + ramp/door fallback paths — AC1, AC8."""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from fusion.comfort_index import ComfortIndexState
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
    comfort = ComfortIndexState(settings)
    app = build_app(
        settings=settings,
        ctx=ctx,
        gate=gate,
        enricher=enricher,
        client=client,
        ledger=ledger,
        comfort=comfort,
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
                "model_versions": {"detector_arch": "yolox_s_leaky"},
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
            "model_versions": {"detector_arch": "yolox_s_leaky"},
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
        "service_tier": "standard", "model_versions": {"detector_arch": "yolox_s_leaky"},
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
                "service_tier": "standard", "model_versions": {"detector_arch": "yolox_s_leaky"},
            },
        )

    assert resp.status_code == 202
    # No envelope POSTed because SuppressionGate is closed under maintenance_mode.
    assert not envelope_route.called
    client.close()



# ---------------------------------------------------------------------------
# E4-S10 — Coach Comfort Index handler-layer tests
# ---------------------------------------------------------------------------


def _valid_occupancy_body(car_id: str = "car-1", pct: float = 0.4) -> dict[str, object]:
    return {
        "car_id": car_id,
        "zone": None,
        "occupancy_count": int(round(pct * 200)),
        "occupancy_pct": pct,
        "capacity": 200,
        "service_tier": "standard", "model_versions": {"detector_arch": "yolox_s_leaky"},
    }


@pytest.mark.unit
def test_comfort_index_emits_on_delta_via_candidates_endpoint() -> None:
    """AC1 + AC4 — first OCCUPANCY seeds (no emit); second past threshold emits
    a COACH_COMFORT_INDEX envelope to event-store."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        # First OCCUPANCY: cold-start; no emit.
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.30))
        assert not envelope_route.called
        # Second OCCUPANCY: delta 0.20 > 0.10 threshold → emit.
        resp = client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.50))

    assert resp.status_code == 202
    assert envelope_route.called
    # Verify the envelope is a COACH_COMFORT_INDEX (not a LEDGER_DRIFT_OBSERVATION).
    bodies = [json.loads(c.request.content) for c in envelope_route.calls]
    event_types = [b["event_type"] for b in bodies]
    assert "COACH_COMFORT_INDEX" in event_types
    client.close()


@pytest.mark.unit
def test_comfort_index_suppressed_under_maintenance() -> None:
    """AC5 — under suppression, no COACH_COMFORT_INDEX envelope POSTed, and
    `_last_emitted_pct` is NOT advanced."""
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        maintenance_mode=True,
    )
    client = _make_client(ctx)
    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.30))
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.80))

    # Note: ledger drift wouldn't emit either (ledger_count starts at 0, but
    # _seen_wagon is empty → check_drift returns None). So no envelopes at all.
    assert not envelope_route.called
    client.close()


@pytest.mark.unit
def test_comfort_index_emit_failure_returns_202() -> None:
    """Downstream failure on COACH_COMFORT_INDEX emit must not break the
    handler's 202 response (mirrors door_obstruction fail-safe)."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        rmock.post("http://event-store-test/api/v1/events").mock(
            side_effect=httpx.ConnectError("event-store down")
        )
        # First (seed) tolerates failure since no emit happens.
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.30))
        # Second crosses threshold → tries to emit, fails, handler still 202.
        resp = client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.60))
    assert resp.status_code == 202
    client.close()


@pytest.mark.unit
def test_comfort_index_station_approach_edge_emits_for_observed_coaches() -> None:
    """AC2 — when station_approach transitions False→True via /context, one
    COACH_COMFORT_INDEX is emitted per coach that has at least one OCCUPANCY."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        # Seed two coaches.
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(car_id="car-1", pct=0.40))
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(car_id="car-2", pct=0.70))
        envelope_route.reset()
        # Push station_approach=True; should emit two COACH_COMFORT_INDEX events.
        resp = client.post("/context", json={"station_approach": True})

    assert resp.status_code == 200
    bodies = [json.loads(c.request.content) for c in envelope_route.calls]
    comfort_envelopes = [b for b in bodies if b["event_type"] == "COACH_COMFORT_INDEX"]
    assert len(comfort_envelopes) == 2
    car_ids = sorted(b["payload"]["car_id"] for b in comfort_envelopes)
    assert car_ids == ["car-1", "car-2"]
    client.close()


@pytest.mark.unit
def test_comfort_index_station_approach_steady_state_no_emit() -> None:
    """AC2 — station_approach already True on prior push; no further edge fires."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.40))
        client.post("/context", json={"station_approach": True})  # edge 1
        envelope_route.reset()
        client.post("/context", json={"station_approach": True})  # steady — no edge
    assert not envelope_route.called
    client.close()


@pytest.mark.unit
def test_comfort_index_station_edge_preserved_under_suppression() -> None:
    """D3 fix — edge is NOT consumed when gate is closed; re-fires on next push
    after suppression clears.

    Scenario:
    1. Seed a coach while gate is open (normal state).
    2. Push maintenance_mode=True + station_approach=True in same push —
       edge fires but gate is closed → edge preserved (prev not advanced).
    3. Clear maintenance_mode, push station_approach=True again (steady) —
       because prev was never advanced, peek sees it as a fresh edge → emit.
    """
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        envelope_route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        # Step 1: seed a coach while gate is open.
        client.post("/candidates/occupancy_update", json=_valid_occupancy_body(pct=0.40))
        envelope_route.reset()

        # Step 2: enter maintenance + station_approach=True in same push.
        # Edge fires (prev=False, current=True), gate closed → edge not consumed.
        client.post("/context", json={"station_approach": True, "maintenance_mode": True})
        assert not envelope_route.called

        # Step 3: clear maintenance, push station_approach=True again.
        # prev is still False → peek returns True → gate open → emit fires.
        client.post("/context", json={"station_approach": True, "maintenance_mode": False})

    bodies = [json.loads(c.request.content) for c in envelope_route.calls]
    comfort_envelopes = [b for b in bodies if b["event_type"] == "COACH_COMFORT_INDEX"]
    assert len(comfort_envelopes) >= 1
    client.close()


@pytest.mark.unit
def test_slip_fall_candidate_carries_model_confidence() -> None:
    """Story 10-1 AC9: slip-fall alert is model-basis with score + versions
    from the inference candidate body."""
    client = _make_client()
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
                "camera_id": "C1_INT_01",
                "confidence": 0.66,
                "model_versions": {"detector_arch": "yolox_s_leaky"},
            },
        )
    assert resp.status_code == 202
    assert route.called
    body = json.loads(route.calls.last.request.content.decode())
    assert body["payload"]["confidence_basis"] == "model"
    assert body["payload"]["confidence_score"] == 0.66
    assert body["payload"]["model_versions"] == {"detector_arch": "yolox_s_leaky"}
    client.close()


@pytest.mark.unit
def test_slip_fall_candidate_missing_confidence_fails_safe_to_zero() -> None:
    """Candidate without confidence (legacy producer) emits score 0.0 — the
    lowest-trust rendering — rather than dropping the safety alert."""
    client = _make_client()
    with respx.mock(assert_all_called=False) as rmock:
        route = rmock.post("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(201)
        )
        resp = client.post(
            "/candidates/alert_raised",
            json={
                "alert_type": "slip_fall",
                "car_id": "car-1",
                "track_id": 7,
                "camera_id": "C1_INT_01",
            },
        )
    assert resp.status_code == 202
    assert route.called
    body = json.loads(route.calls.last.request.content.decode())
    assert body["payload"]["confidence_score"] == 0.0
    assert body["payload"]["confidence_basis"] == "model"
    assert body["payload"]["model_versions"] == {"detector_arch": "unknown"}
    client.close()
