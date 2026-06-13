"""Integration: PostgreSQL schema via testcontainers (AC14)."""
from __future__ import annotations

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def pg_url() -> str:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_events_table_exists(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS journeys (
                    journey_id TEXT PRIMARY KEY,
                    vehicle_id TEXT NOT NULL,
                    trip_number TEXT NOT NULL,
                    route_name TEXT,
                    origin TEXT,
                    destination TEXT,
                    start_time TEXT,
                    end_time TEXT
                )
            """)
        )
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    vehicle_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    payload JSONB NOT NULL,
                    ingested_at TEXT NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::text
                )
            """)
        )

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN ('events', 'journeys')"
            )
        )
        tables = {row[0] for row in result}
    await engine.dispose()
    assert "events" in tables
    assert "journeys" in tables


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_insert_idempotent(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(pg_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    vehicle_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    payload JSONB NOT NULL,
                    ingested_at TEXT NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::text
                )
            """)
        )
        params = {
            "event_id": "test-uuid-001",
            "journey_id": "R5001C-031_RJ-0847_20260516",
            "vehicle_id": "R5001C-031",
            "timestamp": "2026-05-16T10:00:00Z",
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "schema_version": 1,
            "payload": "{}",
        }
        insert = text("""
            INSERT INTO events
                (event_id, journey_id, vehicle_id, timestamp, event_type,
                 severity, source, schema_version, payload)
            VALUES
                (:event_id, :journey_id, :vehicle_id, :timestamp, :event_type,
                 :severity, :source, :schema_version, :payload)
            ON CONFLICT (event_id) DO NOTHING
        """)
        r1 = await conn.execute(insert, params)
        r2 = await conn.execute(insert, params)

    assert r1.rowcount == 1
    assert r2.rowcount == 0
    await engine.dispose()
