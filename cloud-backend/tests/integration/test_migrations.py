"""Integration tests for E1-S3: PostgreSQL schema via Alembic + testcontainers.

Tests run against a real PostgreSQL 15 container — no mocking permitted (NFR).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
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
                {"jid": journey_id, "start_time": datetime(2026, 5, 17, 6, 0, 0, tzinfo=UTC)},
            )

        insert_sql = text("""
            INSERT INTO events
                (event_id, journey_id, vehicle_id, event_type, severity, source,
                 timestamp, source_timestamp, payload)
            VALUES
                (:event_id, :journey_id, :vehicle_id, :event_type, :severity, :source,
                 :ts, :source_ts, :payload)
        """)
        _ts = datetime(2026, 5, 17, 6, 1, 0, tzinfo=UTC)
        base_params = {
            "journey_id": journey_id,
            "vehicle_id": "V001",
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
        code = getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
        assert code == "23505"

        await engine.dispose()

    _run(_check())


# ---------------------------------------------------------------------------
# Story 10-6 AC1 + AC7 — escalations table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_escalations_table_columns(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'escalations'
                    ORDER BY column_name
                """)
            )
            cols = {row[0]: (row[1], row[2]) for row in result}
        await engine.dispose()

        # PK = the ALERT_RAISED event_id (uuid, matches events.event_id type)
        assert cols["escalation_id"][0] == "uuid"
        assert cols["escalation_id"][1] == "NO"
        assert cols["alert_id"][1] == "NO"
        assert cols["alert_event_id"][0] == "uuid"
        assert cols["alert_code"][1] == "NO"
        assert cols["journey_id"][1] == "NO"
        assert cols["vehicle_id"][1] == "NO"
        assert cols["status"][1] == "NO"
        assert cols["t_fired"][0] == "timestamp with time zone"
        assert cols["t_fired"][1] == "NO"
        assert cols["t_ack"][0] == "timestamp with time zone"
        assert cols["t_ack"][1] == "YES"
        assert cols["t_resolve"][0] == "timestamp with time zone"
        assert cols["t_resolve"][1] == "YES"
        assert cols["ack_operator_id"][1] == "YES"
        assert cols["resolve_operator_id"][1] == "YES"
        assert cols["outcome"][1] == "YES"
        assert cols["action_tags"][0] == "jsonb"
        assert cols["confidence_score"][0] == "double precision"
        assert cols["confidence_score"][1] == "YES"
        assert cols["confidence_basis"][1] == "YES"
        assert cols["model_versions"][0] == "jsonb"

    _run(_check())


# ---------------------------------------------------------------------------
# Story 10-2 AC1 + AC5 — escalation_audit table columns
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_escalation_audit_table_columns(pg_url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'escalation_audit'
                    ORDER BY column_name
                """)
            )
            cols = {row[0]: (row[1], row[2]) for row in result}
        await engine.dispose()

        # audit_id PK (TEXT); escalation_id FK matches escalations.escalation_id (uuid)
        assert cols["audit_id"][1] == "NO"
        assert cols["escalation_id"][0] == "uuid"
        assert cols["escalation_id"][1] == "NO"
        assert cols["transition"][1] == "NO"
        assert cols["operator_id"][1] == "YES"  # NULL on raised
        assert cols["alert_code"][1] == "NO"
        assert cols["t_event"][0] == "timestamp with time zone"
        assert cols["t_event"][1] == "NO"
        assert cols["t_fired"][0] == "timestamp with time zone"
        assert cols["t_fired"][1] == "NO"
        assert cols["action_tags"][0] == "jsonb"
        assert cols["action_tags"][1] == "YES"  # only on resolved
        assert cols["dwell_focus_ms"][0] == "bigint"
        assert cols["dwell_focus_ms"][1] == "YES"  # only on silently_dismissed
        assert cols["confidence_score"][0] == "double precision"
        assert cols["confidence_score"][1] == "YES"
        assert cols["confidence_basis"][1] == "YES"
        assert cols["model_versions"][0] == "jsonb"

    _run(_check())


@pytest.mark.integration
def test_escalation_audit_transition_check_constraint(pg_url: str) -> None:
    """The transition CHECK rejects values outside the four-state taxonomy."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        # Seed an escalation row first so the FK is satisfiable.
        journey_id = f"V001_RJ-0001_{uuid.uuid4().hex[:8]}"
        esc_id = str(uuid.uuid4())
        t = datetime(2026, 6, 13, 6, 0, 0, tzinfo=UTC)
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO journeys (journey_id, vehicle_id, trip_number, start_time)
                    VALUES (:jid, 'V001', 'RJ-0001', :t) ON CONFLICT DO NOTHING
                """),
                {"jid": journey_id, "t": t},
            )
            await conn.execute(
                text("""
                    INSERT INTO escalations
                        (escalation_id, alert_id, alert_event_id, alert_code, journey_id,
                         vehicle_id, status, t_fired)
                    VALUES (:id, 'a1', :id, 'UNATTENDED_BAG', :jid, 'V001',
                            'unacknowledged', :t)
                """),
                {"id": esc_id, "jid": journey_id, "t": t},
            )

        with pytest.raises(IntegrityError) as exc_info:
            async with engine.begin() as conn:
                await conn.execute(
                    text("""
                        INSERT INTO escalation_audit
                            (audit_id, escalation_id, transition, alert_code, t_event, t_fired)
                        VALUES (:aid, :eid, 'bogus', 'UNATTENDED_BAG', :t, :t)
                    """),
                    {"aid": str(uuid.uuid4()), "eid": esc_id, "t": t},
                )
        cause = exc_info.value.orig
        code = getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
        assert code == "23514"  # check_violation
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
# Story 11-3 AC2 — operator_preferences re-keyed to UUID FK on users (0011)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_operator_preferences_rekeyed_to_user_fk(pg_url: str) -> None:
    """After 0011, operator_id is uuid with a FK to users(user_id); the two
    threshold CHECK constraints survive the ALTER (asserted via the catalog)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check() -> None:
        engine = create_async_engine(pg_url)
        async with engine.connect() as conn:
            col_type = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name='operator_preferences' "
                        "AND column_name='operator_id'"
                    )
                )
            ).scalar()
            fk = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.table_constraints tc "
                        "JOIN information_schema.constraint_column_usage ccu "
                        "  ON tc.constraint_name = ccu.constraint_name "
                        "WHERE tc.table_name='operator_preferences' "
                        "  AND tc.constraint_type='FOREIGN KEY' "
                        "  AND ccu.table_name='users' AND ccu.column_name='user_id'"
                    )
                )
            ).scalar()
            checks = {
                row[0]
                for row in await conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint con "
                        "JOIN pg_class rel ON rel.oid = con.conrelid "
                        "WHERE rel.relname='operator_preferences' AND con.contype='c'"
                    )
                )
            }
        await engine.dispose()
        assert col_type == "uuid"
        assert fk == 1
        assert "ck_threshold_sec_valid" in checks
        assert "ck_staleness_threshold_sec_valid" in checks

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
