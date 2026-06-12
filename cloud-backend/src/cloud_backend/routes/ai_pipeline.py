"""AI pipeline health — story 10-1 AC19."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db

router = APIRouter(prefix="/api/v1/health", dependencies=[Security(require_api_key)])

_STALE_S = 180.0  # 3 minutes
_RANK = {"green": 0, "amber": 1, "red": 2}


def _train_state(last_seen: datetime, hailo_device_ok: bool, now: datetime) -> str:
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if (now - last_seen).total_seconds() >= _STALE_S:
        return "red"
    return "green" if hailo_device_ok else "amber"


@router.get("/ai-pipeline")
async def ai_pipeline_health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    now = datetime.now(UTC)

    hb_rows = list(
        await db.execute(
            text("""
                SELECT train_id, last_seen, model_versions, hailo_device_ok
                FROM train_inference_heartbeat
                ORDER BY train_id
            """)
        )
    )
    active_rows = list(
        await db.execute(
            text("""
                SELECT DISTINCT vehicle_id
                FROM events
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """)
        )
    )

    trains: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in hb_rows:
        seen.add(r.train_id)
        last_seen = r.last_seen if r.last_seen.tzinfo else r.last_seen.replace(tzinfo=UTC)
        trains.append(
            {
                "train_id": r.train_id,
                "state": _train_state(r.last_seen, r.hailo_device_ok, now),
                "last_seen": last_seen.isoformat().replace("+00:00", "Z"),
                "model_versions": r.model_versions,
                "hailo_device_ok": r.hailo_device_ok,
            }
        )

    # Trains with recent events but no heartbeat row at all → red (AC19).
    # LANDSIDE is the admin audit pseudo-vehicle, never an inferencing train.
    for r in active_rows:
        if r.vehicle_id in seen or r.vehicle_id == "LANDSIDE":
            continue
        trains.append(
            {
                "train_id": r.vehicle_id,
                "state": "red",
                "last_seen": None,
                "model_versions": {},
                "hailo_device_ok": False,
            }
        )

    fleet_state = "green"
    for t in trains:
        if _RANK[t["state"]] > _RANK[fleet_state]:
            fleet_state = t["state"]

    return {"fleet_state": fleet_state, "trains": trains}
