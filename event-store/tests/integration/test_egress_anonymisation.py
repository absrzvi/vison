"""Edge-egress anonymisation — GET /api/v1/events is the train→cloud boundary.

What cloud-sync pulls MUST be anonymised: no per-person track_id, no pixel bbox,
no camera locality, and no Article 9 ACCESSIBILITY_DETECTED. The local store and
the on-train WS fan-out keep full fidelity (asserted by the existing
test_websocket_fanout suite); these tests pin only the egress contract.

Cursor invariant (the subtle one): next_cursor is derived from the RAW DB page,
so a full page whose last row is a WITHHELD event still advances the cursor —
otherwise cloud-sync would re-pull the same page and stall on the gap forever.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from event_store.database import get_connection, init_db
from event_store.main import app

_JOURNEY = "V001_RJ-0001_20260517"

_BAG = {
    "event_id": "a1b2c3d4-e5f6-4789-abcd-ef1234567890",
    "journey_id": _JOURNEY,
    "vehicle_id": "V001",
    "timestamp": "2026-05-17T10:00:00Z",
    "event_type": "UNATTENDED_BAG",
    "severity": "warning",
    "source": "inference",
    "schema_version": 1,
    "payload": {
        "car_id": "car-3",
        "zone": None,
        "track_id": "bag-0042",
        "dwell_s": 180.0,
        "bbox": {"x": 412, "y": 308, "w": 64, "h": 48},
        "camera_id": "cam-3-02",
        "model_versions": {"detector_arch": "yolox_s_leaky"},
    },
}

_ACCESSIBILITY = {
    "event_id": "b1b2c3d4-e5f6-4789-abcd-ef1234567891",
    "journey_id": _JOURNEY,
    "vehicle_id": "V001",
    "timestamp": "2026-05-17T10:00:01Z",
    "event_type": "ACCESSIBILITY_DETECTED",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {
        "car_id": "car-2",
        "zone": None,
        "track_id": "person-0204",
        "assistance_type": ["wheelchair"],
        "camera_id": "cam-2-vest-b",
        "near_door_id": "car-2-door-R-1",
        "model_versions": {"detector_arch": "yolox_s_leaky"},
    },
}


_WAGON_EXIT = {
    "event_id": "c1b2c3d4-e5f6-4789-abcd-ef1234567892",
    "journey_id": _JOURNEY,
    "vehicle_id": "V001",
    "timestamp": "2026-05-17T10:00:02Z",
    "event_type": "WAGON_EXIT",
    "severity": "info",
    "source": "inference",
    "schema_version": 1,
    "payload": {
        "track_id": 312,
        "coach_from": "car-3",
        "coach_to": "car-4",
        "camera_id": "cam-3-gangway-fwd",
        "traversal": "from_to",
        "confidence": 0.88,
        "expect_orphan": False,
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
        (_JOURNEY, "V001", "RJ-0001"),
    )
    conn.commit()
    conn.close()
    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.database.settings.cursor_page_size", 100):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.integration
def test_egress_strips_bag_pii(client: TestClient) -> None:
    """UNATTENDED_BAG on the wire: no bbox, no camera_id, track_id tokenised."""
    assert client.post("/api/v1/events", json=_BAG).status_code == 201

    r = client.get("/api/v1/events", params={"event_type": "UNATTENDED_BAG"})
    assert r.status_code == 200
    payload = r.json()["data"][0]["payload"]
    assert "bbox" not in payload
    assert "camera_id" not in payload
    assert payload["track_id"] != "bag-0042"
    assert payload["track_id"].startswith("tk_")
    # Operational fields survive — the alert stays actionable for operators.
    assert payload["car_id"] == "car-3"
    assert payload["dwell_s"] == 180.0


@pytest.mark.integration
def test_egress_strips_wagon_pii(client: TestClient) -> None:
    """WAGON_EXIT on the wire: camera_id dropped (locality tied to a tracked
    person), int track_id tokenised to a str. (Round-2 P1+P2.)"""
    assert client.post("/api/v1/events", json=_WAGON_EXIT).status_code == 201

    r = client.get("/api/v1/events", params={"event_type": "WAGON_EXIT"})
    assert r.status_code == 200
    payload = r.json()["data"][0]["payload"]
    assert "camera_id" not in payload
    assert isinstance(payload["track_id"], str)
    assert payload["track_id"].startswith("tk_")
    # Operational fields survive — the traversal is still reconcilable in-cloud.
    assert payload["coach_from"] == "car-3"
    assert payload["coach_to"] == "car-4"


@pytest.mark.integration
def test_egress_withholds_accessibility_detected(client: TestClient) -> None:
    """ACCESSIBILITY_DETECTED (Article 9) must NOT appear in the cloud feed."""
    assert client.post("/api/v1/events", json=_ACCESSIBILITY).status_code == 201

    r = client.get("/api/v1/events")
    assert r.status_code == 200
    body = r.json()
    types = [e["event_type"] for e in body["data"]]
    assert "ACCESSIBILITY_DETECTED" not in types


@pytest.mark.integration
def test_withheld_event_still_advances_cursor(client: TestClient) -> None:
    """A full page whose LAST row is withheld must still advance next_cursor to
    that raw row's id — else cloud-sync stalls re-pulling the same gap.

    Seed [BAG, ACCESSIBILITY] and request limit=2 (a full page). The bag is
    redacted-but-present; the accessibility row is withheld, so data has 1 item,
    but next_cursor must equal the ACCESSIBILITY raw event_id.
    """
    assert client.post("/api/v1/events", json=_BAG).status_code == 201
    assert client.post("/api/v1/events", json=_ACCESSIBILITY).status_code == 201

    r = client.get("/api/v1/events", params={"limit": 2})
    assert r.status_code == 200
    body = r.json()
    # Full raw page (2 rows) but one withheld → 1 visible item.
    assert body["count"] == 1
    assert body["data"][0]["event_type"] == "UNATTENDED_BAG"
    # Cursor advances past the withheld tail so the next pull moves forward.
    assert body["next_cursor"] == _ACCESSIBILITY["event_id"]


@pytest.mark.integration
def test_non_pii_event_passes_through_unchanged(client: TestClient) -> None:
    """A normal OCCUPANCY_UPDATE crosses the boundary byte-for-byte."""
    occ = {
        "event_id": "c1b2c3d4-e5f6-4789-abcd-ef1234567892",
        "journey_id": _JOURNEY,
        "vehicle_id": "V001",
        "timestamp": "2026-05-17T10:00:02Z",
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
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        },
    }
    assert client.post("/api/v1/events", json=occ).status_code == 201

    r = client.get("/api/v1/events", params={"event_type": "OCCUPANCY_UPDATE"})
    assert r.status_code == 200
    assert r.json()["data"][0]["payload"] == occ["payload"]
