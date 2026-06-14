"""Capacity review queue endpoints: review / dismiss / reopen / export CSV."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import CurrentUser, get_current_user
from ..api.capacity_review import ReviewRequest, ReviewResponse, StatusResponse
from ..database import get_db

log = structlog.get_logger()

_CSV_FORMULA_CHARS = ('=', '+', '-', '@', '\t', '\r')


def _csv_safe(value: str | None) -> str:
    """Prefix formula-triggering characters to prevent CSV injection."""
    if value is None:
        return ''
    s = str(value)
    if s and s[0] in _CSV_FORMULA_CHARS:
        return "'" + s
    return s


# review/dismiss/reopen share the same router prefix as the analytics exceptions endpoint
_exceptions_router = APIRouter(
    prefix="/api/v1/analytics/exceptions",
    dependencies=[Security(get_current_user)],
)

# export lives under a separate prefix
_export_router = APIRouter(
    prefix="/api/v1/capacity-review-queue",
    dependencies=[Security(get_current_user)],
)


@_exceptions_router.post("/{exception_id}/review", response_model=ReviewResponse)
async def review_exception(
    exception_id: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Security(get_current_user),
) -> ReviewResponse:
    now = datetime.now(UTC)
    result: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
        text("""
            INSERT INTO capacity_review_queue
              (exception_id, route, train_id, departure_date,
               priority, note, queued_by, queued_at, status)
            SELECT
              :eid,
              COALESCE((payload->>'route')::text, ''),
              vehicle_id,
              COALESCE((payload->>'departure')::text, timestamp::date::text),
              :priority,
              :note,
              :queued_by,
              :queued_at,
              'in_review'
            FROM events
            WHERE event_id = :eid
            ON CONFLICT (exception_id)
            DO UPDATE SET
              priority   = EXCLUDED.priority,
              note       = EXCLUDED.note,
              queued_by  = EXCLUDED.queued_by,
              queued_at  = EXCLUDED.queued_at,
              status     = 'in_review'
        """),
        {
            "eid": exception_id,
            "priority": body.priority,
            "note": body.note,
            "queued_by": current_user.username,
            "queued_at": now,
        },
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="exception not found")
    await db.commit()
    return ReviewResponse(status="in_review", queued_at=now.isoformat())


@_exceptions_router.post("/{exception_id}/dismiss", response_model=StatusResponse)
async def dismiss_exception(
    exception_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Security(get_current_user),
) -> StatusResponse:
    result: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
        text("""
            INSERT INTO capacity_review_queue
              (exception_id, route, train_id, departure_date,
               priority, note, queued_by, queued_at, status)
            SELECT
              :eid,
              COALESCE((payload->>'route')::text, ''),
              vehicle_id,
              COALESCE((payload->>'departure')::text, timestamp::date::text),
              'low',
              NULL,
              :queued_by,
              NOW(),
              'dismissed'
            FROM events
            WHERE event_id = :eid
            ON CONFLICT (exception_id)
            DO UPDATE SET status = 'dismissed'
        """),
        {"eid": exception_id, "queued_by": current_user.username},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="exception not found")
    await db.commit()
    return StatusResponse(status="dismissed")


@_exceptions_router.post("/{exception_id}/reopen", response_model=StatusResponse)
async def reopen_exception(
    exception_id: str,
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    result: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
        text("""
            UPDATE capacity_review_queue
            SET status = 'unreviewed'
            WHERE exception_id = :eid
        """),
        {"eid": exception_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="exception not found in review queue")
    await db.commit()
    return StatusResponse(status="unreviewed")


@_export_router.get("/export")
async def export_capacity_review_csv(
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        text("""
            SELECT
              q.exception_id,
              q.route,
              q.train_id,
              q.departure_date,
              q.priority,
              COALESCE(q.note, '') AS note,
              q.queued_by,
              q.queued_at::text AS queued_at,
              q.status
            FROM capacity_review_queue q
            WHERE q.status != 'dismissed'
            ORDER BY q.queued_at DESC
        """),
    )
    rows = result.mappings().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "exception_id", "route", "train_id", "departure_date",
        "priority", "note", "queued_by", "queued_at", "status",
    ])
    for row in rows:
        writer.writerow([
            _csv_safe(row["exception_id"]),
            _csv_safe(row["route"]),
            _csv_safe(row["train_id"]),
            _csv_safe(row["departure_date"]),
            _csv_safe(row["priority"]),
            _csv_safe(row["note"]),
            _csv_safe(row["queued_by"]),
            _csv_safe(row["queued_at"]),
            _csv_safe(row["status"]),
        ])

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"capacity-review-{date_str}.csv"
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Combine sub-routers after all routes are registered
capacity_review_router = APIRouter()
capacity_review_router.include_router(_exceptions_router)
capacity_review_router.include_router(_export_router)
