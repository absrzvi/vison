from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings
from .database import get_connection, init_db
from .routes.events import router as events_router
from .routes.health import router as health_router
from .routes.health import set_db_ready
from .routes.journeys import router as journeys_router
from .websocket.broadcaster import Broadcaster
from .websocket.handler import websocket_endpoint

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: init DB schema, create the Broadcaster, warn on missing api_key.

    The Broadcaster lives on ``app.state`` so routes + WS endpoint share one
    instance (and TestClient sees the same one when reusing the FastAPI app).
    """
    conn = get_connection()
    try:
        init_db(conn)
        set_db_ready(True)
        log.info("event_store_started", db_path=settings.db_path)
    finally:
        conn.close()

    app.state.broadcaster = Broadcaster()
    if settings.api_key is None:
        log.warning(
            "auth.api_key_unset",
            message="EVENT_STORE_API_KEY is not configured — auth bypassed (dev mode)",
        )
    try:
        yield
    finally:
        log.info("event_store_stopping")


app = FastAPI(title="OEBB Event Store", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def _schema_version_adr10_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Re-shape Pydantic ``schema_version`` validation errors into the
    ADR-10 ``UNSUPPORTED_SCHEMA_VERSION`` envelope expected by AC3.

    Pydantic's ``EventEnvelope.schema_version`` validator runs BEFORE the
    route handler, so the route's own ``UnsupportedSchemaVersionError``
    branch never executes for envelope-validated POSTs. This handler
    inspects the validation errors and, when any of them target the
    ``schema_version`` field, returns the ADR-10 envelope instead of
    FastAPI's default ``{"detail": [...]}`` shape.

    Other validation errors pass through to FastAPI's default 422 response.
    Code-review patch (2026-05-20, decision 4).
    """
    schema_version_error = next(
        (
            err
            for err in exc.errors()
            if any(part == "schema_version" for part in err.get("loc", ()))
        ),
        None,
    )
    if schema_version_error is not None:
        log.warning(
            "schema_version_unsupported_via_envelope",
            detail=schema_version_error.get("msg"),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "error": "UNSUPPORTED_SCHEMA_VERSION",
                    "detail": schema_version_error.get(
                        "msg", "unsupported schema_version"
                    ),
                    "recoverable": False,
                }
            },
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


app.include_router(health_router)
app.include_router(events_router)
app.include_router(journeys_router)


@app.websocket("/ws")
async def ws_events(websocket: WebSocket) -> None:
    broadcaster: Broadcaster = websocket.app.state.broadcaster
    await websocket_endpoint(websocket, broadcaster)
