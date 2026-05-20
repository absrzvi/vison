"""X-API-Key auth dependency — AC8 + security tests."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

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
        "occupancy_count": 1,
        "occupancy_pct": 0.01,
        "capacity": 200,
        "service_tier": "standard",
    },
}


@pytest.fixture
def client_with_api_key(tmp_path: Path) -> TestClient:
    """TestClient where Settings.api_key is configured to 'test-key'."""
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.close()

    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.auth.settings.api_key", SecretStr("test-key")):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture
def client_no_api_key(tmp_path: Path) -> TestClient:
    """TestClient where Settings.api_key is None (dev-mode bypass)."""
    db_file = str(tmp_path / "test.db")
    conn = get_connection(db_file)
    init_db(conn)
    conn.close()

    with patch("event_store.database.settings.db_path", db_file), \
         patch("event_store.auth.settings.api_key", None):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


@pytest.mark.unit
def test_post_event_missing_api_key_returns_401(client_with_api_key: TestClient) -> None:
    r = client_with_api_key.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert detail["error"] == "UNAUTHENTICATED"
    assert detail["recoverable"] is False


@pytest.mark.unit
def test_post_event_wrong_api_key_returns_401(client_with_api_key: TestClient) -> None:
    r = client_with_api_key.post(
        "/api/v1/events", json=_VALID_ENVELOPE, headers={"X-API-Key": "wrong"}
    )
    assert r.status_code == 401


@pytest.mark.unit
def test_post_event_correct_api_key_returns_201(client_with_api_key: TestClient) -> None:
    r = client_with_api_key.post(
        "/api/v1/events", json=_VALID_ENVELOPE, headers={"X-API-Key": "test-key"}
    )
    assert r.status_code == 201


@pytest.mark.unit
def test_get_events_missing_api_key_returns_401(client_with_api_key: TestClient) -> None:
    r = client_with_api_key.get("/api/v1/events")
    assert r.status_code == 401


@pytest.mark.unit
def test_get_journey_missing_api_key_returns_401(client_with_api_key: TestClient) -> None:
    r = client_with_api_key.get("/api/v1/journeys/some-journey")
    assert r.status_code == 401


@pytest.mark.unit
def test_health_live_no_auth_required(client_with_api_key: TestClient) -> None:
    """Health endpoints MUST stay open — used by container orchestrators."""
    r = client_with_api_key.get("/health/live")
    assert r.status_code == 200


@pytest.mark.unit
def test_api_key_none_dev_mode_bypasses_auth(client_no_api_key: TestClient) -> None:
    """When api_key is None, requests without the header succeed (dev mode)."""
    r = client_no_api_key.post("/api/v1/events", json=_VALID_ENVELOPE)
    assert r.status_code == 201


@pytest.mark.unit
def test_api_key_uses_hmac_compare_digest() -> None:
    """Defence against timing-attack regressions. AST audit of auth.py asserts
    ``hmac.compare_digest`` is the comparison used."""
    auth_src = (
        Path(__file__).parent.parent.parent
        / "src"
        / "event_store"
        / "auth.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(auth_src)
    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "compare_digest"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "hmac"
        ):
            found = True
            break
    assert found, "auth.py must use hmac.compare_digest for constant-time comparison"


@pytest.mark.unit
def test_no_env_get_in_new_modules() -> None:
    """Rule 8 — no os.environ.get in new/modified modules."""
    src = Path(__file__).parent.parent.parent / "src" / "event_store"
    targets = [
        src / "auth.py",
        src / "websocket" / "broadcaster.py",
        src / "websocket" / "replay.py",
        src / "websocket" / "handler.py",
        src / "routes" / "events.py",
        src / "routes" / "journeys.py",
        src / "main.py",
    ]
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"
            ):
                raise AssertionError(f"{path.name} contains os.environ.get (Rule 8)")


@pytest.mark.unit
def test_empty_string_api_key_treated_as_dev_mode_bypass() -> None:
    """Code-review patch (2026-05-20): ``EVENT_STORE_API_KEY=""`` (empty
    string) must be normalised to None at config-load time, so a Docker
    compose default placeholder doesn't create a "looks configured but
    unreachable" deployment.
    """
    from event_store.config import Settings

    s = Settings(api_key=SecretStr(""))
    assert s.api_key is None


@pytest.mark.unit
def test_ws_endpoint_does_not_require_api_key_in_this_story(
    client_with_api_key: TestClient,
) -> None:
    """AC8 + Dev Notes Rule 9: WS auth is explicitly deferred in this story.

    The /ws endpoint must accept a connection without ``X-API-Key`` even when
    the REST API is auth-gated. WS auth lands in a future story.
    """
    sub = {
        "event_types": ["OCCUPANCY_UPDATE"],
        "min_severity": "info",
        "reconnect_replay_depth": 0,
    }
    # No X-API-Key header here — must succeed despite api_key configured.
    with client_with_api_key.websocket_connect("/ws") as ws:
        import json as _json

        ws.send_text(_json.dumps(sub))
        ack = _json.loads(ws.receive_text())
        assert ack["status"] == "subscribed"
