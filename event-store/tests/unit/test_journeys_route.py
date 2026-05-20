"""GET /api/v1/journeys/{journey_id} — AC5 + AC8.

Verifies the typed ``JourneyMetaResponse`` envelope (code-review patch
2026-05-20 restoring the Pydantic response model).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from event_store.database import get_connection, init_db
from event_store.main import app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT INTO journeys (journey_id, vehicle_id, trip_number, route_name, "
        "origin, destination, start_time, end_time) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "V001_RJ-0001_20260517",
            "V001",
            "RJ-0001",
            "Vienna-Salzburg",
            "Wien Hbf",
            "Salzburg Hbf",
            "2026-05-17T08:00:00Z",
            "2026-05-17T11:00:00Z",
        ),
    )
    conn.commit()
    conn.close()
    with patch("event_store.database.settings.db_path", db_file):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.unit
def test_get_journey_returns_data_envelope(client: TestClient) -> None:
    """AC5: 200 + ``{"data": {...JourneyMeta...}}``."""
    r = client.get("/api/v1/journeys/V001_RJ-0001_20260517")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    meta = body["data"]
    assert meta["journey_id"] == "V001_RJ-0001_20260517"
    assert meta["vehicle_id"] == "V001"
    assert meta["trip_number"] == "RJ-0001"
    assert meta["route_name"] == "Vienna-Salzburg"


@pytest.mark.unit
def test_get_journey_unknown_returns_404_adr10(client: TestClient) -> None:
    """AC5: missing journey → 404 + ADR-10 error envelope."""
    r = client.get("/api/v1/journeys/UNKNOWN_RJ_99999999")
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["error"] == "JOURNEY_NOT_FOUND"
    assert detail["recoverable"] is False
