"""Broadcaster filter routing + slow-consumer drop — AC6, Dev Notes 5-6."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from oebb_shared.ws.subscription import SubscriptionRequest

from event_store.websocket.broadcaster import Broadcaster, Subscriber


def _envelope(
    *,
    event_type: str = "OCCUPANCY_UPDATE",
    severity: str = "info",
    car_id: str | None = "car-1",
) -> dict[str, object]:
    payload: dict[str, object] = {"car_id": car_id} if car_id else {}
    return {
        "event_id": "00000000-0000-4000-8000-000000000000",
        "event_type": event_type,
        "severity": severity,
        "payload": payload,
    }


def _subscriber(
    *,
    event_types: list[str] | None = None,
    min_severity: str = "info",
    coach_ids: list[str] | None = None,
    name: str = "sub-1",
    queue_max: int = 256,
) -> Subscriber:
    sub = Subscriber(
        websocket=MagicMock(),
        subscription=SubscriptionRequest(
            event_types=event_types or ["OCCUPANCY_UPDATE"],
            min_severity=min_severity,
            coach_ids=coach_ids,
            reconnect_replay_depth=0,
        ),
        name=name,
        queue=asyncio.Queue(maxsize=queue_max),
    )
    return sub


@pytest.mark.unit
async def test_broadcast_routes_to_matching_subscriber() -> None:
    bcast = Broadcaster()
    sub = _subscriber(event_types=["OCCUPANCY_UPDATE"])
    await bcast.add(sub)

    await bcast.broadcast(_envelope(event_type="OCCUPANCY_UPDATE"))

    assert sub.queue.qsize() == 1


@pytest.mark.unit
async def test_broadcast_skips_non_matching_event_type() -> None:
    bcast = Broadcaster()
    sub = _subscriber(event_types=["ALERT_RAISED"])
    await bcast.add(sub)

    await bcast.broadcast(_envelope(event_type="OCCUPANCY_UPDATE"))

    assert sub.queue.qsize() == 0


@pytest.mark.unit
async def test_broadcast_filters_by_min_severity() -> None:
    bcast = Broadcaster()
    sub = _subscriber(event_types=["ALERT_RAISED"], min_severity="critical")
    await bcast.add(sub)

    await bcast.broadcast(_envelope(event_type="ALERT_RAISED", severity="warning"))
    assert sub.queue.qsize() == 0

    await bcast.broadcast(_envelope(event_type="ALERT_RAISED", severity="critical"))
    assert sub.queue.qsize() == 1


@pytest.mark.unit
async def test_broadcast_filters_by_coach_ids() -> None:
    bcast = Broadcaster()
    sub = _subscriber(coach_ids=["car-2"])
    await bcast.add(sub)

    await bcast.broadcast(_envelope(car_id="car-1"))
    assert sub.queue.qsize() == 0

    await bcast.broadcast(_envelope(car_id="car-2"))
    assert sub.queue.qsize() == 1


@pytest.mark.unit
async def test_broadcast_full_queue_drops_event_for_that_subscriber_only() -> None:
    """Dev Notes 6 — slow consumer back-pressure: drop, don't block. The fast
    subscriber must still get every event."""
    bcast = Broadcaster()
    slow = _subscriber(name="slow", queue_max=2)
    fast = _subscriber(name="fast", queue_max=100)
    await bcast.add(slow)
    await bcast.add(fast)

    # Fill the slow queue beyond capacity.
    for _ in range(5):
        await bcast.broadcast(_envelope())

    assert slow.queue.qsize() == 2  # capped at maxsize
    assert slow.dropped == 3  # remaining were dropped, counter incremented
    assert fast.queue.qsize() == 5  # fast subscriber unaffected


@pytest.mark.unit
async def test_remove_subscriber_stops_delivery() -> None:
    bcast = Broadcaster()
    sub = _subscriber()
    await bcast.add(sub)
    await bcast.remove(sub)

    await bcast.broadcast(_envelope())

    assert sub.queue.qsize() == 0
    assert await bcast.subscriber_count() == 0
