"""Tests for ContextStateManager — delta push and suppression."""

from __future__ import annotations

import httpx
import pytest
import respx

from vlan_pollers.context_state import ContextStateManager
from vlan_pollers.models import AlarmEntry, PisState

FUSION = "http://fusion-test:8003"
INFERENCE = "http://inference-test:8004"
RTSP = "http://rtsp-test:8005"


def _make_ctx() -> ContextStateManager:
    return ContextStateManager(
        fusion_url=FUSION,
        inference_url=INFERENCE,
        rtsp_ingest_url=RTSP,
    )


@pytest.mark.unit
@respx.mock
async def test_update_journey_pushes_on_change() -> None:
    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    inf_route = respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.update_journey("OBB-1_T1_20260517", "T1", "OBB-1")

    assert fusion_route.called
    assert inf_route.called


@pytest.mark.unit
async def test_update_journey_suppresses_on_no_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    await ctx.update_journey("OBB-1_T1_20260517", "T1", "OBB-1")
    assert call_count == 1

    # Second call with identical values — should NOT push again
    await ctx.update_journey("OBB-1_T1_20260517", "T1", "OBB-1")
    assert call_count == 1  # still 1


@pytest.mark.unit
@respx.mock
async def test_update_alarm_pushes_on_new_alarm() -> None:
    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    entry = AlarmEntry(alarm_id="ALM-1", description="Test", severity="critical", active=True)
    await ctx.update_alarm(entry)

    assert fusion_route.called


@pytest.mark.unit
async def test_update_alarm_suppresses_on_identical_state() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    entry = AlarmEntry(alarm_id="ALM-1", description="Test", severity="critical", active=True)
    await ctx.update_alarm(entry)
    assert call_count == 1

    # Same alarm again — should suppress
    await ctx.update_alarm(entry)
    assert call_count == 1


@pytest.mark.unit
@respx.mock
async def test_door_release_posts_to_rtsp() -> None:
    rtsp_route = respx.post(f"{RTSP}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.set_door_release("CAR-1", "DOOR-A")

    assert rtsp_route.called
    body = rtsp_route.calls[0].request.content
    import json
    payload = json.loads(body)
    assert payload["event"] == "door_release"
    assert payload["car_id"] == "CAR-1"
    assert payload["door_id"] == "DOOR-A"
    assert ctx.state.door_release["CAR-1:DOOR-A"] is True


@pytest.mark.unit
@respx.mock
async def test_station_approach_pushes_to_fusion() -> None:
    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.set_station_approach(True)

    assert fusion_route.called


@pytest.mark.unit
async def test_station_approach_suppresses_on_no_change() -> None:
    call_count = 0

    async def fake_post(url: str, payload: object) -> None:
        nonlocal call_count
        call_count += 1

    from vlan_pollers import context_state as cs_module
    orig = cs_module._post_with_retry

    try:
        cs_module._post_with_retry = fake_post  # type: ignore[assignment]
        ctx = _make_ctx()
        await ctx.set_station_approach(True)
        assert call_count == 1
        await ctx.set_station_approach(True)  # same value — should suppress
        assert call_count == 1
    finally:
        cs_module._post_with_retry = orig  # type: ignore[assignment]


@pytest.mark.unit
@respx.mock
async def test_speed_update_pushes_context() -> None:
    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.update_speed(45.5)

    assert fusion_route.called
    assert ctx.state.speed_kmh == 45.5


@pytest.mark.unit
@respx.mock
async def test_update_pis_delivers_scheduled_departure_via_nested_pis() -> None:
    """E6-S4: scheduled_departure reaches fusion via the full-delta push's NESTED `pis`
    object (fusion's ContextPushModel now declares `pis` and reads pis.scheduled_departure).
    The E10-S4 targeted flat push is removed — single delivery path."""
    import json

    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.update_journey("OBB-1_T1_20260517", "T1", "OBB-1")
    await ctx.update_pis(
        PisState(
            next_station="Wien",
            next_station_arrival_utc="",
            scheduled_departure="2026-05-19T12:05:00Z",
            actual_departure="",
            platform="2",
            delay_min=0,
        )
    )

    bodies = [json.loads(call.request.content) for call in fusion_route.calls]
    # scheduled_departure rides the full-delta push NESTED under `pis` — no flat key.
    sched = "2026-05-19T12:05:00Z"
    with_pis = [b for b in bodies if b.get("pis", {}).get("scheduled_departure") == sched]
    assert with_pis, f"no full-delta push carrying nested pis.scheduled_departure; bodies={bodies}"
    assert all("scheduled_departure" not in b for b in bodies), (
        "flat scheduled_departure key must be gone"
    )


@pytest.mark.unit
@respx.mock
async def test_update_journey_resets_pis_so_journey_change_carries_no_stale_departure() -> None:
    """E6-S4 review R1: a journey change must NOT push the prior journey's PIS. The PIS
    poller for the new journey hasn't run yet, so update_journey resets _state.pis —
    otherwise the J1→J2 full-delta push carries J1's scheduled_departure and fusion
    inherits it on J2."""
    import json

    fusion_route = respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    ctx = _make_ctx()
    await ctx.update_journey("OBB-1_T1_20260517", "T1", "OBB-1")
    await ctx.update_pis(
        PisState(scheduled_departure="2026-05-19T12:05:00Z", next_station="Wien")
    )
    # New journey starts before its PIS is polled.
    fusion_route.calls.reset()
    await ctx.update_journey("OBB-1_T2_20260517", "T2", "OBB-1")

    body = json.loads(fusion_route.calls.last.request.content)
    assert body["journey_id"] == "OBB-1_T2_20260517"
    # The nested pis must be RESET (empty departure), not carry J1's value.
    assert body["pis"]["scheduled_departure"] == "", (
        f"journey-change push leaked stale pis: {body['pis']}"
    )
    assert ctx.state.pis.scheduled_departure == ""


@pytest.mark.unit
async def test_push_context_delta_isolates_per_service_failure() -> None:
    """E6-S4 AC4 / deferred F21: a failure POSTing to one consumer must NOT skip the
    other. If the fusion POST raises, inference must still receive the push."""
    calls: list[str] = []

    async def fake_post(url: str, payload: object) -> None:
        calls.append(url)
        if url.startswith(FUSION):
            raise httpx.ConnectError("fusion down")

    from vlan_pollers import context_state as cs_module

    orig = cs_module._post_with_retry
    try:
        cs_module._post_with_retry = fake_post  # type: ignore[assignment]
        ctx = _make_ctx()
        ctx._state.journey_id = "OBB-1_T1_20260517"
        await ctx._push_context_delta()
    finally:
        cs_module._post_with_retry = orig  # type: ignore[assignment]

    # Both consumers attempted despite fusion raising.
    assert any(u.startswith(FUSION) for u in calls), f"fusion not attempted: {calls}"
    assert any(u.startswith(INFERENCE) for u in calls), (
        f"inference starved by fusion failure: {calls}"
    )


@pytest.mark.unit
@respx.mock
async def test_pis_update_suppresses_on_no_change() -> None:
    # E6-S4: update_pis fires only _push_context_delta (the E10-S4 targeted flat push
    # was removed). Mock fusion so suppression is exercised, not the network.
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))

    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    pis = PisState(next_station="Wien Hbf", next_station_arrival_utc="2026-05-17T10:00:00Z")
    await ctx.update_pis(pis)
    assert call_count == 1

    await ctx.update_pis(pis)  # same values — suppress (no delta push)
    assert call_count == 1


@pytest.mark.unit
async def test_update_occupancy_pushes_on_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    from oebb_shared.adapters.apc.adapter import OccupancyReading

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    readings = {
        "car-1": OccupancyReading(car_id="car-1", count=42, timestamp="2026-05-19T10:00:00Z")
    }
    await ctx.update_occupancy(readings)
    assert call_count == 1


@pytest.mark.unit
async def test_update_occupancy_suppresses_on_no_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    from oebb_shared.adapters.apc.adapter import OccupancyReading

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    readings = {
        "car-1": OccupancyReading(car_id="car-1", count=42, timestamp="2026-05-19T10:00:00Z")
    }
    await ctx.update_occupancy(readings)
    assert call_count == 1

    await ctx.update_occupancy(readings)  # identical — suppress
    assert call_count == 1


@pytest.mark.unit
async def test_update_reservations_pushes_on_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    await ctx.update_reservations({"car-1": 42, "car-2": 180})
    assert call_count == 1


@pytest.mark.unit
async def test_update_reservations_suppresses_on_no_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    data = {"car-1": 42, "car-2": 180}
    await ctx.update_reservations(data)
    assert call_count == 1

    await ctx.update_reservations(data)  # same — suppress
    assert call_count == 1


@pytest.mark.unit
@respx.mock
async def test_state_to_dict_includes_occupancy_and_reservations() -> None:
    """AC2/4: _state_to_dict serializes occupancy and reservations fields."""
    from oebb_shared.adapters.apc.adapter import OccupancyReading

    from vlan_pollers.context_state import _state_to_dict
    from vlan_pollers.models import ContextState

    state = ContextState()
    state.occupancy = {
        "car-1": OccupancyReading(car_id="car-1", count=10, timestamp="2026-05-19T10:00:00Z")
    }
    state.reservations = {"car-1": 99}

    d = _state_to_dict(state)
    assert "occupancy" in d
    assert "car-1" in d["occupancy"]
    assert d["occupancy"]["car-1"]["count"] == 10
    assert "reservations" in d
    assert d["reservations"]["car-1"] == 99
