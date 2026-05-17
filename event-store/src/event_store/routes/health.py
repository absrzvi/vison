from __future__ import annotations

import sqlite3
from collections.abc import Generator

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import get_connection

log = structlog.get_logger()

router = APIRouter()

_db_ready = False  # set to True once init_db succeeds in startup


def set_db_ready(value: bool) -> None:
    global _db_ready
    _db_ready = value


def _get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


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
