from __future__ import annotations

from oebb_shared.events.envelope import EventModel
from pydantic import BaseModel, Field


class EventPage(BaseModel):
    items: list[EventModel]
    next_cursor: str | None = None  # event_id of last item, None if no more pages


class JourneyMeta(BaseModel):
    journey_id: str
    vehicle_id: str
    trip_number: str
    route_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    start_time: str | None = None
    end_time: str | None = None


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


class HealthLiveResponse(BaseModel):
    status: str = "ok"


class HealthReadyResponse(BaseModel):
    status: str = "ok"
    db_connected: bool = True
