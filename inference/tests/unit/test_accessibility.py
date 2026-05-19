"""Unit tests for bicycle → ACCESSIBILITY_DETECTED in OccupancyCallback.

RED phase: tests fail until accessibility detection is implemented in callback.py.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from inference.budget import Budget
from inference.callback import OccupancyCallback
from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder, ZoneMask
from inference.zone_counter import ZoneCounter


def _make_callback(
    camera_id: str = "C1_DOOR_01",
    coach_id: str = "car-1",
    zone: str = "door",
    door_camera_map: dict[str, list[str]] | None = None,
) -> OccupancyCallback:
    if door_camera_map is None:
        door_camera_map = {"door-1A": ["C1_DOOR_01"]}

    camera = {
        "camera_id": camera_id,
        "coach_id": coach_id,
        "zone": zone,
        "rtsp_url": "rtsp://fake",
        "priority": "P1",
        "seat_zones": [
            {"name": "zone-a", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}
        ],
    }
    cameras_json = {"cameras": [camera], "door_camera_map": door_camera_map}

    settings = Settings(
        accessibility_confidence_threshold=0.80,
        fusion_url="http://fusion:8090",
    )
    zone_masks = [ZoneMask(name="zone-a", polygon=[[0, 0], [640, 0], [640, 480], [0, 480]])]
    loop_holder = LoopHolder(loop=None)

    budget = MagicMock(spec=Budget)
    budget.should_process.return_value = True

    client = AsyncMock()
    jh = JourneyHolder(journey_id="OBB-T_001_20260519")
    cameras_list = [camera]
    zone_counter = ZoneCounter(
        cameras=cameras_list,
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
@pytest.mark.asyncio
async def test_bicycle_detection_emits_accessibility_event() -> None:
    """bicycle with confidence >= 0.80 in door zone → ACCESSIBILITY_DETECTED posted."""
    cb = _make_callback()

    posted: list[Any] = []

    async def mock_post(
        camera_id: str, track_id: str, confidence: float | None, car_id: str, zone: str
    ) -> None:
        posted.append({"camera_id": camera_id, "track_id": track_id, "car_id": car_id, "zone": zone})

    cb._post_accessibility_event = mock_post  # type: ignore[method-assign]

    await cb._dispatch_bicycle(
        camera_id="C1_DOOR_01",
        confidence=0.90,
        bbox=(10.0, 10.0, 200.0, 300.0),
    )

    assert len(posted) == 1
    p = posted[0]
    assert p["camera_id"] == "C1_DOOR_01"
    assert p["car_id"] == "car-1"
    assert p["zone"] == "door"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bicycle_below_confidence_threshold_suppressed() -> None:
    """bicycle with confidence < 0.80 → no emit."""
    cb = _make_callback()

    posted: list[Any] = []

    async def mock_post(
        camera_id: str, track_id: str, confidence: float | None, car_id: str, zone: str
    ) -> None:
        posted.append(True)

    cb._post_accessibility_event = mock_post  # type: ignore[method-assign]

    await cb._dispatch_bicycle(
        camera_id="C1_DOOR_01",
        confidence=0.70,
        bbox=(10.0, 10.0, 200.0, 300.0),
    )

    assert len(posted) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bicycle_unmapped_camera_skips_emit() -> None:
    """bicycle in camera not in door_camera_map → skip emit."""
    cb = _make_callback(camera_id="C1_INT_01", zone="interior", door_camera_map={})

    posted: list[Any] = []

    async def mock_post(
        camera_id: str, track_id: str, confidence: float | None, car_id: str, zone: str
    ) -> None:
        posted.append(True)

    cb._post_accessibility_event = mock_post  # type: ignore[method-assign]

    await cb._dispatch_bicycle(
        camera_id="C1_INT_01",
        confidence=0.95,
        bbox=(10.0, 10.0, 200.0, 300.0),
    )

    assert len(posted) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bicycle_none_confidence_still_emits() -> None:
    """bicycle with confidence=None (unavailable) passes threshold check and emits."""
    cb = _make_callback()

    posted: list[Any] = []

    async def mock_post(
        camera_id: str, track_id: str, confidence: float | None, car_id: str, zone: str
    ) -> None:
        posted.append(True)

    cb._post_accessibility_event = mock_post  # type: ignore[method-assign]

    await cb._dispatch_bicycle(
        camera_id="C1_DOOR_01",
        confidence=None,
        bbox=(10.0, 10.0, 200.0, 300.0),
    )

    assert len(posted) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_last_accessibility_track_updated() -> None:
    """After a bicycle detection, _last_accessibility_track stores the synthetic track_id."""
    cb = _make_callback()
    cb._post_accessibility_event = AsyncMock()  # type: ignore[method-assign]

    await cb._dispatch_bicycle(
        camera_id="C1_DOOR_01",
        confidence=0.85,
        bbox=(10.0, 10.0, 200.0, 300.0),
    )

    assert "C1_DOOR_01" in cb._last_accessibility_track
    assert cb._last_accessibility_track["C1_DOOR_01"].startswith("acc-")
