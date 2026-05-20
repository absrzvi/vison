"""GET /api/v1/journeys/{journey_id} — AC5, AC8.

Response wrapped in ``{"data": {...}}`` envelope (ADR-10 success shape) for
consistency with POST + GET events. 404 returns the ADR-10 error envelope.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_api_key
from ..database import get_journey
from ..deps import get_db
from ..exceptions import JourneyNotFoundError

router = APIRouter(
    prefix="/api/v1/journeys",
    dependencies=[Depends(require_api_key)],
)


@router.get("/{journey_id}")
def get_journey_meta(
    journey_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    try:
        row = get_journey(conn, journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    return {"data": row}
