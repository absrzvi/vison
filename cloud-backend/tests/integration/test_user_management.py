"""E11-S2 user management — integration (real Postgres via testcontainers).

A1 hard gate: these MUST run and pass before review. A3: the acting admin is
seeded via the REAL creation path (the app's bcrypt), never a raw INSERT of a
hand-computed hash — so a green test cannot pass while the hash/verify pairing is
broken.

Covers:
- test_user_management_end_to_end         — create→login→deactivate→token-401→reset (A3, AC1/3/4)
- test_deactivation_kills_both_extractors  — AC3/D2 trap: header AND ?token= 401 after deactivation
- test_fresh_user_first_token_passes_liveness — AC1↔D2 rider (is_active default true)
- test_seam_liveness_survives_verifier_swap — D2 seam ruling: liveness fires after an issuer swap
- test_last_admin_guard_*                   — AC6/D3 lock-out, incl. concurrent
- test_duplicate_username_uniform_conflict  — Security Test 3
- test_audit_row_per_mutation              — AC5
- test_migration_0010_genuinely_reapplies   — AC8
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")

_JWT_SECRET = "integration-test-secret-0123456789abcdef0123456789"
_ISSUER = "oebb-cloud-backend"


@pytest.fixture(scope="module", autouse=True)
def _jwt_env() -> Generator[None, None, None]:
    prev = {k: os.environ.get(k) for k in ("JWT_SECRET", "JWT_ISSUER", "JWT_ALGORITHM")}
    os.environ["JWT_SECRET"] = _JWT_SECRET
    os.environ["JWT_ISSUER"] = _ISSUER
    os.environ["JWT_ALGORITHM"] = "HS256"
    try:
        yield
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        from alembic import command
        from alembic.config import Config

        prev = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        try:
            cfg = Config(_ALEMBIC_INI)
            cfg.set_main_option("sqlalchemy.url", url)
            command.upgrade(cfg, "head")
            yield url
        finally:
            if prev is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = prev


@pytest_asyncio.fixture
async def factory(pg_url: str) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(pg_url)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(text("TRUNCATE user_audit, users RESTART IDENTITY CASCADE"))
        await session.commit()
    try:
        yield sm
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def app_client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    from cloud_backend.database import get_db
    from cloud_backend.main import app

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_user(
    factory: async_sessionmaker[AsyncSession],
    *,
    username: str,
    password: str,
    role: str,
) -> str:
    """Seed via the REAL creation path (A3) — the app's bcrypt, not a raw hash."""
    from cloud_backend.routes.auth import create_user

    async with factory() as session:
        return await create_user(session, username=username, password=password, role=role)


async def _login(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── A3 — end-to-end on the real wire ─────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_management_end_to_end(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    # admin seeded via the real path; logs in to get an admin Bearer.
    await _seed_user(factory, username="admin1", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "admin1", "admin-pw-1234")

    # admin creates an operator via the API
    r = await app_client.post(
        "/api/v1/admin/users",
        json={"username": "op1", "password": "operator-pw-12", "role": "operator"},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 201, r.text
    op_body = r.json()
    op_id = op_body["user_id"]
    assert "password" not in op_body and "password_hash" not in op_body  # AC7-7

    # the new operator can immediately log in (proves the real hash/verify pairing)
    op_t = await _login(app_client, "op1", "operator-pw-12")
    me = await app_client.get("/api/v1/auth/me", headers=_bearer(op_t))
    assert me.json()["role"] == "operator"

    # admin deactivates the operator
    r = await app_client.patch(
        f"/api/v1/admin/users/{op_id}",
        json={"is_active": False},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False

    # (AC3a) the operator's existing token now 401s mid-session
    after = await app_client.get("/api/v1/fleet/overview", headers=_bearer(op_t))
    assert after.status_code == 401

    # (AC3a) and the operator can no longer log in
    bad_login = await app_client.post(
        "/api/v1/auth/login", json={"username": "op1", "password": "operator-pw-12"}
    )
    assert bad_login.status_code == 401

    # reactivate → operator can log in again
    r = await app_client.patch(
        f"/api/v1/admin/users/{op_id}",
        json={"is_active": True},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 200
    await _login(app_client, "op1", "operator-pw-12")  # reactivated user can log in

    # (AC4) password reset rotates the credential
    r = await app_client.post(
        f"/api/v1/admin/users/{op_id}/reset-password",
        json={"password": "brand-new-pw-9"},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 204, r.text
    # old creds now fail, new creds work
    assert (
        await app_client.post(
            "/api/v1/auth/login", json={"username": "op1", "password": "operator-pw-12"}
        )
    ).status_code == 401
    await _login(app_client, "op1", "brand-new-pw-9")

    # (AC5) an audit row exists for each mutation: create, deactivate, reactivate, reset
    async with factory() as session:
        rows = await session.execute(
            text("SELECT action FROM user_audit WHERE target_user_id = :t ORDER BY created_at"),
            {"t": op_id},
        )
        actions = [r.action for r in rows]
    assert actions == ["create", "deactivate", "reactivate", "password_reset"], actions


# ── AC3 / D2 trap — deactivation kills BOTH extractors ───────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deactivation_kills_both_extractors(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    from fastapi import HTTPException

    from cloud_backend.api.auth import (
        create_access_token,
        get_current_user,
        get_current_user_from_query,
    )

    uid = await _seed_user(factory, username="sse-op", password="pw-sse-1234", role="operator")
    token = create_access_token(user_id=uid, username="sse-op", role="operator")

    # active: both extractors resolve
    async with factory() as s:
        assert (await get_current_user_from_query(token=token, db=s)).user_id == uid

    # deactivate directly
    async with factory() as s:
        await s.execute(text("UPDATE users SET is_active=false WHERE user_id=:u"), {"u": uid})
        await s.commit()

    # header extractor → 401 (over the real HTTP route)
    r = await app_client.get("/api/v1/fleet/overview", headers=_bearer(token))
    assert r.status_code == 401

    # query extractor (SSE ?token=) → 401 at the dependency AND the route
    async with factory() as s:
        with pytest.raises(HTTPException) as exc:
            await get_current_user_from_query(token=token, db=s)
        assert exc.value.status_code == 401
    r2 = await app_client.get(f"/api/v1/alerts/stream?token={token}")
    assert r2.status_code == 401

    # sanity: header extractor as a dependency also 401s for the dead user
    async with factory() as s:
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException):
            await get_current_user(creds=creds, db=s)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fresh_user_first_token_passes_liveness(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """AC1↔D2 rider: a just-created user's first token authenticates immediately —
    the 0009 is_active server-default resolves true on insert."""
    await _seed_user(factory, username="admin2", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "admin2", "admin-pw-1234")
    r = await app_client.post(
        "/api/v1/admin/users",
        json={"username": "fresh", "password": "fresh-pw-1234", "role": "operator"},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 201
    # create → login → authenticated call, no second mutation
    t = await _login(app_client, "fresh", "fresh-pw-1234")
    ok = await app_client.get("/api/v1/auth/me", headers=_bearer(t))
    assert ok.status_code == 200


# ── D2 seam ruling — liveness survives a verifier (issuer/key) swap ──────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seam_liveness_survives_verifier_swap(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """The liveness gate lives in the EXTRACTOR, not the crypto seam. Swap the
    verifier to a second issuer/key (as in 11-1's OIDC-swap test); a token minted
    by that external issuer verifies — but a DEACTIVATED user is still 401'd. Proves
    liveness is layered on top of verification, not folded into _verify_token.

    NOTE: this mutates JWT_SECRET/JWT_ISSUER in os.environ and restores them in a
    finally (NOT monkeypatch). monkeypatch restores at FUNCTION teardown, which
    interleaves badly with the module-scoped _jwt_env fixtures of OTHER integration
    modules in a full unit+integration run — leaking the alt secret and 401-ing a
    later module's valid token. An explicit try/finally restore is leak-proof."""
    uid = await _seed_user(factory, username="swap-op", password="pw-swap-1234", role="operator")

    alt_secret = "an-entirely-different-external-idp-key-9876543210"
    alt_issuer = "external-keycloak-realm"
    ext_token = jwt.encode(
        {
            "sub": uid,
            "username": "swap-op",
            "role": "operator",
            "iss": alt_issuer,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        alt_secret,
        algorithm="HS256",
    )

    _prev_secret = os.environ.get("JWT_SECRET")
    _prev_issuer = os.environ.get("JWT_ISSUER")
    try:
        # point verification at the external issuer/key (no route/extractor change)
        os.environ["JWT_SECRET"] = alt_secret
        os.environ["JWT_ISSUER"] = alt_issuer

        # active user with the externally-issued token → 200 (verification swapped in)
        ok = await app_client.get("/api/v1/fleet/overview", headers=_bearer(ext_token))
        assert ok.status_code == 200, ok.text

        # deactivate, then the SAME externally-issued, still-cryptographically-valid
        # token is rejected by the liveness gate → 401 (liveness survives the swap)
        async with factory() as s:
            await s.execute(
                text("UPDATE users SET is_active=false WHERE user_id=:u"), {"u": uid}
            )
            await s.commit()
        dead = await app_client.get("/api/v1/fleet/overview", headers=_bearer(ext_token))
        assert dead.status_code == 401
    finally:
        for k, v in (("JWT_SECRET", _prev_secret), ("JWT_ISSUER", _prev_issuer)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── AC6 / D3 — last-active-admin lock-out guard ──────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_admin_cannot_be_deactivated(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    aid = await _seed_user(factory, username="solo-admin", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "solo-admin", "admin-pw-1234")
    r = await app_client.patch(
        f"/api/v1/admin/users/{aid}",
        json={"is_active": False},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "CONFLICT"
    # still active
    async with factory() as s:
        row = (await s.execute(
            text("SELECT is_active FROM users WHERE user_id=:u"), {"u": aid}
        )).fetchone()
    assert row.is_active is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_admin_cannot_be_demoted(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    aid = await _seed_user(factory, username="solo-admin2", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "solo-admin2", "admin-pw-1234")
    r = await app_client.patch(
        f"/api/v1/admin/users/{aid}",
        json={"role": "operator"},
        headers=_bearer(admin_t),
    )
    assert r.status_code == 409, r.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_admin_guard_concurrent(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """D3 TOCTOU: two admins, deactivate BOTH concurrently. The FOR UPDATE guard
    must serialize them so at least one active admin always remains — at most one
    deactivation succeeds."""
    a1 = await _seed_user(factory, username="adminA", password="admin-pw-1234", role="admin")
    a2 = await _seed_user(factory, username="adminB", password="admin-pw-1234", role="admin")
    t1 = await _login(app_client, "adminA", "admin-pw-1234")

    # Fire both deactivations concurrently (admin t1 acts on both targets).
    async def _deact(target: str) -> int:
        r = await app_client.patch(
            f"/api/v1/admin/users/{target}",
            json={"is_active": False},
            headers=_bearer(t1),
        )
        return r.status_code

    codes = await asyncio.gather(_deact(a1), _deact(a2))
    # Security Test 6 (code-review P4): at MOST one deactivation may succeed, and
    # the guard must have fired at least once — a tautological "200 or 409 in codes"
    # would pass even on the catastrophic [200,200]. Pin the exact property.
    assert codes.count(200) <= 1, f"more than one deactivation succeeded: {codes}"
    assert 409 in codes, f"last-admin guard never fired: {codes}"
    async with factory() as s:
        remaining = (await s.execute(
            text("SELECT count(*) AS c FROM users WHERE role='admin' AND is_active=true")
        )).fetchone()
    assert remaining.c >= 1, f"all admins deactivated — lock-out! codes={codes}"


# ── Security Test 3 — duplicate username → uniform conflict ───────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_username_uniform_conflict(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_user(factory, username="admin3", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "admin3", "admin-pw-1234")
    body = {"username": "dup", "password": "operator-pw-12", "role": "operator"}
    first = await app_client.post("/api/v1/admin/users", json=body, headers=_bearer(admin_t))
    assert first.status_code == 201
    second = await app_client.post("/api/v1/admin/users", json=body, headers=_bearer(admin_t))
    assert second.status_code == 409
    # generic detail — does not echo the specific username back
    assert "dup" not in second.json()["detail"]["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_duplicate_create_is_409_not_500(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Code-review P1: two concurrent creates of the same username both pass the
    pre-check SELECT; the loser's INSERT hits uq_users_username. It must surface
    the uniform 409 (caught IntegrityError), NEVER an uncaught 500."""
    await _seed_user(factory, username="admin4", password="admin-pw-1234", role="admin")
    admin_t = await _login(app_client, "admin4", "admin-pw-1234")
    body = {"username": "racer", "password": "operator-pw-12", "role": "operator"}

    async def _create() -> int:
        r = await app_client.post("/api/v1/admin/users", json=body, headers=_bearer(admin_t))
        return r.status_code

    codes = await asyncio.gather(_create(), _create())
    assert codes.count(201) == 1, f"expected exactly one create to win: {codes}"
    assert codes.count(409) == 1, f"loser must be 409, not 500: {codes}"
    assert 500 not in codes


# ── AC8 — migration 0010 idempotent ──────────────────────────────────────────


@pytest.mark.integration
def test_migration_0010_genuinely_reapplies(pg_url: str) -> None:
    """Downgrade to 0009 then upgrade head — genuinely re-executes
    create_table("user_audit"). 0010 has no IF NOT EXISTS, so a broken re-apply
    raises DuplicateTable. Then assert the table + indexes + check constraint."""
    import psycopg2
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    _prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = pg_url
    try:
        command.downgrade(cfg, "0009")
        command.upgrade(cfg, "head")
    finally:
        if _prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev

    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.user_audit')")
        assert cur.fetchone()[0] == "user_audit", "user_audit table missing after re-apply"
        cur.execute(
            "SELECT 1 FROM pg_indexes WHERE tablename='user_audit' "
            "AND indexname IN ('ix_user_audit_target','ix_user_audit_actor')"
        )
        assert cur.fetchone() is not None, "user_audit indexes missing after re-apply"
        cur.execute("SELECT 1 FROM pg_constraint WHERE conname='ck_user_audit_action_valid'")
        assert cur.fetchone() is not None, "action check constraint missing after re-apply"
    finally:
        conn.close()
