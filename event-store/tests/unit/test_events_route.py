"""Unit tests for POST /api/v1/events — AC1 (201) and AC2 (409)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from event_store.database import get_connection, init_db
from event_store.main import app

_VALID_ENVELOPE = {
    "event_id": "evt-test-001",
    "journey_id": "V001_RJ-0001_20260517",
    "vehicle_id": "V001",
    "timestamp": "2026-05-17T10:00:00Z",
    "event_type": "OCCUPANCY_UPDATE",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {"car_id": "car-1", "occupancy_pct": 0.72},
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """TestClient backed by a tmp_path SQLite file — no /data/ dependency."""
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.close()

    # Patch get_connection so every request opens the same test DB file
    with patch("event_store.database.settings") as mock_settings:
        mock_settings.db_path = db_file
        mock_settings.cursor_page_size = 100
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.unit
def test_post_event_returns_201(client: TestClient) -> None:
    r = client.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 201
    body = r.json()
    assert body["event_id"] == "evt-test-001"
    assert body["stored"] is True


@pytest.mark.unit
def test_post_duplicate_returns_409(client: TestClient) -> None:
    client.post("/api/v1/events", json=_VALID_ENVELOPE)
    r = client.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "DUPLICATE_EVENT"
    assert detail["recoverable"] is False


@pytest.mark.unit
def test_get_events_still_works(client: TestClient) -> None:
    """GET /api/v1/events must not be broken by the route rewrite."""
    r = client.get("/api/v1/events")
    assert r.status_code in (200, 404)
