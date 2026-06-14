"""Story 10-4 — delay-minutes-avoided KPI (integration).

Against real Postgres (testcontainers + Alembic head, incl. 0008):
- AC4: GET /api/v1/kpi/delay-minutes-avoided sums seconds_to_departure/60 over
  escalations resolved IN-TIME (resolve before scheduled departure) in the
  trailing 24h.
- Excluded: NULL-seconds rows (alert not pre-departure / feed degraded),
  unresolved escalations, and resolves that happened AFTER departure.
- Empty window → 0.0.
- Auth: missing X-API-Key → 401/403.
"""
from __future__ import annotations

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

from .conftest import auth_header

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_API_HEADERS = auth_header()


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")

        import os

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
        await session.execute(
            text(
                "TRUNCATE events, journeys, escalations, escalation_audit "
                "RESTART IDENTITY CASCADE"
            )
        )
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


async def _seed_escalation(
    factory: async_sessionmaker[AsyncSession],
    *,
    status: str,
    seconds_to_departure: int | None,
    t_fired: datetime,
    t_resolve: datetime | None,
) -> None:
    """Insert one escalation row directly (bypasses ingest so we control
    t_fired/t_resolve precisely for the in-time boundary)."""
    async with factory() as s:
        await s.execute(
            text("""
                INSERT INTO escalations
                    (escalation_id, alert_id, alert_event_id, alert_code,
                     journey_id, vehicle_id, status, t_fired, t_resolve,
                     confidence_score, confidence_basis, model_versions,
                     seconds_to_departure)
                VALUES
                    (:eid, :aid, :eid, 'door_obstruction',
                     'V001_RJ-1_20260614', 'V001', :status, :t_fired, :t_resolve,
                     NULL, 'sensor', '{}'::jsonb, :std)
            """),
            {
                "eid": str(uuid.uuid4()),
                "aid": str(uuid.uuid4()),
                "status": status,
                "t_fired": t_fired,
                "t_resolve": t_resolve,
                "std": seconds_to_departure,
            },
        )
        await s.commit()


async def _get_kpi(client: AsyncClient) -> dict[str, object]:
    r = await client.get("/api/v1/kpi/delay-minutes-avoided", headers=_API_HEADERS)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_window_is_zero(app_client: AsyncClient) -> None:
    body = await _get_kpi(app_client)
    assert body == {"delay_minutes_avoided": 0.0, "window_hours": 24}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_in_time_resolve_is_summed(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    # raised 10 min ago with a 600s (10 min) departure budget; resolved 5 min ago
    # → resolve at t_fired + 5min < t_fired + 10min ⇒ in-time. 600s = 10.0 min.
    await _seed_escalation(
        factory,
        status="resolved",
        seconds_to_departure=600,
        t_fired=now - timedelta(minutes=10),
        t_resolve=now - timedelta(minutes=5),
    )
    body = await _get_kpi(app_client)
    assert body["delay_minutes_avoided"] == pytest.approx(10.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_late_resolve_excluded(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    # 60s budget but resolved 5 min after firing → AFTER departure ⇒ not in-time.
    await _seed_escalation(
        factory,
        status="resolved",
        seconds_to_departure=60,
        t_fired=now - timedelta(minutes=10),
        t_resolve=now - timedelta(minutes=5),
    )
    body = await _get_kpi(app_client)
    assert body["delay_minutes_avoided"] == pytest.approx(0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_null_seconds_excluded(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    # feed-degraded / in-transit alert: seconds_to_departure NULL — excluded.
    await _seed_escalation(
        factory,
        status="resolved",
        seconds_to_departure=None,
        t_fired=now - timedelta(minutes=10),
        t_resolve=now - timedelta(minutes=5),
    )
    body = await _get_kpi(app_client)
    assert body["delay_minutes_avoided"] == pytest.approx(0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unresolved_excluded(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    await _seed_escalation(
        factory,
        status="unacknowledged",
        seconds_to_departure=600,
        t_fired=now - timedelta(minutes=5),
        t_resolve=None,
    )
    body = await _get_kpi(app_client)
    assert body["delay_minutes_avoided"] == pytest.approx(0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_outside_24h_window_excluded(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    now = datetime.now(UTC)
    # resolved 25h ago — outside the trailing 24h window.
    await _seed_escalation(
        factory,
        status="resolved",
        seconds_to_departure=600,
        t_fired=now - timedelta(hours=25, minutes=10),
        t_resolve=now - timedelta(hours=25),
    )
    body = await _get_kpi(app_client)
    assert body["delay_minutes_avoided"] == pytest.approx(0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_stamps_seconds_to_departure(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """The ingest upsert persists payload.seconds_to_departure onto the escalation row."""
    event_id = str(uuid.uuid4())
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    env = {
        "event_id": event_id,
        "journey_id": "V001_RJ-1_20260614",
        "vehicle_id": "V001",
        "timestamp": ts,
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {
            "alert_id": str(uuid.uuid4()),
            "alert_code": "door_obstruction",
            "car_id": "car-6",
            "description": "door obstruction",
            "confidence_score": None,
            "confidence_basis": "sensor",
            "model_versions": {},
            "seconds_to_departure": 90,
        },
    }
    r = await app_client.post(
        "/api/v1/events", headers=_API_HEADERS, json={"events": [env]}
    )
    assert r.status_code == 202, r.text
    async with factory() as s:
        row = (
            await s.execute(
                text("SELECT seconds_to_departure FROM escalations WHERE escalation_id = :id"),
                {"id": event_id},
            )
        ).scalar_one()
    assert row == 90


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kpi_requires_api_key(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/kpi/delay-minutes-avoided")
    assert r.status_code in (401, 403)
