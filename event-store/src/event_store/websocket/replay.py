"""WebSocket reconnect replay — AC7.

On (re)connect, before live event delivery starts, replay the LAST N events
matching the subscriber's filter in chronological order. N is bounded by
``_REPLAY_CAP_HARD`` so a malicious client cannot request unbounded history.

The replay sends events directly via ``websocket.send_text`` — NOT through
the per-subscriber queue. This guarantees that replayed events are flushed
before the subscriber is registered with the broadcaster for live delivery.
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
    """Read the last N matching events and send them to the WS in order.

    No-op when ``reconnect_replay_depth == 0``. Caps at ``_REPLAY_CAP_HARD``
    and logs INFO when the cap is applied. Catches ``WebSocketDisconnect``
    silently and returns.
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
