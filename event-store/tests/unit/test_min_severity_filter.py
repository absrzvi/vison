"""Severity ordering at the SQL layer — AC4."""
from __future__ import annotations

from pathlib import Path

import pytest

from event_store.database import get_connection, get_events_page, init_db, insert_event

_BASE = {
    "journey_id": "V001_RJ-0001_20260517",
    "vehicle_id": "V001",
    "source": "inference",
    "schema_version": 1,
    "payload": "{}",
}


def _row(*, event_id: str, severity: str, ts: str, event_type: str = "OCCUPANCY_UPDATE") -> dict:
    return {
        **_BASE,
        "event_id": event_id,
        "timestamp": ts,
        "event_type": event_type,
        "severity": severity,
    }


@pytest.fixture
def conn(tmp_path: Path):
    db_file = str(tmp_path / "test.db")
    c = get_connection(db_file)
    init_db(c)
    # Seed a journey so JourneyNotFoundError doesn't fire.
    c.execute(
        "INSERT INTO journeys (journey_id, vehicle_id, trip_number) VALUES (?,?,?)",
        ("V001_RJ-0001_20260517", "V001", "RJ-0001"),
    )
    c.commit()
    # Insert via the canonical INSERT OR IGNORE path to mirror real ingest.
    insert_event(c, _row(event_id="11111111-1111-4111-8111-111111111111",
                         severity="info", ts="2026-05-17T10:00:00Z"))
    insert_event(c, _row(event_id="22222222-2222-4222-8222-222222222222",
                         severity="warning", ts="2026-05-17T10:00:01Z"))
    insert_event(c, _row(event_id="33333333-3333-4333-8333-333333333333",
                         severity="critical", ts="2026-05-17T10:00:02Z"))
    yield c
    c.close()


@pytest.mark.unit
def test_min_severity_info_returns_all(conn) -> None:
    rows = get_events_page(conn, min_severity="info")
    assert len(rows) == 3


@pytest.mark.unit
def test_min_severity_warning_excludes_info(conn) -> None:
    rows = get_events_page(conn, min_severity="warning")
    sevs = {r["severity"] for r in rows}
    assert sevs == {"warning", "critical"}


@pytest.mark.unit
def test_min_severity_critical_returns_only_critical(conn) -> None:
    rows = get_events_page(conn, min_severity="critical")
    assert len(rows) == 1
    assert rows[0]["severity"] == "critical"


@pytest.mark.unit
def test_min_severity_none_returns_all(conn) -> None:
    rows = get_events_page(conn, min_severity=None)
    assert len(rows) == 3


@pytest.mark.unit
def test_event_types_filter(conn) -> None:
    # Insert one ALERT_RAISED row to verify the IN filter.
    insert_event(conn, _row(
        event_id="44444444-4444-4444-8444-444444444444",
        severity="info",
        ts="2026-05-17T10:00:03Z",
        event_type="ALERT_RAISED",
    ))
    rows = get_events_page(conn, event_types=["ALERT_RAISED"])
    assert len(rows) == 1
    assert rows[0]["event_type"] == "ALERT_RAISED"


@pytest.mark.unit
def test_event_types_multi_filter(conn) -> None:
    insert_event(conn, _row(
        event_id="55555555-5555-4555-8555-555555555555",
        severity="info",
        ts="2026-05-17T10:00:04Z",
        event_type="ALERT_RAISED",
    ))
    rows = get_events_page(conn, event_types=["ALERT_RAISED", "OCCUPANCY_UPDATE"])
    assert len(rows) == 4
