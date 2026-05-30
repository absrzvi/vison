from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/alerts", dependencies=[Security(require_api_key)])

# Alert event types pushed over SSE (ADR-20: landside push allow-list)
ALERT_EVENT_TYPES = frozenset({
    "ALARM_ACTIVE",
    "ALERT_RAISED",
    "ALERT_RESOLVED",
    "LUGGAGE_RACK_SATURATION",
    "UNATTENDED_BAG",
})

# In-process fan-out: set of queues, one per connected SSE client
_subscribers: set[asyncio.Queue[dict[str, object]]] = set()


def publish_alert(event: dict[str, object]) -> None:
    """Called by ingest route when an alert-class event is stored."""
    for q in _subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


async def _replay_since(
    last_event_id: str | None,
    db: AsyncSession,
) -> list[dict[str, object]]:
    """Return alert-class events stored after last_event_id (for SSE reconnect)."""
    if not last_event_id:
        return []
    rows = await db.execute(
        text("""
            SELECT event_id, event_type, severity, journey_id, vehicle_id,
                   timestamp, payload
            FROM events
            WHERE event_type = ANY(:types)
              AND event_id > :after
            ORDER BY source_timestamp ASC
            LIMIT 200
        """),
        {"types": list(ALERT_EVENT_TYPES), "after": last_event_id},
    )
    return [
        {
            "event_id": r.event_id,
            "event_type": r.event_type,
            "severity": r.severity,
            "journey_id": r.journey_id,
            "vehicle_id": r.vehicle_id,
            "timestamp": str(r.timestamp),
            "payload": r.payload,
        }
        for r in rows
    ]


async def _sse_generator(
    request: Request,
    last_event_id: str | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=256)
    _subscribers.add(queue)
    try:
        # Replay missed events on reconnect
        for event in await _replay_since(last_event_id, db):
            event_type = str(event["event_type"])
            event_id = str(event["event_id"])
            data = json.dumps(event)
            yield f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"

        # Live stream
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_type = str(event["event_type"])
                event_id = str(event["event_id"])
                data = json.dumps(event)
                yield f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"
            except TimeoutError:
                yield ": keep-alive\n\n"
    finally:
        _subscribers.discard(queue)
        log.info("sse_client_disconnected", remaining=len(_subscribers))


@router.get("/stream")
async def alerts_stream(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    last_event_id = request.headers.get("Last-Event-ID")
    return StreamingResponse(
        _sse_generator(request, last_event_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
