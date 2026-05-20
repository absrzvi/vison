"""Unit tests for door obstruction detection in OccupancyCallback."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from inference.budget import Budget
from inference.callback import OccupancyCallback, _on_post_done
from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder, ZoneMask
from inference.zone_counter import ZoneCounter


def _make_callback(
    door_camera_map: dict[str, list[str]] | None = None,
) -> OccupancyCallback:
    if door_camera_map is None:
        door_camera_map = {"door-1A": ["C1_DOOR_01"]}

    camera = {
        "camera_id": "C1_DOOR_01",
        "coach_id": "car-1",
        "zone": "door",
        "rtsp_url": "rtsp://fake",
        "priority": "P1",
        "seat_zones": [
            {"name": "zone-a", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}
        ],
    }
    cameras_json = {"cameras": [camera], "door_camera_map": door_camera_map}
    settings = Settings(
        door_obstruction_min_frames=2,
        fusion_url="http://fusion:8090",
    )
    zone_masks = [ZoneMask(name="zone-a", polygon=[[0, 0], [640, 0], [640, 480], [0, 480]])]
    loop_holder = LoopHolder(loop=None)
    budget = MagicMock(spec=Budget)
    budget.should_process.return_value = True

    client = AsyncMock()
    resp = AsyncMock()
    resp.raise_for_status = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    jh = JourneyHolder(journey_id="OBB-T_001_20260519")
    zone_counter = ZoneCounter(
        cameras=[camera],
        settings=settings,
        event_store_client=client,
        journey_holder=jh,
    )
    return OccupancyCallback(
        camera=camera,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=loop_holder,
        cameras_json=cameras_json,
        event_store_client=client,
        safety_handler=None,
    )


@pytest.mark.unit
def test_on_post_done_logs_exception() -> None:
    """_on_post_done logs exceptions from scheduled futures without raising."""
    from concurrent.futures import Future

    fut: Future[None] = Future()
    fut.set_exception(RuntimeError("network error"))
    # Should not raise
    _on_post_done(fut)


@pytest.mark.unit
def test_on_post_done_no_exception_is_silent() -> None:
    """_on_post_done does nothing when future succeeded."""
    from concurrent.futures import Future

    fut: Future[None] = Future()
    fut.set_result(None)
    _on_post_done(fut)  # should not raise


@pytest.mark.unit
def test_iou_overlapping() -> None:
    cb = _make_callback()
    a = (0.0, 0.0, 100.0, 100.0)
    b = (50.0, 50.0, 150.0, 150.0)
    iou = cb._iou(a, b)
    assert 0.0 < iou < 1.0


@pytest.mark.unit
def test_iou_identical() -> None:
    cb = _make_callback()
    a = (0.0, 0.0, 100.0, 100.0)
    assert cb._iou(a, a) == pytest.approx(1.0)


@pytest.mark.unit
def test_iou_no_overlap() -> None:
    cb = _make_callback()
    a = (0.0, 0.0, 50.0, 50.0)
    b = (100.0, 100.0, 200.0, 200.0)
    assert cb._iou(a, b) == pytest.approx(0.0)


@pytest.mark.unit
def test_handle_person_door_obstruction_emits_on_min_frames() -> None:
    """Person track in door zone for ≥ min_frames → emit candidate to fusion."""
    cb = _make_callback()
    loop = asyncio.new_event_loop()
    cb._loop_holder.loop = loop

    futures_added: list[Any] = []

    def fake_run_coroutine_threadsafe(coro: Any, lp: Any) -> Any:
        import concurrent.futures
        fut: concurrent.futures.Future[None] = concurrent.futures.Future()
        fut.set_result(None)
        futures_added.append(coro)
        loop.run_until_complete(coro)
        return fut

    import asyncio as asyncio_mod
    original = asyncio_mod.run_coroutine_threadsafe
    asyncio_mod.run_coroutine_threadsafe = fake_run_coroutine_threadsafe  # type: ignore[assignment]

    try:
        # First frame — counter = 1, no emit yet (min_frames=2)
        cb._handle_person_door_obstruction(42, loop)
        # Second frame — counter = 2, emit
        cb._handle_person_door_obstruction(42, loop)
        assert len(futures_added) == 1
    finally:
        asyncio_mod.run_coroutine_threadsafe = original  # type: ignore[assignment]
        loop.close()
        cb._loop_holder.loop = None


@pytest.mark.unit
def test_handle_suitcase_door_obstruction_iou_tracking() -> None:
    """Suitcase in door zone across 2 frames with IoU>0.5 → emit on second frame."""
    cb = _make_callback()
    loop = asyncio.new_event_loop()
    cb._loop_holder.loop = loop

    futures_added: list[Any] = []

    def fake_run_coroutine_threadsafe(coro: Any, lp: Any) -> Any:
        import concurrent.futures
        fut: concurrent.futures.Future[None] = concurrent.futures.Future()
        fut.set_result(None)
        futures_added.append(coro)
        loop.run_until_complete(coro)
        return fut

    import asyncio as asyncio_mod
    original = asyncio_mod.run_coroutine_threadsafe
    asyncio_mod.run_coroutine_threadsafe = fake_run_coroutine_threadsafe  # type: ignore[assignment]

    try:
        bbox1 = (50.0, 50.0, 150.0, 200.0)
        bbox2 = (55.0, 55.0, 155.0, 205.0)  # high IoU with bbox1
        cb._handle_suitcase_door_obstruction([bbox1], loop)
        cb._handle_suitcase_door_obstruction([bbox2], loop)
        assert len(futures_added) == 1
    finally:
        asyncio_mod.run_coroutine_threadsafe = original  # type: ignore[assignment]
        loop.close()
        cb._loop_holder.loop = None


@pytest.mark.unit
def test_handle_suitcase_resets_on_low_iou() -> None:
    """Suitcase with IoU < 0.5 compared to prev → counter resets, no emit."""
    cb = _make_callback()
    loop = asyncio.new_event_loop()
    cb._loop_holder.loop = loop

    futures_added: list[Any] = []

    def fake_run_coroutine_threadsafe(coro: Any, lp: Any) -> Any:
        import concurrent.futures
        fut: concurrent.futures.Future[None] = concurrent.futures.Future()
        fut.set_result(None)
        futures_added.append(coro)
        loop.run_until_complete(coro)
        return fut

    import asyncio as asyncio_mod
    original = asyncio_mod.run_coroutine_threadsafe
    asyncio_mod.run_coroutine_threadsafe = fake_run_coroutine_threadsafe  # type: ignore[assignment]

    try:
        bbox1 = (0.0, 0.0, 50.0, 50.0)
        bbox2 = (400.0, 400.0, 500.0, 500.0)  # no overlap
        cb._handle_suitcase_door_obstruction([bbox1], loop)
        cb._handle_suitcase_door_obstruction([bbox2], loop)
        # Counter reset at frame 2, so count=1, still < min_frames=2
        assert len(futures_added) == 0
    finally:
        asyncio_mod.run_coroutine_threadsafe = original  # type: ignore[assignment]
        loop.close()
        cb._loop_holder.loop = None
