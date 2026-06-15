"""Alert-class kill-switch admin endpoints — story 10-1 AC12, E11-S4 auth swap.

JWT-protected: `require_role("admin")` (E11-S4 — was a shared X-Admin-Key, now
retired). Operated from the Control Centre "Alert Classes" admin screen. Every
state change is audited three ways: alert_class_state row, structured log with
source IP, and an ALERT_CLASS_DISABLED/REENABLED event envelope persisted to the
events table. The audit actor is `current_user.username` (the authenticated
admin), never a client-supplied body field (E11-S4 D1).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Request, Security
from oebb_shared.events import AlertClassStatePayload, EventEnvelope, EventType
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import CurrentUser, require_role
from ..database import get_db
from ..services.fanout_filter import alert_class_filter

log = structlog.get_logger()


router = APIRouter(
    prefix="/api/v1/admin/alert-classes",
    dependencies=[Security(require_role("admin"))],
)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _persist_audit_event(
    db: AsyncSession,
    *,
    event_type: str,
    alert_code: str,
    actor_name: str,
    source_ip: str,
) -> None:
    """Persist the admin audit event into the events table (landside-origin)."""
    today = datetime.now(UTC).strftime("%Y%m%d")
    payload = AlertClassStatePayload(
        alert_code=alert_code, actor_name=actor_name, source_ip=source_ip
    )
    env = EventEnvelope(
        journey_id=f"LANDSIDE_admin_{today}",
        vehicle_id="LANDSIDE",
        event_type=EventType(event_type),
        severity="info",
        source="cloud-backend",
        payload=payload.model_dump(),
    )
    ts = datetime.fromisoformat(env.timestamp.replace("Z", "+00:00"))
    await db.execute(
        text("""
            INSERT INTO journeys (journey_id, vehicle_id, trip_number, start_time)
            VALUES (:journey_id, :vehicle_id, :trip_number, :start_time)
            ON CONFLICT (journey_id) DO NOTHING
        """),
        {
            "journey_id": env.journey_id,
            "vehicle_id": env.vehicle_id,
            "trip_number": "admin",
            "start_time": ts,
        },
    )
    await db.execute(
        text("""
            INSERT INTO events
                (event_id, journey_id, vehicle_id, event_type, severity, source,
                 schema_version, timestamp, source_timestamp, payload)
            VALUES
                (:event_id, :journey_id, :vehicle_id, :event_type, :severity, :source,
                 :schema_version, :timestamp, :source_timestamp, :payload)
            ON CONFLICT ON CONSTRAINT uq_events_journey_type_source_ts DO NOTHING
        """),
        {
            "event_id": env.event_id,
            "journey_id": env.journey_id,
            "vehicle_id": env.vehicle_id,
            "event_type": event_type,
            "severity": env.severity,
            "source": env.source,
            "schema_version": env.schema_version,
            "timestamp": ts,
            "source_timestamp": ts,
            "payload": json.dumps(env.payload),
        },
    )


@router.post("/{alert_code}/disable")
async def disable_alert_class(
    alert_code: str,
    request: Request,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    source_ip = _client_ip(request)
    actor = current.username
    await db.execute(
        text("""
            INSERT INTO alert_class_state (alert_code, state, disabled_by, disabled_at)
            VALUES (:alert_code, 'disabled', :actor, NOW())
            ON CONFLICT (alert_code) DO UPDATE
            SET state = 'disabled', disabled_by = :actor, disabled_at = NOW()
        """),
        {"alert_code": alert_code, "actor": actor},
    )
    await _persist_audit_event(
        db,
        event_type="ALERT_CLASS_DISABLED",
        alert_code=alert_code,
        actor_name=actor,
        source_ip=source_ip,
    )
    await db.commit()
    alert_class_filter.invalidate()
    log.info(
        "admin.alert_class_disabled",
        alert_code=alert_code,
        actor_name=actor,
        request_source_ip=source_ip,
    )
    return {"alert_code": alert_code, "state": "disabled"}


@router.post("/{alert_code}/enable")
async def enable_alert_class(
    alert_code: str,
    request: Request,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    source_ip = _client_ip(request)
    actor = current.username
    await db.execute(
        text("""
            INSERT INTO alert_class_state (alert_code, state, enabled_by, enabled_at)
            VALUES (:alert_code, 'enabled', :actor, NOW())
            ON CONFLICT (alert_code) DO UPDATE
            SET state = 'enabled', enabled_by = :actor, enabled_at = NOW()
        """),
        {"alert_code": alert_code, "actor": actor},
    )
    await _persist_audit_event(
        db,
        event_type="ALERT_CLASS_REENABLED",
        alert_code=alert_code,
        actor_name=actor,
        source_ip=source_ip,
    )
    await db.commit()
    alert_class_filter.invalidate()
    log.info(
        "admin.alert_class_reenabled",
        alert_code=alert_code,
        actor_name=actor,
        request_source_ip=source_ip,
    )
    return {"alert_code": alert_code, "state": "enabled"}


@router.get("")
async def list_alert_classes(
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict[str, str | None]]]:
    rows = await db.execute(
        text("""
            SELECT alert_code, state, disabled_by, disabled_at, enabled_by, enabled_at
            FROM alert_class_state
            ORDER BY alert_code
        """)
    )
    return {
        "alert_classes": [
            {
                "alert_code": r.alert_code,
                "state": r.state,
                "disabled_by": r.disabled_by,
                "disabled_at": str(r.disabled_at) if r.disabled_at else None,
                "enabled_by": r.enabled_by,
                "enabled_at": str(r.enabled_at) if r.enabled_at else None,
            }
            for r in rows
        ]
    }
