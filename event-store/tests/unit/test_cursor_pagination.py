"""ADR-4 / AC11: cursor-based pagination returns (items, next_cursor)."""
import pytest
from oebb_shared.events.envelope import EventModel

from event_store.models import EventPage


@pytest.mark.unit
def test_event_page_has_next_cursor_when_full_page() -> None:
    _uuids = [
        f"a1b2c3d4-e5f6-4789-abcd-ef12345678{i:02d}" for i in range(3)
    ]
    items = [
        EventModel(
            event_id=_uuids[i],
            journey_id="V001_RJ-0001_20260517",
            vehicle_id="V001",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
            payload={},
        )
        for i in range(3)
    ]
    page = EventPage(items=items, next_cursor=_uuids[-1])
    assert page.next_cursor == _uuids[-1]
    assert len(page.items) == 3


@pytest.mark.unit
def test_event_page_has_no_cursor_on_last_page() -> None:
    items = [
        EventModel(
            event_id="a1b2c3d4-e5f6-4789-abcd-ef1234567890",
            journey_id="V001_RJ-0001_20260517",
            vehicle_id="V001",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
            payload={},
        )
    ]
    page = EventPage(items=items, next_cursor=None)
    assert page.next_cursor is None
