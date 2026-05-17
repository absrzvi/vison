from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI, WebSocket

from .config import settings
from .database import get_connection, init_db
from .routes.events import router as events_router
from .routes.health import router as health_router
from .routes.health import set_db_ready
from .routes.journeys import router as journeys_router
from .websocket.handler import websocket_stub

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

app = FastAPI(title="OEBB Event Store", version="0.1.0")

app.include_router(health_router)
app.include_router(events_router)
app.include_router(journeys_router)


@app.websocket("/ws")
async def ws_events(websocket: WebSocket) -> None:
    await websocket_stub(websocket)


@app.on_event("startup")
def _startup() -> None:
    conn = get_connection()
    try:
        init_db(conn)
        set_db_ready(True)
        log.info("event_store_started", db_path=settings.db_path)
    finally:
        conn.close()
