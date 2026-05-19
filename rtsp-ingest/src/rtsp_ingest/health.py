from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .gate import Gate
from .scheduler import Scheduler


def build_app(scheduler: Scheduler, gate: Gate) -> FastAPI:
    app = FastAPI(title="rtsp-ingest", version="0.1.0")

    @app.get("/health/ready")
    def health_ready() -> JSONResponse:
        count = scheduler.active_p1_count()
        if count < 1:
            return JSONResponse(
                status_code=503,
                content={"status": "starting", "p1_active": 0, "recoverable": True},
            )
        return JSONResponse(content={"status": "ready", "p1_active": count})

    @app.get("/health/live")
    def health_live() -> JSONResponse:
        return JSONResponse(content={"status": "ok"})

    @app.post("/context")
    def context_push(payload: dict[str, Any]) -> JSONResponse:
        if payload.get("event") == "door_release":
            gate.on_door_release(
                car_id=str(payload.get("car_id", "")),
                door_id=str(payload.get("door_id", "")),
            )
        else:
            gate.on_context_update(payload)
        return JSONResponse(content={"status": "ok"})

    return app
