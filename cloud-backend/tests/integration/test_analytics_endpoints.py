"""Integration tests for E3-S1 analytics endpoints using testcontainers."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from .conftest import auth_header

# ── Shared Postgres container (module-scoped, sync) ───────────────────────────

@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")


def _now_ts() -> str:
    return datetime.now(UTC).isoformat()


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    ts = _now_ts()
    async with session_factory() as conn:
        await conn.execute(text("""
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
        """))
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

        # Journeys
        for jid, vid, trip, route in [
            ("j1", "VH-001", "T100", "Vienna-Salzburg"),
            ("j2", "VH-002", "T200", "Graz-Linz"),
        ]:
            await conn.execute(
                text("INSERT INTO journeys VALUES (:jid,:vid,:trip,:route,NULL,NULL,:ts,NULL)"
                     " ON CONFLICT DO NOTHING"),
                {"jid": jid, "vid": vid, "trip": trip, "route": route, "ts": ts},
            )

        # CAPACITY_EXCEPTION events
        exceptions: list[tuple[str, str, str, str, str, dict[str, Any]]] = [
            ("ex1", "j1", "VH-001", "CAPACITY_EXCEPTION", "critical",
             {"route": "Vienna-Salzburg", "departure": "08:00", "status": "unreviewed",
              "coach_peaks": [{"coach_id": "C1", "peak_pct": 95.0}],
              "trend": [80, 85, 90, 92, 93, 94, 95]}),
            ("ex2", "j1", "VH-001", "CAPACITY_EXCEPTION", "warning",
             {"route": "Vienna-Salzburg", "departure": "10:00", "status": "in_review",
              "coach_peaks": [], "trend": [60, 62, 65, 68, 70, 72, 74]}),
            ("ex3", "j2", "VH-002", "CAPACITY_EXCEPTION", "info",
             {"route": "Graz-Linz", "departure": "09:00", "status": "unreviewed",
              "coach_peaks": [], "trend": [40, 42, 44, 46, 48, 50, 52]}),
        ]
        for eid, jid, vid, etype, sev, payload in exceptions:
            await conn.execute(
                text("INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                     "severity,payload) VALUES(:eid,:jid,:vid,:ts,:etype,:sev,:payload)"
                     " ON CONFLICT DO NOTHING"),
                {"eid": eid, "jid": jid, "vid": vid, "ts": ts, "etype": etype,
                 "sev": sev, "payload": json.dumps(payload)},
            )

        # OCCUPANCY_UPDATE — sparse: only j1/hour=9 and j2/hour=14.
        # Anchor to a recent date so rows fall inside the rolling `range` window
        # (the heatmap query filters timestamp >= now - range); fixed dates would
        # drift out of the window as wall-clock time advances.
        _day = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d")
        for eid, jid, vid, ots, payload in [
            ("oc1", "j1", "VH-001", f"{_day}T09:30:00+00:00", {"occupancy_pct": 80.0}),
            ("oc2", "j1", "VH-001", f"{_day}T09:45:00+00:00", {"occupancy_pct": 85.0}),
            ("oc3", "j2", "VH-002", f"{_day}T14:00:00+00:00", {"occupancy_pct": 40.0}),
        ]:
            await conn.execute(
                text("INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                     "severity,payload) VALUES(:eid,:jid,:vid,:ts,'OCCUPANCY_UPDATE','info',"
                     ":payload) ON CONFLICT DO NOTHING"),
                {"eid": eid, "jid": jid, "vid": vid, "ts": ots, "payload": json.dumps(payload)},
            )

        # DWELL_EVENT — 3 stations
        for eid, jid, vid, payload in [
            ("dw1", "j1", "VH-001",
             {"station": "Wien Hbf", "scheduled_sec": 180, "actual_sec": 240,
              "breach": True, "occupancy_pct": 70}),
            ("dw2", "j1", "VH-001",
             {"station": "Salzburg", "scheduled_sec": 120, "actual_sec": 110,
              "breach": False, "occupancy_pct": 50}),
            ("dw3", "j2", "VH-002",
             {"station": "Graz", "scheduled_sec": 60, "actual_sec": 90,
              "breach": True, "occupancy_pct": None}),
        ]:
            await conn.execute(
                text("INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                     "severity,payload) VALUES(:eid,:jid,:vid,:ts,'DWELL_EVENT','info',:payload)"
                     " ON CONFLICT DO NOTHING"),
                {"eid": eid, "jid": jid, "vid": vid, "ts": ts, "payload": json.dumps(payload)},
            )

        # INFERENCE_RESULT — 5 events, no false positives
        for i in range(5):
            await conn.execute(
                text("INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                     "severity,payload) VALUES(:eid,'j1','VH-001',:ts,'INFERENCE_RESULT','info',"
                     ":payload) ON CONFLICT DO NOTHING"),
                {"eid": f"inf{i}", "ts": ts,
                 "payload": json.dumps({"confidence": 0.9, "fp_flag": False})},
            )

        # SYSTEM_HEALTH
        health: dict[str, Any] = {
            "cctvStatus": "green", "appStatus": "red",
            "deviceStatus": "green", "connectivityStatus": "green",
            "last_healthy": "2026-05-18T09:43:00Z",
            "appDetail": [{"container": "hailo-ingest", "status": "red",
                           "last_healthy": "2026-05-18T09:43:00Z"}],
            "deviceDetail": [{"device": "hailo-8", "status": "green", "temperature_c": 65.0}],
            "connectivity": {"lte_status": "green", "wifi_status": "green",
                             "last_sync": "2026-05-18T10:00:00Z"},
        }
        await conn.execute(
            text("INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                 "severity,payload) VALUES('sh1','j1','VH-001',:ts,'SYSTEM_HEALTH','info',:payload)"
                 " ON CONFLICT DO NOTHING"),
            {"ts": ts, "payload": json.dumps(health)},
        )
        await conn.commit()


# ── Per-test client fixture ───────────────────────────────────────────────────

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


_HEADERS = auth_header()


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_exceptions_endpoint_returns_records(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/exceptions", headers=_HEADERS, params={"range": "7d"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 3
    routes = {rec["route"] for rec in data}
    assert "Vienna-Salzburg" in routes
    assert "Graz-Linz" in routes


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exceptions_record_has_required_fields(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/exceptions", headers=_HEADERS, params={"range": "7d"})
    rec = r.json()[0]
    for field in ("exception_id", "route", "train_id", "departure", "date", "status",
                  "severity", "coach_peaks", "trend"):
        assert field in rec, f"missing field: {field}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heatmap_has_null_for_empty_cells(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/occupancy-heatmap", headers=_HEADERS,
                         params={"range": "7d"})
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data and "hours" in data and "cells" in data
    all_vals = [v for row in data["cells"] for v in row]
    assert None in all_vals, "Expected null values for hours with no occupancy data"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dwell_time_sorted_descending(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/dwell-time", headers=_HEADERS, params={"range": "7d"})
    assert r.status_code == 200
    records = r.json()
    assert len(records) == 3
    actual_secs = [rec["actual_sec"] for rec in records]
    assert actual_secs == sorted(actual_secs, reverse=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fp_rate_not_null_when_events_exist(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/detection-quality", headers=_HEADERS,
                         params={"range": "7d"})
    assert r.status_code == 200
    kpi = r.json()["kpi"]
    assert kpi["total_events"] == 5
    # All fp_flag=False → fp_rate = 0.0 (not null — events exist)
    assert kpi["fp_rate"] == 0.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_health_iso_timestamps(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/system-health", headers=_HEADERS)
    assert r.status_code == 200
    records = r.json()
    assert len(records) >= 1
    ts = records[0]["last_healthy"]
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.year >= 2026


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_range_integration(client: AsyncClient) -> None:
    r = await client.get("/api/v1/analytics/exceptions", headers=_HEADERS,
                         params={"range": "90d"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "INVALID_RANGE"
    assert body["recoverable"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fp_rate_null_when_no_events(client: AsyncClient, pg_url: str) -> None:
    """fp_rate must be None (not 0.0) when no INFERENCE_RESULT events exist in range."""
    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as conn:
        await conn.execute(text("DELETE FROM events WHERE event_type = 'INFERENCE_RESULT'"))
        await conn.commit()
    await engine.dispose()

    r = await client.get("/api/v1/analytics/detection-quality", headers=_HEADERS,
                         params={"range": "7d"})
    assert r.status_code == 200
    kpi = r.json()["kpi"]
    assert kpi["total_events"] == 0
    assert kpi["fp_rate"] is None
