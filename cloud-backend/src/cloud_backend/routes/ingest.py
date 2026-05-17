from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from oebb_shared.events.envelope import EventModel
from ..database import get_db

router = APIRouter(prefix="/ingest")


class IngestRequest(BaseModel):
    events: list[EventModel] = Field(min_length=1, max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    duplicate_ids: list[str] = Field(default_factory=list)


@router.post("", response_model=IngestResponse, status_code=202)
def ingest_events(body: IngestRequest, db: Session = Depends(get_db)) -> IngestResponse:
    accepted = 0
    duplicates: list[str] = []
    for ev in body.events:
        result = db.execute(
            text("""
                INSERT INTO events
                    (event_id, journey_id, vehicle_id, timestamp, event_type, severity, source, schema_version, payload)
                VALUES
                    (:event_id, :journey_id, :vehicle_id, :timestamp, :event_type, :severity, :source, :schema_version, :payload)
                ON CONFLICT (event_id) DO NOTHING
            """),
            {**ev.model_dump(), "payload": ev.model_dump_json()},
        )
        if result.rowcount == 0:
            duplicates.append(ev.event_id)
        else:
            accepted += 1
    db.commit()
    return IngestResponse(accepted=accepted, duplicate_ids=duplicates)
