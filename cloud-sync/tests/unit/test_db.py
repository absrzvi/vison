"""SQLite queue layer tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cloud_sync import db as db_mod


@pytest.fixture
def conn(tmp_path: Path):
    db_file = str(tmp_path / "queue.db")
    c = db_mod.get_connection(db_file)
    db_mod.init_db(c)
    yield c
    c.close()


def _envelope(event_id: str, ts: str, *, vehicle_id: str = "V001",
              event_type: str = "OCCUPANCY_UPDATE") -> dict:
    return {
        "event_id": event_id,
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": vehicle_id,
        "timestamp": ts,
        "event_type": event_type,
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {"car_id": "car-1"},
    }


@pytest.mark.unit
def test_enqueue_then_pending(conn) -> None:
    inserted = db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    assert inserted is True
    pending = db_mod.iter_pending(conn, limit=10)
    assert len(pending) == 1
    assert pending[0]["event_id"] == "e1"
    # envelope_json round-trips.
    assert json.loads(pending[0]["envelope_json"])["event_id"] == "e1"


@pytest.mark.unit
def test_enqueue_is_idempotent_on_duplicate_event_id(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    inserted_again = db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    assert inserted_again is False
    assert db_mod.queue_depth(conn) == 1


@pytest.mark.unit
def test_iter_pending_is_chronological(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e3", "2026-05-17T10:00:03Z"))
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:02Z"))
    pending = db_mod.iter_pending(conn, limit=10)
    assert [r["event_id"] for r in pending] == ["e1", "e2", "e3"]


@pytest.mark.unit
def test_mark_published_excludes_from_pending(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:01Z"))
    db_mod.mark_published(conn, "e1")
    pending = db_mod.iter_pending(conn, limit=10)
    assert [r["event_id"] for r in pending] == ["e2"]
    assert db_mod.queue_depth(conn) == 1


@pytest.mark.unit
def test_last_publish_utc_returns_max(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    assert db_mod.last_publish_utc(conn) is None
    db_mod.mark_published(conn, "e1")
    ts = db_mod.last_publish_utc(conn)
    assert ts is not None
    assert ts.endswith("Z")


@pytest.mark.unit
def test_mark_failed_increments_attempts(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    db_mod.mark_failed(conn, "e1", "broker reset")
    db_mod.mark_failed(conn, "e1", "broker reset")
    row = conn.execute(
        "SELECT attempts, last_error FROM publish_queue WHERE event_id = ?",
        ("e1",),
    ).fetchone()
    assert row["attempts"] == 2
    assert row["last_error"] == "broker reset"


@pytest.mark.unit
def test_cursor_state_get_initial(conn) -> None:
    pulled, acked = db_mod.cursor_state_get(conn)
    assert pulled is None
    assert acked is None


@pytest.mark.unit
def test_cursor_state_set_pulled_and_acked(conn) -> None:
    db_mod.cursor_state_set_pulled(conn, "e5")
    db_mod.cursor_state_set_acked(conn, "e3")
    pulled, acked = db_mod.cursor_state_get(conn)
    assert pulled == "e5"
    assert acked == "e3"


@pytest.mark.unit
def test_contiguous_published_prefix_walks_until_gap(conn) -> None:
    # Insert e1, e2, e3 in order. Publish e1+e2 but NOT e3.
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:02Z"))
    db_mod.enqueue_event(conn, _envelope("e3", "2026-05-17T10:00:03Z"))
    db_mod.mark_published(conn, "e1")
    db_mod.mark_published(conn, "e2")
    assert db_mod.contiguous_published_prefix(conn) == "e2"


@pytest.mark.unit
def test_contiguous_published_prefix_returns_none_when_first_is_pending(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:02Z"))
    # First is unpublished; even if e2 were published it's NOT contiguous from start.
    db_mod.mark_published(conn, "e2")
    assert db_mod.contiguous_published_prefix(conn) is None


@pytest.mark.unit
def test_delete_acked_removes_prefix(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:02Z"))
    db_mod.enqueue_event(conn, _envelope("e3", "2026-05-17T10:00:03Z"))
    db_mod.mark_published(conn, "e1")
    db_mod.mark_published(conn, "e2")
    deleted = db_mod.delete_acked(conn, "e2")
    assert deleted == 2
    remaining = conn.execute(
        "SELECT event_id FROM publish_queue ORDER BY timestamp"
    ).fetchall()
    assert [r["event_id"] for r in remaining] == ["e3"]


@pytest.mark.unit
def test_delete_acked_unknown_cursor_is_safe(conn) -> None:
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
    db_mod.mark_published(conn, "e1")
    deleted = db_mod.delete_acked(conn, "nonexistent")
    assert deleted == 0


@pytest.mark.unit
def test_init_db_idempotent(conn, tmp_path: Path) -> None:
    """Calling init_db twice should not error."""
    db_mod.init_db(conn)
    db_mod.init_db(conn)
    # Insert still works.
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    assert db_mod.queue_depth(conn) == 1
