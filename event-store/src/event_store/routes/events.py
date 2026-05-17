from __future__ import annotations

import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from oebb_shared.events.envelope import EventEnvelope, EventModel

from ..database import get_connection, get_events_page, insert_event
from ..exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError
from ..models import EventPage, IngestSingleResponse

router = APIRouter(prefix="/api/v1/events")


def _get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("", response_model=IngestSingleResponse, status_code=201)
def ingest_event(
    body: EventEnvelope,
    conn: sqlite3.Connection = Depends(_get_db),
) -> IngestSingleResponse:
    try:
        inserted = insert_event(conn, body.model_dump())
    except UnsupportedSchemaVersionError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "UNSUPPORTED_SCHEMA_VERSION",
                "detail": str(exc),
                "recoverable": False,
            },
        ) from exc

    if not inserted:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "DUPLICATE_EVENT",
                "detail": f"Duplicate event: (journey_id={body.journey_id}, "
                          f"event_type={body.event_type}, timestamp={body.timestamp})",
                "recoverable": False,
            },
        )
    return IngestSingleResponse(event_id=body.event_id, stored=True)


@router.get("", response_model=EventPage)
def list_events(
    journey_id: Annotated[str | None, Query()] = None,
    after: Annotated[str | None, Query(description="cursor event_id")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    conn: sqlite3.Connection = Depends(_get_db),
) -> EventPage:
    try:
        rows = get_events_page(conn, journey_id=journey_id, after_event_id=after, limit=limit)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    items = [EventModel(**r) for r in rows]
    next_cursor = items[-1].event_id if len(items) == limit else None
    return EventPage(items=items, next_cursor=next_cursor)
