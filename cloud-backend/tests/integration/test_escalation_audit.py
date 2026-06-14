"""Story 10-2 — operator behavioural telemetry (integration).

Against real Postgres (testcontainers + Alembic head):
- AC1: each escalation lifecycle transition appends an escalation_audit row
  (raised on ALERT_RAISED ingest; acknowledged/resolved on the 10-6 endpoints).
  Idempotent / concurrent-loser transitions do NOT double-write.
- AC2: silently-dismissed endpoint appends a row only while unacknowledged.
- AC3: the funnel endpoint aggregates per alert_code with ack-latency percentiles
  and an action-tag distribution; null-confidence rows do not break aggregation;
  invalid ISO range → 422.
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

from cloud_backend.config import get_settings

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_API_HEADERS = {"X-API-Key": get_settings().api_key}


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


def _alert_envelope(
    *,
    event_id: str,
    alert_id: str,
    alert_code: str = "UNATTENDED_BAG",
    confidence_basis: str = "model",
) -> dict[str, object]:
    """Build a schema-valid ALERT_RAISED envelope. AlertRaisedPayload enforces
    per-basis confidence invariants: model → score in [0,1] + non-empty
    model_versions; sensor → score is None + empty model_versions.

    The envelope timestamp becomes the escalation's t_fired and the 'raised' audit
    row's t_event (ingest stamps both from the parsed envelope clock — the client/
    train clock). The later 'acknowledged'/'resolved' audit rows take t_event from
    the DB clock (t_ack/t_resolve = NOW()). If t_fired were stamped at wall-clock
    now() and the client clock ran a few ms AHEAD of the DB, the raised row would
    sort after — and fall outside the funnel's [.., NOW()) window — relative to the
    DB-clock transitions. Back-dating a few seconds (an alert always fires onboard
    BEFORE it is ingested landside, so this also mirrors real data) keeps t_fired
    deterministically earlier than every DB-clock transition, well inside the
    7-day default window — without weakening the route's skew-proof NOW() default.
    """
    ts = (datetime.now(UTC) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S.%f")[
        :-3
    ] + "Z"
    if confidence_basis == "sensor":
        payload: dict[str, object] = {
            "alert_id": alert_id,
            "alert_code": alert_code,
            "car_id": "car-1",
            "description": "audit fixture alert",
            "confidence_score": None,
            "confidence_basis": "sensor",
            "model_versions": {},
        }
    else:
        payload = {
            "alert_id": alert_id,
            "alert_code": alert_code,
            "car_id": "car-1",
            "description": "audit fixture alert",
            "confidence_score": 0.9,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        }
    return {
        "event_id": event_id,
        "journey_id": "V001_RJ-0001_20260613",
        "vehicle_id": "V001",
        "timestamp": ts,
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": payload,
    }


async def _ingest_alert(
    client: AsyncClient,
    *,
    alert_code: str = "UNATTENDED_BAG",
    confidence_basis: str = "model",
) -> str:
    event_id = str(uuid.uuid4())
    env = _alert_envelope(
        event_id=event_id,
        alert_id=str(uuid.uuid4()),
        alert_code=alert_code,
        confidence_basis=confidence_basis,
    )
    r = await client.post("/api/v1/events", headers=_API_HEADERS, json={"events": [env]})
    assert r.status_code == 202, r.text
    return event_id


async def _ack(client: AsyncClient, escalation_id: str, operator_id: str = "op-1") -> int:
    r = await client.post(
        f"/api/v1/escalations/{escalation_id}/acknowledge",
        headers=_API_HEADERS,
        json={"operator_id": operator_id},
    )
    return r.status_code


async def _resolve(
    client: AsyncClient,
    escalation_id: str,
    *,
    action_tags: list[str],
    operator_id: str = "op-1",
) -> int:
    r = await client.post(
        f"/api/v1/escalations/{escalation_id}/resolve",
        headers=_API_HEADERS,
        json={"outcome": "done", "action_tags": action_tags, "operator_id": operator_id},
    )
    return r.status_code


def _funnel_window() -> dict[str, str]:
    """Query params pinning the funnel's upper bound safely into the future.

    The fixture stamps t_event with the CLIENT clock (datetime.now(UTC)), but the
    route's default `to` is the DB clock's NOW(). A few ms of client→DB skew puts
    freshly-ingested rows at t_event > NOW(), so they fall outside the default
    half-open [NOW()-7d, NOW()) window non-deterministically. Passing an explicit
    `to` one hour ahead dwarfs any ms-level skew and makes the window deterministic
    without weakening the route's skew-proof default for real (non-test) callers.
    """
    return {"to": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], escalation_id: str
) -> list[dict[str, object]]:
    async with factory() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT * FROM escalation_audit WHERE escalation_id = :id "
                    "ORDER BY t_event"
                ),
                {"id": escalation_id},
            )
        ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# AC1 — one audit row per transition
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_raised_appends_audit_row(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    eid = await _ingest_alert(app_client)
    rows = await _audit_rows(factory, eid)
    assert len(rows) == 1
    r = rows[0]
    assert r["transition"] == "raised"
    assert r["operator_id"] is None
    assert r["alert_code"] == "UNATTENDED_BAG"
    assert r["t_event"] == r["t_fired"]
    assert r["action_tags"] is None
    assert r["dwell_focus_ms"] is None
    assert r["confidence_score"] == 0.9
    assert r["confidence_basis"] == "model"
    assert r["model_versions"] == {"detector_arch": "yolox_s_leaky"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_lifecycle_appends_three_rows(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    eid = await _ingest_alert(app_client)
    assert await _ack(app_client, eid, "op-7") == 200
    assert await _resolve(app_client, eid, action_tags=["Resolved remotely"]) == 200
    rows = await _audit_rows(factory, eid)
    assert [r["transition"] for r in rows] == ["raised", "acknowledged", "resolved"]
    ack_row = rows[1]
    assert ack_row["operator_id"] == "op-7"
    assert ack_row["t_event"] is not None
    resolved_row = rows[2]
    # action_tags carried over as canonical keys (10-6 resolve maps label→key).
    assert resolved_row["action_tags"] == ["resolved_remotely"]
    # Denormalised t_fired identical across all three rows.
    assert rows[0]["t_fired"] == ack_row["t_fired"] == resolved_row["t_fired"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotent_ack_does_not_double_write(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    eid = await _ingest_alert(app_client)
    await _ack(app_client, eid, "op-1")
    await _ack(app_client, eid, "op-2")  # idempotent no-op
    rows = await _audit_rows(factory, eid)
    ack_rows = [r for r in rows if r["transition"] == "acknowledged"]
    assert len(ack_rows) == 1
    assert ack_rows[0]["operator_id"] == "op-1"  # first ack wins


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotent_resolve_does_not_double_write(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    eid = await _ingest_alert(app_client)
    await _ack(app_client, eid)
    await _resolve(app_client, eid, action_tags=["No action needed"])
    await _resolve(app_client, eid, action_tags=["No action needed"])  # idempotent
    rows = await _audit_rows(factory, eid)
    assert len([r for r in rows if r["transition"] == "resolved"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reingested_alert_does_not_double_write_raised(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    event_id = str(uuid.uuid4())
    env = _alert_envelope(event_id=event_id, alert_id=str(uuid.uuid4()))
    await app_client.post("/api/v1/events", headers=_API_HEADERS, json={"events": [env]})
    await app_client.post("/api/v1/events", headers=_API_HEADERS, json={"events": [env]})
    rows = await _audit_rows(factory, event_id)
    assert len([r for r in rows if r["transition"] == "raised"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_payload_alert_writes_no_audit_row(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """An empty-payload ALERT_RAISED skips the escalation upsert (10-6 R1) — so it
    must also skip the raised audit row (no escalation to audit)."""
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
    r = await app_client.post("/api/v1/events", headers=_API_HEADERS, json={"events": [env]})
    assert r.status_code == 202
    assert await _audit_rows(factory, event_id) == []


# ---------------------------------------------------------------------------
# AC2 — silently-dismissed endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_silently_dismissed_appends_row_when_unacknowledged(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    eid = await _ingest_alert(app_client)
    t_viewed = datetime.now(UTC)
    t_dismissed = t_viewed + timedelta(seconds=8)
    r = await app_client.post(
        f"/api/v1/escalations/{eid}/silently-dismissed",
        headers=_API_HEADERS,
        json={
            "operator_id": "op-3",
            "t_viewed": t_viewed.isoformat(),
            "t_dismissed": t_dismissed.isoformat(),
            "dwell_focus_ms": 4200,
        },
    )
    assert r.status_code == 204, r.text
    rows = await _audit_rows(factory, eid)
    dismissed = [x for x in rows if x["transition"] == "silently_dismissed"]
    assert len(dismissed) == 1
    assert dismissed[0]["operator_id"] == "op-3"
    assert dismissed[0]["dwell_focus_ms"] == 4200
    assert dismissed[0]["alert_code"] == "UNATTENDED_BAG"  # denormalised
    # escalation status must remain unacknowledged (a non-action).
    async with factory() as s:
        status = (
            await s.execute(
                text("SELECT status FROM escalations WHERE escalation_id = :id"),
                {"id": eid},
            )
        ).scalar_one()
    assert status == "unacknowledged"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_silently_dismissed_skips_when_already_acknowledged(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """Client may race a concurrent ack: a dismissal beacon for an escalation that
    is no longer unacknowledged must not append a row (server-side re-check)."""
    eid = await _ingest_alert(app_client)
    await _ack(app_client, eid)
    r = await app_client.post(
        f"/api/v1/escalations/{eid}/silently-dismissed",
        headers=_API_HEADERS,
        json={
            "operator_id": "op-3",
            "t_viewed": datetime.now(UTC).isoformat(),
            "t_dismissed": datetime.now(UTC).isoformat(),
            "dwell_focus_ms": 100,
        },
    )
    assert r.status_code == 204
    rows = await _audit_rows(factory, eid)
    assert [x for x in rows if x["transition"] == "silently_dismissed"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_silently_dismissed_unknown_returns_404(app_client: AsyncClient) -> None:
    r = await app_client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/silently-dismissed",
        headers=_API_HEADERS,
        json={
            "operator_id": "op-3",
            "t_viewed": datetime.now(UTC).isoformat(),
            "t_dismissed": datetime.now(UTC).isoformat(),
            "dwell_focus_ms": 100,
        },
    )
    assert r.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_silently_dismissed_requires_api_key(app_client: AsyncClient) -> None:
    r = await app_client.post(
        f"/api/v1/escalations/{uuid.uuid4()}/silently-dismissed",
        json={
            "operator_id": "op-3",
            "t_viewed": datetime.now(UTC).isoformat(),
            "t_dismissed": datetime.now(UTC).isoformat(),
            "dwell_focus_ms": 100,
        },
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# AC3 — funnel endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_funnel_aggregates_per_alert_code(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    # Two UNATTENDED_BAG fully resolved, one acknowledged-only, one raised-only.
    e1 = await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")
    await _ack(app_client, e1)
    await _resolve(app_client, e1, action_tags=["Resolved remotely"])
    e2 = await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")
    await _ack(app_client, e2)
    await _resolve(app_client, e2, action_tags=["False alarm"])
    e3 = await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")
    await _ack(app_client, e3)
    await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")  # raised only

    r = await app_client.get(
        "/api/v1/escalations-audit", headers=_API_HEADERS, params=_funnel_window()
    )
    assert r.status_code == 200, r.text
    funnels = {f["alert_code"]: f for f in r.json()}
    bag = funnels["UNATTENDED_BAG"]
    assert bag["count_raised"] == 4
    assert bag["count_acknowledged"] == 3
    assert bag["count_resolved"] == 2
    assert bag["count_silently_dismissed"] == 0
    assert bag["median_t_ack_seconds"] is not None
    assert bag["p95_t_ack_seconds"] is not None
    assert bag["action_tag_distribution"] == {"resolved_remotely": 1, "false_alarm": 1}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_funnel_handles_null_confidence_rows(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """sensor-basis escalations carry NULL confidence_score; the funnel must not
    break on them (the NULL-aggregation bug pattern from deferred-work.md)."""
    eid = await _ingest_alert(
        app_client, alert_code="DOOR_OBSTRUCTION", confidence_basis="sensor"
    )
    await _ack(app_client, eid)
    r = await app_client.get(
        "/api/v1/escalations-audit",
        headers=_API_HEADERS,
        params={"alert_code": "DOOR_OBSTRUCTION", **_funnel_window()},
    )
    assert r.status_code == 200, r.text
    funnels = {f["alert_code"]: f for f in r.json()}
    assert funnels["DOOR_OBSTRUCTION"]["count_acknowledged"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_funnel_filter_by_alert_code(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")
    await _ingest_alert(app_client, alert_code="DOOR_OBSTRUCTION")
    r = await app_client.get(
        "/api/v1/escalations-audit",
        headers=_API_HEADERS,
        params={"alert_code": "UNATTENDED_BAG", **_funnel_window()},
    )
    assert r.status_code == 200
    codes = {f["alert_code"] for f in r.json()}
    assert codes == {"UNATTENDED_BAG"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_funnel_invalid_range_returns_422(app_client: AsyncClient) -> None:
    r = await app_client.get(
        "/api/v1/escalations-audit?from=not-a-date", headers=_API_HEADERS
    )
    assert r.status_code == 422
    assert r.json()["error"] == "INVALID_RANGE"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_funnel_requires_api_key(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/escalations-audit")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# AC4 — weekly effectiveness report (callable, idempotent)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_generates_and_is_idempotent(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    from datetime import datetime as _dt

    from cloud_backend.services.alert_effectiveness_report import (
        generate_alert_effectiveness_report,
    )

    # Seed a full lifecycle + a silent dismissal so the report has content.
    e1 = await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")
    await _ack(app_client, e1)
    await _resolve(app_client, e1, action_tags=["Resolved remotely"])
    e2 = await _ingest_alert(app_client, alert_code="UNATTENDED_BAG")  # raised, never acked
    await app_client.post(
        f"/api/v1/escalations/{e2}/silently-dismissed",
        headers=_API_HEADERS,
        json={
            "operator_id": "op-3",
            "t_viewed": datetime.now(UTC).isoformat(),
            "t_dismissed": datetime.now(UTC).isoformat(),
            "dwell_focus_ms": 1000,
        },
    )

    # The audit rows are stamped with server-side NOW(), so report for THIS ISO week.
    iso_year, iso_week, _ = _dt.now(UTC).isocalendar()

    async with factory() as session:
        path = await generate_alert_effectiveness_report(session, iso_year, iso_week)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert f"{iso_year}-W{iso_week:02d}" in content
    assert "UNATTENDED_BAG" in content
    assert "Retune candidates" in content
    assert "silent-dismissal rate" in content

    # Idempotent: re-running the same week overwrites, does not append/duplicate.
    async with factory() as session:
        path2 = await generate_alert_effectiveness_report(session, iso_year, iso_week)
    assert path2 == path
    content2 = path2.read_text(encoding="utf-8")
    assert content2.count("# Alert Effectiveness") == 1
    path.unlink()  # clean up the generated artifact


@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_empty_week_does_not_crash(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """A week with zero audit rows must produce a valid (empty-state) report, not
    divide-by-zero on the ack-rate / dismissal-rate math."""
    from cloud_backend.services.alert_effectiveness_report import (
        generate_alert_effectiveness_report,
    )

    # A historical week far from any seeded data → no rows in window.
    async with factory() as session:
        path = await generate_alert_effectiveness_report(session, 2020, 1)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "No escalations raised" in content
    assert "No kill-switch activity" in content
    path.unlink()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_clamps_negative_ack_latency(
    app_client: AsyncClient, factory: async_sessionmaker[AsyncSession]
) -> None:
    """A fast onboard clock can stamp t_fired LATER than the landside t_ack, giving a
    negative raw latency. The report's median must clamp to 0 (like the funnel route),
    never render a negative "-Ns" ack time."""
    from cloud_backend.services.alert_effectiveness_report import (
        generate_alert_effectiveness_report,
    )

    # FK parent (escalations row); its incidental 'raised' audit row is ignored —
    # the median FILTERs on transition = 'acknowledged'.
    eid = await _ingest_alert(app_client)
    # Both timestamps pinned inside ISO 2020-W10 (Mon 2020-03-02), t_fired AFTER
    # t_event so the un-clamped latency would be -60s.
    t_event = datetime(2020, 3, 2, 1, 0, tzinfo=UTC)
    t_fired = t_event + timedelta(seconds=60)
    async with factory() as s:
        await s.execute(
            text(
                "INSERT INTO escalation_audit "
                "(audit_id, escalation_id, transition, operator_id, alert_code, "
                "t_event, t_fired, action_tags, dwell_focus_ms, confidence_score, "
                "confidence_basis, model_versions) "
                "VALUES (:aid, :eid, 'acknowledged', 'op-1', 'UNATTENDED_BAG', "
                ":t_event, :t_fired, NULL, NULL, 0.9, 'model', NULL)"
            ),
            {"aid": str(uuid.uuid4()), "eid": eid, "t_event": t_event, "t_fired": t_fired},
        )
        await s.commit()

    async with factory() as session:
        path = await generate_alert_effectiveness_report(session, 2020, 10)
    content = path.read_text(encoding="utf-8")
    path.unlink()
    assert "UNATTENDED_BAG" in content  # the row is in-window
    assert "-60s" not in content  # would appear pre-clamp
    assert "0s" in content  # clamped median renders as 0s
