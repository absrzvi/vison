"""Integration tests for ADR-4: sync cursor SIGKILL safety, dedup, truncation."""
from __future__ import annotations

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
from event_store.sync.cursor import advance_cursor, truncate_old_journeys

_JOURNEY = "V001_RJ-0001_20260517"


def _make_event(n: int, journey_id: str = _JOURNEY) -> dict:
    return {
        "event_id": f"evt-{n:03d}",
        "journey_id": journey_id,
        "vehicle_id": "V001",
        "timestamp": f"2026-05-17T10:{n // 60:02d}:{n % 60:02d}Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {"car_id": "car-1", "count": n},
    }


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(str(tmp_path / "test.db"))
    init_db(conn)
    return conn


@pytest.mark.integration
def test_sigkill_no_data_loss(tmp_path: Path) -> None:
    """ADR-4 SIGKILL scenario: cursor advances, process dies before truncation.
    On restart all events must still be present and re-sync dedup works."""
    db_file = str(tmp_path / "sigkill_test.db")

    # Phase 1: insert 50 events and advance cursor
    conn1 = get_connection(db_file)
    init_db(conn1)
    events = [_make_event(i) for i in range(1, 51)]
    for ev in events:
        assert insert_event(conn1, ev) is True

    advance_cursor(conn1, "evt-050")
    assert get_sync_cursor(conn1) == "evt-050"

    # Simulate SIGKILL: close without truncation
    conn1.close()

    # Phase 2: restart — reopen DB
    conn2 = get_connection(db_file)
    init_db(conn2)

    # All 50 events still present (WAL commit survived)
    rows = get_events_page(conn2, journey_id=_JOURNEY, limit=100)
    assert len(rows) == 50, f"Expected 50 rows, got {len(rows)}"

    # Cursor position preserved
    assert get_sync_cursor(conn2) == "evt-050"

    # Dedup: re-syncing same events returns False (no new rows written)
    for ev in events:
        assert insert_event(conn2, ev) is False, f"Expected dedup for {ev['event_id']}"

    rows_after_resync = get_events_page(conn2, journey_id=_JOURNEY, limit=100)
    assert len(rows_after_resync) == 50
    conn2.close()


@pytest.mark.integration
def test_truncation_retains_last_3_journeys(tmp_path: Path) -> None:
    """Truncation removes events from journeys older than the last 3."""
    db_file = str(tmp_path / "truncate_test.db")
    conn = get_connection(db_file)
    init_db(conn)

    # Insert events for 5 different journeys (j1 = oldest, j5 = newest)
    journeys = [f"V001_RJ-{i:04d}_20260517" for i in range(1, 6)]
    for idx, jid in enumerate(journeys):
        for n in range(3):
            ev = _make_event(n, journey_id=jid)
            ev["event_id"] = f"evt-{idx:02d}-{n:02d}"
            # Stagger timestamps so newer journeys have later timestamps
            ev["timestamp"] = f"2026-05-17T{idx:02d}:{n:02d}:00Z"
            insert_event(conn, ev)

    # Verify 15 events total (5 journeys × 3 events)
    total_before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert total_before == 15

    deleted = truncate_old_journeys(conn, retain=3)

    # 2 oldest journeys deleted × 3 events each = 6 rows removed
    assert deleted == 6

    total_after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert total_after == 9

    # The 3 newest journeys remain
    remaining = {
        r[0] for r in conn.execute("SELECT DISTINCT journey_id FROM events").fetchall()
    }
    assert remaining == set(journeys[-3:])
    conn.close()


@pytest.mark.integration
def test_truncation_noop_when_fewer_than_retain(tmp_path: Path) -> None:
    """Truncation with fewer journeys than retain removes nothing."""
    db_file = str(tmp_path / "noop_test.db")
    conn = get_connection(db_file)
    init_db(conn)

    for n in range(5):
        insert_event(conn, _make_event(n))

    deleted = truncate_old_journeys(conn, retain=3)
    assert deleted == 0
    conn.close()


@pytest.mark.integration
def test_cursor_advance_persists(db: sqlite3.Connection) -> None:
    """Cursor advances atomically; value is readable after commit."""
    assert get_sync_cursor(db) == ""
    advance_cursor(db, "evt-099")
    assert get_sync_cursor(db) == "evt-099"
