from __future__ import annotations

import json
from datetime import UTC, datetime

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
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "UNSUPPORTED_SCHEMA_VERSION",
                    "detail": f"schema_version {ev.schema_version} not supported",
                    "recoverable": False,
                },
            )

        # source_timestamp defaults to envelope timestamp when not separately provided
        source_ts = datetime.now(UTC)

        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            text("""
                INSERT INTO events
                    (event_id, journey_id, event_type, severity, source,
                     timestamp, source_timestamp, payload)
                VALUES
                    (:event_id, :journey_id, :event_type, :severity, :source,
                     :timestamp, :source_timestamp, :payload)
                ON CONFLICT ON CONSTRAINT uq_events_journey_type_source_ts DO NOTHING
            """),
            {
                "event_id": ev.event_id,
                "journey_id": ev.journey_id,
                "event_type": ev.event_type,
                "severity": ev.severity,
                "source": ev.source,
                "timestamp": source_ts,
                "source_timestamp": source_ts,
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
