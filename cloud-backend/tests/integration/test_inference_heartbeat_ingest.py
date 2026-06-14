"""Story 10-1 AC18 — INFERENCE_HEARTBEAT ingest upserts train_inference_heartbeat."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from .conftest import auth_header

_ALEMBIC_INI = str(Path(__file__).parents[2] / "alembic.ini")
_MV = {"detector_arch": "yolox_s_leaky", "detector_code": "git:9d4a60df"}


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
                "TRUNCATE events, journeys, train_inference_heartbeat "
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

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _heartbeat_envelope(train_id: str, frames: int, ok: bool) -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "event_id": str(uuid.uuid4()),
        "journey_id": f"{train_id}_RJ-0001_20260612",
        "vehicle_id": train_id,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event_type": "INFERENCE_HEARTBEAT",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {
            "train_id": train_id,
            "model_versions": dict(_MV),
            "frames_processed_window": frames,
            "last_inference_at": now.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            "hailo_device_ok": ok,
        },
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_heartbeat_ingest_upserts_row(
    app_client: AsyncClient,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    headers = auth_header()

    r = await app_client.post(
        "/api/v1/events",
        headers=headers,
        json={"events": [_heartbeat_envelope("V001", 1480, True)]},
    )
    assert r.status_code == 202
    assert r.json()["accepted"] == 1

    # Second heartbeat for the same train updates the row in place.
    r = await app_client.post(
        "/api/v1/events",
        headers=headers,
        json={"events": [_heartbeat_envelope("V001", 990, False)]},
    )
    assert r.status_code == 202

    async with factory() as session:
        rows = list(
            await session.execute(
                text("""
                    SELECT train_id, model_versions, hailo_device_ok
                    FROM train_inference_heartbeat
                """)
            )
        )
    assert len(rows) == 1
    assert rows[0].train_id == "V001"
    assert rows[0].model_versions == _MV
    assert rows[0].hailo_device_ok is False
