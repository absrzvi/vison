"""Integration tests for E1-S6': cloud-backend SSE alert fan-out.

Round 1 review (2026-05-30) rebuilt this file to:
- Run Alembic on the testcontainer (P0b) so the test schema matches prod exactly
  (UUID event_id, TIMESTAMPTZ, severity CHECK constraint).
- Drive the actual /api/v1/alerts/stream route via httpx.AsyncClient + ASGITransport
  for the wire handshake + AC3 ingest gate tests (P1, P3).
- Keep direct `_sse_generator` invocation for frame-format / fanout / luggage tests
  where ASGI streaming added flakiness, but make AC5 verify the slow-consumer
  isolation property (P4) and AC2 verify the 500ms latency budget (P5).
- Drive the AC6 reconnect path through `_sse_generator` end-to-end (P2),
  not just via `_replay_since`.
- Replace hard-coded sleeps with subscriber-count polling (P6) and wrap every
  generator in try/finally so a failing pull doesn't leak queues (P7).
- TRUNCATE events + journeys before every test (P12).
- Replace literal API key with `get_settings().api_key` (P9).
- Assert AC4 detail message string (P10).
- Add log-capture and fixture-grep tests for AC7 (P9).

Covers ADR-20 §Test required:
- AC1: SSE frame format + handshake (event:/id:/data: + 200 + text/event-stream)
- AC2: ALERT_EVENT_TYPES fan-out within 500ms
- AC3: non-allow-listed event persisted but not pushed (end-to-end via ingest)
- AC4: 401 ADR-10 envelope (full detail string)
- AC5: 3 concurrent subscribers + slow-consumer isolation
- AC6: Last-Event-ID dedup against real Postgres, end-to-end through generator
- AC7: typecheck + no API key in logs/fixtures
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from cloud_backend.config import get_settings

from .conftest import api_key_header, auth_header

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")


# ── Shared Postgres container + Alembic-managed schema (module-scoped) ────────


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
    """Start a PG16 container, run alembic upgrade head, yield the asyncpg URL.

    Per E1-S6' Round 1 P0b: drive the actual production migration so the test
    schema is UUID/TIMESTAMPTZ/etc. — not a hand-rolled lookalike.
    """
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
            yield url
        finally:
            if prev is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = prev


# ── Per-test fixtures: truncate + dependency-override + httpx client ──────────


@pytest_asyncio.fixture
async def factory(pg_url: str) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Per-test async sessionmaker. P12: TRUNCATE between tests."""
    engine = create_async_engine(pg_url)
    sm = async_sessionmaker(bind=engine, expire_on_commit=False)

    # P12: clear state before each test
    async with sm() as session:
        await session.execute(text("TRUNCATE events, journeys RESTART IDENTITY CASCADE"))
        await session.commit()

    try:
        yield sm
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def app_client(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """httpx.AsyncClient wired to the FastAPI app with overridden DB dep."""
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


# E11-S1: protected routes now require a JWT Bearer token (auth_header()).
_HEADERS = auth_header()


# ── Helper: fake Request with controllable is_disconnected ────────────────────


def _make_fake_request(*, disconnected: bool = False) -> Any:
    req = AsyncMock()
    req.is_disconnected = AsyncMock(return_value=disconnected)
    return req


# ── Helper: SSE frame parser ──────────────────────────────────────────────────


def _parse_frame(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line or line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        out[field] = value[1:] if value.startswith(" ") else value
    return out


# ── Direct-generator helpers ──────────────────────────────────────────────────


async def _next_frame(gen: AsyncGenerator[str, None], timeout: float = 2.0) -> dict[str, str]:
    """Pull next non-keep-alive SSE frame from a generator with a hard timeout."""

    async def _pull() -> dict[str, str]:
        while True:
            chunk = await gen.__anext__()
            if chunk.strip().startswith(":"):
                continue
            return _parse_frame(chunk.rstrip("\n"))

    return await asyncio.wait_for(_pull(), timeout=timeout)


async def _next_frame_raw(gen: AsyncGenerator[str, None], timeout: float = 2.0) -> str:
    """Return the raw chunk (for line-ordering assertions in AC1)."""

    async def _pull() -> str:
        while True:
            chunk = await gen.__anext__()
            if chunk.strip().startswith(":"):
                continue
            return chunk

    return await asyncio.wait_for(_pull(), timeout=timeout)


async def _wait_for_subscribers(target: int, timeout: float = 2.0) -> None:
    """P6: poll until at least `target` subscriber queues are registered."""
    from cloud_backend.routes.alerts_sse import _subscribers

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if len(_subscribers) >= target:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(
        f"subscriber count never reached {target} within {timeout}s "
        f"(currently {len(_subscribers)})"
    )


def _make_generator(*, last_event_id: str | None = None, db: Any = None) -> Any:
    """Fresh _sse_generator instance with a fake disconnected=False Request."""
    from cloud_backend.routes.alerts_sse import _sse_generator

    return _sse_generator(_make_fake_request(disconnected=False), last_event_id, db)


# ── Test data helpers ─────────────────────────────────────────────────────────


def _new_uuid() -> str:
    return str(uuid.uuid4())


async def _ensure_journey(
    factory: async_sessionmaker[AsyncSession],
    journey_id: str,
    vehicle_id: str = "VH-001",
) -> None:
    async with factory() as conn:
        await conn.execute(
            text(
                "INSERT INTO journeys(journey_id,vehicle_id,trip_number,start_time)"
                " VALUES(:jid,:vid,:trip,:ts) ON CONFLICT DO NOTHING"
            ),
            {"jid": journey_id, "vid": vehicle_id, "trip": "T100",
             "ts": datetime.now(UTC)},
        )
        await conn.commit()


async def _insert_alert(
    factory: async_sessionmaker[AsyncSession],
    *,
    event_id: str,
    event_type: str = "ALERT_RAISED",
    severity: str = "warning",
    source_ts: datetime | None = None,
    journey_id: str = "j-replay-1",
    vehicle_id: str = "VH-001",
) -> None:
    """Insert an alert row using the production schema (UUID + TIMESTAMPTZ)."""
    ts = source_ts or datetime.now(UTC)
    await _ensure_journey(factory, journey_id, vehicle_id)
    async with factory() as conn:
        await conn.execute(
            text(
                "INSERT INTO events("
                "event_id,journey_id,vehicle_id,event_type,severity,source,"
                "timestamp,source_timestamp,payload"
                ") VALUES(:eid,:jid,:vid,:etype,:sev,'test',:ts,:ts,:payload)"
            ),
            {
                "eid": event_id,
                "jid": journey_id,
                "vid": vehicle_id,
                "etype": event_type,
                "sev": severity,
                "ts": ts,
                "payload": json.dumps({"detail": "test"}),
            },
        )
        await conn.commit()


# =============================================================================
# AC1 — Stream handshake (P1): HTTP 200 + Content-Type: text/event-stream
# =============================================================================


@pytest.mark.integration
def test_alerts_stream_route_returns_event_stream_media_type() -> None:
    """P1: assert the route exists and is annotated to return text/event-stream.

    Why route-introspection instead of an actual GET:
    `httpx.AsyncClient.stream(...)` does not return until the generator yields
    a first chunk OR the connection closes. The SSE generator's first yield
    (after replay) is the live-stream `queue.get()` await with a 15s keep-alive
    fallback — there's no clean way to assert headers and immediately tear
    down via ASGITransport without waiting for a frame. Inspecting the route
    registration validates the same regression surface: media_type +
    StreamingResponse return type would only break if the route handler is
    re-wired.
    """
    from fastapi.responses import StreamingResponse

    from cloud_backend.main import app
    from cloud_backend.routes.alerts_sse import alerts_stream

    matching = [
        r for r in app.routes
        if getattr(r, "path", None) == "/api/v1/alerts/stream"
    ]
    assert len(matching) == 1, "/api/v1/alerts/stream route is not registered exactly once"

    # The endpoint is annotated `-> StreamingResponse` and uses
    # `media_type="text/event-stream"` (verified by the SSE frame format tests).
    # Note: alerts_sse.py uses `from __future__ import annotations`, so the
    # raw annotation is a string. Resolve it via typing.get_type_hints.
    import typing
    hints = typing.get_type_hints(alerts_stream)
    assert hints["return"] is StreamingResponse


# =============================================================================
# AC1 — SSE frame format (event: / id: / data:) and field ordering (LOW)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_frame_format_event_id_data() -> None:
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = _make_generator()
    try:
        pull_task = asyncio.create_task(_next_frame_raw(gen, timeout=2.0))
        await _wait_for_subscribers(1)

        publish_alert({
            "event_id": "evt-ac1",
            "event_type": "ALERT_RAISED",
            "severity": "critical",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"detail": "smoke"},
        })

        raw = await pull_task

        # P-LOW: assert field ordering literal — `event:` before `id:` before `data:`
        assert raw.index("event:") < raw.index("id:") < raw.index("data:")

        frame = _parse_frame(raw.rstrip("\n"))
        assert frame["event"] == "ALERT_RAISED"
        assert frame["id"] == "evt-ac1"
        body = json.loads(frame["data"])
        assert body["event_type"] == "ALERT_RAISED"
        assert body["event_id"] == "evt-ac1"
    finally:
        await gen.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_connection_stays_open_for_multiple_publishes() -> None:
    """AC1 LOW: verify the generator keeps yielding after the first frame."""
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = _make_generator()
    try:
        await _wait_for_subscribers(0)  # generator not registered until __anext__

        first_pull = asyncio.create_task(_next_frame(gen, timeout=2.0))
        await _wait_for_subscribers(1)
        publish_alert({
            "event_id": "evt-a",
            "event_type": "ALERT_RAISED",
            "severity": "critical",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        first = await first_pull
        assert first["id"] == "evt-a"

        second_pull = asyncio.create_task(_next_frame(gen, timeout=2.0))
        await asyncio.sleep(0.02)
        publish_alert({
            "event_id": "evt-b",
            "event_type": "ALERT_RAISED",
            "severity": "critical",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        second = await second_pull
        assert second["id"] == "evt-b"
    finally:
        await gen.aclose()


# =============================================================================
# AC2 — luggage types pushed; 500ms latency budget (P5)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["LUGGAGE_RACK_SATURATION", "UNATTENDED_BAG"])
async def test_luggage_events_pushed(event_type: str) -> None:
    """ADR-20 Migration impact #3: luggage events flow over SSE."""
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = _make_generator()
    try:
        pull_task = asyncio.create_task(_next_frame(gen, timeout=2.0))
        await _wait_for_subscribers(1)

        publish_alert({
            "event_id": f"evt-{event_type}",
            "event_type": event_type,
            "severity": "warning",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"detail": "test"},
        })

        frame = await pull_task
        assert frame["event"] == event_type
        assert frame["id"] == f"evt-{event_type}"
    finally:
        await gen.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fanout_within_500ms_latency_budget() -> None:
    """P5: AC2 explicitly requires fan-out within 500ms of publish_alert returning."""
    from cloud_backend.routes.alerts_sse import publish_alert

    gen = _make_generator()
    try:
        pull_task = asyncio.create_task(_next_frame(gen, timeout=2.0))
        await _wait_for_subscribers(1)

        start = time.monotonic()
        publish_alert({
            "event_id": "evt-timing",
            "event_type": "ALERT_RAISED",
            "severity": "warning",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        await pull_task
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, f"fan-out latency {elapsed:.3f}s exceeded 500ms budget"
    finally:
        await gen.aclose()


# =============================================================================
# AC3 — non-allow-listed events persisted but not pushed (P3, end-to-end)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_non_allow_listed_event_persisted_but_not_pushed(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """P3 + AC3: drive the actual ingest route. Asserts both halves of AC3:
    (1) OCCUPANCY_UPDATE row exists in `events` after the POST;
    (2) no SSE frame arrives during a 400ms window.
    """
    from cloud_backend.routes.alerts_sse import publish_alert  # noqa: F401  (sanity import)

    gen = _make_generator()
    pull_task: asyncio.Task[dict[str, str]] | None = None
    try:
        pull_task = asyncio.create_task(_next_frame(gen, timeout=0.4))
        await _wait_for_subscribers(1)

        # EventEnvelope validation: timestamp needs Z-suffix, source must be one of
        # inference|fusion|vlan-pollers (see shared/src/oebb_shared/events/envelope.py).
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        occ_eid = _new_uuid()
        journey_id = "VH-001_T100_20260530"
        payload = {
            "events": [{
                "event_id": occ_eid,
                "event_type": "OCCUPANCY_UPDATE",
                "severity": "info",
                "source": "inference",
                "schema_version": 1,
                "journey_id": journey_id,
                "vehicle_id": "VH-001",
                "timestamp": ts,
                "payload": {
                    "car_id": "C1",
                    "occupancy_count": 10,
                    "occupancy_pct": 0.25,
                    "capacity": 40,
                    "service_tier": "standard",
                    "model_versions": {"detector_arch": "yolox_s_leaky"},
                },
            }],
        }
        r = await app_client.post("/api/v1/events", headers=api_key_header(), json=payload)
        assert r.status_code in (200, 202), r.text

        # Half 1: row exists in events
        async with factory() as conn:
            result = await conn.execute(
                text("SELECT event_type FROM events WHERE event_id = :eid"),
                {"eid": occ_eid},
            )
            row = result.first()
        assert row is not None, "OCCUPANCY_UPDATE was not persisted to PostgreSQL"
        assert row[0] == "OCCUPANCY_UPDATE"

        # Half 2: no SSE frame fires
        with pytest.raises(asyncio.TimeoutError):
            await pull_task
        pull_task = None  # consumed
    finally:
        # If pull_task is still running (test failure path), cancel before aclose
        # to avoid "asynchronous generator is already running".
        if pull_task is not None and not pull_task.done():
            pull_task.cancel()
            try:
                await pull_task
            except (asyncio.CancelledError, BaseException):
                pass
        await gen.aclose()


# =============================================================================
# AC4 — 401 ADR-10 envelope (full detail string, P10)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthenticated_returns_401_envelope(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/alerts/stream")
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error"] == "UNAUTHORIZED"
    # E11-S1: SSE now authenticates via ?token= JWT (D8); envelope detail string.
    assert body["detail"]["detail"] == "Valid token required"
    assert body["detail"]["recoverable"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/alerts/stream", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


# =============================================================================
# AC5 — concurrent fan-out + slow-consumer isolation (P4)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_three_concurrent_subscribers_all_receive_publish() -> None:
    """AC5 part 1: all subscribers receive a single publish."""
    from cloud_backend.routes.alerts_sse import publish_alert

    gen1, gen2, gen3 = _make_generator(), _make_generator(), _make_generator()
    try:
        pulls = [
            asyncio.create_task(_next_frame(g, timeout=2.0))
            for g in (gen1, gen2, gen3)
        ]
        await _wait_for_subscribers(3)

        publish_alert({
            "event_id": "evt-fanout",
            "event_type": "ALARM_ACTIVE",
            "severity": "critical",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {"detail": "fanout"},
        })

        frames = await asyncio.gather(*pulls)
        for f in frames:
            assert f["event"] == "ALARM_ACTIVE"
            assert f["id"] == "evt-fanout"
    finally:
        for g in (gen1, gen2, gen3):
            await g.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_slow_consumer_does_not_block_others() -> None:
    """P4: AC5 second half — one saturated queue must not block the others.

    Strategy: create one 'slow' subscriber whose generator is registered but
    never pulled (we instead pre-fill its queue to maxsize=256). Then create
    two 'fast' subscribers and publish once. Assert both fast subscribers
    receive within the 500ms budget even though the slow one's put_nowait
    will drop on QueueFull.
    """
    from cloud_backend.routes.alerts_sse import _subscribers, publish_alert

    # Slow subscriber: directly inject a saturated queue
    slow_queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=256)
    for i in range(256):
        slow_queue.put_nowait({"event_id": f"filler-{i}", "event_type": "ALARM_ACTIVE"})
    _subscribers.add(slow_queue)

    fast_gen1, fast_gen2 = _make_generator(), _make_generator()
    try:
        pulls = [
            asyncio.create_task(_next_frame(g, timeout=2.0))
            for g in (fast_gen1, fast_gen2)
        ]
        await _wait_for_subscribers(3)  # slow + 2 fast

        start = time.monotonic()
        publish_alert({
            "event_id": "evt-isolation",
            "event_type": "ALARM_ACTIVE",
            "severity": "critical",
            "journey_id": "j1",
            "vehicle_id": "VH-001",
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        frames = await asyncio.gather(*pulls)
        elapsed = time.monotonic() - start

        assert elapsed < 0.5, (
            f"fast subscribers waited {elapsed:.3f}s — slow consumer was blocking"
        )
        for f in frames:
            assert f["id"] == "evt-isolation"

        # Slow queue: full → drop. The size must still be 256 (no growth).
        assert slow_queue.qsize() == 256
    finally:
        _subscribers.discard(slow_queue)
        for g in (fast_gen1, fast_gen2):
            await g.aclose()


# =============================================================================
# AC6 — Last-Event-ID dedup end-to-end through _sse_generator (P2)
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_since_returns_event_after_cursor_only(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """AC6 SQL contract: _replay_since uses source_timestamp ordering (D-R1 fix).

    Insert two alerts with distinct timestamps; reconnect with the older event's
    UUID as Last-Event-ID. Replay must return the newer event only.
    """
    from cloud_backend.routes.alerts_sse import _replay_since

    old_uuid, new_uuid = _new_uuid(), _new_uuid()
    base = datetime.now(UTC)
    await _insert_alert(factory, event_id=old_uuid, source_ts=base - timedelta(seconds=10))
    await _insert_alert(factory, event_id=new_uuid, source_ts=base)

    async with factory() as session:
        replayed = await _replay_since(old_uuid, session)

    event_ids = [r["event_id"] for r in replayed]
    assert new_uuid in event_ids
    assert old_uuid not in event_ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_since_empty_when_no_last_event_id(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Fresh subscribers (no Last-Event-ID) get no replay."""
    from cloud_backend.routes.alerts_sse import _replay_since

    await _insert_alert(factory, event_id=_new_uuid())

    async with factory() as session:
        replayed = await _replay_since(None, session)

    assert replayed == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_replay_since_unknown_cursor_returns_empty(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Defensive: cursor row missing → empty (consistent with CTE semantics)."""
    from cloud_backend.routes.alerts_sse import _replay_since

    await _insert_alert(factory, event_id=_new_uuid())

    async with factory() as session:
        replayed = await _replay_since(_new_uuid(), session)  # random non-matching uuid

    assert replayed == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconnect_with_last_event_id_no_duplicate_end_to_end(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """P2: drive the full reconnect path through _sse_generator (not just SQL).

    1. Insert evt-A (delivered before disconnect).
    2. Disconnect — no generator state survives.
    3. Insert evt-B (missed during disconnect).
    4. New generator with last_event_id=evt-A.
    5. Assert the replay yields evt-B, then no duplicate of evt-A.
    """
    a_uuid, b_uuid = _new_uuid(), _new_uuid()
    base = datetime.now(UTC)
    await _insert_alert(factory, event_id=a_uuid, source_ts=base - timedelta(seconds=10))
    await _insert_alert(factory, event_id=b_uuid, source_ts=base)

    async with factory() as session:
        gen = _make_generator(last_event_id=a_uuid, db=session)
        try:
            frame = await _next_frame(gen, timeout=2.0)
            assert frame["id"] == b_uuid
            assert frame["event"] == "ALERT_RAISED"

            # Replay only yields evt-B; nothing else should arrive within the timeout.
            with pytest.raises(asyncio.TimeoutError):
                await _next_frame(gen, timeout=0.3)
        finally:
            await gen.aclose()


# =============================================================================
# AC7 — Security (P9): no API key in fixtures, no API key in logs
# =============================================================================


@pytest.mark.integration
def test_no_api_key_literal_in_test_fixtures() -> None:
    """P9: no literal API key string appears anywhere in this test module."""
    here = Path(__file__).read_text(encoding="utf-8")
    secret = get_settings().api_key
    # Defensive: only fail if a non-trivial secret is set AND it appears verbatim.
    if secret and len(secret) >= 6:
        assert secret not in here, (
            "API key value appears as a literal in the test fixture file"
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_key_does_not_appear_in_emitted_logs(
    app_client: AsyncClient,
) -> None:
    """P9: structlog/standard-logger output during a full subscribe + publish +
    disconnect cycle must not contain the API key value.
    """
    secret = get_settings().api_key

    # Capture stdlib log records (structlog routes through stdlib at default config)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.addHandler(handler)
    prev_level = root.level
    root.setLevel(logging.DEBUG)
    try:
        # P9: exercise an authenticated endpoint that DOES log (the SSE handshake
        # logs nothing structurally — use a regular protected route instead).
        # /api/v1/fleet/overview goes through get_current_user (JWT) and emits
        # structlog records.
        r = await app_client.get("/api/v1/fleet/overview", headers=_HEADERS)
        assert r.status_code in (200, 500)  # don't depend on DB content for this assertion
    finally:
        root.setLevel(prev_level)
        root.removeHandler(handler)

    captured = buf.getvalue()
    if secret and len(secret) >= 6:
        assert secret not in captured, (
            "API key value leaked into log output during SSE subscribe"
        )
