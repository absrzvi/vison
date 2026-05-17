"""Integration tests: real SQLite — insert, page, cursor, sync_state."""
import sqlite3

import pytest

from event_store.database import (
    advance_sync_cursor,
    get_events_page,
    get_sync_cursor,
    init_db,
    insert_event,
)
from event_store.exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError


@pytest.fixture
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


_BASE_EVENT = {
    "event_id": "evt-001",
    "journey_id": "V001_RJ-0001_20260516",
    "vehicle_id": "V001",
    "timestamp": "2026-05-16T10:00:00Z",
    "event_type": "OCCUPANCY_UPDATE",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {"car_id": "car-1", "count": 45},
}


@pytest.mark.integration
def test_insert_and_retrieve(db: sqlite3.Connection) -> None:
    insert_event(db, _BASE_EVENT)
    rows = get_events_page(db, journey_id=_BASE_EVENT["journey_id"])
    assert len(rows) == 1
    assert rows[0]["event_id"] == "evt-001"
    assert rows[0]["payload"] == {"car_id": "car-1", "count": 45}


@pytest.mark.integration
def test_idempotent_insert_returns_false(db: sqlite3.Connection) -> None:
    assert insert_event(db, _BASE_EVENT) is True
    assert insert_event(db, _BASE_EVENT) is False  # duplicate
    rows = get_events_page(db, journey_id=_BASE_EVENT["journey_id"])
    assert len(rows) == 1


@pytest.mark.integration
def test_journey_not_found_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(JourneyNotFoundError):
        get_events_page(db, journey_id="nonexistent")


@pytest.mark.integration
def test_unsupported_schema_version_raises(db: sqlite3.Connection) -> None:
    bad_event = {**_BASE_EVENT, "event_id": "evt-bad", "schema_version": 99}
    with pytest.raises(UnsupportedSchemaVersionError):
        insert_event(db, bad_event)


@pytest.mark.integration
def test_cursor_pagination(db: sqlite3.Connection) -> None:
    for i in range(5):
        insert_event(
            db,
            {
                **_BASE_EVENT,
                "event_id": f"evt-{i:03d}",
                "timestamp": f"2026-05-16T10:0{i}:00Z",
            },
        )
    page1 = get_events_page(db, journey_id=_BASE_EVENT["journey_id"], limit=3)
    assert len(page1) == 3
    cursor = page1[-1]["event_id"]
    page2 = get_events_page(
        db, journey_id=_BASE_EVENT["journey_id"], after_event_id=cursor, limit=3
    )
    assert len(page2) == 2
    all_ids = {r["event_id"] for r in page1 + page2}
    assert len(all_ids) == 5


@pytest.mark.integration
def test_sync_cursor_advance(db: sqlite3.Connection) -> None:
    assert get_sync_cursor(db) == ""
    advance_sync_cursor(db, "evt-001", "2026-05-16T10:00:00Z")
    assert get_sync_cursor(db) == "evt-001"
