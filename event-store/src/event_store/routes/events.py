"""POST + GET /api/v1/events — AC1, AC2, AC3, AC4, AC8.

Idempotency contract (AC2 — explicit change from prior 409 behaviour):
  - First insert  → HTTP 201 with ``{"data": {"event_id": ..., "stored": true}}``
  - Duplicate     → HTTP 200 with ``{"data": {"event_id": ..., "stored": false}}``
  - Schema 999    → HTTP 422 ADR-10 envelope
  - Bad envelope  → HTTP 422 (FastAPI default)
  - Bad cursor    → HTTP 400 ADR-10 envelope (code-review patch 2026-05-20)

Idempotency is keyed on the **natural key** ``(journey_id, event_type,
timestamp)`` — NOT on ``event_id``. Producers MUST retry with the SAME
``event_id`` to read back a meaningful response.event_id on duplicate; a
client that retries with a fresh ``event_id`` against the same natural key
will see ``stored=false`` for an event_id that was never persisted (decision
2, code-review 2026-05-20: documented rather than auto-corrected).

After a SUCCESSFUL insert (stored=True only), the envelope is fanned out to
all matching WebSocket subscribers via ``request.app.state.broadcaster``.
"""
from __future__ import annotations

import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from oebb_shared.events.envelope import EventEnvelope

from ..auth import require_api_key
from ..database import get_events_page, insert_event
from ..deps import get_db
from ..exceptions import (
    InvalidCursorError,
    JourneyNotFoundError,
    UnsupportedSchemaVersionError,
)
from ..models import EventPage

router = APIRouter(prefix="/api/v1/events", dependencies=[Depends(require_api_key)])


@router.post("")
async def ingest_event(
    body: EventEnvelope,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> JSONResponse:
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

    body_payload = {
        "data": {
            "event_id": body.event_id,
            "stored": inserted,
        }
    }
    if not inserted:
        # AC2: duplicate is 200 (NOT 409). No fan-out for duplicates — dedup
        # at write time means subscribers already got the first copy (or will
        # get it via replay on reconnect).
        return JSONResponse(body_payload, status_code=200)

    # First-time insert → fan out to matching WS subscribers (AC1, AC6).
    broadcaster = getattr(request.app.state, "broadcaster", None)
    if broadcaster is not None:
        await broadcaster.broadcast(body.model_dump(mode="json"))
    return JSONResponse(body_payload, status_code=201)


@router.get("", response_model=EventPage)
def list_events(
    journey_id: Annotated[str | None, Query()] = None,
    after: Annotated[str | None, Query(description="cursor event_id")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    event_type: Annotated[list[str] | None, Query()] = None,
    min_severity: Annotated[
        Literal["info", "warning", "critical"] | None, Query()
    ] = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> EventPage:
    try:
        rows = get_events_page(
            conn,
            journey_id=journey_id,
            after_event_id=after,
            limit=limit,
            event_types=event_type,
            min_severity=min_severity,
        )
    except InvalidCursorError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_CURSOR",
                "detail": str(exc),
                "recoverable": False,
            },
        ) from exc
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "JOURNEY_NOT_FOUND", "detail": str(exc), "recoverable": False},
        ) from exc
    # EventModel parses each row; EventPage(alias="data") wraps the list.
    from oebb_shared.events.envelope import EventModel  # local import keeps top tidy

    items = [EventModel(**r) for r in rows]
    next_cursor = items[-1].event_id if len(items) == limit else None
    return EventPage(
        data=items,
        count=len(items),
        journey_id=journey_id,
        next_cursor=next_cursor,
    )
