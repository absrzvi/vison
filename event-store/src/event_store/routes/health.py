from __future__ import annotations

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = structlog.get_logger()

router = APIRouter()

_db_ready = False  # set to True once init_db succeeds in startup


def set_db_ready(value: bool) -> None:
    global _db_ready
    _db_ready = value


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready() -> JSONResponse:
    if not _db_ready:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "SQLite WAL not yet open"},
        )
    return JSONResponse(content={"status": "ok", "db_connected": True})
