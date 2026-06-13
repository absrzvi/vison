from __future__ import annotations

import json
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, Security
from oebb_shared.events.envelope import SUPPORTED_SCHEMA_VERSIONS, EventEnvelope
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db
from ..routes.alerts_sse import ALERT_EVENT_TYPES, publish_alert
from ..services.escalation_audit import record_raised
from ..services.fanout_filter import alert_class_filter
from ..services.heartbeat_ingest import upsert_heartbeat

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/events", dependencies=[Security(require_api_key)])


class IngestRequest(BaseModel):
    events: list[EventEnvelope] = Field(min_length=1, max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    duplicate_ids: list[str] = Field(default_factory=list)


@router.post("", response_model=IngestResponse, status_code=202)
async def ingest_events(
    body: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    accepted = 0
    duplicates: list[str] = []

    for ev in body.events:
        if ev.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            log.warning(
                "schema_version_unsupported",
                schema_version=ev.schema_version,
                event_id=ev.event_id,
            )
            continue

        # EventEnvelope.timestamp is a Z-suffixed ISO-8601 string (validated by
        # the shared model). The Postgres journeys.start_time and events.timestamp
        # columns are TIMESTAMP WITH TIME ZONE, so asyncpg needs a datetime.
        # Parse once per event — Z → +00:00 for fromisoformat compatibility.
        ts_dt = datetime.fromisoformat(ev.timestamp.replace("Z", "+00:00"))

        # Ensure journey row exists before inserting the event (FK constraint).
        # Uses ON CONFLICT DO NOTHING — journey metadata is upserted separately
        # by the vlan-pollers when a trip starts; this guard prevents FK violations
        # when events arrive before the journey creation path runs.
        await db.execute(
            text("""
                INSERT INTO journeys (journey_id, vehicle_id, trip_number, start_time)
                VALUES (:journey_id, :vehicle_id, :trip_number, :start_time)
                ON CONFLICT (journey_id) DO NOTHING
            """),
            {
                "journey_id": ev.journey_id,
                "vehicle_id": ev.vehicle_id,
                "trip_number": (
                    ev.journey_id.split("_")[1] if "_" in ev.journey_id else ev.journey_id
                ),
                "start_time": ts_dt,
            },
        )

        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
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
                "event_id": ev.event_id,
                "journey_id": ev.journey_id,
                "vehicle_id": ev.vehicle_id,
                "event_type": ev.event_type,
                "severity": ev.severity,
                "source": ev.source,
                "schema_version": ev.schema_version,
                "timestamp": ts_dt,
                "source_timestamp": ts_dt,
                "payload": json.dumps(ev.payload),
            },
        )

        if result.rowcount == 0:
            duplicates.append(ev.event_id)
            log.info("event_duplicate", event_id=ev.event_id)
        else:
            accepted += 1
            log.info("event_stored", event_id=ev.event_id, journey_id=ev.journey_id)
            # E10-S1 AC18: heartbeat upsert keyed by payload.train_id,
            # last_seen is server-side NOW().
            if ev.event_type == "INFERENCE_HEARTBEAT":
                await upsert_heartbeat(db, ev.payload)
            # E10-S6 AC2: create the authoritative escalation row from ALERT_RAISED.
            # escalation_id = the envelope event_id (the id the Control Centre uses in
            # its acknowledge/resolve URLs); alert_id from payload pairs ALERT_RESOLVED.
            # Review R1: EventEnvelope skips typed-payload validation when payload is
            # empty, so a malformed ALERT_RAISED with no alert_id/alert_code can reach
            # here. Skip the upsert (NOT-NULL columns) rather than 500 — log + move on.
            alert_id = ev.payload.get("alert_id")
            alert_code = ev.payload.get("alert_code")
            if ev.event_type == "ALERT_RAISED" and not (alert_id and alert_code):
                log.warning(
                    "escalation_skipped_missing_alert_fields",
                    event_id=ev.event_id,
                    has_alert_id=bool(alert_id),
                    has_alert_code=bool(alert_code),
                )
            elif ev.event_type == "ALERT_RAISED":
                esc_result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
                    text("""
                        INSERT INTO escalations
                            (escalation_id, alert_id, alert_event_id, alert_code,
                             journey_id, vehicle_id, status, t_fired,
                             confidence_score, confidence_basis, model_versions)
                        VALUES
                            (:escalation_id, :alert_id, :alert_event_id, :alert_code,
                             :journey_id, :vehicle_id, 'unacknowledged', :t_fired,
                             :confidence_score, :confidence_basis, :model_versions)
                        ON CONFLICT (escalation_id) DO NOTHING
                    """),
                    {
                        "escalation_id": ev.event_id,
                        "alert_id": alert_id,
                        "alert_event_id": ev.event_id,
                        "alert_code": alert_code,
                        "journey_id": ev.journey_id,
                        "vehicle_id": ev.vehicle_id,
                        "t_fired": ts_dt,
                        "confidence_score": ev.payload.get("confidence_score"),
                        "confidence_basis": ev.payload.get("confidence_basis"),
                        "model_versions": json.dumps(ev.payload.get("model_versions", {})),
                    },
                )
                # E10-S2 AC1: one 'raised' audit row per new escalation. Gate on the
                # escalations insert rowcount so a re-raised ALERT_RAISED (ON CONFLICT
                # DO NOTHING) does not append a duplicate audit row.
                if esc_result.rowcount == 1:
                    await record_raised(
                        db,
                        escalation_id=ev.event_id,
                        # Guaranteed truthy by the not-(alert_id and alert_code) guard
                        # above; str() narrows the untyped-payload Any|None to str.
                        alert_code=str(alert_code),
                        t_fired=ts_dt,
                        confidence_score=ev.payload.get("confidence_score"),
                        confidence_basis=ev.payload.get("confidence_basis"),
                        model_versions=ev.payload.get("model_versions", {}),
                    )
            # Fan-out alert-class events to SSE subscribers immediately.
            # E10-S1 AC13: kill-switch — disabled alert classes raised after
            # disabled_at are stored but never fanned out to Control Centre.
            if ev.event_type in ALERT_EVENT_TYPES and not await alert_class_filter.is_filtered(
                db, event_type=ev.event_type, payload=ev.payload, t_raised=ts_dt
            ):
                publish_alert({
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "severity": ev.severity,
                    "journey_id": ev.journey_id,
                    "vehicle_id": ev.vehicle_id,
                    "timestamp": ev.timestamp,
                    "payload": ev.payload,
                })

    await db.commit()
    return IngestResponse(accepted=accepted, duplicate_ids=duplicates)
