from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from oebb_shared.events.envelope import EventModel


class EventPage(BaseModel):
    items: list[EventModel]
    next_cursor: str | None = None  # event_id of last item, None if no more pages


class JourneyListItem(BaseModel):
    journey_id: str
    vehicle_id: str
    event_count: int
    first_seen: str
    last_seen: str


class IngestRequest(BaseModel):
    events: list[EventModel] = Field(min_length=1, max_length=500)


class IngestResponse(BaseModel):
    accepted: int
    duplicate_ids: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    db_path: str
    event_count: int
    extra: dict[str, Any] = Field(default_factory=dict)
