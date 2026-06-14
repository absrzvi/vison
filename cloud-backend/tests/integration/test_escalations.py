"""Story 10-6 — escalation lifecycle persistence (integration).

Against real Postgres (testcontainers + Alembic head):
- AC2: ALERT_RAISED ingest upserts an `escalations` row keyed on the event_id.
- AC3: acknowledge transitions unacknowledged → acknowledged (idempotent, 404).
- AC4: resolve transitions acknowledged → resolved (409 before ack, 422 bad tag).
- AC5: ack/resolve publish an ESCALATION_UPDATED frame to SSE subscribers.
- Auth: endpoints reject a missing/invalid X-API-Key with 401.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

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
            text("TRUNCATE events, journeys, escalations RESTART IDENTITY CASCADE")
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


_API_HEADERS = auth_header()


def _alert_envelope(
    *, event_id: str, alert_id: str, alert_code: str = "UNATTENDED_BAG"
) -> dict[str, object]:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "event_id": event_id,
        "journey_id": "V001_RJ-0001_20260613",
        "vehicle_id": "V001",
        "timestamp": ts,
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {
            "alert_id": alert_id,
            "alert_code": alert_code,
            "car_id": "car-1",
            "description": "integration fixture alert",
            "confidence_score": 0.9,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        },
    }


async def _ingest_alert(
    client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> tuple[str, str]:
    """Ingest one ALERT_RAISED; return (event_id, alert_id)."""
    event_id = str(uuid.uuid4())
    alert_id = str(uuid.uuid4())
    env = _alert_envelope(event_id=event_id, alert_id=alert_id)
    r = await client.post("/api/v1/events", headers=api_key_header(), json={"events": [env]})
    assert r.status_code == 202, r.text
    return event_id, alert_id


async def _ack(client: AsyncClient, escalation_id: str, operator_id: str = "op-1") -> int:
    """POST acknowledge; return the status code."""
    r = await client.post(
        f"/api/v1/escalations/{escalation_id}/acknowledge",
        headers=_API_HEADERS,
        json={"operator_id": operator_id},
    )
    return r.status_code


async def _fetch_escalation(
    factory: async_sessionmaker[AsyncSession], escalation_id: str
) -> dict[str, object] | None:
    async with factory() as s:
        row = (
            await s.execute(
                text("SELECT * FROM escalations WHERE escalation_id = :id"),
                {"id": escalation_id},
            )
        ).mappings().first()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# AC2 — escalation row created on ALERT_RAISED ingest
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alert_raised_creates_escalation_row(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, alert_id = await _ingest_alert(app_client, factory)
    esc = await _fetch_escalation(factory, event_id)
    assert esc is not None
    assert str(esc["escalation_id"]) == event_id
    assert esc["alert_id"] == alert_id
    assert esc["alert_code"] == "UNATTENDED_BAG"
    assert esc["status"] == "unacknowledged"
    assert esc["t_fired"] is not None
    assert esc["confidence_score"] == 0.9
    assert esc["confidence_basis"] == "model"
    assert esc["model_versions"] == {"detector_arch": "yolox_s_leaky"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alert_raised_empty_payload_skips_escalation_no_500(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Review R1: an empty-payload ALERT_RAISED bypasses typed validation
    (EventEnvelope skips it when payload is empty). The escalation upsert must
    skip rather than 500 on the NOT-NULL alert_id/alert_code columns."""
    event_id = str(uuid.uuid4())
    env = {
        "event_id": event_id,
        "journey_id": "V001_RJ-0001_20260613",
        "vehicle_id": "V001",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {},
    }
    r = await app_client.post("/api/v1/events", headers=api_key_header(), json={"events": [env]})
    # Ingest still succeeds (the event is stored); no escalation row is created.
    assert r.status_code == 202, r.text
    assert await _fetch_escalation(factory, event_id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_alert_raised_escalation_idempotent(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id = str(uuid.uuid4())
    alert_id = str(uuid.uuid4())
    env = _alert_envelope(event_id=event_id, alert_id=alert_id)
    # Same event ingested twice → ON CONFLICT DO NOTHING, still one escalation row.
    await app_client.post("/api/v1/events", headers=api_key_header(), json={"events": [env]})
    await app_client.post("/api/v1/events", headers=api_key_header(), json={"events": [env]})
    async with factory() as s:
        n = (
            await s.execute(
                text("SELECT COUNT(*) FROM escalations WHERE escalation_id = :id"),
                {"id": event_id},
            )
        ).scalar_one()
    assert n == 1


# ---------------------------------------------------------------------------
# AC3 — acknowledge endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledge_transitions_to_acknowledged(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    assert await _ack(app_client, event_id, "op-7") == 200
    esc = await _fetch_escalation(factory, event_id)
    assert esc is not None
    assert esc["status"] == "acknowledged"
    assert esc["t_ack"] is not None
    assert esc["ack_operator_id"] == "op-7"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledge_idempotent(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    assert await _ack(app_client, event_id, "op-1") == 200
    assert await _ack(app_client, event_id, "op-2") == 200
    esc = await _fetch_escalation(factory, event_id)
    assert esc is not None
    # First ack wins; second is a no-op.
    assert esc["ack_operator_id"] == "op-1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledge_unknown_returns_404(app_client: AsyncClient) -> None:
    r = await app_client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/acknowledge",
        headers=_API_HEADERS,
        json={"operator_id": "op-1"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# AC4 — resolve endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_transitions_to_resolved(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    await _ack(app_client, event_id)
    r = await app_client.post(
        f"/api/v1/escalations/{event_id}/resolve",
        headers=_API_HEADERS,
        json={
            "outcome": "Verified via CCTV",
            "action_tags": ["Resolved remotely"],
            "operator_id": "op-1",
        },
    )
    assert r.status_code == 200, r.text
    esc = await _fetch_escalation(factory, event_id)
    assert esc is not None
    assert esc["status"] == "resolved"
    assert esc["t_resolve"] is not None
    assert esc["resolve_operator_id"] == "op-1"
    assert esc["outcome"] == "Verified via CCTV"
    # Stored as canonical keys, not labels.
    assert esc["action_tags"] == ["resolved_remotely"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_before_acknowledge_returns_409(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    r = await app_client.post(
        f"/api/v1/escalations/{event_id}/resolve",
        headers=_API_HEADERS,
        json={"outcome": "x", "action_tags": ["False alarm"], "operator_id": "op-1"},
    )
    assert r.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_invalid_tag_returns_422(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    await _ack(app_client, event_id)
    r = await app_client.post(
        f"/api/v1/escalations/{event_id}/resolve",
        headers=_API_HEADERS,
        json={"outcome": "x", "action_tags": ["Conrad instructed"], "operator_id": "op-1"},
    )
    assert r.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_idempotent(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id, _ = await _ingest_alert(app_client, factory)
    await _ack(app_client, event_id)
    body = {"outcome": "done", "action_tags": ["No action needed"], "operator_id": "op-1"}
    a = await app_client.post(
        f"/api/v1/escalations/{event_id}/resolve", headers=_API_HEADERS, json=body
    )
    b = await app_client.post(
        f"/api/v1/escalations/{event_id}/resolve", headers=_API_HEADERS, json=body
    )
    assert a.status_code == 200
    assert b.status_code == 200


# ---------------------------------------------------------------------------
# AC5 — SSE fan-out of lifecycle transitions
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledge_publishes_sse_frame(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    from cloud_backend.routes.alerts_sse import _subscribers

    event_id, _ = await _ingest_alert(app_client, factory)
    q: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=8)
    _subscribers.add(q)
    try:
        await _ack(app_client, event_id)
        frame = await asyncio.wait_for(q.get(), timeout=2.0)
    finally:
        _subscribers.discard(q)
    assert frame["event_type"] == "ESCALATION_UPDATED"
    assert str(frame["event_id"]) == event_id
    # Review R1 blocker: the CC consumer (FleetContext) matches on payload.id, so the
    # frame must carry `id` (= escalation_id), not only escalation_id.
    assert str(frame["id"]) == event_id
    assert frame["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# Auth — endpoints reject missing/invalid X-API-Key
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_acknowledge_requires_api_key(app_client: AsyncClient) -> None:
    r = await app_client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/acknowledge", json={"operator_id": "op-1"}
    )
    assert r.status_code == 401
