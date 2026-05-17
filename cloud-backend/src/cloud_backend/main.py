from __future__ import annotations

import structlog
from fastapi import FastAPI

from .config import get_settings
from .routes.health import router as health_router
from .routes.ingest import router as ingest_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()

app = FastAPI(title="OEBB Cloud Backend", version="0.1.0")

app.include_router(health_router)
app.include_router(ingest_router)


@app.on_event("startup")
async def _startup() -> None:
    settings = get_settings()
    log.info("cloud_backend_started", db_url=settings.database_url)
