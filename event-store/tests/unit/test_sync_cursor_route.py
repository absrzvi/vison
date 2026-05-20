"""POST /api/v1/sync/cursor — story 4-CS1 companion endpoint."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from event_store.database import get_connection, get_sync_cursor, init_db, insert_event
from event_store.main import app

_J1 = "V001_RJ-0001_20260517"
_E1 = "11111111-1111-4111-8111-111111111111"
_E2 = "22222222-2222-4222-8222-222222222222"
_E3 = "33333333-3333-4333-8333-333333333333"


def _envelope(event_id: str, journey_id: str, ts: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "journey_id": journey_id,
        "vehicle_id": "V001",
        "timestamp": ts,
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {
            "car_id": "car-1",
            "occupancy_count": 1,
            "occupancy_pct": 0.01,
            "capacity": 200,
            "service_tier": "standard",
        },
    }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        (_J1, "V001", "RJ-0001"),
    )
    conn.commit()
    insert_event(
        conn,
        {
            "event_id": _E1,
            "journey_id": _J1,
            "vehicle_id": "V001",
            "timestamp": "2026-05-17T10:00:00Z",
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "schema_version": 1,
            "payload": "{}",
        },
    )
    insert_event(
        conn,
        {
            "event_id": _E2,
            "journey_id": _J1,
            "vehicle_id": "V001",
            "timestamp": "2026-05-17T10:00:01Z",
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "schema_version": 1,
            "payload": "{}",
        },
    )
    conn.close()
    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.auth.settings.api_key", None):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def client_with_key(tmp_path: Path) -> TestClient:
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        (_J1, "V001", "RJ-0001"),
    )
    conn.commit()
    insert_event(
        conn,
        {
            "event_id": _E1,
            "journey_id": _J1,
            "vehicle_id": "V001",
            "timestamp": "2026-05-17T10:00:00Z",
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "schema_version": 1,
            "payload": "{}",
        },
    )
    conn.close()
    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.auth.settings.api_key", SecretStr("test-key")):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.unit
def test_post_cursor_advances_and_returns_data_envelope(client: TestClient) -> None:
    """AC9/AC12: happy path advances sync_state + returns data envelope."""
    r = client.post("/api/v1/sync/cursor", json={"last_event_id": _E1})
    assert r.status_code == 200
    body = r.json()
    assert body == {"data": {"acked": _E1, "truncated_journeys": 0}}


@pytest.mark.unit
def test_post_cursor_idempotent_on_same_id(client: TestClient) -> None:
    """Re-submitting the same cursor is a no-op (no truncate, no advance)."""
    r1 = client.post("/api/v1/sync/cursor", json={"last_event_id": _E1})
    assert r1.status_code == 200
    r2 = client.post("/api/v1/sync/cursor", json={"last_event_id": _E1})
    assert r2.status_code == 200
    body = r2.json()
    assert body == {"data": {"acked": _E1, "truncated_journeys": 0}}


@pytest.mark.unit
def test_post_cursor_unknown_event_id_returns_400(client: TestClient) -> None:
    """ADR-10 INVALID_CURSOR envelope on unknown event_id."""
    unknown = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    r = client.post("/api/v1/sync/cursor", json={"last_event_id": unknown})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "INVALID_CURSOR"
    assert detail["recoverable"] is False


@pytest.mark.unit
def test_post_cursor_missing_api_key_returns_401(client_with_key: TestClient) -> None:
    """Auth is enforced at the router level."""
    r = client_with_key.post("/api/v1/sync/cursor", json={"last_event_id": _E1})
    assert r.status_code == 401


@pytest.mark.unit
def test_post_cursor_correct_api_key_advances(client_with_key: TestClient) -> None:
    r = client_with_key.post(
        "/api/v1/sync/cursor",
        json={"last_event_id": _E1},
        headers={"X-API-Key": "test-key"},
    )
    assert r.status_code == 200


@pytest.mark.unit
def test_post_cursor_bad_uuid_returns_422(client: TestClient) -> None:
    """The Pydantic regex on last_event_id rejects non-UUIDs at validation time."""
    r = client.post("/api/v1/sync/cursor", json={"last_event_id": "not-a-uuid"})
    assert r.status_code == 422


@pytest.mark.unit
def test_post_cursor_advances_sync_state_table(tmp_path: Path) -> None:
    """Direct verification: after the POST, get_sync_cursor returns last_event_id."""
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        (_J1, "V001", "RJ-0001"),
    )
    conn.commit()
    insert_event(
        conn,
        {
            "event_id": _E1,
            "journey_id": _J1,
            "vehicle_id": "V001",
            "timestamp": "2026-05-17T10:00:00Z",
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "schema_version": 1,
            "payload": "{}",
        },
    )
    conn.close()

    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.auth.settings.api_key", None):
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.post("/api/v1/sync/cursor", json={"last_event_id": _E1})
            assert r.status_code == 200

    conn2 = get_connection(db_file)
    try:
        assert get_sync_cursor(conn2) == _E1
    finally:
        conn2.close()
