"""Integration tests for E3-S2 capacity review endpoints using testcontainers."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    ts = datetime.now(UTC).isoformat()
    async with session_factory() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                journey_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                source TEXT NOT NULL DEFAULT 'test',
                schema_version INTEGER NOT NULL DEFAULT 1,
                source_timestamp TEXT,
                payload JSONB NOT NULL DEFAULT '{}',
                ingested_at TEXT NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::text
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS capacity_review_queue (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                exception_id TEXT NOT NULL UNIQUE,
                route TEXT NOT NULL,
                train_id TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                priority TEXT NOT NULL,
                note TEXT,
                queued_by TEXT NOT NULL,
                queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status TEXT NOT NULL DEFAULT 'in_review',
                CONSTRAINT ck_crq_priority_valid CHECK (priority IN ('low', 'medium', 'high')),
                CONSTRAINT ck_crq_status_valid
                    CHECK (status IN ('in_review', 'dismissed', 'unreviewed'))
            )
        """))

        # Seed one CAPACITY_EXCEPTION event
        await conn.execute(
            text("""
                INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,
                                   severity,payload)
                VALUES(:eid,'j1','VH-001',:ts,'CAPACITY_EXCEPTION','critical',:payload)
                ON CONFLICT DO NOTHING
            """),
            {
                "eid": "ex1",
                "ts": ts,
                "payload": json.dumps({
                    "route": "Vienna-Salzburg",
                    "departure": "08:00",
                    "status": "unreviewed",
                    "coach_peaks": [{"coach_id": "C1", "peak_pct": 95.0}],
                    "trend": [80, 85, 90, 92, 93, 94, 95],
                }),
            },
        )
        await conn.commit()


@pytest_asyncio.fixture
async def client(pg_url: str) -> AsyncGenerator[AsyncClient, None]:
    from cloud_backend.database import get_db
    from cloud_backend.main import app

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _seed(factory)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


_HEADERS = {"X-API-Key": "dev-insecure-key"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_review_exception_inserts_queue_row(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/analytics/exceptions/ex1/review",
        json={"note": "Needs attention", "priority": "High"},
        headers=_HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_review"
    assert "queued_at" in body
    # ISO timestamp parseable
    datetime.fromisoformat(body["queued_at"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismiss_exception_updates_status(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/analytics/exceptions/ex1/dismiss",
        headers=_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reopen_exception_reverts_status(client: AsyncClient) -> None:
    # First ensure a row exists in queue
    await client.post(
        "/api/v1/analytics/exceptions/ex1/dismiss",
        headers=_HEADERS,
    )
    r = await client.post(
        "/api/v1/analytics/exceptions/ex1/reopen",
        headers=_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "unreviewed"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_csv_headers(client: AsyncClient) -> None:
    # Seed a review row first
    await client.post(
        "/api/v1/analytics/exceptions/ex1/review",
        json={"priority": "low"},
        headers=_HEADERS,
    )
    r = await client.get("/api/v1/capacity-review-queue/export", headers=_HEADERS)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    lines = r.text.splitlines()
    expected_header = (
        "exception_id,route,train_id,departure_date,priority,note,queued_by,queued_at,status"
    )
    assert lines[0] == expected_header


@pytest.mark.integration
@pytest.mark.asyncio
async def test_export_csv_excludes_dismissed(client: AsyncClient) -> None:
    # Mark as dismissed — should not appear in export
    await client.post(
        "/api/v1/analytics/exceptions/ex1/dismiss",
        headers=_HEADERS,
    )
    r = await client.get("/api/v1/capacity-review-queue/export", headers=_HEADERS)
    assert r.status_code == 200
    # Only header row — no data rows for dismissed
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert len(lines) == 1  # header only


@pytest.mark.integration
@pytest.mark.asyncio
async def test_review_invalid_priority_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/analytics/exceptions/ex1/review",
        json={"priority": "extreme"},
        headers=_HEADERS,
    )
    assert r.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_review_missing_event_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/analytics/exceptions/nonexistent-id/review",
        json={"priority": "high"},
        headers=_HEADERS,
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reopen_missing_queue_row_returns_404(client: AsyncClient) -> None:
    # No row in queue for this id — reopen should 404
    r = await client.post(
        "/api/v1/analytics/exceptions/nonexistent-id/reopen",
        headers=_HEADERS,
    )
    assert r.status_code == 404
