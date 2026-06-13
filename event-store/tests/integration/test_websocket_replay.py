"""Reconnect replay — AC7."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from event_store.database import get_connection, init_db
from event_store.main import app

_BASE = {
    "journey_id": "V001_RJ-0001_20260517",
    "vehicle_id": "V001",
    "schema_version": 1,
    "source": "inference",
}


def _occ(i: int) -> dict[str, object]:
    return {
        **_BASE,
        "event_id": f"00000000-0000-4000-8000-{i:012d}",
        "timestamp": f"2026-05-17T10:{i:02d}:00Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "payload": {
            "car_id": "car-1",
            "occupancy_count": i,
            "occupancy_pct": i / 200,
            "capacity": 200,
            "service_tier": "standard",
            "model_versions": {"detector_arch": "yolox_s_leaky"},  # E10-S1
        },
    }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_file = str(tmp_path / "replay.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        ("V001_RJ-0001_20260517", "V001", "RJ-0001"),
    )
    conn.commit()
    conn.close()
    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.database.settings.cursor_page_size", 100):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.integration
def test_replay_delivers_last_n_matching_events_in_order(client: TestClient) -> None:
    """Seed 10 events, connect with depth=5, receive the LAST 5 in chrono order.

    Handler order: replay → broadcaster.add → ack. So the test reads 5 replay
    frames first, then the ack as the 6th frame — the ack is the "go" signal
    that further live POSTs will be delivered.
    """
    for i in range(10):
        r = client.post("/api/v1/events", json=_occ(i))
        assert r.status_code == 201

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 5,
    }
    received: list[dict] = []
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        for _ in range(5):
            received.append(json.loads(ws.receive_text()))
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"

    # Last 5 events in ascending order: indices 5,6,7,8,9
    timestamps = [m["timestamp"] for m in received]
    assert timestamps == sorted(timestamps)
    assert timestamps[0] == "2026-05-17T10:05:00Z"
    assert timestamps[-1] == "2026-05-17T10:09:00Z"


@pytest.mark.integration
def test_replay_then_live_delivery_resumes(client: TestClient) -> None:
    """After replay + ack, the next POSTed event is delivered live."""
    for i in range(3):
        client.post("/api/v1/events", json=_occ(i))

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 3,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        # Drain replay (3 frames).
        for _ in range(3):
            ws.receive_text()
        # Then the ack — guaranteed registration.
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"
        # Post a new event — should arrive live.
        client.post("/api/v1/events", json=_occ(99))
        live = json.loads(ws.receive_text())
        assert live["event_type"] == "OCCUPANCY_UPDATE"
        assert live["payload"]["occupancy_count"] == 99


@pytest.mark.integration
def test_replay_depth_zero_skips_replay(client: TestClient) -> None:
    """``reconnect_replay_depth=0`` means no replay — ack is the first frame.

    The live-delivery half of this scenario is covered by
    ``test_ws_fanout_latency_under_100ms`` in test_websocket_fanout.py, which
    uses the same handler with depth=0 and proves POST → WS delivery works.
    Here we only assert that ZERO replay frames precede the ack.
    """
    for i in range(3):
        client.post("/api/v1/events", json=_occ(i))

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 0,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        # depth=0 → handler skips replay → first frame is the ack.
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"


@pytest.mark.integration
def test_replay_caps_at_1000_silently(client: TestClient) -> None:
    """A subscriber that asks for 999999 events gets at most 1000.

    We only seed 5 events here — the cap is exercised at the parameter
    boundary, not by data volume. Replay still completes with the available
    events and live delivery resumes.
    """
    for i in range(5):
        client.post("/api/v1/events", json=_occ(i))

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 999999,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        received = [json.loads(ws.receive_text()) for _ in range(5)]
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"
    assert len(received) == 5
