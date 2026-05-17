"""ADR-4 / AC11: cursor-based pagination returns (items, next_cursor)."""
import pytest

from event_store.models import EventPage
from oebb_shared.events.envelope import EventModel


@pytest.mark.unit
def test_event_page_has_next_cursor_when_full_page() -> None:
    items = [
        EventModel(
            event_id=f"id-{i}",
            journey_id="j1",
            vehicle_id="V001",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
            payload={},
        )
        for i in range(3)
    ]
    page = EventPage(items=items, next_cursor="id-2")
    assert page.next_cursor == "id-2"
    assert len(page.items) == 3


@pytest.mark.unit
def test_event_page_has_no_cursor_on_last_page() -> None:
    items = [
        EventModel(
            event_id="id-0",
            journey_id="j1",
            vehicle_id="V001",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
            payload={},
        )
    ]
    page = EventPage(items=items, next_cursor=None)
    assert page.next_cursor is None
