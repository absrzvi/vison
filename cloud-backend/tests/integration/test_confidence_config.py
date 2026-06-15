"""Story 11-5 — mutable confidence thresholds (integration, A1 hard gate).

Against real Postgres (testcontainers + Alembic head, mirrors
test_killswitch_auth_swap.py). Proves on the REAL wire:
  - 0012 migration applied: the confidence_thresholds table exists, is seeded with
    the hardcoded defaults, and carries the value-range CHECK constraint;
  - admin PATCH of the degraded-banner floor is read by the LIVE ai_quality_degraded
    gate on the next evaluation — verified by ingesting model-basis ALERT_RAISED rows
    via the REAL POST /api/v1/events path (A3: not raw INSERTs) whose rolling-1h mean
    sits BETWEEN the old and new floor, then PATCHing the floor across that mean and
    asserting the flag flips (AC1 — drive an alert through, not just re-GET);
  - operator PATCH → 403, store unchanged (ST1);
  - out-of-range PATCH → 422, store unchanged (ST2).
"""
from __future__ import annotations

import os
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

from cloud_backend.api.auth import create_access_token

from .conftest import api_key_header, seed_auth_users

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_ADMIN_UID = "00000000-0000-0000-0000-0000000000ad"
_OPERATOR_UID = "00000000-0000-0000-0000-0000000000a1"


@pytest.fixture(scope="module")
def pg_url() -> Generator[str, None, None]:
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
        await session.execute(text("TRUNCATE events, journeys RESTART IDENTITY CASCADE"))
        # Reset thresholds to the seeded defaults between tests.
        await session.execute(text("DELETE FROM confidence_thresholds"))
        await session.execute(
            text("""
                INSERT INTO confidence_thresholds (config_key, value) VALUES
                ('per_class:unattended_bag', 0.75),
                ('per_class:door_obstruction', 0.85),
                ('per_class:accessibility_detected', 0.70),
                ('per_class:slip_fall', 0.75),
                ('per_class:luggage_rack_saturation', 0.70),
                ('degraded_banner_floor', 0.60)
            """)
        )
        await session.commit()
    # Reset both in-process caches so each test reads fresh.
    from cloud_backend.config.confidence_thresholds import threshold_store
    from cloud_backend.routes.health import degraded_cache

    threshold_store.invalidate()
    degraded_cache.reset()
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

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _admin_header() -> dict[str, str]:
    token = create_access_token(user_id=_ADMIN_UID, username="claudia", role="admin")
    return {"Authorization": f"Bearer {token}"}


def _operator_header() -> dict[str, str]:
    token = create_access_token(user_id=_OPERATOR_UID, username="otto", role="operator")
    return {"Authorization": f"Bearer {token}"}


def _alert_envelope(confidence: float, ts: datetime) -> dict[str, object]:
    return {
        "event_id": str(uuid.uuid4()),
        "journey_id": "V001_RJ-0001_20260612",
        "vehicle_id": "V001",
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": "ALERT_RAISED",
        "severity": "warning",
        "source": "fusion",
        "schema_version": 1,
        "payload": {
            "alert_id": str(uuid.uuid4()),
            "alert_code": "slip_fall",
            "car_id": "car-1",
            "description": "confidence-config fixture alert",
            "confidence_score": confidence,
            "confidence_basis": "model",
            "model_versions": {"detector_arch": "yolox_s_leaky"},
        },
    }


# ---------------------------------------------------------------------------
# AC4 — migration applied: table seeded + CHECK constraint present
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_0012_table_seeded_and_check_constraint_present(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        rows = list(
            await session.execute(
                text("SELECT config_key, value FROM confidence_thresholds ORDER BY config_key")
            )
        )
        seeded = {r.config_key: r.value for r in rows}
        assert seeded["degraded_banner_floor"] == 0.60
        assert seeded["per_class:unattended_bag"] == 0.75
        assert len(seeded) == 6
        # The value-range CHECK exists in the catalog (AC4 — assert via catalog,
        # not only an app-layer 422 that never reaches the DB).
        check = (
            await session.execute(
                text("""
                    SELECT conname FROM pg_constraint
                    WHERE conname = 'ck_confidence_thresholds_range'
                """)
            )
        ).fetchone()
        assert check is not None


# ---------------------------------------------------------------------------
# AC1 — admin PATCH of the floor is read by the LIVE gate (drive alerts through)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_floor_patch_flips_live_degraded_flag(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    from cloud_backend.routes.health import degraded_cache

    # Ingest model-basis alerts via the REAL ingest path; mean confidence = 0.50.
    now = datetime.now(UTC)
    events = [
        _alert_envelope(0.50, now - timedelta(minutes=5)),
        _alert_envelope(0.50, now - timedelta(minutes=4)),
    ]
    r = await app_client.post(
        "/api/v1/events", headers=api_key_header(), json={"events": events}
    )
    assert r.status_code == 202

    # With the seeded floor 0.60, mean 0.50 < 0.60 → degraded TRUE. (Reset the flag
    # cache once to establish the baseline — this is initial-state seeding, NOT the
    # propagation under test.)
    degraded_cache.reset()
    r = await app_client.get("/api/v1/health", headers=_operator_header())
    assert r.status_code == 200
    assert r.json()["ai_quality_degraded"] is True

    # Admin lowers the floor to 0.40 (below the 0.50 mean).
    r = await app_client.patch(
        "/api/v1/config/confidence-thresholds",
        headers=_admin_header(),
        json={"degraded_banner_floor": 0.40},
    )
    assert r.status_code == 200
    assert r.json()["degraded_banner_floor"] == 0.40

    # R1: the LIVE gate flips with NO manual cache reset — the PATCH itself resets
    # degraded_cache, so the next request recomputes against the persisted 0.40
    # (mean 0.50 >= 0.40 → degraded FALSE). This proves production behaviour, not a
    # test-only reset that masks the ≤30s staleness.
    r = await app_client.get("/api/v1/health", headers=_operator_header())
    assert r.json()["ai_quality_degraded"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_per_class_patch_read_back_via_get(
    app_client: AsyncClient,
) -> None:
    r = await app_client.patch(
        "/api/v1/config/confidence-thresholds",
        headers=_admin_header(),
        json={"per_class": {"unattended_bag": 0.80}},
    )
    assert r.status_code == 200
    r = await app_client.get(
        "/api/v1/config/confidence-thresholds", headers=_operator_header()
    )
    assert r.status_code == 200
    assert r.json()["per_class"]["unattended_bag"] == 0.80


# ---------------------------------------------------------------------------
# ST1 / ST2 — operator → 403, out-of-range → 422, store unchanged
# ---------------------------------------------------------------------------


_FLOOR_SQL = (
    "SELECT value FROM confidence_thresholds "
    "WHERE config_key='degraded_banner_floor'"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_operator_patch_403_store_unchanged(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    r = await app_client.patch(
        "/api/v1/config/confidence-thresholds",
        headers=_operator_header(),
        json={"degraded_banner_floor": 0.10},
    )
    assert r.status_code == 403
    async with factory() as session:
        floor = (await session.execute(text(_FLOOR_SQL))).scalar()
        assert floor == 0.60  # unchanged


@pytest.mark.integration
@pytest.mark.asyncio
async def test_out_of_range_patch_422_store_unchanged(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    r = await app_client.patch(
        "/api/v1/config/confidence-thresholds",
        headers=_admin_header(),
        json={"degraded_banner_floor": 1.5},
    )
    assert r.status_code == 422
    # R1 — ADR-10 envelope, not FastAPI's default RequestValidationError body.
    assert r.json()["detail"]["error"] == "UNPROCESSABLE"
    async with factory() as session:
        floor = (await session.execute(text(_FLOOR_SQL))).scalar()
        assert floor == 0.60  # unchanged


@pytest.mark.integration
@pytest.mark.asyncio
async def test_floor_zero_rejected_422_store_unchanged(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """R1 — a floor of 0.0 is a fail-OPEN and must be rejected on the real wire,
    leaving the seeded 0.60 intact."""
    r = await app_client.patch(
        "/api/v1/config/confidence-thresholds",
        headers=_admin_header(),
        json={"degraded_banner_floor": 0.0},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "UNPROCESSABLE"
    async with factory() as session:
        floor = (await session.execute(text(_FLOOR_SQL))).scalar()
        assert floor == 0.60  # unchanged


@pytest.mark.integration
@pytest.mark.asyncio
async def test_db_check_forbids_zero_floor_raw_write(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """R1 defense-in-depth: the 0013 partial CHECK rejects a RAW write of a 0.0
    floor at the DB layer, while a raw 0.0 per-class write is allowed."""
    from sqlalchemy.exc import IntegrityError

    async with factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    "UPDATE confidence_thresholds SET value = 0.0 "
                    "WHERE config_key = 'degraded_banner_floor'"
                )
            )
            await session.commit()
    # A per-class 0.0 raw write is permitted (no fail-open — display only).
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE confidence_thresholds SET value = 0.0 "
                "WHERE config_key = 'per_class:unattended_bag'"
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# 0012 migration idempotency + downgrade→upgrade re-apply
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_0012_downgrade_upgrade_reapplies(pg_url: str) -> None:
    """Sync test (NOT async): Alembic runs asyncio.run() internally, which cannot
    nest inside a running event loop — mirrors the sync up/down tests in
    test_migrations.py. head → 0011 (drops the table) → head (recreates + reseeds)."""
    import psycopg2
    from alembic import command
    from alembic.config import Config

    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.downgrade(cfg, "0011")
    command.upgrade(cfg, "head")

    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM confidence_thresholds")
        assert cur.fetchone()[0] == 6
    finally:
        conn.close()
    # The downgrade wiped only confidence_thresholds; users/auth rows survive (0011
    # is above 0009/0010), so no re-seed of auth users is needed.
