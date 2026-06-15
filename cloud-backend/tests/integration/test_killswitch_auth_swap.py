"""Story 11-4 — kill-switch auth swap (X-Admin-Key → require_role("admin")).

A1 hard gate (real Postgres, testcontainers + Alembic head). Proves on the REAL
wire that:
  - an ADMIN Bearer token toggles a class AND the audit actor is the TOKEN's
    username (E11-S4 D1), persisted to alert_class_state.disabled_by and the
    ALERT_CLASS_DISABLED event envelope — never a body-supplied value;
  - a NEW ALERT_RAISED of that class, ingested through the real ingest path AFTER
    the disable, is suppressed from fan-out (the E10-S1 behaviour preserved
    end-to-end through the new auth path — AC1);
  - an OPERATOR Bearer token is forbidden (403) and changes no state (AC2).

Seeds auth users via the real path (seed_auth_users + real create_access_token),
not raw inserts of hand-built tokens (A3).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from cloud_backend.api.auth import create_access_token
from cloud_backend.services.fanout_filter import alert_class_filter

from .conftest import api_key_header, seed_auth_users

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
# Distinct, recognisable username on the admin token so the actor-source assertion
# is unambiguous (the actor must be THIS, not the seeded row's username or a body).
_ADMIN_UID = "00000000-0000-0000-0000-0000000000ad"  # seeded by seed_auth_users (admin)
_OPERATOR_UID = "00000000-0000-0000-0000-0000000000a1"  # seeded (operator)
_ADMIN_TOKEN_USERNAME = "claudia"


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
            seed_auth_users(url)
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
        await session.execute(
            text("TRUNCATE events, journeys, alert_class_state RESTART IDENTITY CASCADE")
        )
        await session.commit()
    alert_class_filter.invalidate()
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
    from cloud_backend.routes.alerts_sse import _subscribers

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    _subscribers.clear()
    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    _subscribers.clear()


def _admin_header() -> dict[str, str]:
    token = create_access_token(
        user_id=_ADMIN_UID, username=_ADMIN_TOKEN_USERNAME, role="admin"
    )
    return {"Authorization": f"Bearer {token}"}


def _operator_header() -> dict[str, str]:
    token = create_access_token(user_id=_OPERATOR_UID, username="op1", role="operator")
    return {"Authorization": f"Bearer {token}"}


def _alert_envelope(alert_code: str, ts: datetime) -> dict[str, object]:
    return {
        "event_id": str(uuid.uuid4()),
        "journey_id": "V001_RJ-0001_20260612",
        "vehicle_id": "V001",
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {
            "alert_id": str(uuid.uuid4()),
            "alert_code": alert_code,
            "car_id": "car-1",
            "description": "auth-swap fixture alert",
            "confidence_score": 0.9,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        },
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_toggle_suppresses_new_alert_actor_is_token_username(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """AC1 + AC3: admin Bearer toggle suppresses a subsequently-ingested alert AND
    records the token's username as the actor (not a body field)."""
    # Disable via the JWT admin path, with a spoof body that MUST be ignored.
    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers=_admin_header(),
        json={"actor_name": "spoofed-should-be-ignored"},
    )
    assert r.status_code == 200

    # AC3 — actor is the token username, persisted to alert_class_state + the envelope.
    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT state, disabled_by FROM alert_class_state "
                    "WHERE alert_code = 'UNATTENDED_BAG'"
                )
            )
        ).fetchone()
        assert row is not None
        assert row.state == "disabled"
        assert row.disabled_by == _ADMIN_TOKEN_USERNAME
        assert row.disabled_by != "spoofed-should-be-ignored"

        audit = (
            await session.execute(
                text(
                    "SELECT payload FROM events WHERE event_type = 'ALERT_CLASS_DISABLED'"
                )
            )
        ).fetchone()
        assert audit is not None
        assert _ADMIN_TOKEN_USERNAME in str(audit.payload)
        assert "spoofed-should-be-ignored" not in str(audit.payload)

    # AC1 — a NEW alert of the disabled class, ingested via the real path, is
    # suppressed from live fan-out (the E10-S1 behaviour, preserved through JWT auth).
    from cloud_backend.routes.alerts_sse import _subscribers

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=16)
    _subscribers.add(queue)
    try:
        post = _alert_envelope("UNATTENDED_BAG", datetime.now(UTC) + timedelta(seconds=5))
        other = _alert_envelope("slip_fall", datetime.now(UTC) + timedelta(seconds=6))
        r = await app_client.post(
            "/api/v1/events", headers=api_key_header(), json={"events": [post, other]}
        )
        assert r.status_code == 202
        delivered = queue.get_nowait()
        assert delivered["payload"]["alert_code"] == "slip_fall"  # type: ignore[index]
        assert queue.empty()  # UNATTENDED_BAG suppressed
    finally:
        _subscribers.discard(queue)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_operator_token_forbidden_and_no_state_change(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """AC2: operator Bearer token → 403 on disable, and no alert_class_state row
    is written."""
    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers=_operator_header(),
    )
    assert r.status_code == 403

    async with factory() as session:
        count = (
            await session.execute(text("SELECT COUNT(*) AS n FROM alert_class_state"))
        ).fetchone()
        assert count is not None
        assert count.n == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_old_admin_key_without_bearer_is_401(app_client: AsyncClient) -> None:
    """AC4: the retired X-Admin-Key path 401s (no Bearer token = unauthenticated)."""
    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers={"X-Admin-Key": "any-old-value"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Security-envelope regression net (code-review R1, E11S4-R1: promoted from the
# Edge Case Hunter's real-wire probes so the auth swap can't silently regress).
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/disable", "post"),
        ("/api/v1/admin/alert-classes/UNATTENDED_BAG/enable", "post"),
        ("/api/v1/admin/alert-classes", "get"),
    ],
)
async def test_operator_forbidden_on_every_endpoint(
    app_client: AsyncClient, path: str, method: str
) -> None:
    """AC2 on the real wire: an operator token is 403 on ALL THREE endpoints,
    not just disable. The GET has no per-route guard — this proves the router-
    level dependency alone gates it."""
    if method == "post":
        r = await app_client.post(path, headers=_operator_header())
    else:
        r = await app_client.get(path, headers=_operator_header())
    assert r.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_actor_spoof_ignored_on_enable_too(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """AC3 on the enable path (the disable path is covered above): a spoof body is
    ignored and the actor is the token username, persisted to enabled_by + the
    ALERT_CLASS_REENABLED envelope."""
    r = await app_client.post(
        "/api/v1/admin/alert-classes/slip_fall/enable",
        headers=_admin_header(),
        json={"actor_name": "spoofed-enable", "enabled_by": "spoofed2"},
    )
    assert r.status_code == 200

    async with factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT state, enabled_by FROM alert_class_state "
                    "WHERE alert_code = 'slip_fall'"
                )
            )
        ).fetchone()
        assert row is not None
        assert row.state == "enabled"
        assert row.enabled_by == _ADMIN_TOKEN_USERNAME
        assert row.enabled_by not in ("spoofed-enable", "spoofed2")

        audit = (
            await session.execute(
                text(
                    "SELECT payload FROM events WHERE event_type = 'ALERT_CLASS_REENABLED'"
                )
            )
        ).fetchone()
        assert audit is not None
        assert _ADMIN_TOKEN_USERNAME in str(audit.payload)
        assert "spoofed" not in str(audit.payload)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_sub",
    [
        "00000000-0000-0000-0000-0000deadbeef",  # valid UUID, no users row (deleted/never-existed)
        "not-a-uuid-at-all",  # non-UUID sub → the uuid-column bind raises, must be caught → 401
    ],
)
async def test_malformed_admin_sub_is_401_not_500(
    app_client: AsyncClient, bad_sub: str
) -> None:
    """The liveness gate must turn an absent or non-UUID `sub` into 401, never an
    uncaught 500 (no stack-trace info-leak). Even a well-formed admin-role token
    is rejected if its subject is not a live principal."""
    token = create_access_token(user_id=bad_sub, username="ghost", role="admin")
    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
