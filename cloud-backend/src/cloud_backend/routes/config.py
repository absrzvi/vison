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
from pydantic import BaseModel, field_validator
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
    """A threshold must be a finite float in [0.0, 1.0]. Rejects NaN/Inf/out-of-range
    at the API boundary (422) so a malformed value can never be persisted."""
    if not math.isfinite(v) or not (0.0 <= v <= 1.0):
        raise ValueError("threshold must be a finite number in [0.0, 1.0]")
    return v


class ThresholdPatch(BaseModel):
    per_class: dict[str, float] | None = None
    degraded_banner_floor: float | None = None

    @field_validator("degraded_banner_floor")
    @classmethod
    def _floor_unit(cls, v: float | None) -> float | None:
        return None if v is None else _check_unit_interval(v)

    @field_validator("per_class")
    @classmethod
    def _per_class_unit(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return None
        for code, value in v.items():
            if code not in DEFAULT_CONFIDENCE_THRESHOLDS:
                raise ValueError(f"unknown alert class: {code}")
            _check_unit_interval(value)
        return v


@router.get("/confidence-thresholds")
async def confidence_thresholds(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, float] | float]:
    """Read the (persisted, cached, fail-safe) thresholds. Operator-readable."""
    return await threshold_store.load(db)


@router.patch("/confidence-thresholds")
async def patch_confidence_thresholds(
    body: ThresholdPatch,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, float] | float]:
    """Admin-only upsert of one or more thresholds. Actor = token username."""
    updates: dict[str, float] = {}
    if body.degraded_banner_floor is not None:
        updates[_FLOOR_KEY] = body.degraded_banner_floor
    if body.per_class:
        for code, value in body.per_class.items():
            updates[f"{_PER_CLASS_PREFIX}{code}"] = value
    if not updates:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "UNPROCESSABLE",
                "detail": "no threshold values supplied",
                "recoverable": True,
            },
        )
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
    return await threshold_store.load(db)


# Re-export for callers that imported the module symbol historically.
__all__ = ["router"]
