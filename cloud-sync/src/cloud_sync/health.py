"""GET /health endpoint — AC7.

Returns:
  {
    "status": "ok",
    "broker_connected": bool,
    "queue_depth": int,
    "last_publish_utc": "ISO-8601" | None
  }

Defensive (code-review 2026-05-20): when ``app.state.mqtt`` or
``app.state.queue_db_path`` is not set (request lands before lifespan
populates state, or in test harnesses without lifespan), return a
``"status": "starting"`` response with conservative defaults instead of
raising AttributeError → 500.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from . import db as db_mod

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Open endpoint — no auth (orchestrator probe)."""
    queue_db_path = getattr(request.app.state, "queue_db_path", None)
    mqtt = getattr(request.app.state, "mqtt", None)
    if queue_db_path is None or mqtt is None:
        return {
            "status": "starting",
            "broker_connected": False,
            "queue_depth": 0,
            "last_publish_utc": None,
        }
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
