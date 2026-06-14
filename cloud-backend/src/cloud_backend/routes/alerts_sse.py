from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request, Security
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import get_current_user_from_query
from ..database import get_db
from ..services.fanout_filter import alert_class_filter

log = structlog.get_logger()

# SSE/EventSource cannot set an Authorization header, so this stream authenticates
# via a ?token=<jwt> query param verified by the same JWT core as the header path
# (D8 / ADR-23). Header-based get_current_user is NOT used here.
router = APIRouter(
    prefix="/api/v1/alerts", dependencies=[Security(get_current_user_from_query)]
)

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
    """Called by ingest route when an alert-class event is stored.

    Iterates a list-snapshot of `_subscribers` so that concurrent
    subscriber registration / disconnection during fan-out cannot raise
    `RuntimeError: Set changed size during iteration` (P8 defence).
    """
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def _build_frame(event: dict[str, object]) -> str | None:
    """Render an event dict to a single SSE frame, or None if malformed.

    Per E1-S6' code-review P11: bare `event["event_type"]` access would
    propagate a KeyError out of the generator and tear down the SSE
    connection. Instead, skip malformed events with a structured log.
    A missing `event_type` or `event_id` (or a NULL value) is treated as
    a producer-side bug, not a client-facing crash.
    """
    event_type_raw = event.get("event_type")
    event_id_raw = event.get("event_id")
    if event_type_raw is None or event_id_raw is None:
        log.warning(
            "sse_frame_skipped_missing_field",
            event_type=event_type_raw,
            event_id=event_id_raw,
        )
        return None
    event_type = str(event_type_raw)
    event_id = str(event_id_raw)
    data = json.dumps(event, default=str)
    return f"event: {event_type}\nid: {event_id}\ndata: {data}\n\n"


async def _replay_since(
    last_event_id: str | None,
    db: AsyncSession,
) -> list[dict[str, object]]:
    """Return alert-class events stored after the row with `last_event_id`.

    Ordering and cursor semantics (per E1-S6' code-review D-R1):
    - Filter on `source_timestamp > (cursor row's source_timestamp)`. Using
      `event_id` as the cursor would fail on production because the column
      is `UUID` (not text) and because UUIDv4 has no temporal ordering.
    - Order deterministically by `(source_timestamp ASC, event_id ASC)` so
      ties on `source_timestamp` resolve identically across calls.
    - If `last_event_id` is missing or does not exist, returns an empty
      list — fresh subscribers get no replay (consistent with current
      behaviour and ADR-20: "reconnect reconciliation goes through REST").
    - `LIMIT 200` caps the wire-replay payload; clients use the REST
      endpoints to reconcile any older gap.
    """
    if not last_event_id:
        return []
    rows = await db.execute(
        text("""
            WITH cursor AS (
                SELECT source_timestamp AS ts
                FROM events
                WHERE event_id = :after
            )
            SELECT event_id, event_type, severity, journey_id, vehicle_id,
                   timestamp, payload
            FROM events, cursor
            WHERE event_type = ANY(:types)
              AND source_timestamp > cursor.ts
            ORDER BY source_timestamp ASC, event_id ASC
            LIMIT 200
        """),
        {"types": list(ALERT_EVENT_TYPES), "after": last_event_id},
    )
    # E10-S1 AC13: kill-switch applies to the replay path too — disabled alert
    # classes raised after disabled_at never reach a reconnecting client.
    events: list[dict[str, object]] = []
    for r in rows:
        payload = r.payload if isinstance(r.payload, dict) else json.loads(r.payload)
        if await alert_class_filter.is_filtered(
            db, event_type=r.event_type, payload=payload, t_raised=r.timestamp
        ):
            continue
        events.append(
            {
                "event_id": str(r.event_id),
                "event_type": r.event_type,
                "severity": r.severity,
                "journey_id": r.journey_id,
                "vehicle_id": r.vehicle_id,
                "timestamp": str(r.timestamp),
                "payload": payload,
            }
        )
    return events


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
            frame = _build_frame(event)
            if frame is not None:
                yield frame

        # Live stream
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                frame = _build_frame(event)
                if frame is not None:
                    yield frame
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
