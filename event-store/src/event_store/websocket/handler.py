"""WebSocket endpoint — full fan-out + replay (AC6, AC7).

Flow (code-review 2026-05-20 race fix):
  1. accept connection
  2. parse the first text frame as a SubscriptionRequest JSON
  3. register subscriber with the Broadcaster — live events from this moment
     onward queue safely (closes the replay→live race)
  4. open a SQLite connection, run replay_to(subscriber, conn) — replayed
     event_ids are recorded in ``subscriber.pending_replay_ids``
  5. send the "subscribed" ack — clients can use this as a "live delivery
     begins now" barrier
  6. run reader + writer tasks concurrently. The writer skips any queued
     event whose event_id is in pending_replay_ids (then removes it),
     deduplicating events that the broadcaster placed in the queue during
     the replay window.
  7. on any exit: deregister and close cleanly

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
    """Drain the subscriber's queue → send_text, deduping replayed event_ids.

    If an envelope's event_id is in ``subscriber.pending_replay_ids``, drop
    it (the client already received it via replay) and remove the id from
    the set. This is the consume-side of the register-first dedupe-by-id
    design (code-review decision 1).
    """
    while True:
        envelope = await subscriber.queue.get()
        event_id = str(envelope.get("event_id", ""))
        if event_id and event_id in subscriber.pending_replay_ids:
            subscriber.pending_replay_ids.discard(event_id)
            subscriber.deduped += 1
            continue
        await subscriber.websocket.send_text(json.dumps(envelope))


async def _reader(subscriber: Subscriber) -> None:
    """Read frames from the client; primarily a disconnect detector.

    Catches ``WebSocketDisconnect`` silently. Any other exception (e.g. a
    binary frame raising ``RuntimeError`` on a text-only socket) is logged
    structurally and re-raised so the handler can clean up — see
    ``websocket_endpoint``'s ``done`` block which swallows the re-raise.
    """
    try:
        while True:
            await subscriber.websocket.receive_text()
    except WebSocketDisconnect:
        return
    except RuntimeError as exc:  # pragma: no cover  # defence-in-depth
        # Binary frame on a text-only socket, or send-after-close, etc.
        log.warning("ws.reader_protocol_error", name=subscriber.name, error=str(exc))
        return


def _parse_subscription(data: dict[str, object]) -> SubscriptionRequest:
    """Validate and construct a SubscriptionRequest from inbound JSON.

    Strict validation per code-review patches (2026-05-20):
      * ``event_types`` MUST be a non-empty list of strings — an empty list
        would create a "deaf" subscriber that receives no live events but
        all replay events.
      * ``coach_ids`` MUST be either ``None`` (= all coaches) or a non-empty
        list of strings. An empty list has inconsistent semantics between
        live and replay paths; explicit rejection is clearer.
      * ``reconnect_replay_depth`` MUST be an ``int`` but NOT a ``bool``
        (since ``bool`` is a subclass of ``int`` in Python).
    """
    event_types_raw = data.get("event_types", [])
    if not isinstance(event_types_raw, list):
        raise ValueError("event_types must be a list")
    if not event_types_raw:
        raise ValueError("event_types must be a non-empty list")
    event_types = [str(x) for x in event_types_raw]

    min_severity = str(data.get("min_severity", "info"))
    if min_severity not in {"info", "warning", "critical"}:
        raise ValueError(f"invalid min_severity: {min_severity!r}")

    coach_ids_raw = data.get("coach_ids")
    coach_ids: list[str] | None
    if coach_ids_raw is None:
        coach_ids = None
    elif isinstance(coach_ids_raw, list):
        if not coach_ids_raw:
            raise ValueError("coach_ids must be null or a non-empty list")
        coach_ids = [str(x) for x in coach_ids_raw]
    else:
        raise ValueError("coach_ids must be a list or null")

    depth_raw = data.get("reconnect_replay_depth", 50)
    # bool is a subclass of int — reject explicitly so `true`/`false` aren't
    # silently coerced to 1/0.
    if isinstance(depth_raw, bool) or not isinstance(depth_raw, int):
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
    except RuntimeError as exc:  # pragma: no cover  # defence-in-depth
        # Binary frame as the first message, or other protocol violation.
        log.warning("ws.handshake_protocol_error", name=name, error=str(exc))
        try:
            await websocket.close(code=1003)
        except RuntimeError:
            pass
        return

    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("subscription frame must be a JSON object")
        subscription = _parse_subscription(data)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        log.warning("ws.invalid_subscription", name=name, error=str(exc))
        try:
            await websocket.close(code=1003)
        except RuntimeError:
            pass
        return

    subscriber = Subscriber(
        websocket=websocket,
        subscription=subscription,
        name=name,
    )

    # REGISTER FIRST (code-review decision 1, 2026-05-20). Any event broadcast
    # from this point onward queues into subscriber.queue. Replay below will
    # populate subscriber.pending_replay_ids so the writer task dedupes the
    # overlap when it starts draining.
    await broadcaster.add(subscriber)
    try:
        # Replay reads from DB and sends directly via websocket.send_text.
        # Events queued by concurrent producers during this window remain in
        # subscriber.queue, awaiting the writer.
        conn = get_connection()
        try:
            await replay_mod.replay_to(subscriber, conn)
        finally:
            conn.close()

        # Acknowledge AFTER replay completes so the client sees a clear
        # boundary between historical and live streams.
        try:
            await websocket.send_text(
                json.dumps({"status": "subscribed", "filter": data})
            )
        except WebSocketDisconnect:  # pragma: no cover  # rare ack-time disconnect
            log.info("ws.disconnected_before_live", name=name)
            return

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
            except Exception as exc:  # pragma: no cover  # defence-in-depth
                log.warning(
                    "ws.task_cleanup_error", name=name, error=str(exc)
                )
        for task in done:
            try:
                task.result()
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass
            except Exception as exc:  # pragma: no cover  # defence-in-depth
                log.warning(
                    "ws.task_terminal_error", name=name, error=str(exc)
                )
    finally:
        await broadcaster.remove(subscriber)
        log.info(
            "ws.disconnected",
            name=name,
            dropped=subscriber.dropped,
            deduped=subscriber.deduped,
        )
