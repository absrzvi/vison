from __future__ import annotations

from fastapi import WebSocket

from oebb_shared.ws.subscription import SubscriptionRequest


async def websocket_stub(websocket: WebSocket) -> None:
    """Skeleton WebSocket handler — full fan-out implemented in Story 1-3."""
    await websocket.accept()
    raw = await websocket.receive_json()
    _sub = SubscriptionRequest(
        event_types=raw.get("event_types", []),
        min_severity=raw.get("min_severity", "info"),
        coach_ids=raw.get("coach_ids"),
        reconnect_replay_depth=raw.get("reconnect_replay_depth", 50),
    )
    # Acknowledge subscription; real fan-out loop deferred to Story 1-3
    await websocket.send_json({"status": "subscribed", "replay_depth": _sub.reconnect_replay_depth})
    await websocket.close()
