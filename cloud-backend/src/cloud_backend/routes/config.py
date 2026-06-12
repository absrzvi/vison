"""Read-only config endpoints — story 10-1 AC16."""
from __future__ import annotations

from fastapi import APIRouter, Security

from ..api.auth import require_api_key
from ..config.confidence_thresholds import (
    DEFAULT_CONFIDENCE_THRESHOLDS,
    DEGRADED_BANNER_FLOOR,
)

router = APIRouter(prefix="/api/v1/config", dependencies=[Security(require_api_key)])


@router.get("/confidence-thresholds")
async def confidence_thresholds() -> dict[str, dict[str, float] | float]:
    return {
        "per_class": dict(DEFAULT_CONFIDENCE_THRESHOLDS),
        "degraded_banner_floor": DEGRADED_BANNER_FLOOR,
    }
