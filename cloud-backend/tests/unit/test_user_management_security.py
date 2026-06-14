"""E11-S2 user management — unit security tests (no DB).

RED-first per dev-story DoD. Covers the boundary-level guarantees that don't need
a real Postgres: the bcrypt-rounds fail-closed floor (D6), the password-policy
Pydantic validators (D6), and the no-secret-in-output guarantee (AC7-7).

The role/auth/concurrency security tests that need a real DB live in
tests/integration/test_user_management.py.
"""
from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from cloud_backend.api.users import PasswordReset, UserCreate, UserOut, UserPatch

# ── D6 — bcrypt_rounds fail-closed floor ─────────────────────────────────────


def _settings_with(env: dict[str, str]):
    """Build a fresh Settings with the given env overrides applied, restoring the
    prior environment afterward. Settings reads the process env at construction."""
    from cloud_backend.config import Settings

    prev = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return Settings()
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.mark.unit
def test_bcrypt_rounds_below_floor_rejected_in_prod() -> None:
    """A cost below 10 in a non-test env fails at Settings load — the cheap test
    value cannot escape into a deployment (D6 fail-closed floor)."""
    with pytest.raises(ValidationError):
        _settings_with({"APP_ENV": "prod", "BCRYPT_ROUNDS": "4"})


@pytest.mark.unit
def test_bcrypt_rounds_below_floor_allowed_in_test_env() -> None:
    """The test env MAY lower the cost (that's the whole point — fast real-path
    integration tests)."""
    s = _settings_with({"APP_ENV": "test", "BCRYPT_ROUNDS": "4"})
    assert s.bcrypt_rounds == 4


@pytest.mark.unit
def test_bcrypt_rounds_prod_default_is_12() -> None:
    s = _settings_with({"APP_ENV": "prod", "BCRYPT_ROUNDS": "12"})
    assert s.bcrypt_rounds == 12


# ── D6 — password policy at the boundary ─────────────────────────────────────


@pytest.mark.unit
def test_password_below_min_length_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="x", password="short", role="operator")
    with pytest.raises(ValidationError):
        PasswordReset(password="short")


@pytest.mark.unit
def test_password_over_72_bytes_rejected_not_truncated() -> None:
    """The 72-byte cap closes the silent-truncation footgun: a >72-byte password
    is rejected at the boundary, never quietly hashed on its first 72 bytes."""
    too_long = "a" * 73
    with pytest.raises(ValidationError):
        UserCreate(username="x", password=too_long, role="operator")
    with pytest.raises(ValidationError):
        PasswordReset(password=too_long)


@pytest.mark.unit
def test_password_no_composition_rules() -> None:
    """NIST length-only: a 12-char all-lowercase password is accepted (no
    upper/digit/symbol requirement)."""
    u = UserCreate(username="x", password="abcdefghijkl", role="operator")
    assert u.password == "abcdefghijkl"


@pytest.mark.unit
def test_invalid_role_rejected() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="x", password="abcdefghijkl", role="superuser")


# ── AC7-7 — no secret in the response model ──────────────────────────────────


@pytest.mark.unit
def test_user_out_has_no_password_or_hash_field() -> None:
    fields = set(UserOut.model_fields)
    assert "password" not in fields
    assert "password_hash" not in fields
    assert fields == {"user_id", "username", "role", "is_active"}


# ── UserPatch — partial-update guard ─────────────────────────────────────────


@pytest.mark.unit
def test_user_patch_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        UserPatch()
    # one field is enough
    assert UserPatch(role="admin").role == "admin"
    assert UserPatch(is_active=False).is_active is False


# ── Security Tests 1, 2 — role gating (operator → 403 on every admin endpoint) ─
# These fire on require_role("admin") BEFORE any DB access, so they are unit-tier.
# (Concurrency / deactivated-mid-session / duplicate-enumeration tests that need a
# real DB live in tests/integration/test_user_management.py.)

from fastapi.testclient import TestClient  # noqa: E402

from cloud_backend.main import app  # noqa: E402

from .conftest import auth_header  # noqa: E402

_OPERATOR = auth_header(role="operator")
_ADMIN = auth_header(role="admin")

_ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/users", None),
    ("POST", "/api/v1/admin/users",
     {"username": "n", "password": "abcdefghijkl", "role": "operator"}),
    ("PATCH", "/api/v1/admin/users/some-id", {"is_active": False}),
    ("POST", "/api/v1/admin/users/some-id/reset-password", {"password": "abcdefghijkl"}),
]


@pytest.mark.unit
@pytest.mark.parametrize("method,path,body", _ADMIN_ENDPOINTS)
def test_operator_forbidden_on_every_admin_endpoint(
    method: str, path: str, body: dict | None
) -> None:
    """Security Test 1/2: an operator token → 403 on EVERY user-management endpoint
    (role enforced at the router, before any handler/DB work)."""
    with TestClient(app) as client:
        r = client.request(method, path, json=body, headers=_OPERATOR)
    assert r.status_code == 403, f"{method} {path} gave {r.status_code}, expected 403"
    assert r.json()["detail"]["error"] == "FORBIDDEN"


@pytest.mark.unit
@pytest.mark.parametrize("method,path,body", _ADMIN_ENDPOINTS)
def test_missing_token_unauthorized_on_every_admin_endpoint(
    method: str, path: str, body: dict | None
) -> None:
    """No token → 401 (not 403) on every endpoint."""
    with TestClient(app) as client:
        r = client.request(method, path, json=body)
    assert r.status_code == 401, f"{method} {path} gave {r.status_code}, expected 401"


@pytest.mark.unit
def test_operator_self_escalation_via_patch_is_403() -> None:
    """Security Test: an operator cannot PATCH any user to role=admin — the router
    gate rejects it before the role-change logic runs."""
    with TestClient(app) as client:
        r = client.patch(
            "/api/v1/admin/users/whoever",
            json={"role": "admin"},
            headers=_OPERATOR,
        )
    assert r.status_code == 403
