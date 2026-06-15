"""Story 10-1 AC13 + ST5 — kill-switch fan-out enforcement (integration).

Against real Postgres (testcontainers + Alembic head):
- ALERT_RAISED of a disabled alert_code raised AFTER disabled_at is stored but
  filtered from SSE live fan-out and SSE replay.
- In-flight escalation raised BEFORE disabled_at is NOT filtered from replay.
- Admin disable/enable round-trip persists rows + audit events.
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

from cloud_backend.services.fanout_filter import alert_class_filter

from .conftest import api_key_header, auth_header, seed_auth_users

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")


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


_API_HEADERS = auth_header()
# E11-S4: the kill-switch is now JWT role-gated — toggles use an admin Bearer
# token (was X-Admin-Key). The audit actor is the token's username claim
# ("tester", auth_header's default) — NOT the seeded users-row username; these
# tests assert only fan-out state/event-type, so the actor value is exercised by
# test_killswitch_auth_swap.py, not here.
_ADMIN_HEADERS = auth_header(role="admin")


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
            "description": "integration fixture alert",
            "confidence_score": 0.9,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        },
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disabled_class_filtered_from_live_fanout_and_replay(
    app_client: AsyncClient,
) -> None:
    from cloud_backend.routes.alerts_sse import _subscribers

    # 1. Ingest a pre-disable alert (in-flight escalation).
    pre = _alert_envelope("UNATTENDED_BAG", datetime.now(UTC) - timedelta(minutes=5))
    r = await app_client.post("/api/v1/events", headers=api_key_header(), json={"events": [pre]})
    assert r.status_code == 202

    # 2. Disable the class.
    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers=_ADMIN_HEADERS,
    )
    assert r.status_code == 200

    # 3. Subscribe a live queue, then ingest a post-disable alert.
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=16)
    _subscribers.add(queue)
    try:
        post = _alert_envelope("UNATTENDED_BAG", datetime.now(UTC) + timedelta(seconds=5))
        other = _alert_envelope("slip_fall", datetime.now(UTC) + timedelta(seconds=6))
        r = await app_client.post(
            "/api/v1/events", headers=api_key_header(), json={"events": [post, other]}
        )
        assert r.status_code == 202

        # Only the slip_fall alert reaches the live queue.
        delivered = queue.get_nowait()
        assert delivered["payload"]["alert_code"] == "slip_fall"  # type: ignore[index]
        assert queue.empty()
    finally:
        _subscribers.discard(queue)

    # 4. Replay since the pre-disable event: post-disable UNATTENDED_BAG is
    # filtered; slip_fall is replayed; the in-flight pre event is the cursor
    # (not part of replay output by definition).
    from cloud_backend.database import get_db
    from cloud_backend.main import app
    from cloud_backend.routes.alerts_sse import _replay_since

    gen_db = app.dependency_overrides[get_db]()
    db = await gen_db.__anext__()
    try:
        replayed = await _replay_since(str(pre["event_id"]), db)
        codes = [e["payload"]["alert_code"] for e in replayed]  # type: ignore[index]
        assert "slip_fall" in codes
        assert "UNATTENDED_BAG" not in codes
    finally:
        await gen_db.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_inflight_escalation_survives_disable_in_replay(
    app_client: AsyncClient,
) -> None:
    # Cursor event well in the past, in-flight alert before disable.
    cursor = _alert_envelope("slip_fall", datetime.now(UTC) - timedelta(minutes=30))
    inflight = _alert_envelope("UNATTENDED_BAG", datetime.now(UTC) - timedelta(minutes=10))
    r = await app_client.post(
        "/api/v1/events", headers=api_key_header(), json={"events": [cursor, inflight]}
    )
    assert r.status_code == 202

    r = await app_client.post(
        "/api/v1/admin/alert-classes/UNATTENDED_BAG/disable",
        headers=_ADMIN_HEADERS,
    )
    assert r.status_code == 200

    from cloud_backend.database import get_db
    from cloud_backend.main import app
    from cloud_backend.routes.alerts_sse import _replay_since

    gen_db = app.dependency_overrides[get_db]()
    db = await gen_db.__anext__()
    try:
        replayed = await _replay_since(str(cursor["event_id"]), db)
        codes = [e["payload"]["alert_code"] for e in replayed]  # type: ignore[index]
        # t_raised < disabled_at → in-flight escalation stays visible.
        assert "UNATTENDED_BAG" in codes
    finally:
        await gen_db.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enable_restores_fanout_and_audit_rows_persisted(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    for action in ("disable", "enable"):
        r = await app_client.post(
            f"/api/v1/admin/alert-classes/UNATTENDED_BAG/{action}",
            headers=_ADMIN_HEADERS,
        )
        assert r.status_code == 200

    async with factory() as session:
        rows = list(
            await session.execute(
                text("SELECT alert_code, state FROM alert_class_state")
            )
        )
        assert rows == [("UNATTENDED_BAG", "enabled")]
        audit = list(
            await session.execute(
                text("""
                    SELECT event_type FROM events
                    WHERE event_type IN ('ALERT_CLASS_DISABLED', 'ALERT_CLASS_REENABLED')
                    ORDER BY timestamp
                """)
            )
        )
        assert [a.event_type for a in audit] == [
            "ALERT_CLASS_DISABLED",
            "ALERT_CLASS_REENABLED",
        ]

    # Post-enable alert flows again.
    from cloud_backend.routes.alerts_sse import _subscribers

    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=16)
    _subscribers.add(queue)
    try:
        ev = _alert_envelope("UNATTENDED_BAG", datetime.now(UTC) + timedelta(seconds=5))
        r = await app_client.post(
            "/api/v1/events", headers=api_key_header(), json={"events": [ev]}
        )
        assert r.status_code == 202
        delivered = queue.get_nowait()
        assert delivered["payload"]["alert_code"] == "UNATTENDED_BAG"  # type: ignore[index]
    finally:
        _subscribers.discard(queue)
