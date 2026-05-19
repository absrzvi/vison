"""Unit tests for main.py — camera loading, zone mask building, wiring."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from inference.config import Settings


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


@pytest.mark.unit
def test_load_cameras(cameras_file: Path) -> None:
    from inference.main import _load_cameras

    cameras = _load_cameras(str(cameras_file))
    assert len(cameras) == 1
    assert cameras[0]["camera_id"] == "C1_DOOR_01"


@pytest.mark.unit
def test_build_zone_masks(cameras_file: Path) -> None:
    from inference.main import _build_zone_masks, _load_cameras

    cameras = _load_cameras(str(cameras_file))
    masks = _build_zone_masks(cameras)
    assert "car-1" in masks
    assert masks["car-1"][0].name == "zone-a"


@pytest.mark.unit
def test_build_zone_masks_missing_seat_zones_exits(tmp_path: Path) -> None:
    from inference.main import _build_zone_masks

    cameras = [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "seat_zones": [],
        }
    ]
    with pytest.raises(SystemExit):
        _build_zone_masks(cameras)  # type: ignore[arg-type]


@pytest.mark.unit
def test_wire_returns_budget_callback_app(cameras_file: Path) -> None:
    from inference.main import _load_cameras, wire

    settings = Settings(cameras_json_path=str(cameras_file))
    cameras = _load_cameras(str(cameras_file))
    budget, callback, app = wire(settings, cameras, pipeline_ready=True)
    from fastapi import FastAPI

    from inference.budget import Budget
    from inference.callback import OccupancyCallback

    assert isinstance(budget, Budget)
    assert isinstance(callback, OccupancyCallback)
    assert isinstance(app, FastAPI)
