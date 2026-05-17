from __future__ import annotations

import sqlite3
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_connection, get_journey
from ..exceptions import JourneyNotFoundError
from ..models import JourneyMeta

router = APIRouter(prefix="/api/v1/journeys")


def _get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/{journey_id}", response_model=JourneyMeta)
def get_journey_meta(
    journey_id: str,
    conn: sqlite3.Connection = Depends(_get_db),
) -> JourneyMeta:
    try:
        row = get_journey(conn, journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    return JourneyMeta(**row)
