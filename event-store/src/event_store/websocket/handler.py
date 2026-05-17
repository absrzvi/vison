from __future__ import annotations

import json

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from oebb_shared.ws.subscription import SubscriptionRequest

log = structlog.get_logger()


async def websocket_stub(websocket: WebSocket) -> None:
    """Skeleton WebSocket handler — parses SubscriptionRequest and stays open.

    Full event fan-out implemented in Story E1-S6.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        data = json.loads(raw)
        sub = SubscriptionRequest(
            event_types=data.get("event_types", []),
            min_severity=data.get("min_severity", "info"),
            coach_ids=data.get("coach_ids"),
            reconnect_replay_depth=data.get("reconnect_replay_depth", 50),
        )
        log.info("ws_subscribed", event_types=sub.event_types, min_severity=sub.min_severity)
        await websocket.send_text(
            json.dumps({"status": "subscribed", "filter": data})
        )
        # Hold connection open — no event delivery in this story
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        log.info("ws_disconnected")
    except Exception:
        pass
