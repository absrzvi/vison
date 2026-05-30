from __future__ import annotations

import json
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from oebb_shared.events.envelope import SUPPORTED_SCHEMA_VERSIONS, EventEnvelope
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db
from ..routes.alerts_sse import ALERT_EVENT_TYPES, publish_alert

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
                "trip_number": ev.journey_id.split("_")[1] if "_" in ev.journey_id else ev.journey_id,
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
            # Fan-out alert-class events to SSE subscribers immediately
            if ev.event_type in ALERT_EVENT_TYPES:
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
