"""Unit tests for OccupancyCallback — class filtering, zone masking, budget suppression."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inference.config import Settings
from inference.models import ZoneMask


def make_mock_detection(label: str, bbox: tuple[float, float, float, float], track_id: int) -> MagicMock:
    det = MagicMock()
    det.get_label.return_value = label
    b = MagicMock()
    b.xmin.return_value = bbox[0]
    b.ymin.return_value = bbox[1]
    b.xmax.return_value = bbox[2]
    b.ymax.return_value = bbox[3]
    det.get_bbox.return_value = b
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
def cameras() -> list[dict[str, object]]:
    return [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
            "seat_zones": [
                {"name": "zone-a", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}
            ],
        }
    ]


@pytest.fixture
def zone_masks() -> dict[str, list[ZoneMask]]:
    return {
        "car-1": [ZoneMask(name="zone-a", polygon=[[0, 0], [640, 0], [640, 480], [0, 480]])]
    }


@pytest.fixture
def zone_counter() -> AsyncMock:
    zc = AsyncMock()
    zc.update = AsyncMock()
    return zc


@pytest.fixture
def budget() -> MagicMock:
    b = MagicMock()
    b.should_process.return_value = True
    return b


@pytest.fixture
def callback(
    cameras: list[dict[str, object]],
    zone_masks: dict[str, list[ZoneMask]],
    zone_counter: AsyncMock,
    budget: MagicMock,
    settings: Settings,
) -> object:
    from inference.callback import OccupancyCallback

    return OccupancyCallback(
        cameras=cameras,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
    )


@pytest.mark.unit
@pytest.mark.anyio
async def test_person_detection_forwarded(callback: object, zone_counter: AsyncMock) -> None:
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=1)
    roi = make_mock_roi([det])
    with patch("inference.callback.hailo") as mock_hailo:
        mock_hailo.get_roi_from_buffer.return_value = roi
        mock_hailo.HAILO_DETECTION = "HAILO_DETECTION"
        mock_hailo.HAILO_UNIQUE_ID = "HAILO_UNIQUE_ID"
        roi.get_objects_typed.return_value = [det]
        await callback(MagicMock(), None)  # type: ignore[operator]
    zone_counter.update.assert_called_once()
    args = zone_counter.update.call_args
    car_id = args.args[0] if args.args else args.kwargs["car_id"]
    assert car_id == "car-1"


@pytest.mark.unit
@pytest.mark.anyio
async def test_unknown_class_filtered_out(callback: object, zone_counter: AsyncMock) -> None:
    det = make_mock_detection("dog", (100, 100, 200, 200), track_id=2)
    roi = make_mock_roi([det])
    with patch("inference.callback.hailo") as mock_hailo:
        mock_hailo.get_roi_from_buffer.return_value = roi
        mock_hailo.HAILO_DETECTION = "HAILO_DETECTION"
        mock_hailo.HAILO_UNIQUE_ID = "HAILO_UNIQUE_ID"
        roi.get_objects_typed.return_value = [det]
        await callback(MagicMock(), None)  # type: ignore[operator]
    # update called but with empty detections
    call_args = zone_counter.update.call_args
    if call_args:
        dets = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("detections", [])
        assert len(dets) == 0


@pytest.mark.unit
@pytest.mark.anyio
async def test_budget_suppression_skips_p2(
    cameras: list[dict[str, object]],
    zone_masks: dict[str, list[ZoneMask]],
    zone_counter: AsyncMock,
    settings: Settings,
) -> None:
    from inference.callback import OccupancyCallback

    budget = MagicMock()
    budget.should_process.return_value = False  # P2 suppressed
    cb = OccupancyCallback(
        cameras=cameras,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
    )
    det = make_mock_detection("person", (100, 100, 200, 200), track_id=3)
    roi = make_mock_roi([det])
    with patch("inference.callback.hailo") as mock_hailo:
        mock_hailo.get_roi_from_buffer.return_value = roi
        mock_hailo.HAILO_DETECTION = "HAILO_DETECTION"
        mock_hailo.HAILO_UNIQUE_ID = "HAILO_UNIQUE_ID"
        roi.get_objects_typed.return_value = [det]
        await cb(MagicMock(), None)  # type: ignore[operator]
    zone_counter.update.assert_not_called()


@pytest.mark.unit
@pytest.mark.anyio
async def test_hailo_none_returns_early(
    cameras: list[dict[str, object]],
    zone_masks: dict[str, list[ZoneMask]],
    zone_counter: AsyncMock,
    budget: MagicMock,
    settings: Settings,
) -> None:
    """When hailo module is None and not in sys.modules, callback should return early."""
    import inference.callback as cb_module
    from inference.callback import OccupancyCallback

    orig = cb_module.hailo
    cb_module.hailo = None  # type: ignore[assignment]
    import sys
    sys.modules.pop("inference.callback.hailo", None)

    cb = OccupancyCallback(
        cameras=cameras,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
    )
    await cb(MagicMock(), None)
    zone_counter.update.assert_not_called()
    cb_module.hailo = orig  # type: ignore[assignment]


@pytest.mark.unit
def test_missing_zone_config_raises() -> None:
    from inference.callback import OccupancyCallback

    cameras = [
        {
            "camera_id": "C2_DOOR_01",
            "coach_id": "car-2",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
            "seat_zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
        }
    ]
    # zone_masks intentionally empty — missing car-2
    with pytest.raises(RuntimeError, match="Missing zone config"):
        OccupancyCallback(
            cameras=cameras,
            zone_masks={},  # missing car-2
            zone_counter=AsyncMock(),
            budget=MagicMock(),
            settings=Settings(),
        )
