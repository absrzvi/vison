"""Pull loop resilience — malformed envelopes from event-store don't kill it."""
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


def _valid_envelope(i: int) -> dict:
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
async def test_malformed_envelope_skipped_loop_continues(tmp_path: Path) -> None:
    """A mid-batch envelope missing required keys is logged + skipped; the
    pull loop continues + advances the cursor to the last well-formed row.
    """
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()

    settings = Settings(
        event_store_url="http://event-store-test",
        queue_db_path=db_file,
        pull_poll_interval_s=0.01,
    )

    valid_a = _valid_envelope(1)
    malformed = {"event_id": "deadbeef-1111-4111-8111-111111111111"}  # missing fields
    valid_b = _valid_envelope(2)

    with respx.mock(assert_all_called=False) as rmock:
        # First call returns the mixed page; subsequent calls return empty.
        def _handler(request: httpx.Request) -> httpx.Response:
            after = request.url.params.get("after")
            if after is None:
                return httpx.Response(
                    200,
                    json={
                        "data": [valid_a, malformed, valid_b],
                        "count": 3,
                        "journey_id": None,
                        "next_cursor": None,
                    },
                )
            return httpx.Response(
                200,
                json={"data": [], "count": 0, "journey_id": None, "next_cursor": None},
            )

        rmock.get("http://event-store-test/api/v1/events").mock(side_effect=_handler)
        stop_event = asyncio.Event()
        async with httpx.AsyncClient() as http_client:
            client = EventStoreClient(http_client, settings)

            def _conn_factory():
                return db_mod.get_connection(db_file)

            task = asyncio.create_task(
                pull_loop.run(stop_event, client, _conn_factory, settings)
            )
            # Wait until the pull happens.
            await asyncio.sleep(0.2)
            stop_event.set()
            await asyncio.wait_for(task, timeout=5.0)

    # Two valid envelopes enqueued; malformed one skipped.
    conn2 = db_mod.get_connection(db_file)
    try:
        depth = db_mod.queue_depth(conn2)
        assert depth == 2
        # Cursor advanced to the LAST well-formed envelope (valid_b).
        pulled, _ = db_mod.cursor_state_get(conn2)
        assert pulled == valid_b["event_id"]
    finally:
        conn2.close()


@pytest.mark.unit
async def test_trailing_malformed_envelope_does_not_pin_cursor(tmp_path: Path) -> None:
    """A malformed envelope at the TAIL of the batch must not prevent cursor
    advancement to the last well-formed envelope (otherwise loop spins forever).
    """
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()

    settings = Settings(
        event_store_url="http://event-store-test",
        queue_db_path=db_file,
        pull_poll_interval_s=0.01,
    )
    valid_a = _valid_envelope(1)
    malformed_tail = {"event_id": "deadbeef-1111-4111-8111-222222222222"}

    with respx.mock(assert_all_called=False) as rmock:
        def _handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("after") is None:
                return httpx.Response(
                    200,
                    json={
                        "data": [valid_a, malformed_tail],
                        "count": 2,
                        "journey_id": None,
                        "next_cursor": None,
                    },
                )
            return httpx.Response(
                200,
                json={"data": [], "count": 0, "journey_id": None, "next_cursor": None},
            )

        rmock.get("http://event-store-test/api/v1/events").mock(side_effect=_handler)
        stop_event = asyncio.Event()
        async with httpx.AsyncClient() as http_client:
            client = EventStoreClient(http_client, settings)
            task = asyncio.create_task(
                pull_loop.run(stop_event, client, lambda: db_mod.get_connection(db_file), settings)
            )
            await asyncio.sleep(0.2)
            stop_event.set()
            await asyncio.wait_for(task, timeout=5.0)

    conn2 = db_mod.get_connection(db_file)
    try:
        pulled, _ = db_mod.cursor_state_get(conn2)
        assert pulled == valid_a["event_id"]
    finally:
        conn2.close()
