"""WebSocket endpoint — full fan-out + replay (AC6, AC7).

Flow:
  1. accept connection
  2. parse the first text frame as a SubscriptionRequest JSON
  3. open a SQLite connection (read-only path) for replay
  4. run replay_to(subscriber, conn) — flushes last N matching events
  5. register subscriber with the Broadcaster
  6. run reader + writer tasks concurrently until disconnect
  7. deregister + close

# TODO(post-PoC): add per-app authentication on WS connect.
# The PoC relies on the on-train VLAN being the security boundary; story 4-7
# explicitly defers WS auth (see Dev Notes Rule 9).
"""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from oebb_shared.ws.subscription import SubscriptionRequest

from ..database import get_connection
from . import replay as replay_mod
from .broadcaster import Broadcaster, Subscriber

log = structlog.get_logger()


async def _writer(subscriber: Subscriber) -> None:
    """Drain the subscriber's queue → send_text."""
    while True:
        envelope = await subscriber.queue.get()
        await subscriber.websocket.send_text(json.dumps(envelope))


async def _reader(subscriber: Subscriber) -> None:
    """Read frames from the client; primarily a disconnect detector."""
    while True:
        await subscriber.websocket.receive_text()


def _parse_subscription(data: dict[str, object]) -> SubscriptionRequest:
    event_types_raw = data.get("event_types", [])
    if not isinstance(event_types_raw, list):
        raise ValueError("event_types must be a list")
    event_types = [str(x) for x in event_types_raw]

    min_severity = str(data.get("min_severity", "info"))
    if min_severity not in {"info", "warning", "critical"}:
        raise ValueError(f"invalid min_severity: {min_severity!r}")

    coach_ids_raw = data.get("coach_ids")
    coach_ids: list[str] | None
    if coach_ids_raw is None:
        coach_ids = None
    elif isinstance(coach_ids_raw, list):
        coach_ids = [str(x) for x in coach_ids_raw]
    else:
        raise ValueError("coach_ids must be a list or null")

    depth_raw = data.get("reconnect_replay_depth", 50)
    if not isinstance(depth_raw, int):
        raise ValueError("reconnect_replay_depth must be int")

    return SubscriptionRequest(
        event_types=event_types,
        min_severity=min_severity,
        coach_ids=coach_ids,
        reconnect_replay_depth=depth_raw,
    )


async def websocket_endpoint(websocket: WebSocket, broadcaster: Broadcaster) -> None:
    """Main WebSocket entry. The first message must be a SubscriptionRequest JSON.

    Bad JSON / bad shape → close with code 1003 (unsupported data).
    """
    await websocket.accept()
    name = f"ws-{uuid.uuid4().hex[:8]}"

    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        log.info("ws.disconnected_before_subscribe", name=name)
        return

    try:
        data = json.loads(raw)
        subscription = _parse_subscription(data)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        log.warning("ws.invalid_subscription", name=name, error=str(exc))
        await websocket.close(code=1003)
        return

    subscriber = Subscriber(
        websocket=websocket,
        subscription=subscription,
        name=name,
    )

    # Replay BEFORE registering with the broadcaster — guarantees that no live
    # event slots in between replay and the live loop.
    conn = get_connection()
    try:
        await replay_mod.replay_to(subscriber, conn)
    finally:
        conn.close()

    await broadcaster.add(subscriber)
    # Acknowledge AFTER the subscriber is registered with the broadcaster so the
    # client can use the ack as a "go" signal — any POST it makes after seeing
    # the ack is guaranteed to fan out to this subscriber.
    await websocket.send_text(json.dumps({"status": "subscribed", "filter": data}))
    try:
        reader_task = asyncio.create_task(_reader(subscriber))
        writer_task = asyncio.create_task(_writer(subscriber))
        done, pending = await asyncio.wait(
            {reader_task, writer_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in pending:
            try:
                await task
            except (asyncio.CancelledError, WebSocketDisconnect):
                pass
        # Surface any reader/writer exception that isn't a disconnect.
        for task in done:
            try:
                task.result()
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass
    finally:
        await broadcaster.remove(subscriber)
        log.info("ws.disconnected", name=name, dropped=subscriber.dropped)
