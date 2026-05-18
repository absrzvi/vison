"""Operator preferences endpoints — E2-S8.

GET  /api/v1/operators/me/preferences
PATCH /api/v1/operators/me/preferences

operator_id is derived server-side from the X-API-Key header value.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/operators/me",
    dependencies=[Security(require_api_key)],
)

_VALID_THRESHOLD = frozenset({30, 60, 90, 120})
_VALID_STALENESS = frozenset({60, 120, 180, 300})


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
    api_key: str = Security(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> PreferencesOut:
    result = await db.execute(
        text(
            "SELECT operator_id, threshold_sec, staleness_threshold_sec "
            "FROM operator_preferences WHERE operator_id = :oid"
        ),
        {"oid": api_key},
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
    api_key: str = Security(require_api_key),
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
            "oid": api_key,
            "t": body.threshold_sec or 60,
            "s": body.staleness_threshold_sec or 120,
            "t_patch": body.threshold_sec,
            "s_patch": body.staleness_threshold_sec,
        },
    )
    await db.commit()
    row = result.fetchone()
    return PreferencesPatchOut(
        operator_id=row.operator_id,
        threshold_sec=row.threshold_sec,
        staleness_threshold_sec=row.staleness_threshold_sec,
        updated_at=str(row.updated_at),
    )
