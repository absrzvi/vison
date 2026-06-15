"""Story 11-4 — alert-class kill-switch under JWT role auth (was X-Admin-Key).

E11-S4 swapped the router gate from `require_admin_key` (shared X-Admin-Key) to
`require_role("admin")`, and the audit actor from a body field to
`current_user.username`. Security tests written RED-first per team convention:
  ST1 — operator token → 403 on every endpoint
  ST2 — old X-Admin-Key, no Bearer → 401 (the curl path is dead)
  ST3 — authentication alone is insufficient (operator authenticated → 403, distinct from 401)
  ST4 — no body-supplied actor can override the token identity (actor is the token's username)

These are unit tests: `get_db` is mocked. The mock session also serves the
`assert_user_active` liveness SELECT (is_active=True) so a valid token resolves.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.api.auth import create_access_token
from cloud_backend.database import get_db
from cloud_backend.main import app

pytestmark = pytest.mark.unit

_JWT_SECRET = "unit-test-jwt-secret-0123456789abcdef0123456789"
_ADMIN_USERNAME = "claudia"
_ADMIN_UID = "00000000-0000-0000-0000-0000000000ad"
_OPERATOR_UID = "00000000-0000-0000-0000-0000000000a1"


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    monkeypatch.setenv("JWT_ISSUER", "oebb-cloud-backend")


def _admin_header() -> dict[str, str]:
    token = create_access_token(user_id=_ADMIN_UID, username=_ADMIN_USERNAME, role="admin")
    return {"Authorization": f"Bearer {token}"}


def _operator_header() -> dict[str, str]:
    token = create_access_token(user_id=_OPERATOR_UID, username="op1", role="operator")
    return {"Authorization": f"Bearer {token}"}


class _CapturingSession:
    """Mock AsyncSession that records execute() calls, serves the liveness row,
    and serves GET rows. `assert_user_active` does a SELECT is_active then
    `.fetchone()`; the kill-switch GET iterates the result. We return a result
    object that satisfies both shapes (an active row + iterability)."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self._rows = rows or []
        self.commit = AsyncMock()

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> MagicMock:
        self.calls.append((str(stmt), params))
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter(self._rows))
        # assert_user_active: SELECT is_active FROM users → fetchone().is_active
        live = MagicMock()
        live.is_active = True
        result.fetchone = MagicMock(return_value=live)
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
# ST1 / ST3 — operator token → 403 on every endpoint (authenticated, under-privileged)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/disable", "post"),
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/enable", "post"),
        ("/api/v1/admin/alert-classes", "get"),
    ],
)
def test_operator_token_forbidden_on_every_endpoint(path: str, method: str) -> None:
    """ST1+ST3 — a VALID operator token (auth succeeds, role check fails) → 403,
    not 401. Distinguishes 'authenticated but under-privileged' from 'no token'."""
    _override_db(_CapturingSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        if method == "post":
            r = client.post(path, headers=_operator_header())
        else:
            r = client.get(path, headers=_operator_header())
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# ST2 — old X-Admin-Key, no Bearer → 401 (the curl path is dead)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/disable", "post"),
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/enable", "post"),
        ("/api/v1/admin/alert-classes", "get"),
    ],
)
def test_old_admin_key_without_bearer_is_401(path: str, method: str) -> None:
    """The retired X-Admin-Key header carries no JWT → unauthenticated → 401.
    Confirms the swap left no dual-auth backdoor."""
    _override_db(_CapturingSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = {"X-Admin-Key": "any-old-value"}
        if method == "post":
            r = client.post(path, headers=headers)
        else:
            r = client.get(path, headers=headers)
    assert r.status_code == 401


def test_no_token_at_all_is_401() -> None:
    _override_db(_CapturingSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post("/api/v1/admin/alert-classes/X/disable")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# ST4 — no body-supplied actor can override the token identity
# ---------------------------------------------------------------------------


def test_body_supplied_actor_is_ignored_actor_is_token_username() -> None:
    """A spoof body {"actor_name": "spoofed"} must NOT set the audit actor — the
    actor is current_user.username. The body field no longer exists on the model,
    so the upsert/audit/log all bind the token's username."""
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
            headers=_admin_header(),
            json={"actor_name": "spoofed"},
        )
    assert r.status_code == 200
    # The alert_class_state upsert binds :actor = the token username, never "spoofed".
    actor_params = [p for _, p in session.calls if p and "actor" in p]
    assert actor_params, "expected an upsert binding :actor"
    assert all(p["actor"] == _ADMIN_USERNAME for p in actor_params)
    assert all(p["actor"] != "spoofed" for p in actor_params)
    # The persisted audit envelope carries the token username, not the body value.
    audit_params = [
        p for _, p in session.calls if p and p.get("event_type") == "ALERT_CLASS_DISABLED"
    ]
    assert audit_params
    assert _ADMIN_USERNAME in str(audit_params[0]["payload"])
    assert "spoofed" not in str(audit_params[0]["payload"])


# ---------------------------------------------------------------------------
# AC1/AC3 — disable/enable upsert + paired audit events + actor=token.username
# ---------------------------------------------------------------------------


def test_disable_upserts_and_emits_audit_event_with_token_actor() -> None:
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
            headers=_admin_header(),
        )
    assert r.status_code == 200
    assert r.json() == {"alert_code": "UNATTENDED_BAG", "state": "disabled"}
    sql_blob = " ".join(sql for sql, _ in session.calls)
    assert "alert_class_state" in sql_blob
    assert "disabled" in sql_blob
    assert any(
        params and params.get("event_type") == "ALERT_CLASS_DISABLED"
        for _, params in session.calls
    )
    # Actor on the upsert is the token's username (AC3).
    assert any(p and p.get("actor") == _ADMIN_USERNAME for _, p in session.calls)
    session.commit.assert_awaited()


def test_enable_upserts_and_emits_reenabled_event() -> None:
    session = _CapturingSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/admin/alert-classes/UNATTENDED_BAG/enable",
            headers=_admin_header(),
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
    row.disabled_by = _ADMIN_USERNAME
    row.disabled_at = None
    row.enabled_by = None
    row.enabled_at = None
    session = _CapturingSession(rows=[row])
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/admin/alert-classes", headers=_admin_header())
    assert r.status_code == 200
    body = r.json()
    assert body["alert_classes"][0]["alert_code"] == "UNATTENDED_BAG"
    assert body["alert_classes"][0]["state"] == "disabled"


# ---------------------------------------------------------------------------
# AC3 — structured audit log includes alert_code, actor_name (=username), source_ip
# ---------------------------------------------------------------------------


def test_disable_logs_token_actor_and_source_ip() -> None:
    import structlog

    session = _CapturingSession()
    _override_db(session)
    with structlog.testing.capture_logs() as cap_logs:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.post(
                "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
                headers=_admin_header(),
            )
    entries = [e for e in cap_logs if e["event"] == "admin.alert_class_disabled"]
    assert len(entries) == 1
    assert entries[0]["alert_code"] == "UNATTENDED_BAG"
    assert entries[0]["actor_name"] == _ADMIN_USERNAME
    assert "request_source_ip" in entries[0]
