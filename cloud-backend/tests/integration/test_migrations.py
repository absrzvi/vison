"""Integration tests for E1-S3: PostgreSQL schema via Alembic + testcontainers.

Tests run against a real PostgreSQL 15 container — no mocking permitted (NFR).
"""

from __future__ import annotations

import os
import uuid

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def pg_container():  # type: ignore[no-untyped-def]
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="module")
def migrated_engine(pg_container):  # type: ignore[no-untyped-def]
    """Run alembic upgrade head once; yield the async engine for assertions."""
    import asyncio

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.ext.asyncio import create_async_engine

    # Build asyncpg URL from testcontainers
    url = pg_container.get_connection_url().replace("psycopg2", "asyncpg")

    # Run alembic upgrade head synchronously (env.py reads DATABASE_URL)
    os.environ["DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_async_engine(url)
    yield engine

    asyncio.get_event_loop().run_until_complete(engine.dispose())


# ---------------------------------------------------------------------------
# AC1 — journeys table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_journeys_table_columns(migrated_engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    async with migrated_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'journeys'
                ORDER BY column_name
            """)
        )
        cols = {row[0]: (row[1], row[2]) for row in result}

    assert "journey_id" in cols
    assert "vehicle_id" in cols
    assert cols["vehicle_id"][1] == "NO"  # not null
    assert "trip_number" in cols
    assert cols["trip_number"][1] == "NO"
    assert "route_name" in cols
    assert cols["route_name"][1] == "YES"  # nullable
    assert "origin" in cols
    assert "destination" in cols
    assert "start_time" in cols
    assert cols["start_time"][0] == "timestamp with time zone"
    assert cols["start_time"][1] == "NO"  # not null
    assert "end_time" in cols
    assert cols["end_time"][0] == "timestamp with time zone"
    assert cols["end_time"][1] == "YES"  # nullable


# ---------------------------------------------------------------------------
# AC2 — events table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_events_table_columns(migrated_engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    async with migrated_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'events'
                ORDER BY column_name
            """)
        )
        cols = {row[0]: (row[1], row[2]) for row in result}

    assert "event_id" in cols
    assert cols["event_id"][0] == "uuid"
    assert "journey_id" in cols
    assert cols["journey_id"][1] == "NO"
    assert "event_type" in cols
    assert "severity" in cols
    assert "source" in cols
    assert "timestamp" in cols
    assert cols["timestamp"][0] == "timestamp with time zone"
    assert "payload" in cols
    assert cols["payload"][0] == "jsonb"
    assert "source_timestamp" in cols
    assert cols["source_timestamp"][0] == "timestamp with time zone"
    assert cols["source_timestamp"][1] == "NO"


# ---------------------------------------------------------------------------
# AC3 + AC6 — UNIQUE(journey_id, event_type, source_timestamp) raises 23505
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_source_timestamp_raises_unique_violation(migrated_engine) -> None:  # type: ignore[no-untyped-def]
    from asyncpg import UniqueViolationError
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    journey_id = "V001_RJ-0001_20260517"
    async with migrated_engine.begin() as conn:
        # Insert parent journey first
        await conn.execute(
            text("""
                INSERT INTO journeys (journey_id, vehicle_id, trip_number, start_time)
                VALUES (:jid, 'V001', 'RJ-0001', '2026-05-17T06:00:00+00:00')
                ON CONFLICT DO NOTHING
            """),
            {"jid": journey_id},
        )

    event_params = {
        "event_id": str(uuid.uuid4()),
        "journey_id": journey_id,
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "ts": "2026-05-17T06:01:00+00:00",
        "source_ts": "2026-05-17T06:01:00+00:00",
        "payload": "{}",
    }
    insert_sql = text("""
        INSERT INTO events
            (event_id, journey_id, event_type, severity, source,
             timestamp, source_timestamp, payload)
        VALUES
            (:event_id, :journey_id, :event_type, :severity, :source,
             :ts, :source_ts, :payload::jsonb)
    """)

    # First insert succeeds
    async with migrated_engine.begin() as conn:
        await conn.execute(insert_sql, event_params)

    # Second insert with same (journey_id, event_type, source_timestamp) must fail
    dup_params = {**event_params, "event_id": str(uuid.uuid4())}
    with pytest.raises((IntegrityError, UniqueViolationError)):
        async with migrated_engine.begin() as conn:
            await conn.execute(insert_sql, dup_params)


# ---------------------------------------------------------------------------
# AC4 — column comment on journey_id in both tables
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_journey_id_column_comment(migrated_engine) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    expected_fragment = "stable across midnight crossings"

    async with migrated_engine.connect() as conn:
        for table in ("journeys", "events"):
            result = await conn.execute(
                text("""
                    SELECT pg_catalog.col_description(
                        c.oid, a.attnum
                    )
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
                    WHERE c.relname = :tbl
                      AND a.attname = 'journey_id'
                      AND a.attnum > 0
                """),
                {"tbl": table},
            )
            comment = result.scalar()
            assert comment is not None, f"No comment on {table}.journey_id"
            assert expected_fragment in comment, f"Comment missing expected text on {table}.journey_id"


# ---------------------------------------------------------------------------
# AC5 — second alembic upgrade head is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_upgrade_head_idempotent(migrated_engine) -> None:  # type: ignore[no-untyped-def]
    from alembic import command
    from alembic.config import Config

    url = os.environ["DATABASE_URL"]
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    # Should not raise
    command.upgrade(cfg, "head")
