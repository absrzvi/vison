"""Unit tests for slip/fall detection heuristic in ZoneCounter.

Pure bbox math — no Hailo hardware required.
RED phase: tests fail until _check_slip_fall is implemented in zone_counter.py.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from inference.config import Settings
from inference.models import JourneyHolder
from inference.zone_counter import ZoneCounter


def _make_zone_counter(
    fusion_url: str = "http://fusion:8090",
    slip_height: float = 0.5,
    slip_velocity: float = 50.0,
) -> ZoneCounter:
    settings = Settings(
        slip_fall_height_collapse_threshold=slip_height,
        slip_fall_velocity_threshold=slip_velocity,
        fusion_url=fusion_url,
    )
    cameras = [
        {
            "camera_id": "C1_INT_01",
            "coach_id": "car-1",
            "zone": "interior",
            "capacity": 50,
            "seat_zones": [{"name": "z1", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}],
        }
    ]
    client = AsyncMock()
    jh = JourneyHolder(journey_id="OBB-T_001_20260519")
    return ZoneCounter(cameras=cameras, settings=settings, event_store_client=client, journey_holder=jh)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fall_detected_on_height_collapse_and_velocity() -> None:
    """Height collapses by >50% AND centroid moves >50px → slip_fall emitted to fusion."""
    zc = _make_zone_counter()

    # Standing: tall bbox
    prev_bbox = (100.0, 100.0, 200.0, 400.0)  # h = 300
    # Collapsed and centroid dropped: h = 100, cy moved from 250 → 400
    curr_bbox = (100.0, 350.0, 200.0, 450.0)  # h = 100

    posted: list[Any] = []

    async def mock_post_slip(car_id: str, track_id: int, camera_id: str) -> None:
        posted.append({"car_id": car_id, "track_id": track_id, "camera_id": camera_id})

    zc._post_slip_fall_candidate = mock_post_slip  # type: ignore[method-assign]

    # Seed previous bbox under the (car_id, camera_id) bucket
    zc._track_bboxes.setdefault(("car-1", "C1_INT_01"), {})[42] = prev_bbox  # type: ignore[attr-defined]

    detections: list[dict[str, Any]] = [
        {"track_id": 42, "label": "person", "bbox": curr_bbox}
    ]
    await zc._check_slip_fall("car-1", detections, camera_id="C1_INT_01")  # type: ignore[attr-defined]

    assert len(posted) == 1
    assert posted[0]["car_id"] == "car-1"
    assert posted[0]["track_id"] == 42
    assert posted[0]["camera_id"] == "C1_INT_01"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_fall_on_height_collapse_alone() -> None:
    """Height collapses but centroid velocity is low → no emit."""
    zc = _make_zone_counter()

    prev_bbox = (100.0, 100.0, 200.0, 400.0)  # h = 300
    # h=100 (collapse > 50%), cy=270, velocity = |250-270|=20 < 50 → no emit
    curr_bbox_low_vel = (100.0, 220.0, 200.0, 320.0)

    posted: list[Any] = []

    async def mock_post_slip(car_id: str, track_id: int, camera_id: str) -> None:
        posted.append(True)

    zc._post_slip_fall_candidate = mock_post_slip  # type: ignore[method-assign]
    zc._track_bboxes.setdefault(("car-1", "C1_INT_01"), {})[7] = prev_bbox  # type: ignore[attr-defined]

    await zc._check_slip_fall(
        "car-1",
        [{"track_id": 7, "label": "person", "bbox": curr_bbox_low_vel}],
        camera_id="C1_INT_01",
    )  # type: ignore[attr-defined]
    assert len(posted) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_fall_on_velocity_alone() -> None:
    """High centroid velocity but no height collapse → no emit."""
    zc = _make_zone_counter()

    prev_bbox = (100.0, 100.0, 200.0, 400.0)  # h = 300
    # h = 250 (only 17% collapse < 50%) but cy moved 200px
    curr_bbox = (100.0, 300.0, 200.0, 550.0)

    posted: list[Any] = []

    async def mock_post_slip(car_id: str, track_id: int, camera_id: str) -> None:
        posted.append(True)

    zc._post_slip_fall_candidate = mock_post_slip  # type: ignore[method-assign]
    zc._track_bboxes.setdefault(("car-1", "C1_INT_01"), {})[99] = prev_bbox  # type: ignore[attr-defined]

    await zc._check_slip_fall(
        "car-1",
        [{"track_id": 99, "label": "person", "bbox": curr_bbox}],
        camera_id="C1_INT_01",
    )  # type: ignore[attr-defined]
    assert len(posted) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_fall_on_first_frame() -> None:
    """First frame for a track_id has no previous bbox → no comparison, no emit."""
    zc = _make_zone_counter()
    curr_bbox = (100.0, 350.0, 200.0, 450.0)

    posted: list[Any] = []

    async def mock_post_slip(car_id: str, track_id: int, camera_id: str) -> None:
        posted.append(True)

    zc._post_slip_fall_candidate = mock_post_slip  # type: ignore[method-assign]

    await zc._check_slip_fall(
        "car-1",
        [{"track_id": 5, "label": "person", "bbox": curr_bbox}],
        camera_id="C1_INT_01",
    )  # type: ignore[attr-defined]
    assert len(posted) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bbox_updated_after_check() -> None:
    """After _check_slip_fall, the current bbox is stored for the next frame."""
    zc = _make_zone_counter()
    bbox = (10.0, 20.0, 30.0, 40.0)

    zc._track_bboxes = {}  # type: ignore[attr-defined]
    zc._post_slip_fall_candidate = AsyncMock()  # type: ignore[method-assign]

    await zc._check_slip_fall(
        "car-1",
        [{"track_id": 3, "label": "person", "bbox": bbox}],
        camera_id="C1_INT_01",
    )  # type: ignore[attr-defined]
    assert zc._track_bboxes[("car-1", "C1_INT_01")][3] == bbox  # type: ignore[attr-defined]
