"""Unit tests for OccupancyCallback — sync handoff, class/zone filtering, budget suppression."""
from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inference.config import Settings
from inference.models import LoopHolder, ZoneMask


def make_mock_detection(
    label: str, bbox: tuple[float, float, float, float], track_id: int | None
) -> MagicMock:
    det = MagicMock()
    det.get_label.return_value = label
    b = MagicMock()
    b.xmin.return_value = bbox[0]
    b.ymin.return_value = bbox[1]
    b.xmax.return_value = bbox[2]
    b.ymax.return_value = bbox[3]
    det.get_bbox.return_value = b
    if track_id is None:
        det.get_objects_typed.return_value = []
    else:
        uid = MagicMock()
        uid.get_id.return_value = track_id
        det.get_objects_typed.return_value = [uid]
    return det


def make_mock_roi(detections: list[MagicMock]) -> MagicMock:
    roi = MagicMock()
    roi.get_objects_typed.return_value = detections
    return roi


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def camera() -> dict[str, Any]:
    return {
        "camera_id": "C1_DOOR_01",
        "coach_id": "car-1",
        "zone": "door",
        "priority": "P1",
        "capacity": 200,
    }


@pytest.fixture
def zone_masks() -> list[ZoneMask]:
    return [ZoneMask(name="zone-a", polygon=[[0, 0], [640, 0], [640, 480], [0, 480]])]


@pytest.fixture
def zone_counter() -> AsyncMock:
    zc = MagicMock()
    zc.update = AsyncMock()
    return zc


@pytest.fixture
def budget() -> MagicMock:
    b = MagicMock()
    b.should_process.return_value = True
    return b


@pytest.fixture
def loop_holder_with_loop() -> LoopHolder:
    """LoopHolder pre-wired to a running loop in a background thread."""
    holder = LoopHolder(loop=None)
    started = threading.Event()

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder.loop = loop
        started.set()
        loop.run_forever()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    started.wait(timeout=2.0)
    yield holder
    if holder.loop is not None:
        holder.loop.call_soon_threadsafe(holder.loop.stop)
    t.join(timeout=2.0)


@pytest.fixture
def callback(
    camera: dict[str, Any],
    zone_masks: list[ZoneMask],
    zone_counter: MagicMock,
    budget: MagicMock,
    settings: Settings,
    loop_holder_with_loop: LoopHolder,
) -> object:
    from inference.callback import OccupancyCallback

    return OccupancyCallback(
        camera=camera,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=loop_holder_with_loop,
    )


def _patched_hailo() -> Any:
    mock_hailo = MagicMock()
    mock_hailo.HAILO_DETECTION = "HAILO_DETECTION"
    mock_hailo.HAILO_UNIQUE_ID = "HAILO_UNIQUE_ID"
    return mock_hailo


def _wait_for_call(mock: AsyncMock, timeout: float = 2.0) -> None:
    """Poll for the AsyncMock to be invoked from a background thread."""
    deadline = asyncio.get_event_loop().time() + timeout
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if mock.call_count > 0:
            return
        time.sleep(0.01)
    del deadline


@pytest.mark.unit
def test_person_detection_inside_zone_forwarded(callback: object, zone_counter: MagicMock) -> None:
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=1)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        callback(MagicMock(), None)  # type: ignore[operator]
    _wait_for_call(zone_counter.update)
    zone_counter.update.assert_called_once()
    args = zone_counter.update.call_args
    car_id = args.args[0]
    accepted = args.args[1]
    assert car_id == "car-1"
    assert len(accepted) == 1
    assert accepted[0]["label"] == "person"
    assert accepted[0]["track_id"] == 1


@pytest.mark.unit
def test_unknown_class_filtered_out(callback: object, zone_counter: MagicMock) -> None:
    det = make_mock_detection("dog", (100, 100, 200, 200), track_id=2)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        callback(MagicMock(), None)  # type: ignore[operator]
    _wait_for_call(zone_counter.update)
    # update is called once with an empty accepted list — vacuous "if call_args"
    # check from earlier review is fixed: we assert the contents directly.
    zone_counter.update.assert_called_once()
    accepted = zone_counter.update.call_args.args[1]
    assert accepted == []


@pytest.mark.unit
def test_detection_outside_zone_filtered_out(
    camera: dict[str, Any],
    zone_counter: MagicMock,
    budget: MagicMock,
    settings: Settings,
    loop_holder_with_loop: LoopHolder,
) -> None:
    from inference.callback import OccupancyCallback

    # Zone is a small box; detection centroid is far outside.
    small_zone = [ZoneMask(name="z", polygon=[[0, 0], [10, 0], [10, 10], [0, 10]])]
    cb = OccupancyCallback(
        camera=camera,
        zone_masks=small_zone,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=loop_holder_with_loop,
    )
    det = make_mock_detection("person", (500, 500, 600, 600), track_id=1)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        cb(MagicMock(), None)
    _wait_for_call(zone_counter.update)
    zone_counter.update.assert_called_once()
    accepted = zone_counter.update.call_args.args[1]
    assert accepted == []


@pytest.mark.unit
def test_none_track_id_filtered_out(callback: object, zone_counter: MagicMock) -> None:
    """Detection without a track UID (e.g. first frame before tracker assigns) is dropped."""
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=None)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        callback(MagicMock(), None)  # type: ignore[operator]
    _wait_for_call(zone_counter.update)
    zone_counter.update.assert_called_once()
    accepted = zone_counter.update.call_args.args[1]
    assert accepted == []


@pytest.mark.unit
def test_budget_suppression_skips_callback(
    camera: dict[str, Any],
    zone_masks: list[ZoneMask],
    zone_counter: MagicMock,
    settings: Settings,
    loop_holder_with_loop: LoopHolder,
) -> None:
    from inference.callback import OccupancyCallback

    budget = MagicMock()
    budget.should_process.return_value = False  # P2 suppressed
    cb = OccupancyCallback(
        camera=camera,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=loop_holder_with_loop,
    )
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=3)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        cb(MagicMock(), None)
    zone_counter.update.assert_not_called()


@pytest.mark.unit
def test_hailo_none_returns_early(
    camera: dict[str, Any],
    zone_masks: list[ZoneMask],
    zone_counter: MagicMock,
    budget: MagicMock,
    settings: Settings,
    loop_holder_with_loop: LoopHolder,
) -> None:
    """When hailo module is None, callback returns early without crashing."""
    from inference.callback import OccupancyCallback

    cb = OccupancyCallback(
        camera=camera,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=loop_holder_with_loop,
    )
    # Use patch context manager — guarantees restoration even on assertion failure.
    with patch("inference.callback.hailo", None):
        cb(MagicMock(), None)
    zone_counter.update.assert_not_called()


@pytest.mark.unit
def test_no_loop_yet_skips_dispatch(
    camera: dict[str, Any],
    zone_masks: list[ZoneMask],
    zone_counter: MagicMock,
    budget: MagicMock,
    settings: Settings,
) -> None:
    """Before main's lifespan sets the loop, callback returns without scheduling."""
    from inference.callback import OccupancyCallback

    empty_holder = LoopHolder(loop=None)
    cb = OccupancyCallback(
        camera=camera,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
        loop_holder=empty_holder,
    )
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=1)
    roi = make_mock_roi([det])
    mock_hailo = _patched_hailo()
    mock_hailo.get_roi_from_buffer.return_value = roi
    with patch("inference.callback.hailo", mock_hailo):
        cb(MagicMock(), None)
    zone_counter.update.assert_not_called()


@pytest.mark.unit
def test_missing_zone_config_raises(
    camera: dict[str, Any],
    zone_counter: MagicMock,
    budget: MagicMock,
    settings: Settings,
    loop_holder_with_loop: LoopHolder,
) -> None:
    from inference.callback import OccupancyCallback

    with pytest.raises(RuntimeError, match="Missing zone config"):
        OccupancyCallback(
            camera=camera,
            zone_masks=[],  # no zones — must refuse to start
            zone_counter=zone_counter,
            budget=budget,
            settings=settings,
            loop_holder=loop_holder_with_loop,
        )


@pytest.mark.unit
def test_point_in_polygon_basic() -> None:
    from inference.callback import _point_in_polygon

    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert _point_in_polygon(5, 5, square) is True
    assert _point_in_polygon(20, 5, square) is False
    assert _point_in_polygon(-1, 5, square) is False


@pytest.mark.unit
def test_point_in_polygon_degenerate_returns_false() -> None:
    from inference.callback import _point_in_polygon

    # < 3 vertices is not a polygon
    assert _point_in_polygon(0, 0, [[0, 0], [1, 1]]) is False
