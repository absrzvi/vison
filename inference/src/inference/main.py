"""Entry point for the inference container.

Loads config, cameras, zone masks; wires OccupancyCallback(s), ZoneCounter, Budget;
runs the GStreamer pipeline on a background thread and uvicorn on the main asyncio loop.

No os.environ.get() — all config via pydantic-settings.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
import structlog
import uvicorn
from fastapi import FastAPI

from inference.budget import Budget
from inference.callback import OccupancyCallback
from inference.config import Settings
from inference.health import build_app
from inference.models import JourneyHolder, LoopHolder, ReadinessHolder, ZoneMask
from inference.zone_counter import ZoneCounter

log = structlog.get_logger(__name__)


def _load_cameras(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cameras = list(data["cameras"])
    if not cameras:
        log.critical("main.no_cameras_configured", path=path)
        sys.exit(1)
    return cameras


def _zone_masks_for_camera(camera: dict[str, Any]) -> list[ZoneMask]:
    seat_zones = camera.get("seat_zones", [])
    if not seat_zones:
        log.critical(
            "main.missing_seat_zones",
            camera_id=camera.get("camera_id"),
            car_id=camera.get("coach_id"),
        )
        sys.exit(1)
    return [
        ZoneMask(name=str(sz["name"]), polygon=[list(p) for p in sz["polygon"]])
        for sz in seat_zones
    ]


def wire(
    settings: Settings,
    cameras: list[dict[str, Any]],
    event_client: httpx.AsyncClient,
    readiness: ReadinessHolder,
    loop_holder: LoopHolder,
    journey_holder: JourneyHolder | None = None,
) -> tuple[Budget, JourneyHolder, list[OccupancyCallback], FastAPI]:
    """Wire components together. One OccupancyCallback per camera.

    Returns (budget, journey_holder, [callbacks...], FastAPI app). pipeline.py is
    imported only by main(), not by wire() — so unit tests can call wire() without
    TAPPAS installed.

    NOTE: P-M16 / M1 still pending hardware day — main.py currently calls wire()
    twice (bootstrap + lifespan) which constructs two Budget/JourneyHolder/ZoneCounter
    instances. The HTTP layer in the bootstrap app points at the bootstrap Budget;
    streaming threads point at the lifespan one. This will be fixed when P-M16
    rewrites the deploy topology.
    """
    journey_holder = journey_holder or JourneyHolder(journey_id=settings.journey_id)
    zone_counter = ZoneCounter(
        cameras=cameras,
        settings=settings,
        event_store_client=event_client,
        journey_holder=journey_holder,
    )
    budget = Budget(settings=settings)

    callbacks: list[OccupancyCallback] = []
    for cam in cameras:
        zone_masks = _zone_masks_for_camera(cam)
        callbacks.append(
            OccupancyCallback(
                camera=cam,
                zone_masks=zone_masks,
                zone_counter=zone_counter,
                budget=budget,
                settings=settings,
                loop_holder=loop_holder,
            )
        )

    app = build_app(readiness=readiness, budget=budget, journey_holder=journey_holder)
    return budget, journey_holder, callbacks, app


def main() -> None:  # pragma: no cover — integration entry point
    settings = Settings()
    cameras = _load_cameras(settings.cameras_json_path)
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop_holder.loop = asyncio.get_running_loop()
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Rewire with the real client now that the loop is up.
            _, _, callbacks, _ = wire(settings, cameras, client, readiness, loop_holder)
            app.state.event_client = client
            app.state.callbacks = callbacks

            from inference.pipeline import InferencePipeline  # noqa: PLC0415

            for cb in callbacks:
                pipeline = InferencePipeline(callback=cb, settings=settings)
                t = threading.Thread(
                    target=pipeline.run, name=f"gst-{cb.camera_id}", daemon=True
                )
                t.start()

            readiness.ready = True
            log.info("main.pipelines_started", count=len(callbacks))
            try:
                yield
            finally:
                readiness.ready = False
                loop_holder.loop = None

    # FastAPI needs an app object before the loop runs. The httpx client and callbacks
    # built here are throwaway — lifespan rebuilds them with the real loop. We discard
    # the app produced by this wire() call and build a clean one wired only with the
    # readiness/budget the lifespan needs to expose health endpoints.
    bootstrap_client = httpx.AsyncClient(timeout=5.0)
    try:
        _, _, _, app = wire(settings, cameras, bootstrap_client, readiness, loop_holder)
    finally:
        asyncio.run(bootstrap_client.aclose())

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=settings.context_push_port)


if __name__ == "__main__":  # pragma: no cover
    main()
