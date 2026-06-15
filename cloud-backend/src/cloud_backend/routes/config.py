"""Config endpoints — story 10-1 AC16 (read), E11-S5 (admin-mutable).

GET stays operator-readable (`get_current_user`) — the shipped UnifiedFeed
ConfidenceChip contract depends on it. The PATCH is admin-only
(`require_role("admin")`, per-route) — mirrors the E11-S4 kill-switch auth swap;
the actor is `current_user.username`, never a body field. Values are read through
the cached `ThresholdStore` (persisted store with hardcoded fail-safe defaults),
not the module constants.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import CurrentUser, get_current_user, require_role
from ..config.confidence_thresholds import (
    DEFAULT_CONFIDENCE_THRESHOLDS,
    threshold_store,
)
from ..database import get_db

router = APIRouter(prefix="/api/v1/config", dependencies=[Security(get_current_user)])

_FLOOR_KEY = "degraded_banner_floor"
_PER_CLASS_PREFIX = "per_class:"


def _check_unit_interval(v: float) -> float:
    """A per-class threshold must be a finite float in [0.0, 1.0]. Rejects
    NaN/Inf/out-of-range at the API boundary so a malformed value can never be
    persisted."""
    if not math.isfinite(v) or not (0.0 <= v <= 1.0):
        raise ValueError("threshold must be a finite number in [0.0, 1.0]")
    return v


def _check_floor(v: float) -> float:
    """The degraded-banner floor must be a finite float in (0.0, 1.0] — strictly
    ABOVE zero. A floor of 0.0 would make the gate (`mean < floor`) never fire,
    silently disabling the degraded banner fleet-wide (a fail-OPEN); the banner
    must not be disable-able via a 'valid' value. (E11-S5 code-review R1.)"""
    if not math.isfinite(v) or not (0.0 < v <= 1.0):
        raise ValueError("degraded_banner_floor must be a finite number in (0.0, 1.0]")
    return v


# Validation errors raised in the PATCH handler use the ADR-10 envelope (the
# in-handler raise below), matching the sibling preferences.py PATCH — NOT the
# default FastAPI RequestValidationError body. So validators here are invoked
# explicitly in the handler, not declared as Pydantic field_validators.
class ThresholdPatch(BaseModel):
    per_class: dict[str, float] | None = None
    degraded_banner_floor: float | None = None


@router.get("/confidence-thresholds")
async def confidence_thresholds(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, float] | float]:
    """Read the (persisted, cached, fail-safe) thresholds. Operator-readable."""
    return await threshold_store.load(db)


def _unprocessable(detail: str) -> HTTPException:
    """422 in the ADR-10 envelope (matches preferences.py; NOT the default
    FastAPI RequestValidationError body)."""
    return HTTPException(
        status_code=422,
        detail={"error": "UNPROCESSABLE", "detail": detail, "recoverable": True},
    )


@router.patch("/confidence-thresholds")
async def patch_confidence_thresholds(
    body: ThresholdPatch,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, float] | float]:
    """Admin-only upsert of one or more thresholds. Actor = token username.

    All value validation happens HERE (not as Pydantic field_validators) so a
    bad value yields the ADR-10 422 envelope, and NOTHING is persisted until the
    whole body validates (atomic — a valid key in a mixed-invalid PATCH does not
    leak)."""
    updates: dict[str, float] = {}
    try:
        if body.degraded_banner_floor is not None:
            updates[_FLOOR_KEY] = _check_floor(body.degraded_banner_floor)
        if body.per_class:
            for code, value in body.per_class.items():
                if code not in DEFAULT_CONFIDENCE_THRESHOLDS:
                    raise ValueError(f"unknown alert class: {code}")
                updates[f"{_PER_CLASS_PREFIX}{code}"] = _check_unit_interval(value)
    except ValueError as exc:
        raise _unprocessable(str(exc)) from exc
    if not updates:
        raise _unprocessable("no threshold values supplied")
    now = datetime.now(UTC)
    for config_key, value in updates.items():
        await db.execute(
            text("""
                INSERT INTO confidence_thresholds (config_key, value, updated_by, updated_at)
                VALUES (:k, :v, :actor, :ts)
                ON CONFLICT (config_key) DO UPDATE
                SET value = :v, updated_by = :actor, updated_at = :ts
            """),
            {"k": config_key, "v": value, "actor": current.username, "ts": now},
        )
    await db.commit()
    threshold_store.invalidate()
    # The degraded-banner gate has its OWN 30s flag cache (health.py) keyed off the
    # floor — reset it too so an edit takes effect on the next request, not after a
    # ≤30s lag (the UI promises "changes apply without a redeploy"). E11-S5 R1.
    from .health import degraded_cache

    degraded_cache.reset()
    return await threshold_store.load(db)


# Re-export for callers that imported the module symbol historically.
__all__ = ["router"]
