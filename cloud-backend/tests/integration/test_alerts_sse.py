"""Integration tests for E1-S6': cloud-backend SSE alert fan-out.

Covers ADR-20 §Test required:
- AC1: SSE frame format (event:/id:/data: lines) emitted by `_sse_generator`
- AC2: ALERT_EVENT_TYPES fan-out (incl. luggage types added per ADR-20 #3)
- AC3: non-allow-listed events not pushed (gate at ingest.py:97)
- AC4: 401 ADR-10 envelope on unauthenticated GET
- AC5: 3 concurrent subscribers all receive a single publish
- AC6: Last-Event-ID replay-since against real Postgres

Strategy: rather than wire-stream through httpx+ASGITransport (which is
unreliable for SSE because chunks are buffered and the ASGI app's StreamingResponse
yield-points don't surface deterministically), this file:

- drives `_sse_generator` directly for the frame-format / fan-out / luggage tests
  (same code path, deterministic; no ASGI buffering involved); and
- drives `_replay_since` directly against a real Postgres testcontainer for AC6.

Auth tests still go through the FastAPI app via httpx.AsyncClient — they don't
involve streaming.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# ── Shared Postgres container (module-scoped, sync) ───────────────────────────


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")


def _now_ts() -> str:
    return datetime.now(UTC).isoformat()


async def _create_schema(session_factory: async_sessionmaker[AsyncSession]) -> None:
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
        await conn.commit()


async def _insert_event(
    factory: async_sessionmaker[AsyncSession],
    event_id: str,
    event_type: str,
    *,
    severity: str = "warning",
    source_ts: str | None = None,
) -> None:
    ts = source_ts or _now_ts()
    async with factory() as conn:
        await conn.execute(
            text(
                "INSERT INTO events(event_id,journey_id,vehicle_id,timestamp,event_type,"
                "severity,source_timestamp,payload) VALUES(:eid,'j1','VH-001',:ts,:etype,"
                ":sev,:ts,:payload) ON CONFLICT DO NOTHING"
            ),
            {
                "eid": event_id,
                "ts": ts,
                "etype": event_type,
                "sev": severity,
                "payload": json.dumps({"detail": "test"}),
            },
        )
        await conn.commit()


_HEADERS = {"X-API-Key": "dev-insecure-key"}


# ── Helper: fake Request with controllable is_disconnected ────────────────────


def _make_fake_request(*, disconnected: bool = False) -> Any:
    """Return an object that satisfies the `Request` shape the SSE generator
    needs: ``await request.is_disconnected()`` returns the supplied flag.
    """
    req = AsyncMock()
    req.is_disconnected = AsyncMock(return_value=disconnected)
    return req


# ── Helper: SSE frame parser ──────────────────────────────────────────────────


def _parse_frame(raw: str) -> dict[str, str]:
    """Parse one SSE frame string (without trailing blank line)."""
    out: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line or line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        out[field] = value[1:] if value.startswith(" ") else value
    return out


# ── AC4: Unauthenticated → 401 ADR-10 envelope (via FastAPI app) ──────────────


@pytest_asyncio.fixture
async def app_client(pg_url: str) -> AsyncGenerator[AsyncClient, None]:
    """A bare httpx.AsyncClient against the FastAPI app for auth tests."""
    from cloud_backend.database import get_db
    from cloud_backend.main import app

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _create_schema(factory)

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthenticated_returns_401_envelope(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/alerts/stream")
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error"] == "UNAUTHORIZED"
    assert body["detail"]["recoverable"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/alerts/stream", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


# ── Direct-generator fixture (fast, deterministic) ────────────────────────────


@pytest_asyncio.fixture
async def gen_factory() -> AsyncGenerator[Any, None]:
    """Yields a helper that produces a fresh _sse_generator instance and ensures
    the module-level `_subscribers` set is cleaned up between tests."""
    from cloud_backend.routes.alerts_sse import _sse_generator, _subscribers

    _subscribers.clear()

    def _make(*, last_event_id: str | None = None, db: Any = None) -> Any:
        return _sse_generator(
            _make_fake_request(disconnected=False),
            last_event_id,
            db,
        )

    yield _make
    _subscribers.clear()


async def _next_frame(gen: AsyncGenerator[str, None], timeout: float = 2.0) -> dict[str, str]:
    """Pull the next non-keep-alive frame from an SSE generator with a hard timeout."""
    async def _pull() -> dict[str, str]:
        while True:
            chunk = await gen.__anext__()
            if chunk.strip().startswith(":"):  # keep-alive, skip
                continue
            return _parse_frame(chunk.rstrip("\n"))

    return await asyncio.wait_for(_pull(), timeout=timeout)


# ── AC1: SSE frame format (event:/id:/data:) ──────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_frame_format_event_id_data(gen_factory: Any) -> None:
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = gen_factory()
    # Drive the generator to the queue.get() point so the queue is registered.
    pull_task = asyncio.create_task(_next_frame(gen, timeout=2.0))
    await asyncio.sleep(0.05)  # let the generator reach queue.get()

    publish_alert({
        "event_id": "evt-ac1",
        "event_type": "ALERT_RAISED",
        "severity": "critical",
        "journey_id": "j1",
        "vehicle_id": "VH-001",
        "timestamp": _now_ts(),
        "payload": {"detail": "smoke"},
    })

    frame = await pull_task
    assert frame["event"] == "ALERT_RAISED"
    assert frame["id"] == "evt-ac1"
    body = json.loads(frame["data"])
    assert body["event_type"] == "ALERT_RAISED"
    assert body["event_id"] == "evt-ac1"

    await gen.aclose()


# ── AC2 extension: luggage event types pushed ─────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["LUGGAGE_RACK_SATURATION", "UNATTENDED_BAG"])
async def test_luggage_events_pushed(gen_factory: Any, event_type: str) -> None:
    """ADR-20 Migration impact #3: luggage events now flow over SSE."""
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = gen_factory()
    pull_task = asyncio.create_task(_next_frame(gen, timeout=2.0))
    await asyncio.sleep(0.05)

    publish_alert({
        "event_id": f"evt-{event_type}",
        "event_type": event_type,
        "severity": "warning",
        "journey_id": "j1",
        "vehicle_id": "VH-001",
        "timestamp": _now_ts(),
        "payload": {"detail": "test"},
    })

    frame = await pull_task
    assert frame["event"] == event_type
    assert frame["id"] == f"evt-{event_type}"

    await gen.aclose()


# ── AC3: non-allow-listed events not pushed ───────────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_allow_listed_event_blocked_by_ingest_gate() -> None:
    """AC3: the gate at ingest.py:97 is `if ev.event_type in ALERT_EVENT_TYPES`.

    Lock the gate by asserting the imported reference behaves as the spec requires.
    """
    from cloud_backend.routes.alerts_sse import ALERT_EVENT_TYPES

    # Allow-listed
    for et in ("ALARM_ACTIVE", "ALERT_RAISED", "ALERT_RESOLVED",
               "LUGGAGE_RACK_SATURATION", "UNATTENDED_BAG"):
        assert et in ALERT_EVENT_TYPES

    # Non-allow-listed (anything else)
    for et in ("OCCUPANCY_UPDATE", "DOOR_OBSTRUCTION", "VESTIBULE_CONGESTION",
               "COACH_COMFORT_INDEX", "INFERENCE_RESULT", "SYSTEM_HEALTH"):
        assert et not in ALERT_EVENT_TYPES


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_alert_only_fires_when_gate_matches(gen_factory: Any) -> None:
    """Belt-and-braces: drive the gate logic the way ingest.py does."""
    from cloud_backend.routes.alerts_sse import ALERT_EVENT_TYPES, publish_alert

    gen = gen_factory()
    pull_task = asyncio.create_task(_next_frame(gen, timeout=0.4))
    await asyncio.sleep(0.05)

    # OCCUPANCY_UPDATE — would be skipped at ingest.py:97
    occupancy = {"event_id": "occ-1", "event_type": "OCCUPANCY_UPDATE",
                 "severity": "info", "journey_id": "j1", "vehicle_id": "VH-001",
                 "timestamp": _now_ts(), "payload": {}}
    if occupancy["event_type"] in ALERT_EVENT_TYPES:  # the actual ingest gate
        publish_alert(occupancy)  # pragma: no cover — must not execute

    # No frame should arrive
    with pytest.raises(asyncio.TimeoutError):
        await pull_task

    await gen.aclose()


# ── AC5: three concurrent subscribers all receive a single publish ────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_concurrent_subscribers_all_receive_publish(gen_factory: Any) -> None:
    from cloud_backend.routes.alerts_sse import _subscribers, publish_alert

    gen1, gen2, gen3 = gen_factory(), gen_factory(), gen_factory()
    pulls = [
        asyncio.create_task(_next_frame(gen1, timeout=2.0)),
        asyncio.create_task(_next_frame(gen2, timeout=2.0)),
        asyncio.create_task(_next_frame(gen3, timeout=2.0)),
    ]
    # Drive each generator to its queue.get() point
    await asyncio.sleep(0.1)
    assert len(_subscribers) == 3, f"only {len(_subscribers)} subscribers registered"

    publish_alert({
        "event_id": "evt-fanout",
        "event_type": "ALARM_ACTIVE",
        "severity": "critical",
        "journey_id": "j1",
        "vehicle_id": "VH-001",
        "timestamp": _now_ts(),
        "payload": {"detail": "fanout"},
    })

    frames = await asyncio.gather(*pulls)
    for f in frames:
        assert f["event"] == "ALARM_ACTIVE"
        assert f["id"] == "evt-fanout"

    for g in (gen1, gen2, gen3):
        await g.aclose()


# ── AC6: Last-Event-ID dedup against real Postgres ────────────────────────────


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_since_no_duplicate_after_last_event_id(pg_url: str) -> None:
    """AC6: simulates an EventSource reconnect after worker restart.

    Insert evt-001 + evt-002 into the events table. Replay with
    Last-Event-ID = evt-001. Assert: evt-002 is replayed (event_id > evt-001
    by string compare), evt-001 is NOT (the > filter excludes equality).

    Note: `_replay_since` uses string comparison on `event_id`, so this AC
    only holds when `event_id` values are monotonically increasing strings.
    See Decision D2 in the story file for the ratification finding.
    """
    from cloud_backend.routes.alerts_sse import _replay_since

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _create_schema(factory)

    # source_timestamp ordering matters for the ORDER BY in _replay_since.
    # event_id must sort lexicographically: 'evt-001' < 'evt-002'.
    await _insert_event(factory, "evt-001", "ALERT_RAISED",
                        source_ts="2026-05-30T10:00:00+00:00")
    await _insert_event(factory, "evt-002", "ALERT_RAISED",
                        source_ts="2026-05-30T10:01:00+00:00")

    async with factory() as session:
        replayed = await _replay_since("evt-001", session)

    event_ids = [r["event_id"] for r in replayed]
    assert "evt-002" in event_ids, f"expected evt-002 in replay, got {event_ids}"
    assert "evt-001" not in event_ids, f"evt-001 must NOT be replayed, got {event_ids}"

    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_since_empty_when_no_last_event_id(pg_url: str) -> None:
    """Boundary: a fresh subscriber (no Last-Event-ID header) gets no replay,
    avoiding spurious replay-on-first-connect."""
    from cloud_backend.routes.alerts_sse import _replay_since

    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    await _create_schema(factory)
    await _insert_event(factory, "evt-prior", "ALERT_RAISED")

    async with factory() as session:
        replayed = await _replay_since(None, session)

    assert replayed == []
    await engine.dispose()
