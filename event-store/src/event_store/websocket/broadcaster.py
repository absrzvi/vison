"""In-process WebSocket event broadcaster — AC6.

One Broadcaster instance lives on ``app.state`` (set in main.py lifespan).
Subscribers register themselves on connect and deregister on disconnect.
Fan-out is non-blocking — slow consumers get their event dropped (their queue
is full) rather than blocking the writer path.

Design notes (see story Dev Notes 5-7):
- ``asyncio.Lock`` protects the subscriber set. All add/remove operations
  must be guarded — fixes the same class of race surfaced in story 4-6 review.
- Per-subscriber ``asyncio.Queue(maxsize=256)`` with ``put_nowait`` for
  back-pressure. One slow client must NOT stall every writer.
- Filter routing uses ``SubscriptionRequest.matches(event_type, severity,
  coach_id)`` from ``oebb_shared.ws.subscription``. Re-uses tested logic.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import WebSocket
from oebb_shared.ws.subscription import SubscriptionRequest

log = structlog.get_logger()

_QUEUE_MAX = 256


@dataclass(eq=False)
class Subscriber:
    """A connected WS client with its filter and per-connection delivery queue.

    ``eq=False`` so the dataclass remains hashable (identity-based) — required
    to live in the broadcaster's ``set``.
    """

    websocket: WebSocket
    subscription: SubscriptionRequest
    name: str
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=_QUEUE_MAX)
    )
    dropped: int = 0


def _coach_id_from_payload(envelope: dict[str, Any]) -> str | None:
    """Extract car_id from envelope payload for SubscriptionRequest filtering."""
    payload = envelope.get("payload") or {}
    if isinstance(payload, dict):
        car_id = payload.get("car_id")
        if isinstance(car_id, str):
            return car_id
    return None


class Broadcaster:
    """Owns the subscriber set and the broadcast fan-out."""

    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()
        self._lock = asyncio.Lock()

    async def add(self, subscriber: Subscriber) -> None:
        async with self._lock:
            self._subscribers.add(subscriber)
        log.info(
            "ws.subscriber_added",
            name=subscriber.name,
            event_types=subscriber.subscription.event_types,
            min_severity=subscriber.subscription.min_severity,
        )

    async def remove(self, subscriber: Subscriber) -> None:
        async with self._lock:
            self._subscribers.discard(subscriber)
        log.info(
            "ws.subscriber_removed",
            name=subscriber.name,
            dropped=subscriber.dropped,
        )

    async def subscriber_count(self) -> int:
        async with self._lock:
            return len(self._subscribers)

    async def broadcast(self, envelope: dict[str, Any]) -> None:
        """Fan-out one envelope to every matching subscriber.

        Filter is applied per-subscriber via ``SubscriptionRequest.matches``.
        On ``QueueFull`` the event is dropped for that subscriber only — log
        + increment a counter; never raise, never block the writer.
        """
        event_type = str(envelope.get("event_type", ""))
        severity = str(envelope.get("severity", ""))
        coach_id = _coach_id_from_payload(envelope)

        # Snapshot subscribers under the lock; do the broadcast outside it so
        # a slow put_nowait (none expected, but defensively) cannot stall add/remove.
        async with self._lock:
            targets = list(self._subscribers)

        for sub in targets:
            if not sub.subscription.matches(event_type, severity, coach_id):
                continue
            try:
                sub.queue.put_nowait(envelope)
            except asyncio.QueueFull:
                sub.dropped += 1
                log.warning(
                    "ws.subscriber_slow_dropped",
                    name=sub.name,
                    dropped_total=sub.dropped,
                    event_type=event_type,
                )
