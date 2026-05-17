"""Integration tests for E1-S3: PostgreSQL schema via Alembic + testcontainers.

Tests run against a real PostgreSQL 15 container — no mocking permitted (NFR).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")


@pytest.fixture(scope="module")
def pg_url() -> str:  # type: ignore[return]
    """Start a PG15 container, run alembic upgrade head, yield the asyncpg URL."""
    with PostgresContainer("postgres:15-alpine") as pg:
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


def _run(coro):  # type: ignore[no-untyped-def]
    """Run a coroutine in a fresh event loop (avoids closed-loop issues in module fixtures)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# AC1 — journeys table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_journeys_table_columns(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'journeys'
                    ORDER BY column_name
                """)
            )
            cols = {row[0]: (row[1], row[2]) for row in result}
        await engine.dispose()

        assert "journey_id" in cols
        assert "vehicle_id" in cols
        assert cols["vehicle_id"][1] == "NO"
        assert "trip_number" in cols
        assert cols["trip_number"][1] == "NO"
        assert "route_name" in cols
        assert cols["route_name"][1] == "YES"
        assert "origin" in cols
        assert "destination" in cols
        assert "start_time" in cols
        assert cols["start_time"][0] == "timestamp with time zone"
        assert cols["start_time"][1] == "NO"
        assert "end_time" in cols
        assert cols["end_time"][0] == "timestamp with time zone"
        assert cols["end_time"][1] == "YES"

    _run(_check())


# ---------------------------------------------------------------------------
# AC2 — events table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_events_table_columns(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'events'
                    ORDER BY column_name
                """)
            )
            cols = {row[0]: (row[1], row[2]) for row in result}
        await engine.dispose()

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

    _run(_check())


# ---------------------------------------------------------------------------
# AC3 + AC6 — UNIQUE(journey_id, event_type, source_timestamp) raises 23505
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_duplicate_source_timestamp_raises_unique_violation(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    journey_id = f"V001_RJ-0001_{uuid.uuid4().hex[:8]}"

    async def _check() -> None:
        engine = create_async_engine(pg_url)

        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO journeys (journey_id, vehicle_id, trip_number, start_time)
                    VALUES (:jid, 'V001', 'RJ-0001', :start_time)
                    ON CONFLICT DO NOTHING
                """),
                {"jid": journey_id, "start_time": datetime(2026, 5, 17, 6, 0, 0, tzinfo=timezone.utc)},
            )

        insert_sql = text("""
            INSERT INTO events
                (event_id, journey_id, event_type, severity, source,
                 timestamp, source_timestamp, payload)
            VALUES
                (:event_id, :journey_id, :event_type, :severity, :source,
                 :ts, :source_ts, :payload)
        """)
        _ts = datetime(2026, 5, 17, 6, 1, 0, tzinfo=timezone.utc)
        base_params = {
            "journey_id": journey_id,
            "event_type": "OCCUPANCY_UPDATE",
            "severity": "info",
            "source": "inference",
            "ts": _ts,
            "source_ts": _ts,
            "payload": "{}",
        }

        async with engine.begin() as conn:
            await conn.execute(insert_sql, {"event_id": str(uuid.uuid4()), **base_params})

        with pytest.raises(IntegrityError) as exc_info:
            async with engine.begin() as conn:
                await conn.execute(insert_sql, {"event_id": str(uuid.uuid4()), **base_params})
        cause = exc_info.value.orig
        assert getattr(cause, "pgcode", None) == "23505" or getattr(cause, "sqlstate", None) == "23505"

        await engine.dispose()

    _run(_check())


# ---------------------------------------------------------------------------
# AC4 — column comment on journey_id in both tables
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_journey_id_column_comment(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    expected_fragment = "stable across midnight crossings"

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            for table in ("journeys", "events"):
                result = await conn.execute(
                    text("""
                        SELECT pg_catalog.col_description(c.oid, a.attnum)
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
                assert expected_fragment in comment
        await engine.dispose()

    _run(_check())


# ---------------------------------------------------------------------------
# AC5 — second alembic upgrade head is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_upgrade_head_idempotent(pg_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")  # must not raise
