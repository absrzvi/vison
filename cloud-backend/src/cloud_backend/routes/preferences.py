"""Operator preferences endpoints — E2-S8.

GET  /api/v1/operators/me/preferences
PATCH /api/v1/operators/me/preferences

operator_id is the authenticated user's user_id (E11-S1 JWT cutover). Existing
rows keyed by the old shared API-key string read as 404 → graceful defaults
until E11-S3 re-keys/backfills them (Alembic migration). The data migration is
E11-S3's job; this story only swaps the identity source.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import CurrentUser, get_current_user
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/operators/me",
    dependencies=[Security(get_current_user)],
)

_VALID_THRESHOLD = frozenset({30, 60, 90, 120})
_VALID_STALENESS = frozenset({60, 120, 180, 300})
_DEFAULT_THRESHOLD = 60
_DEFAULT_STALENESS = 120


class PreferencesOut(BaseModel):
    operator_id: str
    threshold_sec: int
    staleness_threshold_sec: int


class PreferencesPatchOut(BaseModel):
    operator_id: str
    threshold_sec: int
    staleness_threshold_sec: int
    updated_at: str


class PreferencesPatch(BaseModel):
    threshold_sec: int | None = None
    staleness_threshold_sec: int | None = None


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    current_user: CurrentUser = Security(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    result = await db.execute(
        text(
            "SELECT operator_id, threshold_sec, staleness_threshold_sec "
            "FROM operator_preferences WHERE operator_id = :oid"
        ),
        {"oid": current_user.user_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NOT_FOUND",
                "detail": (
                    "No preferences saved; use defaults "
                    "threshold_sec=60, staleness_threshold_sec=120"
                ),
                "recoverable": True,
            },
        )
    return PreferencesOut(
        operator_id=row.operator_id,
        threshold_sec=row.threshold_sec,
        staleness_threshold_sec=row.staleness_threshold_sec,
    )


@router.patch("/preferences", response_model=PreferencesPatchOut)
async def patch_preferences(
    body: PreferencesPatch,
    current_user: CurrentUser = Security(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreferencesPatchOut:
    if body.threshold_sec is not None and body.threshold_sec not in _VALID_THRESHOLD:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INVALID_PREFERENCE",
                "detail": f"threshold_sec must be one of {sorted(_VALID_THRESHOLD)}",
                "recoverable": True,
            },
        )
    if (
        body.staleness_threshold_sec is not None
        and body.staleness_threshold_sec not in _VALID_STALENESS
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INVALID_PREFERENCE",
                "detail": f"staleness_threshold_sec must be one of {sorted(_VALID_STALENESS)}",
                "recoverable": True,
            },
        )

    _UPSERT = (
        "INSERT INTO operator_preferences"
        " (operator_id, threshold_sec, staleness_threshold_sec, updated_at)"
        " VALUES (:oid, :t, :s, NOW())"
        " ON CONFLICT (operator_id) DO UPDATE SET"
        " threshold_sec = COALESCE(:t_patch, operator_preferences.threshold_sec),"
        " staleness_threshold_sec ="
        " COALESCE(:s_patch, operator_preferences.staleness_threshold_sec),"
        " updated_at = NOW()"
        " RETURNING operator_id, threshold_sec, staleness_threshold_sec, updated_at::text"
    )
    result = await db.execute(
        text(_UPSERT),
        {
            "oid": current_user.user_id,
            "t": body.threshold_sec if body.threshold_sec is not None else _DEFAULT_THRESHOLD,
            "s": (
                body.staleness_threshold_sec
                if body.staleness_threshold_sec is not None
                else _DEFAULT_STALENESS
            ),
            "t_patch": body.threshold_sec,
            "s_patch": body.staleness_threshold_sec,
        },
    )
    await db.commit()
    row = result.one()
    return PreferencesPatchOut(
        operator_id=row.operator_id,
        threshold_sec=row.threshold_sec,
        staleness_threshold_sec=row.staleness_threshold_sec,
        updated_at=str(row.updated_at),
    )
