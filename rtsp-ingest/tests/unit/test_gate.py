"""Tests for gate.py — P3 station window activation and door-release P1 override."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from rtsp_ingest.config import Settings
from rtsp_ingest.gate import Gate
from rtsp_ingest.models import CameraConfig, Priority
from rtsp_ingest.scheduler import Scheduler


def make_cameras() -> list[CameraConfig]:
    return [
        CameraConfig("C1_DOOR_01", "car-1", "rtsp://host/C1_DOOR_01", "door", Priority.P1),
        CameraConfig("C1_INT_01", "car-1", "rtsp://host/C1_INT_01", "interior", Priority.P2),
        CameraConfig("C1_EXT_01", "car-1", "rtsp://host/C1_EXT_01", "exterior", Priority.P3),
    ]


def make_settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        cameras_json_path="cameras.json",
        tops_budget_pct_threshold=0.90,
        tops_total=26.0,
        p1_fps=10.0,
        p2_fps=5.0,
        p2_throttled_fps=2.0,
        p3_fps=8.0,
        station_speed_threshold_kmh=20.0,
        door_release_override_s=120.0,
        event_store_url="http://event-store:8000",
        context_push_port=8080,
    )


def make_door_camera_map() -> dict[str, list[str]]:
    return {"door-1A": ["C1_DOOR_01"], "door-1B": ["C1_EXT_01"]}


@pytest.fixture
def gate() -> Gate:
    cameras = make_cameras()
    settings = make_settings()
    scheduler = Scheduler(cameras, settings)
    return Gate(
        cameras=cameras,
        scheduler=scheduler,
        settings=settings,
        door_camera_map=make_door_camera_map(),
    )


def test_p3_activated_when_speed_low_and_station_set(gate: Gate) -> None:
    """AC4: speed=15, next_station='Wien Hbf' → gate_p3(True) called once (transition False→True)."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        gate.on_context_update({"speed_kmh": 15.0, "next_station": "Wien Hbf"})
        mock_gate.assert_called_once_with(True)


def test_p3_deactivated_when_speed_high(gate: Gate) -> None:
    """AC4: speed=80, default state is inactive → gate_p3 not called (False→False, no transition)."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        gate.on_context_update({"speed_kmh": 80.0, "next_station": "Wien Hbf"})
        mock_gate.assert_not_called()


def test_p3_deactivated_on_speed_recovery(gate: Gate) -> None:
    """AC4: activate then speed rises → gate_p3(False) called on transition."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        gate.on_context_update({"speed_kmh": 15.0, "next_station": "Wien Hbf"})
        gate.on_context_update({"speed_kmh": 80.0, "next_station": "Wien Hbf"})
        assert mock_gate.call_count == 2
        mock_gate.assert_called_with(False)


def test_p3_idempotent_on_repeated_ticks(gate: Gate) -> None:
    """Edge: same active condition repeated → gate_p3 called only once (no redundant calls)."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        for _ in range(5):
            gate.on_context_update({"speed_kmh": 15.0, "next_station": "Wien Hbf"})
        mock_gate.assert_called_once_with(True)


def test_p3_not_activated_when_speed_low_but_no_station(gate: Gate) -> None:
    """AC4: speed=10, next_station=None → gate_p3 not called (remains inactive)."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        gate.on_context_update({"speed_kmh": 10.0, "next_station": None})
        mock_gate.assert_not_called()


def test_p3_not_activated_when_no_speed_key(gate: Gate) -> None:
    """Edge: missing speed_kmh key → gate_p3 not called (remains inactive)."""
    with patch.object(gate._scheduler, "gate_p3") as mock_gate:
        gate.on_context_update({"next_station": "Wien Hbf"})
        mock_gate.assert_not_called()


def test_door_release_overrides_camera_to_p1(gate: Gate) -> None:
    """AC6: door_release → override_to_p1 called with correct camera_ids, duration=120."""
    with patch.object(gate._scheduler, "override_to_p1") as mock_override:
        gate.on_door_release(car_id="car-1", door_id="door-1A")
        mock_override.assert_called_once_with(["C1_DOOR_01"], 120.0)


def test_door_release_unknown_door_id_no_error(gate: Gate) -> None:
    """Edge: unknown door_id → no exception, no override_to_p1 call."""
    with patch.object(gate._scheduler, "override_to_p1") as mock_override:
        gate.on_door_release(car_id="car-1", door_id="door-UNKNOWN")
        mock_override.assert_not_called()


def test_door_release_stream_priority_not_posted_to_event_store(gate: Gate) -> None:
    """ADR-18: on_door_release must not make any HTTP call."""
    with patch("httpx.AsyncClient") as mock_client:
        gate.on_door_release(car_id="car-1", door_id="door-1A")
        mock_client.assert_not_called()


def test_p3_activation_within_500ms(gate: Gate) -> None:
    """AC4: Time from on_context_update to gate_p3 call < 0.5s."""
    calls: list[float] = []

    def timed_gate_p3(active: bool) -> None:
        calls.append(time.perf_counter())

    gate._scheduler.gate_p3 = timed_gate_p3  # type: ignore[method-assign]
    start = time.perf_counter()
    gate.on_context_update({"speed_kmh": 15.0, "next_station": "Wien Hbf"})
    assert calls, "gate_p3 was never called"
    elapsed = calls[0] - start
    assert elapsed < 0.5, f"gate_p3 called after {elapsed:.3f}s — must be < 0.5s"
