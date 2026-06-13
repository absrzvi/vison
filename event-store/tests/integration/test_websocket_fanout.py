"""WebSocket fan-out — AC6, AC9 (latency < 100 ms)."""
from __future__ import annotations

import json
import time
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


def _occupancy(i: int, severity: str = "info") -> dict[str, object]:
    return {
        **_BASE,
        "event_id": f"00000000-0000-4000-8000-{i:012d}",
        "timestamp": f"2026-05-17T10:00:{i:02d}Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": severity,
        "payload": {
            "car_id": "car-1",
            "occupancy_count": i,
            "occupancy_pct": i / 200,
            "capacity": 200,
            "service_tier": "standard",
            "model_versions": {"detector_arch": "yolox_s_leaky"},  # E10-S1
        },
    }


def _alert(i: int) -> dict[str, object]:
    return {
        **_BASE,
        "source": "fusion",
        "event_id": f"11111111-1111-4111-8111-{i:012d}",
        "timestamp": f"2026-05-17T11:00:{i:02d}Z",
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "payload": {
            "alert_id": f"11111111-1111-4111-8111-{i:012d}",
            "alert_code": "slip_fall",
            "car_id": "car-1",
            "description": "fall detected",
            "confidence_score": 0.91,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},  # E10-S1
        },
    }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db_file = str(tmp_path / "ws.db")
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
def test_ws_fanout_routes_only_matching_events(client: TestClient) -> None:
    """Two clients with disjoint filters — each receives only matching events."""
    occ_sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 0,
    }
    alert_sub = {
        "event_types": ["ALERT_RAISED"],
        "min_severity": "warning",
        "reconnect_replay_depth": 0,
    }
    with client.websocket_connect("/ws") as occ_ws, \
         client.websocket_connect("/ws") as alert_ws:
        occ_ws.send_text(json.dumps(occ_sub))
        alert_ws.send_text(json.dumps(alert_sub))
        # Acknowledgements (no replay because depth=0; ack is the first frame).
        ack_occ = json.loads(occ_ws.receive_text())
        ack_alert = json.loads(alert_ws.receive_text())
        assert ack_occ["status"] == "subscribed"
        assert ack_alert["status"] == "subscribed"

        # Post one of each.
        r = client.post("/api/v1/events", json=_occupancy(1))
        assert r.status_code == 201
        r = client.post("/api/v1/events", json=_alert(1))
        assert r.status_code == 201

        # Each subscriber receives its single matching envelope.
        occ_msg = json.loads(occ_ws.receive_text())
        assert occ_msg["event_type"] == "OCCUPANCY_UPDATE"
        alert_msg = json.loads(alert_ws.receive_text())
        assert alert_msg["event_type"] == "ALERT_RAISED"


@pytest.mark.integration
def test_ws_fanout_latency_under_100ms(client: TestClient) -> None:
    """Latency between POST completing and WS receiving the message < 100 ms."""
    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 0,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"

        t0 = time.perf_counter()
        r = client.post("/api/v1/events", json=_occupancy(2))
        msg = json.loads(ws.receive_text())
        t1 = time.perf_counter()

        assert r.status_code == 201
        assert msg["event_id"].startswith("00000000")
    latency_ms = (t1 - t0) * 1000.0
    assert latency_ms < 100.0, f"fan-out latency {latency_ms:.2f}ms exceeds 100ms"


@pytest.mark.integration
def test_ws_min_severity_excludes_lower(client: TestClient) -> None:
    """Defence in depth: a client with min_severity=critical receives ZERO
    info/warning events even when posted (Security Tests)."""
    sub = {
        "event_types": ["ALERT_RAISED"],
        "min_severity": "critical",
        "reconnect_replay_depth": 0,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"
        # warning event — should NOT be delivered.
        client.post("/api/v1/events", json=_alert(3))
        # send a critical to flush the channel and confirm filter selectivity.
        critical = _alert(4)
        critical["severity"] = "critical"
        critical["event_id"] = "22222222-2222-4222-8222-000000000004"
        client.post("/api/v1/events", json=critical)

        msg = json.loads(ws.receive_text())
        assert msg["severity"] == "critical"
        assert msg["event_id"] == "22222222-2222-4222-8222-000000000004"


@pytest.mark.integration
def test_ws_no_raw_video_or_stream_url_in_messages(client: TestClient) -> None:
    """Security: no raw RTSP/file:// URLs in any WS message."""
    import re

    forbidden = re.compile(
        r"(rtsp://|rtmp://|file://|/dev/video|raw_video|\.h264\b|\.hevc\b|\.mp4\b)",
        re.IGNORECASE,
    )
    sub = {
        "event_types": ["OCCUPANCY_UPDATE", "ALERT_RAISED"],
        "min_severity": "info",
        "reconnect_replay_depth": 0,
    }
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(sub))
        ack = json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"
        client.post("/api/v1/events", json=_occupancy(5))
        client.post("/api/v1/events", json=_alert(5))
        for _ in range(2):
            raw = ws.receive_text()
            assert not forbidden.search(raw), f"forbidden pattern in WS msg: {raw}"


@pytest.mark.integration
def test_ws_rejects_empty_event_types_subscription(client: TestClient) -> None:
    """Code-review patch (2026-05-20): empty event_types makes a "deaf"
    subscriber (no live events, all replay events). Reject explicitly."""
    from starlette.websockets import WebSocketDisconnect

    sub = {"event_types": [], "min_severity": "info", "reconnect_replay_depth": 0}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps(sub))
            ws.receive_text()  # handler closes with 1003 before sending ack


@pytest.mark.integration
def test_ws_rejects_empty_coach_ids_subscription(client: TestClient) -> None:
    """Code-review patch (2026-05-20): empty coach_ids has inconsistent live
    vs replay semantics. Reject; client must send null or a non-empty list."""
    from starlette.websockets import WebSocketDisconnect

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "coach_ids": [],
        "reconnect_replay_depth": 0,
    }
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps(sub))
            ws.receive_text()


@pytest.mark.integration
def test_ws_rejects_bool_reconnect_replay_depth(client: TestClient) -> None:
    """Code-review patch (2026-05-20): ``true``/``false`` for depth must NOT
    be silently coerced to 1/0 (bool is a subclass of int)."""
    from starlette.websockets import WebSocketDisconnect

    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": True,
    }
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps(sub))
            ws.receive_text()
