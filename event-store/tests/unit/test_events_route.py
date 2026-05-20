"""Unit tests for POST /api/v1/events — AC1 (201), AC2 (200 duplicate), AC4 (filters)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from event_store.database import get_connection, init_db
from event_store.main import app

_VALID_ENVELOPE = {
    "event_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
    "journey_id": "V001_RJ-0001_20260517",
    "vehicle_id": "V001",
    "timestamp": "2026-05-17T10:00:00Z",
    "event_type": "OCCUPANCY_UPDATE",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {
        "car_id": "car-1",
        "zone": None,
        "occupancy_count": 144,
        "occupancy_pct": 0.72,
        "capacity": 200,
        "service_tier": "standard",
    },
}


def _envelope(
    *,
    event_id: str,
    event_type: str = "OCCUPANCY_UPDATE",
    severity: str = "info",
    timestamp: str | None = None,
) -> dict[str, object]:
    env = dict(_VALID_ENVELOPE)
    env["event_id"] = event_id
    env["event_type"] = event_type
    env["severity"] = severity
    if timestamp:
        env["timestamp"] = timestamp
    return env


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """TestClient backed by a tmp_path SQLite file — no /data/ dependency.

    Pre-seeds the ``journeys`` row referenced by ``_VALID_ENVELOPE.journey_id``
    so ``GET /api/v1/events?journey_id=...`` does not 404 on a non-existent
    journey during filter tests.
    """
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        (_VALID_ENVELOPE["journey_id"], "V001", "RJ-0001"),
    )
    conn.commit()
    conn.close()

    # Patch only the two attributes database.py reads — avoids MagicMock bleed.
    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.database.settings.cursor_page_size", 100):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.unit
def test_post_event_first_insert_returns_201_with_data_envelope(client: TestClient) -> None:
    r = client.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 201
    body = r.json()
    assert body == {
        "data": {
            "event_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
            "stored": True,
        }
    }


@pytest.mark.unit
def test_post_duplicate_returns_200_with_stored_false(client: TestClient) -> None:
    """AC2: duplicate (journey_id, event_type, timestamp) returns 200 — NOT 409."""
    client.post("/api/v1/events", json=_VALID_ENVELOPE)
    r = client.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "data": {
            "event_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
            "stored": False,
        }
    }


@pytest.mark.unit
def test_post_schema_version_999_returns_422(client: TestClient) -> None:
    """AC3: unsupported schema_version → 422 + service does not crash.

    The shared ``EventEnvelope`` model rejects unsupported ``schema_version`` at
    Pydantic validation time (returns FastAPI's standard 422 with a list of
    validation errors). The route layer's UnsupportedSchemaVersionError path is
    reached only if Pydantic accepts the value — for the canonical envelope
    today the validator catches it first. Either way: 422, no crash.
    """
    body = dict(_VALID_ENVELOPE)
    body["schema_version"] = 999
    r = client.post("/api/v1/events", json=body)
    assert r.status_code == 422
    # Service is still alive after the 422.
    r2 = client.get("/health/live")
    assert r2.status_code == 200


@pytest.mark.unit
def test_get_events_still_works(client: TestClient) -> None:
    """GET /api/v1/events must not be broken by the route rewrite."""
    r = client.get("/api/v1/events")
    assert r.status_code in (200, 404)


@pytest.mark.unit
def test_get_events_filter_by_event_type(client: TestClient) -> None:
    """AC4: repeatable event_type query param filters results."""
    # Seed: one OCCUPANCY_UPDATE, one ALERT_RAISED.
    alert_env = {
        "event_id": "11111111-1111-4111-8111-111111111111",
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": "V001",
        "timestamp": "2026-05-17T10:00:01Z",
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {
            "alert_id": "11111111-1111-4111-8111-111111111111",
            "alert_code": "slip_fall",
            "car_id": "car-1",
            "description": "fall detected",
        },
    }
    client.post("/api/v1/events", json=_VALID_ENVELOPE)
    client.post("/api/v1/events", json=alert_env)

    r = client.get("/api/v1/events", params={"event_type": "ALERT_RAISED"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["data"][0]["event_type"] == "ALERT_RAISED"


@pytest.mark.unit
def test_get_events_filter_by_min_severity(client: TestClient) -> None:
    """AC4: min_severity=warning excludes info-level events."""
    client.post("/api/v1/events", json=_VALID_ENVELOPE)  # info
    warn_env = _envelope(
        event_id="22222222-2222-4222-8222-222222222222",
        event_type="ALERT_RAISED",
        severity="warning",
        timestamp="2026-05-17T10:00:02Z",
    )
    warn_env["source"] = "fusion"
    warn_env["payload"] = {
        "alert_id": "22222222-2222-4222-8222-222222222222",
        "alert_code": "door_obstruction",
        "car_id": "car-1",
        "description": "door obstruction",
    }
    client.post("/api/v1/events", json=warn_env)

    r = client.get("/api/v1/events", params={"min_severity": "warning"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["data"][0]["severity"] == "warning"


@pytest.mark.unit
def test_get_events_filter_combination(client: TestClient) -> None:
    """AC4: combining event_type + min_severity + journey_id."""
    # info OCCUPANCY_UPDATE
    client.post("/api/v1/events", json=_VALID_ENVELOPE)
    # warning ALERT_RAISED
    warn_env = _envelope(
        event_id="33333333-3333-4333-8333-333333333333",
        event_type="ALERT_RAISED",
        severity="warning",
        timestamp="2026-05-17T10:00:03Z",
    )
    warn_env["source"] = "fusion"
    warn_env["payload"] = {
        "alert_id": "33333333-3333-4333-8333-333333333333",
        "alert_code": "x",
        "car_id": "car-1",
        "description": "x",
    }
    client.post("/api/v1/events", json=warn_env)

    r = client.get(
        "/api/v1/events",
        params={
            "journey_id": "V001_RJ-0001_20260517",
            "event_type": "ALERT_RAISED",
            "min_severity": "warning",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["data"][0]["event_type"] == "ALERT_RAISED"
    assert body["data"][0]["severity"] == "warning"
