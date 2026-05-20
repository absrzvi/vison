"""GET /health endpoint — AC7.

Returns:
  {
    "status": "ok",
    "broker_connected": bool,
    "queue_depth": int,
    "last_publish_utc": "ISO-8601" | None
  }
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from . import db as db_mod

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Open endpoint — no auth (orchestrator probe)."""
    queue_db_path: str = request.app.state.queue_db_path
    mqtt = request.app.state.mqtt  # MqttPublisher
    conn = db_mod.get_connection(queue_db_path)
    try:
        depth = db_mod.queue_depth(conn)
        last_pub = db_mod.last_publish_utc(conn)
    finally:
        conn.close()
    return {
        "status": "ok",
        "broker_connected": mqtt.broker_connected.is_set(),
        "queue_depth": depth,
        "last_publish_utc": last_pub,
    }
