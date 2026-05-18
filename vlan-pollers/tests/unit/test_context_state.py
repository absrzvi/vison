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
async def test_pis_update_suppresses_on_no_change() -> None:
    call_count = 0

    async def fake_push() -> None:
        nonlocal call_count
        call_count += 1

    ctx = _make_ctx()
    ctx._push_context_delta = fake_push  # type: ignore[method-assign]

    pis = PisState(next_station="Wien Hbf", next_station_arrival_utc="2026-05-17T10:00:00Z")
    await ctx.update_pis(pis)
    assert call_count == 1

    await ctx.update_pis(pis)  # same values — suppress
    assert call_count == 1
