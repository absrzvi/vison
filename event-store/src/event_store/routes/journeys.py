"""GET /api/v1/journeys/{journey_id} — AC5, AC8.

Response wrapped in ``{"data": {...}}`` envelope (ADR-10 success shape) for
consistency with POST + GET events. 404 returns the ADR-10 error envelope.

Code-review patch (2026-05-20): restored typed response model via
``JourneyMetaResponse`` so Pydantic validates the response shape; previously
returned a raw ``dict[str, Any]`` which skipped output validation.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_api_key
from ..database import get_journey
from ..deps import get_db
from ..exceptions import JourneyNotFoundError
from ..models import JourneyMeta, JourneyMetaResponse

router = APIRouter(
    prefix="/api/v1/journeys",
    dependencies=[Depends(require_api_key)],
)


@router.get("/{journey_id}", response_model=JourneyMetaResponse)
def get_journey_meta(
    journey_id: str,
    conn: sqlite3.Connection = Depends(get_db),
) -> JourneyMetaResponse:
    try:
        row = get_journey(conn, journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    return JourneyMetaResponse(data=JourneyMeta(**row))
