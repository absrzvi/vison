from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket

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

app.include_router(health_router)
app.include_router(events_router)
app.include_router(journeys_router)


@app.websocket("/ws")
async def ws_events(websocket: WebSocket) -> None:
    broadcaster: Broadcaster = websocket.app.state.broadcaster
    await websocket_endpoint(websocket, broadcaster)
