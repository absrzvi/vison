from __future__ import annotations

import structlog
from fastapi import FastAPI

from .config import settings
from .routes.health import router as health_router
from .routes.ingest import router as ingest_router

log = structlog.get_logger()

app = FastAPI(title="OEBB Cloud Backend", version="0.1.0")

app.include_router(health_router)
app.include_router(ingest_router)


@app.on_event("startup")
def _startup() -> None:
    log.info("cloud-backend started", db_url=settings.database_url)
