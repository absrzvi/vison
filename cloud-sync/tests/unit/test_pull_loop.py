"""Pull loop — HTTP error path + empty page path."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from cloud_sync import db as db_mod
from cloud_sync import pull_loop
from cloud_sync.config import Settings
from cloud_sync.event_store_client import EventStoreClient


def _envelope(i: int) -> dict:
    return {
        "event_id": f"{i:08x}-0000-4000-8000-000000000000",
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": "V001",
        "timestamp": f"2026-05-17T10:00:{i:02d}Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {"car_id": "car-1"},
    }


@pytest.mark.unit
async def test_pull_loop_handles_http_error_and_retries(tmp_path: Path) -> None:
    """When event-store is unreachable, pull_loop logs + backs off without
    crashing."""
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()

    settings = Settings(
        event_store_url="http://event-store-test",
        queue_db_path=db_file,
        pull_poll_interval_s=0.01,
    )

    with respx.mock(assert_all_called=False) as rmock:
        rmock.get("http://event-store-test/api/v1/events").mock(
            side_effect=httpx.ConnectError("network down")
        )
        stop_event = asyncio.Event()
        async with httpx.AsyncClient() as http_client:
            client = EventStoreClient(http_client, settings)

            def _conn_factory():
                return db_mod.get_connection(db_file)

            task = asyncio.create_task(
                pull_loop.run(stop_event, client, _conn_factory, settings)
            )
            await asyncio.sleep(0.3)  # let it cycle through the error path
            stop_event.set()
            # Cancel to interrupt any in-flight tenacity backoff sleep.
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=10.0)
            except (TimeoutError, asyncio.CancelledError):
                pass

    # No rows enqueued; the pull loop survived the HTTP error.
    conn2 = db_mod.get_connection(db_file)
    try:
        assert db_mod.queue_depth(conn2) == 0
    finally:
        conn2.close()


@pytest.mark.unit
async def test_pull_loop_handles_empty_page(tmp_path: Path) -> None:
    """Empty page → sleep + retry without changing cursor."""
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()

    settings = Settings(
        event_store_url="http://event-store-test",
        queue_db_path=db_file,
        pull_poll_interval_s=0.01,
    )

    with respx.mock(assert_all_called=False) as rmock:
        rmock.get("http://event-store-test/api/v1/events").mock(
            return_value=httpx.Response(
                200,
                json={"data": [], "count": 0, "journey_id": None, "next_cursor": None},
            )
        )
        stop_event = asyncio.Event()
        async with httpx.AsyncClient() as http_client:
            client = EventStoreClient(http_client, settings)

            def _conn_factory():
                return db_mod.get_connection(db_file)

            task = asyncio.create_task(
                pull_loop.run(stop_event, client, _conn_factory, settings)
            )
            await asyncio.sleep(0.2)
            stop_event.set()
            await asyncio.wait_for(task, timeout=5.0)

    conn2 = db_mod.get_connection(db_file)
    try:
        assert db_mod.queue_depth(conn2) == 0
        pulled, _ = db_mod.cursor_state_get(conn2)
        assert pulled is None  # never advanced
    finally:
        conn2.close()
