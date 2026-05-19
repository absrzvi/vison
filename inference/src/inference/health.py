"""FastAPI health and context-push endpoints for the inference container."""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from inference.budget import Budget

log = structlog.get_logger(__name__)


def build_app(pipeline_ready: bool, budget: Budget) -> FastAPI:
    app = FastAPI(title="inference-health")

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        if pipeline_ready:
            return JSONResponse({"status": "ready", "hailo_initialised": True}, status_code=200)
        return JSONResponse(
            {"status": "not_ready", "recoverable": False},
            status_code=503,
        )

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/context")
    def context_push(payload: dict[str, Any]) -> dict[str, str]:
        budget.on_context_update(payload)
        return {"status": "accepted"}

    return app
