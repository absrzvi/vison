from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException
from oebb_shared.events.envelope import SUPPORTED_SCHEMA_VERSIONS, EventModel
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/events")


class IngestRequest(BaseModel):
    events: list[EventModel] = Field(min_length=1, max_length=500)


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
                recoverable=True,
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "UNSUPPORTED_SCHEMA_VERSION",
                    "detail": f"schema_version {ev.schema_version} not supported",
                    "recoverable": False,
                },
            )
        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            text("""
                INSERT INTO events
                    (event_id, journey_id, vehicle_id, timestamp, event_type,
                     severity, source, schema_version, payload)
                VALUES
                    (:event_id, :journey_id, :vehicle_id, :timestamp, :event_type,
                     :severity, :source, :schema_version, :payload)
                ON CONFLICT (event_id) DO NOTHING
            """),
            {
                **ev.model_dump(exclude={"payload"}),
                "payload": json.dumps(ev.payload),
            },
        )
        if result.rowcount == 0:
            duplicates.append(ev.event_id)
            log.info("event_duplicate", event_id=ev.event_id)
        else:
            accepted += 1
            log.info("event_stored", event_id=ev.event_id, journey_id=ev.journey_id)
    await db.commit()
    return IngestResponse(accepted=accepted, duplicate_ids=duplicates)
