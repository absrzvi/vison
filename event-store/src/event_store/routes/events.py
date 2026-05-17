from __future__ import annotations

import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from oebb_shared.events.envelope import EventModel

from ..database import get_connection, get_events_page, insert_event
from ..exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError
from ..models import EventPage, IngestRequest, IngestResponse

router = APIRouter(prefix="/api/v1/events")


def _get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("", response_model=IngestResponse, status_code=202)
def ingest_events(
    body: IngestRequest,
    conn: sqlite3.Connection = Depends(_get_db),
) -> IngestResponse:
    accepted = 0
    duplicates: list[str] = []
    for ev in body.events:
        try:
            inserted = insert_event(conn, ev.model_dump())
            if inserted:
                accepted += 1
            else:
                duplicates.append(ev.event_id)
        except UnsupportedSchemaVersionError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "UNSUPPORTED_SCHEMA_VERSION",
                    "detail": str(exc),
                    "recoverable": False,
                },
            ) from exc
    return IngestResponse(accepted=accepted, duplicate_ids=duplicates)


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
