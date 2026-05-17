from __future__ import annotations

from fastapi import APIRouter, Depends
import sqlite3

from ..database import get_connection
from ..models import HealthResponse
from ..config import settings

router = APIRouter()


def _get_db() -> sqlite3.Connection:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/health", response_model=HealthResponse)
def health(conn: sqlite3.Connection = Depends(_get_db)) -> HealthResponse:
    row = conn.execute("SELECT COUNT(*) AS cnt FROM events").fetchone()
    return HealthResponse(
        status="ok",
        db_path=settings.db_path,
        event_count=int(row["cnt"]),
    )
