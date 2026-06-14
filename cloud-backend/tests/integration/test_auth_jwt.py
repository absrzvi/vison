"""E11-S1 JWT auth — integration (real Postgres via testcontainers + Alembic head).

A1 gate: these MUST run and pass before review. A3: the test user is created via
the REAL creation path (`routes.auth.create_user` → the app's bcrypt), never a
raw INSERT of a hand-computed hash — so a green test cannot pass while the real
hash/verify pairing is broken.

Covers:
- test_auth_flow_end_to_end    — create → login → Bearer → 200 → tamper → 401 (A3)
- test_protected_route_*        — every protected prefix 401s w/o token (AC5)
- test_open_route_*             — infra probes + login stay open (AC5/D3)
- test_seam_oidc_swap          — a 2nd issuer/key verifies via Settings (AC4)
- test_upgrade_head_idempotent — 0009 applies twice without error (AC9)
"""
from __future__ import annotations

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
        await session.execute(text("TRUNCATE users RESTART IDENTITY CASCADE"))
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
    """Seed via the REAL creation path (A3) — not a raw hash INSERT."""
    from cloud_backend.routes.auth import create_user

    async with factory() as session:
        return await create_user(session, username=username, password=password, role=role)


# ── A3 — end-to-end on the real wire ─────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_flow_end_to_end(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    user_id = await _seed_user(factory, username="alice", password="s3cret-pw", role="operator")

    # login → token
    r = await app_client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "s3cret-pw"}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    # Bearer → /auth/me resolves the real identity
    me = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json() == {"user_id": user_id, "username": "alice", "role": "operator"}

    # Bearer → a protected route works (fleet overview)
    ok = await app_client.get(
        "/api/v1/fleet/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert ok.status_code == 200, ok.text

    # tamper the signature → 401. Reverse the whole signature segment: guaranteed
    # to change the signature bytes (vs the old last-char A/B flip, which left the
    # signature byte-identical ~5% of the time because the trailing base64url char
    # carries only ~2 significant bits — a latent flake; the verifier itself is fine).
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[::-1]}"
    bad = await app_client.get(
        "/api/v1/fleet/overview", headers={"Authorization": f"Bearer {tampered}"}
    )
    assert bad.status_code == 401, bad.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password_401(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_user(factory, username="bob", password="right-pw", role="operator")
    r = await app_client.post(
        "/api/v1/auth/login", json={"username": "bob", "password": "WRONG"}
    )
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "UNAUTHORIZED"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inactive_user_cannot_login(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_user(factory, username="carol", password="pw-123456", role="operator")
    async with factory() as session:
        await session.execute(
            text("UPDATE users SET is_active = false WHERE username = 'carol'")
        )
        await session.commit()
    r = await app_client.post(
        "/api/v1/auth/login", json={"username": "carol", "password": "pw-123456"}
    )
    assert r.status_code == 401


# ── AC5 — every protected surface requires a token; probes + login stay open ──

# One real path per protected prefix (a 401 fires on the router dependency before
# routing, so any path under the prefix exercises the gate).
_PROTECTED_PATHS = [
    ("GET", "/api/v1/fleet/overview"),
    ("GET", "/api/v1/analytics/dwell-time?range=7d"),
    ("POST", "/api/v1/analytics/exceptions/x/review"),
    ("GET", "/api/v1/capacity-review-queue/export"),
    ("GET", "/api/v1/alerts/stream"),  # SSE: gated via ?token= query param (no token → 401)
    ("GET", "/api/v1/config/confidence-thresholds"),
    ("GET", "/api/v1/health/ai-pipeline"),
    ("GET", "/api/v1/ai-quality/resolution-rates"),
    ("POST", "/api/v1/maintenance/tickets"),
    ("GET", "/api/v1/operators/me/preferences"),
    ("POST", "/api/v1/escalations/x/acknowledge"),
    ("GET", "/api/v1/escalations-audit"),
    ("GET", "/api/v1/kpi/delay-minutes-avoided"),
    ("POST", "/api/v1/events"),
    ("GET", "/api/v1/health"),  # the auth-gated summary (NOT the infra probes)
]

_OPEN_PATHS = [
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _PROTECTED_PATHS)
async def test_protected_route_requires_token(
    app_client: AsyncClient, method: str, path: str
) -> None:
    r = await app_client.request(method, path)
    assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sse_query_token_gate_accepts_valid_rejects_invalid(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Positive + negative coverage for the ?token= SSE extractor
    (get_current_user_from_query) — the only route on that distinct code path. A
    regression in the query wiring would 401 a valid token while the negative
    no-token HTTP test still passed.

    The route body is a long-lived text/event-stream that blocks on the live queue,
    and httpx ASGITransport buffers the full response (it won't surface the head of
    a never-ending stream) — so we CANNOT exercise the valid path over HTTP without
    hanging. Instead we call the dependency directly for the valid token (proving it
    resolves the same CurrentUser via the shared _verify_token core) and assert the
    invalid/missing token is rejected both at the dependency AND over the real HTTP
    route (which short-circuits to 401 before any stream starts)."""
    from fastapi import HTTPException

    from cloud_backend.api.auth import (
        create_access_token,
        get_current_user_from_query,
    )

    # Seed an ACTIVE user via the real path so the E11-S2 liveness gate (added to
    # both extractors) passes for the valid-token case. Mint the token for THAT
    # user_id so sub matches the row.
    sse_uid = await _seed_user(
        factory, username="sse", password="pw-sse-12345", role="operator"
    )

    # Valid ?token= → resolves the user via the same verify core as the header path.
    token = create_access_token(user_id=sse_uid, username="sse", role="operator")
    async with factory() as session:
        user = await get_current_user_from_query(token=token, db=session)
    assert user.user_id == sse_uid
    assert user.role == "operator"

    # Invalid / missing ?token= → 401 at the dependency (raises in _verify_token
    # before the liveness check, so no db is needed).
    for bad in ("not-a-jwt", None):
        with pytest.raises(HTTPException) as exc:
            async with factory() as session:
                await get_current_user_from_query(token=bad, db=session)
        assert exc.value.status_code == 401

    # And over the real HTTP route the bad token short-circuits to 401 (no stream).
    resp = await app_client.get("/api/v1/alerts/stream?token=not-a-jwt")
    assert resp.status_code == 401
    resp2 = await app_client.get("/api/v1/alerts/stream")  # no token at all
    assert resp2.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _OPEN_PATHS)
async def test_open_route_does_not_require_token(
    app_client: AsyncClient, method: str, path: str
) -> None:
    r = await app_client.request(method, path)
    assert r.status_code != 401, f"{method} {path} returned 401 — infra probe must stay open"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_endpoint_stays_open(app_client: AsyncClient) -> None:
    # No token; invalid creds → 401 (auth failure), NOT 401-from-the-gate. The point
    # is the endpoint is reachable without a token (it does not 401 before the body
    # is processed — a 422 on a malformed body proves reachability too).
    r = await app_client.post("/api/v1/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 401  # invalid creds, but endpoint was reached
    # A malformed body would 422 (reached + validated), never a gate 401.
    r2 = await app_client.post("/api/v1/auth/login", json={})
    assert r2.status_code == 422


# ── AC4 — OIDC-swap seam: a second issuer verifies via Settings, no route edits ─


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seam_oidc_swap(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mint a token signed by a DIFFERENT issuer + key, point Settings at that
    issuer/key, and verify a protected route accepts it — WITHOUT editing any
    route. Proves verification is decoupled from issuance (the OIDC-swap guarantee).
    """
    user_id = await _seed_user(
        factory, username="dave", password="pw-abcdef", role="operator"
    )

    alt_secret = "an-entirely-different-external-idp-key-9876543210"
    alt_issuer = "external-keycloak-realm"
    ext_token = jwt.encode(
        {
            "sub": user_id,
            "username": "dave",
            "role": "operator",
            "iss": alt_issuer,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        alt_secret,
        algorithm="HS256",
    )

    # Before the swap: the app's issuer/key reject the external token.
    before = await app_client.get(
        "/api/v1/fleet/overview", headers={"Authorization": f"Bearer {ext_token}"}
    )
    assert before.status_code == 401

    # Swap verification config only (Settings) — no route or extractor code changes.
    monkeypatch.setenv("JWT_SECRET", alt_secret)
    monkeypatch.setenv("JWT_ISSUER", alt_issuer)

    after = await app_client.get(
        "/api/v1/fleet/overview", headers={"Authorization": f"Bearer {ext_token}"}
    )
    assert after.status_code == 200, after.text


# ── AC9 — migration 0009 idempotent ──────────────────────────────────────────


@pytest.mark.integration
def test_migration_0009_genuinely_reapplies(pg_url: str) -> None:
    """Actually RE-RUN 0009's DDL (downgrade to 0008 then upgrade head), not just
    a no-op `upgrade head` while already at head — which would never execute
    create_table again. 0009 has no IF NOT EXISTS, so a broken re-apply would
    raise DuplicateTable. Then assert the users table + unique index + role check
    constraint exist.

    SYNC test (not async): Alembic's async env.py calls asyncio.run() internally,
    which cannot be nested inside a running event loop — so this must run outside
    one, exactly like the pg_url fixture. The post-apply schema check uses a sync
    psycopg2 connection (testcontainers' default URL) for the same reason."""
    import psycopg2
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    # env.py prefers the DATABASE_URL env var over sqlalchemy.url, so pin it to THIS
    # container around the alembic calls and restore it after — otherwise the
    # downgrade/upgrade could target the wrong container and leak DATABASE_URL to a
    # later test module (cross-module flakiness).
    _prev_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = pg_url
    try:
        # Roll 0009 back, then forward — genuinely re-executes create_table("users").
        command.downgrade(cfg, "0008")
        command.upgrade(cfg, "head")  # must not raise (DuplicateTable = non-idempotent)
    finally:
        if _prev_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev_db_url

    # Sync DB check (psycopg2 — strip the asyncpg driver suffix from the URL).
    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.users')")
        assert cur.fetchone()[0] == "users", "users table missing after re-apply"
        cur.execute(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = 'users' AND indexname = 'uq_users_username'"
        )
        assert cur.fetchone() is not None, "uq_users_username index missing after re-apply"
        cur.execute("SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role_valid'")
        assert cur.fetchone() is not None, "role check constraint missing after re-apply"
    finally:
        conn.close()
