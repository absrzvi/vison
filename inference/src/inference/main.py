"""Entry point for the inference container.

Loads config, cameras, zone masks; wires OccupancyCallback, ZoneCounter, Budget;
starts uvicorn on 127.0.0.1:8081 (loopback — same as rtsp-ingest).
No os.environ.get() — all config via pydantic-settings.
"""
from __future__ import annotations

import json
import sys

from typing import Any

import httpx
import structlog
import uvicorn
from fastapi import FastAPI

from inference.budget import Budget
from inference.callback import OccupancyCallback
from inference.config import Settings
from inference.health import build_app
from inference.models import ZoneMask
from inference.zone_counter import ZoneCounter

log = structlog.get_logger(__name__)


def _load_cameras(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return list(data["cameras"])


def _build_zone_masks(cameras: list[dict[str, Any]]) -> dict[str, list[ZoneMask]]:
    masks: dict[str, list[ZoneMask]] = {}
    for cam in cameras:
        car_id = str(cam["coach_id"])
        seat_zones = cam.get("seat_zones", [])
        if not seat_zones:
            log.critical("main.missing_seat_zones", camera_id=cam["camera_id"], car_id=car_id)
            sys.exit(1)
        masks.setdefault(car_id, [])
        for sz in seat_zones:
            masks[car_id].append(ZoneMask(name=str(sz["name"]), polygon=list(sz["polygon"])))
    return masks


def wire(
    settings: Settings,
    cameras: list[dict[str, Any]],
    pipeline_ready: bool = True,
) -> tuple[Budget, OccupancyCallback, FastAPI]:
    """Wire all components together. Returns (budget, callback, FastAPI app).

    Separated from main() so unit tests can call wire() without importing pipeline.py.
    """
    zone_masks = _build_zone_masks(cameras)
    event_client = httpx.AsyncClient(timeout=5.0)
    zone_counter = ZoneCounter(cameras=cameras, settings=settings, event_store_client=event_client)
    budget = Budget(settings=settings)
    callback = OccupancyCallback(
        cameras=cameras,
        zone_masks=zone_masks,
        zone_counter=zone_counter,
        budget=budget,
        settings=settings,
    )
    app = build_app(pipeline_ready=pipeline_ready, budget=budget)
    return budget, callback, app


def main() -> None:
    settings = Settings()
    cameras = _load_cameras(settings.cameras_json_path)
    budget, callback, app = wire(settings, cameras)

    # pipeline.py is excluded from unit coverage and only imported here
    from inference.pipeline import InferencePipeline  # noqa: PLC0415

    InferencePipeline(callback=callback, settings=settings)

    uvicorn.run(app, host="127.0.0.1", port=settings.context_push_port)


if __name__ == "__main__":
    main()
