from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .gate import Gate
from .health import build_app
from .models import load_cameras
from .pipeline import Pipeline
from .scheduler import Scheduler

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

_cameras = load_cameras(settings.cameras_json_path)

# Load door_camera_map from cameras.json alongside the cameras list
_raw = json.loads(__import__("pathlib").Path(settings.cameras_json_path).read_text())
_door_camera_map: dict[str, list[str]] = (
    _raw.get("door_camera_map", {}) if isinstance(_raw, dict) else {}
)

_scheduler = Scheduler(_cameras, settings)
_gate = Gate(
    cameras=_cameras,
    scheduler=_scheduler,
    settings=settings,
    door_camera_map=_door_camera_map,
)
_pipeline = Pipeline(
    cameras=_cameras,
    scheduler=_scheduler,
    event_store_url=settings.event_store_url,
)

_bg_tasks: list[asyncio.Task[None]] = []

app: FastAPI = build_app(scheduler=_scheduler, gate=_gate)


@asynccontextmanager
async def _lifespan(a: FastAPI) -> AsyncIterator[None]:
    log.info("rtsp_ingest_started")
    try:
        yield
    finally:
        for task in _bg_tasks:
            task.cancel()
        await asyncio.gather(*_bg_tasks, return_exceptions=True)
        await _pipeline.aclose()
        log.info("rtsp_ingest_stopped")


app.router.lifespan_context = _lifespan

if __name__ == "__main__":
    uvicorn.run(
        "rtsp_ingest.main:app", host="0.0.0.0", port=settings.context_push_port, reload=False
    )
