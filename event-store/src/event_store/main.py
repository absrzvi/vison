from __future__ import annotations

import structlog
from fastapi import FastAPI, WebSocket

from .config import settings
from .database import get_connection, init_db
from .routes.events import router as events_router
from .routes.health import router as health_router
from .routes.journeys import router as journeys_router
from .websocket.handler import websocket_stub

log = structlog.get_logger()

app = FastAPI(title="OEBB Event Store", version="0.1.0")

app.include_router(health_router)
app.include_router(events_router)
app.include_router(journeys_router)


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    await websocket_stub(websocket)


@app.on_event("startup")
def _startup() -> None:
    conn = get_connection()
    init_db(conn)
    conn.close()
    log.info("event-store started", db_path=settings.db_path)
