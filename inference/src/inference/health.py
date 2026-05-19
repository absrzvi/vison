"""FastAPI health and context-push endpoints for the inference container."""
from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool

from inference.budget import Budget
from inference.models import JourneyHolder, ReadinessHolder

log = structlog.get_logger(__name__)


class ContextPushModel(BaseModel):
    """Schema for POST /context — strict bool so truthiness can't flip throttle."""

    model_config = ConfigDict(strict=True)

    p2_throttled: StrictBool = False
    journey_id: str | None = None


def build_app(
    readiness: ReadinessHolder,
    budget: Budget,
    journey_holder: JourneyHolder,
) -> FastAPI:
    """Build the FastAPI app.

    readiness is a mutable holder so main.py can flip pipeline_ready from True→False
    if the GStreamer pipeline crashes after startup. journey_holder is mutated when
    /context push carries a new journey_id (M13 — keeps outbound envelopes tied to
    the live trip without container restart).
    """
    app = FastAPI(title="inference-health")

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        if readiness.ready:
            return JSONResponse(
                {"status": "ready", "hailo_initialised": True}, status_code=200
            )
        return JSONResponse(
            {"status": "not_ready", "recoverable": False},
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
        return {"status": "accepted"}

    return app
