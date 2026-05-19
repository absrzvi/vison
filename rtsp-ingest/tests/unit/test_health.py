"""Tests for health.py — readiness endpoint and context dispatch."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from rtsp_ingest import health
from rtsp_ingest.config import Settings
from rtsp_ingest.gate import Gate
from rtsp_ingest.models import CameraConfig, Priority
from rtsp_ingest.scheduler import Scheduler


def make_cameras(with_p1: bool = True) -> list[CameraConfig]:
    cameras: list[CameraConfig] = [
        CameraConfig("C1_INT_01", "car-1", "rtsp://host/C1_INT_01", "interior", Priority.P2),
        CameraConfig("C1_EXT_01", "car-1", "rtsp://host/C1_EXT_01", "exterior", Priority.P3),
    ]
    if with_p1:
        cameras.insert(
            0,
            CameraConfig("C1_DOOR_01", "car-1", "rtsp://host/C1_DOOR_01", "door", Priority.P1),
        )
    return cameras


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


def make_gate(cameras: list[CameraConfig]) -> Gate:
    settings = make_settings()
    scheduler = Scheduler(cameras, settings)
    return Gate(
        cameras=cameras,
        scheduler=scheduler,
        settings=settings,
        door_camera_map={"door-1A": ["C1_DOOR_01"]},
    )


def make_client(cameras: list[CameraConfig]) -> TestClient:
    gate = make_gate(cameras)
    scheduler = gate._scheduler
    app = health.build_app(scheduler=scheduler, gate=gate)
    return TestClient(app)


def test_ready_returns_200_when_p1_active() -> None:
    client = make_client(make_cameras(with_p1=True))
    resp = client.get("/health/ready")
    assert resp.status_code == 200


def test_ready_returns_503_when_no_p1_active() -> None:
    client = make_client(make_cameras(with_p1=False))
    resp = client.get("/health/ready")
    assert resp.status_code == 503


def test_live_always_returns_200() -> None:
    client = make_client(make_cameras())
    resp = client.get("/health/live")
    assert resp.status_code == 200


def test_context_post_dispatches_to_gate() -> None:
    cameras = make_cameras()
    gate = make_gate(cameras)
    scheduler = gate._scheduler

    with patch.object(gate, "on_context_update") as mock_update:
        app = health.build_app(scheduler=scheduler, gate=gate)
        client = TestClient(app)
        resp = client.post("/context", json={"speed_kmh": 15.0, "next_station": "Wien Hbf"})
        assert resp.status_code == 200
        mock_update.assert_called_once_with({"speed_kmh": 15.0, "next_station": "Wien Hbf"})


def test_context_post_door_release_dispatches_to_gate() -> None:
    cameras = make_cameras()
    gate = make_gate(cameras)
    scheduler = gate._scheduler

    with patch.object(gate, "on_door_release") as mock_release:
        app = health.build_app(scheduler=scheduler, gate=gate)
        client = TestClient(app)
        resp = client.post(
            "/context",
            json={"event": "door_release", "car_id": "car-1", "door_id": "door-1A"},
        )
        assert resp.status_code == 200
        mock_release.assert_called_once_with(car_id="car-1", door_id="door-1A")


def test_context_post_malformed_payload_returns_422() -> None:
    """Security: POST /context with invalid JSON returns 422."""
    cameras = make_cameras()
    gate = make_gate(cameras)
    scheduler = gate._scheduler
    app = health.build_app(scheduler=scheduler, gate=gate)
    client = TestClient(app)
    resp = client.post(
        "/context",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422
