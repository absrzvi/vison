"""Security tests for E11-S1 JWT auth — RED-first.

These are the 8 enumerated story Security Tests. They exercise the verification
core and role enforcement directly (unit-tier, no DB) plus the login
user-enumeration property via a dependency-overridden mock DB.

Every JWT-path rejection must be 401/403 with the ADR-10 envelope, never 500.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from cloud_backend.api.auth import (
    CurrentUser,
    create_access_token,
    get_current_user,
    require_role,
)
from cloud_backend.config import Settings, get_settings
from cloud_backend.database import get_db


async def _active_user_db() -> AsyncGenerator[AsyncMock, None]:
    """get_db override for the unit auth app: the E11-S2 liveness check
    (assert_user_active) does a `SELECT is_active ...` after token verification.
    These unit tests exercise the CRYPTO path (valid/invalid token, role), not
    deactivation — so the liveness SELECT must see an ACTIVE user. A bad token
    raises in _verify_token BEFORE this is reached, so it doesn't affect the
    rejection tests."""
    session = AsyncMock()

    async def _execute(stmt: object, params: object = None) -> MagicMock:
        result = MagicMock()
        row = MagicMock()
        row.is_active = True
        result.fetchone = MagicMock(return_value=row)
        return result

    session.execute = _execute
    yield session

# Use the suite-stable secret/issuer from the root conftest so a token minted
# here verifies consistently regardless of test ordering.
_SECRET = os.environ["JWT_SECRET"]
_ISSUER = os.environ["JWT_ISSUER"]


def _mint(
    *,
    secret: str = _SECRET,
    issuer: str = _ISSUER,
    algorithm: str = "HS256",
    sub: str = "u-1",
    role: str | None = "operator",
    exp_delta: timedelta = timedelta(minutes=60),
    include_exp: bool = True,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {"sub": sub, "username": "alice", "iss": issuer, "iat": now}
    if role is not None:
        claims["role"] = role
    if include_exp:
        claims["exp"] = now + exp_delta
    return jwt.encode(claims, secret, algorithm=algorithm)


def _app_with_protected() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def _protected(user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
        return {"user_id": user.user_id, "role": user.role}

    @app.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    async def _admin_only() -> dict[str, str]:
        return {"ok": "yes"}

    # The liveness check (E11-S2) makes get_current_user depend on get_db; in unit
    # tests we feed it an always-active user so the crypto-path assertions hold.
    app.dependency_overrides[get_db] = _active_user_db
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_app_with_protected())


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Security Test 1 — expired token → 401 (not 500) ──────────────────────────


@pytest.mark.unit
def test_expired_token_returns_401(client: TestClient) -> None:
    token = _mint(exp_delta=timedelta(minutes=-5))
    r = client.get("/protected", headers=_auth(token))
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "UNAUTHORIZED"


# ── Security Test 2 — tampered signature → 401 ───────────────────────────────


@pytest.mark.unit
def test_tampered_signature_returns_401(client: TestClient) -> None:
    token = _mint()
    # Reverse the whole signature segment — guaranteed to change the bytes. (A
    # last-char base64url A/B flip leaves the signature byte-identical ~5.5% of the
    # time because the trailing char carries only ~2 significant bits — a latent
    # flake; the verifier itself is correct.)
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[::-1]}"
    r = client.get("/protected", headers=_auth(tampered))
    assert r.status_code == 401


# ── Security Test 3 — alg:none / algorithm confusion → 401 ───────────────────


@pytest.mark.unit
def test_alg_none_token_returns_401(client: TestClient) -> None:
    # Unsigned token with alg=none — must be rejected by the algorithms allow-list.
    claims = {
        "sub": "u-1",
        "role": "operator",
        "iss": _ISSUER,
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    unsigned = jwt.encode(claims, key="", algorithm="none")
    r = client.get("/protected", headers=_auth(unsigned))
    assert r.status_code == 401


# ── Security Test 4 — wrong issuer → 401 ─────────────────────────────────────


@pytest.mark.unit
def test_wrong_issuer_returns_401(client: TestClient) -> None:
    token = _mint(issuer="evil-issuer")
    r = client.get("/protected", headers=_auth(token))
    assert r.status_code == 401


# ── Security Test 5 — operator token on admin route → 403 (not 401/500) ──────


@pytest.mark.unit
def test_operator_on_admin_route_returns_403(client: TestClient) -> None:
    token = _mint(role="operator")
    r = client.get("/admin-only", headers=_auth(token))
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "FORBIDDEN"


@pytest.mark.unit
def test_admin_on_admin_route_returns_200(client: TestClient) -> None:
    token = _mint(role="admin")
    r = client.get("/admin-only", headers=_auth(token))
    assert r.status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("bad_role", ["", "superuser", "Admin", "admin "])
def test_empty_or_junk_role_cannot_reach_admin_route(
    client: TestClient, bad_role: str
) -> None:
    """E11-S2 D7 / Security Test 5 (code-review P3): a token whose role is empty or
    not in the allow-list must NOT satisfy require_role('admin') — 403, never 200,
    never 500. Closes 11-1's deferred 'empty role authenticates' gap at the route
    level (the model-boundary role check doesn't cover a hand-minted token)."""
    token = _mint(role=bad_role)
    r = client.get("/admin-only", headers=_auth(token))
    assert r.status_code == 403, f"role={bad_role!r} reached admin route ({r.status_code})"
    assert r.json()["detail"]["error"] == "FORBIDDEN"


# ── Security Test 6 — missing role claim → 401/403, not 500 ──────────────────


@pytest.mark.unit
def test_missing_role_claim_does_not_500(client: TestClient) -> None:
    token = _mint(role=None)  # no role claim; options=require role → InvalidToken
    r = client.get("/protected", headers=_auth(token))
    assert r.status_code in (401, 403)


@pytest.mark.unit
def test_missing_token_returns_401(client: TestClient) -> None:
    r = client.get("/protected")
    assert r.status_code == 401


# ── Security Test 7 — login user-enumeration → uniform 401 ───────────────────


def _login_app(rows_for_query: list[Any]) -> FastAPI:
    """Build the real app with get_db overridden to return a session whose
    fetchone() yields rows_for_query[0] (or None)."""
    from cloud_backend.database import get_db
    from cloud_backend.main import app

    async def _override_db() -> AsyncGenerator[AsyncMock, None]:
        session = AsyncMock()

        async def _execute(stmt: object, params: object = None) -> MagicMock:
            result = MagicMock()
            result.fetchone = MagicMock(
                return_value=rows_for_query[0] if rows_for_query else None
            )
            return result

        session.execute = _execute
        session.commit = AsyncMock()
        yield session

    app.dependency_overrides[get_db] = _override_db
    return app


@pytest.mark.unit
def test_login_unknown_user_and_wrong_password_are_identical_401() -> None:
    from cloud_backend.api.auth import hash_password

    # Known user with a real hash; we'll send the WRONG password.
    real_row = MagicMock()
    real_row.user_id = "u-1"
    real_row.username = "alice"
    real_row.password_hash = hash_password("correct-horse")
    real_row.role = "operator"
    real_row.is_active = True

    app_known = _login_app([real_row])
    app_unknown = _login_app([])  # no such user

    try:
        c_known = TestClient(app_known)
        r_wrong_pw = c_known.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "WRONG"}
        )

        c_unknown = TestClient(app_unknown)
        r_unknown = c_unknown.post(
            "/api/v1/auth/login", json={"username": "ghost", "password": "WRONG"}
        )

        assert r_wrong_pw.status_code == 401
        assert r_unknown.status_code == 401
        # Byte-identical bodies — no enumeration signal.
        assert r_wrong_pw.json() == r_unknown.json()
    finally:
        app_known.dependency_overrides.clear()
        app_unknown.dependency_overrides.clear()


@pytest.mark.unit
def test_login_runs_password_verify_even_for_unknown_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the TIMING property, not just the response shape: the byte-identity test
    would still pass if a regression short-circuited `row is None` BEFORE the bcrypt
    verify (a timing oracle). Spy on verify_password and assert it IS called on the
    unknown-user path (against the dummy hash) — so the constant-time guard can't be
    silently removed."""
    import cloud_backend.routes.auth as auth_routes

    calls: list[tuple[str, str]] = []
    real_verify = auth_routes.verify_password

    def _spy(password: str, password_hash: str) -> bool:
        calls.append((password, password_hash))
        return real_verify(password, password_hash)

    monkeypatch.setattr(auth_routes, "verify_password", _spy)

    app_unknown = _login_app([])  # no such user
    try:
        c = TestClient(app_unknown)
        r = c.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
        assert r.status_code == 401
        # The dummy-hash verify MUST have run despite the user being absent.
        assert len(calls) == 1, "verify_password was not called on the unknown-user path"
        assert calls[0][1] == auth_routes._DUMMY_HASH
    finally:
        app_unknown.dependency_overrides.clear()


# ── Security Test 8 — empty jwt_secret fails closed ──────────────────────────


@pytest.mark.unit
def test_empty_secret_fails_closed_verify(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mint a token while the secret IS set...
    token = _mint()
    # ...then clear the secret; the previously-valid token must no longer verify.
    monkeypatch.setenv("JWT_SECRET", "")
    r = client.get("/protected", headers=_auth(token))
    assert r.status_code == 401


@pytest.mark.unit
def test_empty_secret_cannot_mint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    # get_settings() builds fresh from env, so jwt_secret is now "".
    assert get_settings().jwt_secret == ""
    with pytest.raises(ValueError, match="jwt_secret"):
        create_access_token(user_id="u-1", username="alice", role="operator")


# ── Sanity: a valid token resolves the user (AC2 positive path) ──────────────


@pytest.mark.unit
def test_valid_token_resolves_user(client: TestClient) -> None:
    token = create_access_token(user_id="u-9", username="bob", role="admin")
    r = client.get("/protected", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"user_id": "u-9", "role": "admin"}


@pytest.mark.unit
def test_settings_has_jwt_fields() -> None:
    s = Settings(jwt_secret="x")
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_issuer == "oebb-cloud-backend"
    assert s.jwt_access_ttl_minutes == 60
