"""Unit tests for main.py — camera loading, zone mask building, wire()."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder, ReadinessHolder


@pytest.fixture
def cameras_file(tmp_path: Path) -> Path:
    data = {
        "cameras": [
            {
                "camera_id": "C1_DOOR_01",
                "coach_id": "car-1",
                "rtsp_url": "rtsp://test/1",
                "zone": "door",
                "priority": "P1",
                "capacity": 200,
                "seat_zones": [
                    {"name": "zone-a", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}
                ],
            }
        ]
    }
    p = tmp_path / "cameras.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def empty_cameras_file(tmp_path: Path) -> Path:
    p = tmp_path / "cameras.json"
    p.write_text(json.dumps({"cameras": []}))
    return p


@pytest.mark.unit
def test_load_cameras(cameras_file: Path) -> None:
    from inference.main import _load_cameras

    cameras = _load_cameras(str(cameras_file))
    assert len(cameras) == 1
    assert cameras[0]["camera_id"] == "C1_DOOR_01"


@pytest.mark.unit
def test_load_cameras_empty_exits(empty_cameras_file: Path) -> None:
    from inference.main import _load_cameras

    with pytest.raises(SystemExit):
        _load_cameras(str(empty_cameras_file))


@pytest.mark.unit
def test_zone_masks_missing_seat_zones_exits() -> None:
    from inference.main import _zone_masks_for_camera

    cam = {"camera_id": "C1", "coach_id": "car-1", "seat_zones": []}
    with pytest.raises(SystemExit):
        _zone_masks_for_camera(cam)


@pytest.mark.unit
@pytest.mark.anyio
async def test_wire_returns_budget_callbacks_app(cameras_file: Path) -> None:
    from fastapi import FastAPI

    from inference.budget import Budget
    from inference.callback import OccupancyCallback
    from inference.main import _load_cameras, wire

    settings = Settings(cameras_json_path=str(cameras_file))
    cameras = _load_cameras(str(cameras_file))
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    async with httpx.AsyncClient() as client:
        budget, journey_holder, callbacks, app = wire(
            settings, cameras, client, readiness, loop_holder
        )

    assert isinstance(budget, Budget)
    assert isinstance(journey_holder, JourneyHolder)
    assert len(callbacks) == 1
    assert isinstance(callbacks[0], OccupancyCallback)
    assert isinstance(app, FastAPI)


@pytest.mark.unit
@pytest.mark.anyio
async def test_wire_one_callback_per_camera(tmp_path: Path) -> None:
    """Multi-camera config produces one OccupancyCallback per camera — no dict collapse."""
    from inference.main import wire

    data = {
        "cameras": [
            {
                "camera_id": "C1",
                "coach_id": "car-1",
                "priority": "P1",
                "capacity": 200,
                "seat_zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
            },
            {
                "camera_id": "C2",
                "coach_id": "car-2",
                "priority": "P1",
                "capacity": 200,
                "seat_zones": [{"name": "z", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}],
            },
        ]
    }
    p = tmp_path / "c.json"
    p.write_text(json.dumps(data))

    settings = Settings(cameras_json_path=str(p))
    cameras = data["cameras"]
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    async with httpx.AsyncClient() as client:
        _, _, callbacks, _ = wire(settings, cameras, client, readiness, loop_holder)

    assert len(callbacks) == 2
    assert {cb.camera_id for cb in callbacks} == {"C1", "C2"}


@pytest.mark.unit
def test_readiness_false_before_first_buffer(cameras_file: Path) -> None:
    """M6/M7: ReadinessHolder starts False after wire() — pipeline hasn't fired yet.

    In production, InferencePipeline._dispatch sets ready=True on the first buffer.
    This test verifies the bootstrap path doesn't pre-flip readiness.
    """
    import asyncio

    from inference.main import _load_cameras, wire

    settings = Settings(cameras_json_path=str(cameras_file))
    cameras = _load_cameras(str(cameras_file))
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    async def _run() -> None:
        async with httpx.AsyncClient() as client:
            wire(settings, cameras, client, readiness, loop_holder)

    asyncio.run(_run())
    assert readiness.ready is False, (
        "readiness must stay False until InferencePipeline._dispatch fires on first buffer"
    )


@pytest.mark.unit
def test_callback_stores_rtsp_url(cameras_file: Path) -> None:
    """M2/P-M16: OccupancyCallback stores _rtsp_url from cameras config so
    InferencePipeline can pass the real RTSP URI to GStreamer uridecodebin."""
    import asyncio

    from inference.main import _load_cameras, wire

    settings = Settings(cameras_json_path=str(cameras_file))
    cameras = _load_cameras(str(cameras_file))
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    async def _run() -> str:
        async with httpx.AsyncClient() as client:
            _, _, callbacks, _ = wire(settings, cameras, client, readiness, loop_holder)
            return callbacks[0]._rtsp_url

    url = asyncio.run(_run())
    assert url == "rtsp://test/1"
