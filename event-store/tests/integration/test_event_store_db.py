"""Integration tests: real SQLite — insert, page, cursor, sync_state."""
import sqlite3
from pathlib import Path

import pytest

from event_store.database import (
    advance_sync_cursor,
    get_connection,
    get_events_page,
    get_sync_cursor,
    init_db,
    insert_event,
)
from event_store.exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError

_JOURNEY_ID = "V001_RJ-0001_20260516"

_BASE_EVENT = {
    "event_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
    "journey_id": _JOURNEY_ID,
    "vehicle_id": "V001",
    "timestamp": "2026-05-16T10:00:00Z",
    "event_type": "OCCUPANCY_UPDATE",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {"car_id": "car-1", "count": 45},
}


def _seed_journey(conn: sqlite3.Connection) -> None:
    """Insert the test journey row so get_events_page doesn't raise JourneyNotFoundError."""
    conn.execute(
        """
        INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number, start_time)
        VALUES (?, ?, ?, ?)
        """,
        (_JOURNEY_ID, "V001", "RJ-0001", "2026-05-16T08:00:00Z"),
    )
    conn.commit()


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    _seed_journey(conn)
    return conn


@pytest.mark.integration
def test_insert_and_retrieve(db: sqlite3.Connection) -> None:
    insert_event(db, _BASE_EVENT)
    rows = get_events_page(db, journey_id=_JOURNEY_ID)
    assert len(rows) == 1
    assert rows[0]["event_id"] == _BASE_EVENT["event_id"]
    assert rows[0]["payload"] == {"car_id": "car-1", "count": 45}


@pytest.mark.integration
def test_idempotent_insert_returns_false(db: sqlite3.Connection) -> None:
    assert insert_event(db, _BASE_EVENT) is True
    assert insert_event(db, _BASE_EVENT) is False  # duplicate
    rows = get_events_page(db, journey_id=_JOURNEY_ID)
    assert len(rows) == 1


@pytest.mark.integration
def test_journey_not_found_raises(db: sqlite3.Connection) -> None:
    with pytest.raises(JourneyNotFoundError):
        get_events_page(db, journey_id="nonexistent")


@pytest.mark.integration
def test_unsupported_schema_version_raises(db: sqlite3.Connection) -> None:
    bad_event = {
        **_BASE_EVENT,
        "event_id": "b2c3d4e5-f6a7-4890-bcde-f12345678901",
        "schema_version": 99,
    }
    with pytest.raises(UnsupportedSchemaVersionError):
        insert_event(db, bad_event)


@pytest.mark.integration
def test_cursor_pagination(db: sqlite3.Connection) -> None:
    uuids = [f"c{i}b2c3d4-e5f6-4789-abcd-ef12345678{i:02d}" for i in range(5)]
    for i in range(5):
        insert_event(
            db,
            {
                **_BASE_EVENT,
                "event_id": uuids[i],
                "timestamp": f"2026-05-16T10:0{i}:00Z",
            },
        )
    page1 = get_events_page(db, journey_id=_JOURNEY_ID, limit=3)
    assert len(page1) == 3
    cursor = page1[-1]["event_id"]
    page2 = get_events_page(db, journey_id=_JOURNEY_ID, after_event_id=cursor, limit=3)
    assert len(page2) == 2
    all_ids = {r["event_id"] for r in page1 + page2}
    assert len(all_ids) == 5


@pytest.mark.integration
def test_sync_cursor_advance(db: sqlite3.Connection) -> None:
    assert get_sync_cursor(db) == ""
    advance_sync_cursor(db, _BASE_EVENT["event_id"], "2026-05-16T10:00:00Z")
    assert get_sync_cursor(db) == _BASE_EVENT["event_id"]
