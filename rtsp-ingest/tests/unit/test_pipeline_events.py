"""Tests for pipeline.py — CAMERA_DEGRADED / CAMERA_RECOVERED event posting (mocked httpx)."""
from __future__ import annotations

import ast
import json
import pathlib

import httpx
import pytest
import respx

from rtsp_ingest.config import Settings
from rtsp_ingest.models import CameraConfig, Priority
from rtsp_ingest.pipeline import Pipeline
from rtsp_ingest.scheduler import Scheduler


def make_cameras() -> list[CameraConfig]:
    return [
        CameraConfig("C1_DOOR_01", "car-1", "rtsp://host/C1_DOOR_01", "door", Priority.P1),
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


@pytest.mark.anyio
async def test_degraded_posts_camera_degraded_event() -> None:
    """AC5: on_stream_degraded POSTs CAMERA_DEGRADED to event-store."""
    cameras = make_cameras()
    settings = make_settings()
    scheduler = Scheduler(cameras, settings)
    pipeline = Pipeline(
        cameras=cameras, scheduler=scheduler, event_store_url="http://event-store:8000"
    )

    with respx.mock:
        route = respx.post("http://event-store:8000/api/v1/events").mock(
            return_value=httpx.Response(201, json={"stored": True})
        )
        await pipeline.on_stream_degraded("C1_DOOR_01", reason="RTSP disconnect")

    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload["event_type"] == "CAMERA_DEGRADED"
    assert payload["payload"]["camera_id"] == "C1_DOOR_01"
    assert payload["payload"]["coach_id"] == "car-1"
    assert "reason" in payload["payload"]


@pytest.mark.anyio
async def test_recovered_posts_camera_recovered_event() -> None:
    """AC5: on_stream_recovered POSTs CAMERA_RECOVERED to event-store."""
    cameras = make_cameras()
    settings = make_settings()
    scheduler = Scheduler(cameras, settings)
    pipeline = Pipeline(
        cameras=cameras, scheduler=scheduler, event_store_url="http://event-store:8000"
    )

    with respx.mock:
        route = respx.post("http://event-store:8000/api/v1/events").mock(
            return_value=httpx.Response(201, json={"stored": True})
        )
        await pipeline.on_stream_recovered("C1_DOOR_01")

    assert route.called
    payload = json.loads(route.calls[0].request.content)
    assert payload["event_type"] == "CAMERA_RECOVERED"
    assert payload["payload"]["camera_id"] == "C1_DOOR_01"


def test_no_env_get_in_pipeline() -> None:
    """Rule 8: pipeline.py must not call os.environ.get()."""
    src = pathlib.Path("src/rtsp_ingest/pipeline.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    pytest.fail("pipeline.py calls os.environ.get() — Rule 8 violation")
