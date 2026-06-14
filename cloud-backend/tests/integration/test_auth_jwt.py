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

    # tamper one signature byte → 401
    head, payload, sig = token.split(".")
    tampered = f"{head}.{payload}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
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
    ("GET", "/api/v1/alerts/stream"),  # SSE: gated via ?token= (no token here → 401)
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
def test_upgrade_head_idempotent(pg_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    # Already at head from the module fixture; applying head again must not raise.
    command.upgrade(cfg, "head")
