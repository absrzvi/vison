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

    M1/M12 fix: this is now called ONCE, inside lifespan, where the running loop and
    real httpx client both exist. The bootstrap path (before lifespan) only creates
    the bare FastAPI app shell and the shared holders; no ZoneCounter or httpx client
    is built until the asyncio loop is up.
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


def _make_pipeline_thread(
    callback: OccupancyCallback,
    settings: Settings,
    readiness: ReadinessHolder,
) -> threading.Thread:
    """Return a daemon thread that runs one InferencePipeline.

    M6/M7 fix: readiness is set True only when the pipeline thread signals it on first
    successful buffer (via the ReadinessHolder), NOT immediately after t.start(). On
    pipeline crash the thread wraps pipeline.run() in try/except and flips ready→False.
    """
    from inference.pipeline import InferencePipeline  # noqa: PLC0415

    pipeline = InferencePipeline(callback=callback, settings=settings, readiness=readiness)

    def _run() -> None:
        try:
            pipeline.run()
        except Exception as exc:
            log.critical(
                "main.pipeline_crashed",
                camera_id=callback.camera_id,
                error=str(exc),
            )
        finally:
            readiness.ready = False
            log.warning("main.pipeline_exited", camera_id=callback.camera_id)

    return threading.Thread(target=_run, name=f"gst-{callback.camera_id}", daemon=True)


def main() -> None:  # pragma: no cover — integration entry point
    settings = Settings()
    cameras = _load_cameras(settings.cameras_json_path)
    readiness = ReadinessHolder(ready=False)
    loop_holder = LoopHolder(loop=None)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop_holder.loop = asyncio.get_running_loop()
        async with httpx.AsyncClient(timeout=5.0) as client:
            # M1 fix: single wire() call here, where the running loop and real httpx
            # client both exist. Bootstrap below constructs only the app shell.
            budget, journey_holder, callbacks, wired_app = wire(
                settings, cameras, client, readiness, loop_holder
            )
            # Swap the health/context routes into the already-created app object so
            # uvicorn's reference stays valid.
            app.router.routes = wired_app.router.routes
            app.state.event_client = client
            app.state.callbacks = callbacks

            threads = [
                _make_pipeline_thread(cb, settings, readiness) for cb in callbacks
            ]
            for t in threads:
                t.start()

            log.info("main.pipeline_threads_started", count=len(threads))
            try:
                yield
            finally:
                readiness.ready = False
                loop_holder.loop = None

    # M12 fix: bootstrap builds only the bare app shell (ReadinessHolder + placeholder
    # budget/journey). No ZoneCounter or httpx.AsyncClient is constructed here.
    # lifespan replaces the routes once the real loop is running.
    _bootstrap_budget = Budget(settings=settings)
    _bootstrap_journey = JourneyHolder(journey_id=settings.journey_id)
    app = build_app(
        readiness=readiness,
        budget=_bootstrap_budget,
        journey_holder=_bootstrap_journey,
    )
    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=settings.context_push_port)


if __name__ == "__main__":  # pragma: no cover
    main()
