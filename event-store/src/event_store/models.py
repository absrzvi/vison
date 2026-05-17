from __future__ import annotations

from oebb_shared.events.envelope import EventModel
from pydantic import BaseModel, Field


class EventPage(BaseModel):
    """Cursor-paginated event list.

    `next_cursor` is the `event_id` of the last returned item. When non-null,
    pass it as `?after=<next_cursor>` to fetch the next page. A non-null cursor
    on the last page (when result count equals the requested limit but no more
    rows exist) will return an empty `data: []` — callers must check `data`
    length, not just `next_cursor`, to detect end-of-stream.
    """

    items: list[EventModel] = Field(alias="data", default_factory=list)
    count: int = 0
    journey_id: str | None = None
    next_cursor: str | None = None

    model_config = {"populate_by_name": True}


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


class IngestSingleResponse(BaseModel):
    event_id: str
    stored: bool


class HealthLiveResponse(BaseModel):
    status: str = "ok"


class HealthReadyResponse(BaseModel):
    status: str = "ok"
    db_connected: bool = True
