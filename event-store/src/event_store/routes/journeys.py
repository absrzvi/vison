from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_connection, get_events_page
from ..exceptions import JourneyNotFoundError
from ..models import EventPage, JourneyListItem

router = APIRouter(prefix="/journeys")


def _get_db() -> sqlite3.Connection:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=list[JourneyListItem])
def list_journeys(conn: sqlite3.Connection = Depends(_get_db)) -> list[JourneyListItem]:
    rows = conn.execute(
        """
        SELECT journey_id, vehicle_id,
               COUNT(*) AS event_count,
               MIN(timestamp) AS first_seen,
               MAX(timestamp) AS last_seen
        FROM events
        GROUP BY journey_id, vehicle_id
        ORDER BY first_seen DESC
        """  # noqa: S608
    ).fetchall()
    return [JourneyListItem(**dict(r)) for r in rows]


@router.get("/{journey_id}/events", response_model=EventPage)
def journey_events(
    journey_id: str,
    conn: sqlite3.Connection = Depends(_get_db),
) -> EventPage:
    try:
        rows = get_events_page(conn, journey_id=journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from oebb_shared.events.envelope import EventModel
    items = [EventModel(**r) for r in rows]
    return EventPage(items=items, next_cursor=None)
