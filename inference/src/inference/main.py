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
from inference.heartbeat import HeartbeatEmitter
from inference.model_provenance import compute_model_versions
from inference.models import JourneyHolder, LoopHolder, ReadinessHolder, ZoneMask
from inference.safety import SafetyHandler
from inference.tripwire import TripwireHandler
from inference.zone_counter import ZoneCounter

log = structlog.get_logger(__name__)


def _load_cameras(path: str) -> list[dict[str, Any]]:
    return _load_cameras_data(path)[0]


def _load_cameras_data(path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cameras = list(data["cameras"])
    if not cameras:
        log.critical("main.no_cameras_configured", path=path)
        sys.exit(1)
    return cameras, data


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
    readiness: list[ReadinessHolder],
    loop_holder: LoopHolder,
    journey_holder: JourneyHolder | None = None,
    cameras_json: dict[str, Any] | None = None,
    model_versions: dict[str, str] | None = None,
    heartbeat: HeartbeatEmitter | None = None,
) -> tuple[Budget, JourneyHolder, list[OccupancyCallback], FastAPI]:
    """Wire components together. One OccupancyCallback and one ReadinessHolder per camera.

    Returns (budget, journey_holder, [callbacks...], FastAPI app). pipeline.py is
    imported only by main(), not by wire() — so unit tests can call wire() without
    TAPPAS installed.

    F2 decision: readiness is a list of per-camera holders. health.py aggregates them.
    M1/M12 fix: called ONCE inside lifespan where the running loop and real httpx
    client both exist.
    """
    journey_holder = journey_holder or JourneyHolder(journey_id=settings.journey_id)
    zone_counter = ZoneCounter(
        cameras=cameras,
        settings=settings,
        event_store_client=event_client,
        journey_holder=journey_holder,
        model_versions=model_versions,
    )
    safety_handler = SafetyHandler(
        settings=settings,
        event_store_client=event_client,
        journey_holder=journey_holder,
    )
    budget = Budget(settings=settings)

    _GANGWAY_ZONES = ("gangway-fwd", "gangway-aft")

    callbacks: list[OccupancyCallback] = []
    for cam, cam_readiness in zip(cameras, readiness, strict=True):
        zone_masks = _zone_masks_for_camera(cam)

        # E4-S8: construct TripwireHandler for gangway cameras; validate all required fields.
        tripwire_handler: TripwireHandler | None = None
        cam_zone = str(cam.get("zone", ""))
        if cam_zone in _GANGWAY_ZONES:
            missing: list[str] = []
            if not cam.get("tripwire") or "tripwire_polygon" not in cam.get("tripwire", {}):
                missing.append("tripwire.tripwire_polygon")
            for req in ("coach_from", "coach_to", "direction_axis"):
                if not cam.get(req):
                    missing.append(req)
            if missing:
                log.critical(
                    "main.missing_tripwire_config",
                    camera_id=cam.get("camera_id"),
                    zone=cam_zone,
                    missing=missing,
                )
                sys.exit(1)
            tripwire_handler = TripwireHandler(
                camera=cam,
                settings=settings,
                event_store_client=event_client,
                loop_holder=loop_holder,
                journey_holder=journey_holder,
            )

        callbacks.append(
            OccupancyCallback(
                camera=cam,
                zone_masks=zone_masks,
                zone_counter=zone_counter,
                budget=budget,
                settings=settings,
                loop_holder=loop_holder,
                readiness=cam_readiness,
                cameras_json=cameras_json,
                event_store_client=event_client,
                safety_handler=safety_handler,
                tripwire_handler=tripwire_handler,
                model_versions=model_versions,
                heartbeat=heartbeat,
            )
        )

    app = build_app(
        readiness=readiness,
        budget=budget,
        journey_holder=journey_holder,
        safety_handler=safety_handler,
        loop_holder=loop_holder,
    )
    return budget, journey_holder, callbacks, app


def _log_heartbeat_task_exit(task: "asyncio.Task[None]") -> None:
    """Surface a heartbeat-loop crash. The loop swallows per-emit failures, so the
    only way it ends is cancellation (clean shutdown) or an unexpected escape —
    the latter must not vanish into an unobserved task exception."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:  # pragma: no cover — defensive; emit_once catches everything
        log.critical("main.heartbeat_loop_crashed", error=str(exc))


def _make_pipeline_thread(
    callback: OccupancyCallback,
    settings: Settings,
    readiness: ReadinessHolder,
) -> threading.Thread:
    """Return a daemon thread that runs one InferencePipeline.

    M6/M7 fix: readiness is set True only when the pipeline thread signals it on first
    successful buffer (via callback._readiness), NOT immediately after t.start(). On
    pipeline crash the thread wrapper flips ready→False.

    F2: readiness is the per-camera holder passed through here only for the finally
    flip; InferencePipeline reads it from callback._readiness directly.
    """
    from inference.pipeline import InferencePipeline  # noqa: PLC0415

    pipeline = InferencePipeline(callback=callback, settings=settings)

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
    # E10-S1 AC5/AC6: provenance computed once at startup; failure is fatal.
    model_versions = compute_model_versions(settings)
    log.info(
        "inference.model_provenance",
        **model_versions,
        hef_bottleneck_fps=settings.pipeline_fps,
    )
    cameras, cameras_json = _load_cameras_data(settings.cameras_json_path)
    # F2 decision: one ReadinessHolder per camera; health.py aggregates.
    cam_readiness = [
        ReadinessHolder(camera_id=str(cam["camera_id"]), ready=False) for cam in cameras
    ]
    loop_holder = LoopHolder(loop=None)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        loop_holder.loop = asyncio.get_running_loop()
        async with httpx.AsyncClient(timeout=5.0) as client:
            # M1 fix: single wire() call here, where the running loop and real httpx
            # client both exist. Bootstrap below constructs only the app shell.
            # E10-S1 AC7: heartbeat loop, independent of detections. The shared
            # JourneyHolder is created here so heartbeat and wire() see the same one.
            journey_holder = JourneyHolder(journey_id=settings.journey_id)
            heartbeat = HeartbeatEmitter(
                settings=settings,
                client=client,
                journey_holder=journey_holder,
                model_versions=model_versions,
                readiness=cam_readiness,
            )
            budget, journey_holder, callbacks, wired_app = wire(
                settings, cameras, client, cam_readiness, loop_holder,
                journey_holder=journey_holder,
                cameras_json=cameras_json,
                model_versions=model_versions,
                heartbeat=heartbeat,
            )
            heartbeat_task = asyncio.create_task(heartbeat.run())
            heartbeat_task.add_done_callback(_log_heartbeat_task_exit)
            # Patch E: append routes into the already-created app so uvicorn's reference
            # stays valid. include_router only works before app startup; route list append
            # is the safe runtime alternative.
            for route in wired_app.routes:
                app.router.routes.append(route)
            app.state.event_client = client
            app.state.callbacks = callbacks

            threads = [
                _make_pipeline_thread(cb, settings, r)
                for cb, r in zip(callbacks, cam_readiness, strict=True)
            ]
            for t in threads:
                t.start()

            log.info("main.pipeline_threads_started", count=len(threads))
            try:
                yield
            finally:
                heartbeat_task.cancel()
                for r in cam_readiness:
                    r.ready = False
                loop_holder.loop = None

    # M12 fix: bootstrap builds only the bare app shell. No ZoneCounter or httpx client
    # constructed here. lifespan replaces the routes once the real loop is running.
    _bootstrap_budget = Budget(settings=settings)
    _bootstrap_journey = JourneyHolder(journey_id=settings.journey_id)
    app = build_app(
        readiness=cam_readiness,
        budget=_bootstrap_budget,
        journey_holder=_bootstrap_journey,
    )
    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="0.0.0.0", port=settings.context_push_port)


if __name__ == "__main__":  # pragma: no cover
    main()
