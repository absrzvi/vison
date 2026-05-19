"""Security tests — Rule 8 (no os.environ.get) and ADR-18 (STREAM_PRIORITY internal)."""
from __future__ import annotations

import ast
import pathlib

import pytest

SRC = pathlib.Path("src/rtsp_ingest")


def _has_env_get(filename: str) -> bool:
    src = (SRC / filename).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    return True
    return False


def test_no_env_get_in_scheduler() -> None:
    assert not _has_env_get("scheduler.py"), "scheduler.py calls os.environ.get() — Rule 8"


def test_no_env_get_in_gate() -> None:
    assert not _has_env_get("gate.py"), "gate.py calls os.environ.get() — Rule 8"


def test_no_env_get_in_config() -> None:
    assert not _has_env_get("config.py"), "config.py calls os.environ.get() — Rule 8"


def test_no_env_get_in_pipeline() -> None:
    assert not _has_env_get("pipeline.py"), "pipeline.py calls os.environ.get() — Rule 8"


def test_stream_priority_not_posted_to_event_store() -> None:
    """ADR-18: STREAM_PRIORITY must not appear in any event-store POST in gate.py."""
    src = (SRC / "gate.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "httpx", "gate.py imports httpx — must not POST to event-store"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "httpx", "gate.py imports httpx — must not POST"


def test_stream_priority_not_logged_as_event() -> None:
    """ADR-18: gate.py must not contain .post()/.request() calls."""
    src = (SRC / "gate.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("post", "request"):
                pytest.fail("gate.py contains a .post()/.request() call — ADR-18 violation")


def test_context_post_malformed_payload_returns_422() -> None:
    """POST /context with invalid JSON returns 422 — validated in test_health.py::test_context_malformed_returns_422."""
    from fastapi.testclient import TestClient
    from unittest.mock import MagicMock
    from rtsp_ingest.health import build_app
    from rtsp_ingest.models import CameraConfig, Priority
    from rtsp_ingest.scheduler import Scheduler
    from rtsp_ingest.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    cameras = [CameraConfig("C1", "car-1", "rtsp://h/s", "door", Priority.P1)]
    sched = Scheduler(cameras, settings)
    gate = MagicMock()
    pipeline = MagicMock()
    app = build_app(sched, gate, pipeline)
    client = TestClient(app)
    r = client.post("/context", content=b"not-json", headers={"content-type": "application/json"})
    assert r.status_code == 422
