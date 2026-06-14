"""AI-quality resolution-rates endpoint (10-5 AC1).

GET /api/v1/ai-quality/resolution-rates?from=<iso>&to=<iso>
Returns two orthogonal resolution-quality rates per alert class (no-action rate +
explicit-false-positive rate, the latter keyed on the shipped `false_alarm` tag —
D1). Both params optional; default window is the last 7 days. Read-only; auth via
X-API-Key like the escalation-audit funnel and the KPI route.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.ai_quality import AlertQualityRates
from ..api.auth import require_api_key
from ..database import get_db
from ..services.ai_quality_rates import resolution_rates

router = APIRouter(
    prefix="/api/v1/ai-quality", dependencies=[Security(require_api_key)]
)


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 instant; tolerate a trailing Z. Raises ValueError on bad input."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _invalid_range_response() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "INVALID_RANGE",
            "detail": "from/to must be ISO-8601 timestamps; from must not be after to",
            "recoverable": True,
        },
    )


@router.get("/resolution-rates", response_model=None)
async def get_resolution_rates(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | list[AlertQualityRates]:
    try:
        dt_from = _parse_iso(from_) if from_ is not None else None
        dt_to = _parse_iso(to) if to is not None else None
    except ValueError:
        return _invalid_range_response()
    if dt_from is not None and dt_to is not None and dt_from > dt_to:
        return _invalid_range_response()

    return await resolution_rates(db, dt_from=dt_from, dt_to=dt_to)
