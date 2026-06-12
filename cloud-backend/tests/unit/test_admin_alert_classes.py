"""Story 10-1 ST1-ST4, ST6 + AC12 — X-Admin-Key kill-switch endpoints.

Security tests written RED-first per team convention.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.config import get_settings
from cloud_backend.database import get_db
from cloud_backend.main import app

pytestmark = pytest.mark.unit

_ADMIN_KEY = "test-admin-key-fixture"


@pytest.fixture(autouse=True)
def _admin_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CC_ADMIN_KEY", _ADMIN_KEY)
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None


class _CapturingSession:
    """Mock AsyncSession that records execute() calls and serves row results."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self._rows = rows or []
        self.commit = AsyncMock()

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> MagicMock:
        self.calls.append((str(stmt), params))
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter(self._rows))
        result.rowcount = 1
        return result


def _override_db(session: _CapturingSession) -> None:
    async def _gen() -> AsyncGenerator[Any, None]:
        yield session

    app.dependency_overrides[get_db] = _gen


@pytest.fixture(autouse=True)
def _clean_overrides() -> Any:
    yield
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# ST1/ST2 — auth: missing or wrong X-Admin-Key → 401
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/disable", "post"),
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/enable", "post"),
        ("/api/v1/admin/alert-classes", "get"),
    ],
)
@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong-key"}])
def test_missing_or_wrong_admin_key_returns_401(
    path: str, method: str, headers: dict[str, str]
) -> None:
    _override_db(_CapturingSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        if method == "post":
            r = client.post(path, headers=headers, json={"actor_name": "nomad-oncall"})
        else:
            r = client.get(path, headers=headers)
    assert r.status_code == 401


def test_auth_fails_closed_when_admin_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty CC_ADMIN_KEY must never mean 'no auth' — even the empty string
    header is rejected."""
    monkeypatch.setenv("CC_ADMIN_KEY", "")
    _override_db(_CapturingSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/X/disable",
            headers={"X-Admin-Key": ""},
            json={"actor_name": "a"},
        )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ST3 — empty actor_name → 422, nothing written
# ---------------------------------------------------------------------------


def test_empty_actor_name_returns_422_and_writes_nothing() -> None:
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
            headers={"X-Admin-Key": _ADMIN_KEY},
            json={"actor_name": ""},
        )
    assert r.status_code == 422
    assert session.calls == []


# ---------------------------------------------------------------------------
# AC12 — disable/enable upsert + paired audit events + response shape
# ---------------------------------------------------------------------------


def test_disable_upserts_and_emits_audit_event() -> None:
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
            headers={"X-Admin-Key": _ADMIN_KEY},
            json={"actor_name": "nomad-oncall"},
        )
    assert r.status_code == 200
    assert r.json() == {"alert_code": "UNATTENDED_BAG", "state": "disabled"}
    sql_blob = " ".join(sql for sql, _ in session.calls)
    assert "alert_class_state" in sql_blob
    assert "disabled" in sql_blob
    # Audit event envelope persisted to the events table
    assert any(
        params and params.get("event_type") == "ALERT_CLASS_DISABLED"
        for _, params in session.calls
    )
    session.commit.assert_awaited()


def test_enable_upserts_and_emits_reenabled_event() -> None:
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/enable",
            headers={"X-Admin-Key": _ADMIN_KEY},
            json={"actor_name": "nomad-oncall"},
        )
    assert r.status_code == 200
    assert r.json() == {"alert_code": "UNATTENDED_BAG", "state": "enabled"}
    assert any(
        params and params.get("event_type") == "ALERT_CLASS_REENABLED"
        for _, params in session.calls
    )


def test_get_alert_classes_returns_rows() -> None:
    row = MagicMock()
    row.alert_code = "UNATTENDED_BAG"
    row.state = "disabled"
    row.disabled_by = "nomad-oncall"
    row.disabled_at = None
    row.enabled_by = None
    row.enabled_at = None
    session = _CapturingSession(rows=[row])
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/admin/alert-classes", headers={"X-Admin-Key": _ADMIN_KEY})
    assert r.status_code == 200
    body = r.json()
    assert body["alert_classes"][0]["alert_code"] == "UNATTENDED_BAG"
    assert body["alert_classes"][0]["state"] == "disabled"


# ---------------------------------------------------------------------------
# ST6 — structured audit log includes alert_code, actor_name, request_source_ip
# ---------------------------------------------------------------------------


def test_disable_logs_actor_and_source_ip() -> None:
    import structlog

    session = _CapturingSession()
    _override_db(session)
    with structlog.testing.capture_logs() as cap_logs:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.post(
                "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
                headers={"X-Admin-Key": _ADMIN_KEY},
                json={"actor_name": "nomad-oncall"},
            )
    entries = [e for e in cap_logs if e["event"] == "admin.alert_class_disabled"]
    assert len(entries) == 1
    assert entries[0]["alert_code"] == "UNATTENDED_BAG"
    assert entries[0]["actor_name"] == "nomad-oncall"
    assert "request_source_ip" in entries[0]


# ---------------------------------------------------------------------------
# ST4 — CC_ADMIN_KEY never hardcoded in repo source
# ---------------------------------------------------------------------------


def test_no_default_admin_key_in_settings() -> None:
    """Settings must not ship a baked-in admin key default."""
    import inspect

    from cloud_backend import config

    src = inspect.getsource(config)
    assert "cc_admin_key" in src
    # The default must be the empty string — anything else is a baked-in secret.
    assert 'cc_admin_key: str = ""' in src


def test_admin_key_literal_not_hardcoded_in_source_tree() -> None:
    """Grep the cloud-backend source tree for the live CC_ADMIN_KEY value.

    Allowed: .env.example (placeholder), tests (fixture values). The env var in
    this test session is the test fixture value — assert it appears nowhere
    under src/.
    """
    src_root = Path(__file__).parents[2] / "src"
    offenders = [
        str(p)
        for p in src_root.rglob("*.py")
        if _ADMIN_KEY in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
