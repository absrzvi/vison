"""Story 10-5 — AI quality resolution-rates endpoint (integration).

Against real Postgres (testcontainers + Alembic head):
- AC1: GET /api/v1/ai-quality/resolution-rates returns two rates per alert_code
  over a rolling 7-day window:
    no_action_rate  = resolved-with-zero-action-tags / resolved_total
    explicit_fp_rate = resolved-with-tag('false_alarm') / resolved_total
  Both carry integer count denominators; both None when resolved_total == 0.
- D1: explicit_fp_rate keys on the SHIPPED `false_alarm` canonical tag (NOT a new
  `false_positive` tag — none exists).
- D2: there is NO third (auto-resolved-before-ack) rate.
- Window boundary: a row exactly on the half-open `to` edge is counted by one window.
- Auth: missing X-API-Key → 401/403.
"""
from __future__ import annotations

import json
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

from .conftest import auth_header, seed_auth_users

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_API_HEADERS = auth_header()
_ENDPOINT = "/api/v1/ai-quality/resolution-rates"


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
        # Truncate both: this story now seeds escalations parents for the audit
        # rows' FK, so clearing only escalation_audit would leak parent rows
        # across the module's tests. CASCADE from escalations also clears audit.
        await session.execute(
            text("TRUNCATE escalations, escalation_audit RESTART IDENTITY CASCADE")
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


async def _seed_parent(s: AsyncSession, *, eid: str, alert_code: str, t_event: datetime) -> None:
    """Insert the escalations parent row keyed by `eid`.

    escalation_audit.escalation_id is NOT NULL with a non-deferrable FK to
    escalations.escalation_id (0007 / 0006), so every audit row needs a parent.
    The funnel/rates queries read only escalation_audit, so the parent's other
    columns just need to satisfy NOT NULL — status defaults to 'unacknowledged'.
    """
    await s.execute(
        text("""
            INSERT INTO escalations
                (escalation_id, alert_id, alert_event_id, alert_code,
                 journey_id, vehicle_id, t_fired)
            VALUES
                (:eid, :aid, :eid, :alert_code,
                 'V001_RJ-1_20260614', 'V001', :t_event)
        """),
        {"eid": eid, "aid": str(uuid.uuid4()), "alert_code": alert_code, "t_event": t_event},
    )


async def _seed_resolved(
    factory: async_sessionmaker[AsyncSession],
    *,
    alert_code: str,
    action_tags: list[str] | None,
    t_event: datetime,
) -> None:
    """Append one resolved escalation_audit row (+ its escalations parent).

    action_tags=None or [] models a zero-action resolve (no_action_rate numerator);
    ['false_alarm'] models the explicit-FP numerator.
    """
    eid = str(uuid.uuid4())
    async with factory() as s:
        await _seed_parent(s, eid=eid, alert_code=alert_code, t_event=t_event)
        await s.execute(
            text("""
                INSERT INTO escalation_audit
                    (audit_id, escalation_id, transition, operator_id, alert_code,
                     t_event, t_fired, action_tags, dwell_focus_ms,
                     confidence_score, confidence_basis, model_versions)
                VALUES
                    (:audit_id, :eid, 'resolved', 'op-1', :alert_code,
                     :t_event, :t_event, :tags, NULL, NULL, 'sensor', '{}'::jsonb)
            """),
            {
                "audit_id": str(uuid.uuid4()),
                "eid": eid,
                "alert_code": alert_code,
                "t_event": t_event,
                "tags": json.dumps(action_tags) if action_tags is not None else None,
            },
        )
        await s.commit()


def _by_code(body: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {row["alert_code"]: row for row in body}  # type: ignore[index]


async def _get(client: AsyncClient, **params: str) -> list[dict[str, object]]:
    r = await client.get(_ENDPOINT, headers=_API_HEADERS, params=params or None)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_window_returns_empty_list(app_client: AsyncClient) -> None:
    assert await _get(app_client) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_rates_with_denominators(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    # Back-date well inside the window. The query's upper bound is the DB clock
    # (`t_event < NOW()`); seeding at the Python-host clock is flaky because under
    # testcontainers the host clock can run ~100s of ms AHEAD of the container's,
    # so a t_event stamped at host-now() lands >= the container's NOW() at query
    # time and the half-open upper bound drops every freshly-seeded row.
    now = datetime.now(UTC) - timedelta(minutes=1)

    async def seed(tags: list[str] | None) -> None:
        await _seed_resolved(
            factory, alert_code="door_obstruction", action_tags=tags, t_event=now
        )

    # door_obstruction: 4 resolved — 1 false_alarm, 1 zero-tag, 2 action tags.
    await seed(["false_alarm"])
    await seed([])
    await seed(["resolved_remotely"])
    await seed(["field_team_dispatched"])

    row = _by_code(await _get(app_client))["door_obstruction"]
    assert row["resolved_total"] == 4
    assert row["false_alarm_count"] == 1
    assert row["no_action_count"] == 1
    assert row["explicit_fp_rate"] == pytest.approx(0.25)
    assert row["no_action_rate"] == pytest.approx(0.25)
    # D2: no third rate is present on the row.
    assert "auto_resolved_before_ack_rate" not in row


@pytest.mark.integration
@pytest.mark.asyncio
async def test_null_action_tags_counts_as_no_action(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    # Back-date inside the window — see test_two_rates_with_denominators for why
    # host-now() flakes against the DB-clock half-open upper bound.
    now = datetime.now(UTC) - timedelta(minutes=1)
    # NULL action_tags (not just []) must count toward no_action and not crash.
    await _seed_resolved(factory, alert_code="slip_fall", action_tags=None, t_event=now)
    row = _by_code(await _get(app_client))["slip_fall"]
    assert row["resolved_total"] == 1
    assert row["no_action_count"] == 1
    assert row["no_action_rate"] == pytest.approx(1.0)
    assert row["explicit_fp_rate"] == pytest.approx(0.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raised_rows_do_not_count_as_resolved(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    # Back-date inside the window — see test_two_rates_with_denominators for why
    # host-now() flakes against the DB-clock half-open upper bound.
    now = datetime.now(UTC) - timedelta(minutes=1)
    # A 'raised' audit row in window must not inflate resolved_total.
    raised_eid = str(uuid.uuid4())
    async with factory() as s:
        await _seed_parent(s, eid=raised_eid, alert_code="door_obstruction", t_event=now)
        await s.execute(
            text("""
                INSERT INTO escalation_audit
                    (audit_id, escalation_id, transition, operator_id, alert_code,
                     t_event, t_fired, action_tags, dwell_focus_ms,
                     confidence_score, confidence_basis, model_versions)
                VALUES
                    (:a, :e, 'raised', NULL, 'door_obstruction',
                     :t, :t, NULL, NULL, NULL, 'sensor', '{}'::jsonb)
            """),
            {"a": str(uuid.uuid4()), "e": raised_eid, "t": now},
        )
        await s.commit()
    await _seed_resolved(
        factory, alert_code="door_obstruction", action_tags=["false_alarm"], t_event=now
    )
    row = _by_code(await _get(app_client))["door_obstruction"]
    assert row["resolved_total"] == 1
    assert row["explicit_fp_rate"] == pytest.approx(1.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_window_upper_bound_is_half_open(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    boundary = datetime(2026, 6, 10, 0, 0, 0, tzinfo=UTC)
    # row exactly at `to` must be EXCLUDED (half-open upper bound).
    await _seed_resolved(
        factory, alert_code="door_obstruction", action_tags=["false_alarm"], t_event=boundary
    )
    body = await _get(
        app_client,
        **{"from": "2026-06-01T00:00:00Z", "to": "2026-06-10T00:00:00Z"},
    )
    assert body == []
    # one microsecond before `to` is INCLUDED.
    await _seed_resolved(
        factory,
        alert_code="door_obstruction",
        action_tags=["false_alarm"],
        t_event=boundary - timedelta(microseconds=1),
    )
    body = await _get(
        app_client,
        **{"from": "2026-06-01T00:00:00Z", "to": "2026-06-10T00:00:00Z"},
    )
    assert _by_code(body)["door_obstruction"]["resolved_total"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_requires_api_key(app_client: AsyncClient) -> None:
    r = await app_client.get(_ENDPOINT)
    assert r.status_code in (401, 403)
