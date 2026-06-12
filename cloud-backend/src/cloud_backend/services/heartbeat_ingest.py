"""INFERENCE_HEARTBEAT ingest hook — story 10-1 AC18.

Upserts train_inference_heartbeat on every heartbeat event. last_seen is
server-side NOW() — landside freshness must not trust onboard clocks.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def upsert_heartbeat(db: AsyncSession, payload: dict[str, Any]) -> None:
    await db.execute(
        text("""
            INSERT INTO train_inference_heartbeat
                (train_id, last_seen, model_versions, hailo_device_ok)
            VALUES (:train_id, NOW(), :model_versions, :hailo_device_ok)
            ON CONFLICT (train_id) DO UPDATE
            SET last_seen = NOW(),
                model_versions = :model_versions,
                hailo_device_ok = :hailo_device_ok
        """),
        {
            "train_id": str(payload.get("train_id", "")),
            "model_versions": json.dumps(payload.get("model_versions", {})),
            "hailo_device_ok": bool(payload.get("hailo_device_ok", False)),
        },
    )
