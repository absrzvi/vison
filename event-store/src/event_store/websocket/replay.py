"""WebSocket reconnect replay — AC7.

On (re)connect the handler registers the subscriber with the Broadcaster FIRST
(so live events committed during this window queue safely), then calls
``replay_to`` which:

  1. Reads the last N events matching the subscriber's filter, in chronological
     order. N is capped at ``_REPLAY_CAP_HARD`` (1000) to bound memory.
  2. Sends each replayed event directly via ``websocket.send_text`` (NOT via
     the per-subscriber queue) so order is guaranteed.
  3. Records each replayed event_id in ``subscriber.pending_replay_ids`` so
     the writer task can de-duplicate any concurrent live event that ALSO
     made it into the queue during the replay window.

The dedupe set is intentionally a per-subscriber state, not a global. The
writer drops the id from the set the first time it sees a match, so the set
never grows beyond the replay depth.
"""
from __future__ import annotations

import json
import sqlite3

import structlog
from fastapi import WebSocketDisconnect

from ..database import get_filtered_events_for_replay
from .broadcaster import Subscriber

log = structlog.get_logger()

_REPLAY_CAP_HARD = 1000


async def replay_to(subscriber: Subscriber, conn: sqlite3.Connection) -> None:
    """Replay the last N matching events to the subscriber's WS.

    No-op when ``reconnect_replay_depth == 0``. Caps at ``_REPLAY_CAP_HARD``
    with an INFO log. Catches ``WebSocketDisconnect`` silently and returns.
    Populates ``subscriber.pending_replay_ids`` with every event_id sent so
    the writer task can dedupe concurrent live deliveries.
    """
    requested = subscriber.subscription.reconnect_replay_depth
    if requested <= 0:
        return
    depth = requested
    if depth > _REPLAY_CAP_HARD:
        log.info(
            "ws.replay_depth_capped",
            requested=requested,
            cap=_REPLAY_CAP_HARD,
            name=subscriber.name,
        )
        depth = _REPLAY_CAP_HARD

    rows = get_filtered_events_for_replay(
        conn,
        event_types=subscriber.subscription.event_types or None,
        min_severity=subscriber.subscription.min_severity,
        coach_ids=subscriber.subscription.coach_ids,
        limit=depth,
    )

    try:
        for envelope in rows:
            event_id = str(envelope.get("event_id", ""))
            if event_id:
                subscriber.pending_replay_ids.add(event_id)
            await subscriber.websocket.send_text(json.dumps(envelope))
    except WebSocketDisconnect:
        log.info("ws.replay_disconnected_mid_stream", name=subscriber.name)
        return

    log.info(
        "ws.replay_complete",
        name=subscriber.name,
        delivered=len(rows),
        requested=requested,
    )
