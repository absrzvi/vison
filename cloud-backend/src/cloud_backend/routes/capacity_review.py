"""Capacity review queue endpoints: review / dismiss / reopen / export CSV."""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..api.capacity_review import ReviewRequest, ReviewResponse, StatusResponse
from ..database import get_db

log = structlog.get_logger()

# review/dismiss/reopen share the same router prefix as the analytics exceptions endpoint
_exceptions_router = APIRouter(
    prefix="/api/v1/analytics/exceptions",
    dependencies=[Security(require_api_key)],
)

# export lives under a separate prefix
_export_router = APIRouter(
    prefix="/api/v1/capacity-review-queue",
    dependencies=[Security(require_api_key)],
)

@_exceptions_router.post("/{exception_id}/review", response_model=ReviewResponse)
async def review_exception(
    exception_id: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(require_api_key),
) -> ReviewResponse:
    now = datetime.now(UTC)
    await db.execute(
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
            "queued_by": api_key,
            "queued_at": now,
        },
    )
    await db.commit()
    return ReviewResponse(status="in_review", queued_at=now.isoformat())


@_exceptions_router.post("/{exception_id}/dismiss", response_model=StatusResponse)
async def dismiss_exception(
    exception_id: str,
    db: AsyncSession = Depends(get_db),
    api_key: str = Security(require_api_key),
) -> StatusResponse:
    await db.execute(
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
        {"eid": exception_id, "queued_by": api_key},
    )
    await db.commit()
    return StatusResponse(status="dismissed")


@_exceptions_router.post("/{exception_id}/reopen", response_model=StatusResponse)
async def reopen_exception(
    exception_id: str,
    db: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await db.execute(
        text("""
            UPDATE capacity_review_queue
            SET status = 'unreviewed'
            WHERE exception_id = :eid
        """),
        {"eid": exception_id},
    )
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
            row["exception_id"], row["route"], row["train_id"],
            row["departure_date"], row["priority"], row["note"],
            row["queued_by"], row["queued_at"], row["status"],
        ])

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    filename = f"capacity-review-{date_str}.csv"
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# Combine sub-routers after all routes are registered
capacity_review_router = APIRouter()
capacity_review_router.include_router(_exceptions_router)
capacity_review_router.include_router(_export_router)
