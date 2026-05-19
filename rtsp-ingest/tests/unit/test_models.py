"""Tests for models.py — CameraConfig, CameraState, Priority enum, load_cameras."""
from __future__ import annotations

import json
import pathlib

import pytest

from rtsp_ingest.models import CameraState, Priority, load_cameras


def test_priority_enum_values() -> None:
    assert Priority.P1.value == "P1"
    assert Priority.P2.value == "P2"
    assert Priority.P3.value == "P3"


def test_load_cameras_valid_json(tmp_path: pathlib.Path) -> None:
    data = {
        "cameras": [
            {
                "camera_id": "C1", "coach_id": "car-1",
                "rtsp_url": "rtsp://h/C1", "zone": "door", "priority": "P1",
            },
            {
                "camera_id": "C2", "coach_id": "car-1",
                "rtsp_url": "rtsp://h/C2", "zone": "interior", "priority": "P2",
            },
        ],
        "door_camera_map": {"door-1A": ["C1"]},
    }
    f = tmp_path / "cameras.json"
    f.write_text(json.dumps(data))
    cameras = load_cameras(str(f))
    assert len(cameras) == 2
    assert cameras[0].camera_id == "C1"
    assert cameras[0].priority == Priority.P1
    assert cameras[1].priority == Priority.P2


def test_load_cameras_missing_field_raises(tmp_path: pathlib.Path) -> None:
    data = {"cameras": [{"camera_id": "C1", "coach_id": "car-1"}]}
    f = tmp_path / "cameras.json"
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing required field"):
        load_cameras(str(f))


def test_load_cameras_empty_list(tmp_path: pathlib.Path) -> None:
    data = {"cameras": [], "door_camera_map": {}}
    f = tmp_path / "cameras.json"
    f.write_text(json.dumps(data))
    cameras = load_cameras(str(f))
    assert cameras == []


def test_camera_state_defaults() -> None:
    state = CameraState(camera_id="C1")
    assert state.active is True
    assert state.current_fps == 0.0
    assert state.override_until is None
