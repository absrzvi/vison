from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_journey
from ..deps import get_db
from ..exceptions import JourneyNotFoundError
from ..models import JourneyMeta

router = APIRouter(prefix="/api/v1/journeys")


@router.get("/{journey_id}", response_model=JourneyMeta)
def get_journey_meta(
    journey_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> JourneyMeta:
    try:
        row = get_journey(conn, journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    return JourneyMeta(**row)
