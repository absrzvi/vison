"""FastAPI health and context-push endpoints for the inference container."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool

from inference.budget import Budget
from inference.models import JourneyHolder, LoopHolder, ReadinessHolder

if TYPE_CHECKING:
    from inference.safety import SafetyHandler

log = structlog.get_logger(__name__)


def _on_post_done(future: Future[Any]) -> None:
    """Surface exceptions from scheduled async POSTs so failures aren't silent (R8)."""
    exc = future.exception()
    if exc is not None:
        log.warning("health.scheduled_post_failed", error=str(exc))


class ContextPushModel(BaseModel):
    """Schema for POST /context — strict bool so truthiness can't flip throttle."""

    model_config = ConfigDict(strict=True)

    p2_throttled: StrictBool = False
    journey_id: str | None = None
    ramp_deployed: StrictBool = False
    ramp_door_id: str | None = None
    ramp_station_id: str | None = None


def build_app(
    readiness: list[ReadinessHolder],
    budget: Budget,
    journey_holder: JourneyHolder,
    safety_handler: SafetyHandler | None = None,
    loop_holder: LoopHolder | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    readiness is a list of per-camera ReadinessHolders (F2 decision). Aggregation:
      - all ready   → status "ready",    HTTP 200
      - some ready  → status "degraded", HTTP 200
      - none ready  → status "not_ready", HTTP 503

    journey_holder is mutated when /context push carries a new journey_id (M13).

    loop_holder, when provided, lets the sync POST /context handler schedule
    safety_handler.on_ramp_deployed onto the FastAPI/asyncio loop via the
    canonical run_coroutine_threadsafe + add_done_callback path (F7/R9 fix).
    """
    app = FastAPI(title="inference-health")

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        cameras = [{"camera_id": h.camera_id, "ready": h.ready} for h in readiness]
        ready_count = sum(1 for h in readiness if h.ready)
        total = len(readiness)
        if ready_count == total and total > 0:
            return JSONResponse(
                {"status": "ready", "cameras": cameras}, status_code=200
            )
        if ready_count > 0:
            return JSONResponse(
                {"status": "degraded", "cameras": cameras}, status_code=200
            )
        return JSONResponse(
            {"status": "not_ready", "cameras": cameras, "recoverable": False},
            status_code=503,
        )

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/context")
    def context_push(payload: ContextPushModel) -> dict[str, str]:
        budget.on_context_update(payload.model_dump(exclude_none=True))
        if payload.journey_id is not None:
            journey_holder.journey_id = payload.journey_id
            log.info("context_push.journey_id_updated", journey_id=payload.journey_id)
        if payload.ramp_deployed and safety_handler is not None:
            door_id = payload.ramp_door_id or "unknown"
            station_id = payload.ramp_station_id or "unknown"
            loop = loop_holder.loop if loop_holder is not None else None
            if loop is None:
                # Fall back to the running loop (FastAPI lifespan owns it). This
                # branch is taken in tests that build the app without a loop_holder.
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
            if loop is None:
                log.warning("context_push.no_loop_for_ramp", door_id=door_id)
            else:
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        safety_handler.on_ramp_deployed(door_id, station_id),
                        loop,
                    )
                    fut.add_done_callback(_on_post_done)
                except RuntimeError as exc:
                    log.warning(
                        "context_push.schedule_during_shutdown",
                        door_id=door_id,
                        error=str(exc),
                    )
            log.info("context_push.ramp_deployed", door_id=door_id, station_id=station_id)
        return {"status": "accepted"}

    return app
