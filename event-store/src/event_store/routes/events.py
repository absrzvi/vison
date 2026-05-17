from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_connection, get_events_page, insert_event
from ..exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError
from ..models import EventPage, IngestRequest, IngestResponse
from oebb_shared.events.envelope import EventModel

router = APIRouter(prefix="/events")


def _get_db() -> sqlite3.Connection:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.post("/ingest", response_model=IngestResponse, status_code=202)
def ingest_events(
    body: IngestRequest,
    conn: sqlite3.Connection = Depends(_get_db),
) -> IngestResponse:
    accepted = 0
    duplicates: list[str] = []
    for ev in body.events:
        try:
            insert_event(conn, ev.model_dump())
            accepted += 1
        except UnsupportedSchemaVersionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception:
            duplicates.append(ev.event_id)
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = [EventModel(**r) for r in rows]
    next_cursor = items[-1].event_id if len(items) == limit else None
    return EventPage(items=items, next_cursor=next_cursor)
