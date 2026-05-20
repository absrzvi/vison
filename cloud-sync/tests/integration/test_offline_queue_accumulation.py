"""AC5: when MQTT is down, pull loop continues — queue accumulates."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx

from cloud_sync import db as db_mod
from cloud_sync import pull_loop as pull_loop_mod
from cloud_sync.config import Settings
from cloud_sync.event_store_client import EventStoreClient


def _envelope(event_id: str, ts: str) -> dict:
    return {
        "event_id": event_id,
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": "V001",
        "timestamp": ts,
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {"car_id": "car-1"},
    }


@pytest.mark.integration
async def test_pull_loop_accumulates_100_events_when_broker_offline(tmp_path: Path) -> None:
    """Simulate broker totally unreachable. The pull loop is independent
    of broker state — it MUST keep draining event-store into the local
    queue. After 100 events, queue_depth == 100, all unpublished.
    """
    db_file = str(tmp_path / "queue.db")
    boot = db_mod.get_connection(db_file)
    db_mod.init_db(boot)
    boot.close()

    settings = Settings(
        event_store_url="http://event-store-test",
        queue_db_path=db_file,
        pull_batch_size=50,
        pull_poll_interval_s=0.01,
    )

    # Pre-seed 100 envelopes; serve them in 2 batches via respx.
    all_envelopes = [
        _envelope(
            f"{i:08x}-0000-4000-8000-000000000000",
            f"2026-05-17T10:00:{i:02d}Z",
        )
        for i in range(100)
    ]

    with respx.mock(assert_all_called=False) as rmock:
        # Batch 1: first 50, with next_cursor pointing to the 50th id.
        # Batch 2: next 50, with next_cursor=None.
        # Subsequent calls: empty data, signaling end-of-stream.
        def _handler(request: httpx.Request) -> httpx.Response:
            after = request.url.params.get("after")
            if after is None:
                batch = all_envelopes[:50]
            elif after == all_envelopes[49]["event_id"]:
                batch = all_envelopes[50:]
            else:
                batch = []
            return httpx.Response(
                200,
                json={
                    "data": batch,
                    "count": len(batch),
                    "journey_id": None,
                    "next_cursor": (
                        batch[-1]["event_id"] if len(batch) == 50 else None
                    ),
                },
            )

        rmock.get("http://event-store-test/api/v1/events").mock(side_effect=_handler)

        stop_event = asyncio.Event()
        async with httpx.AsyncClient() as http_client:
            client = EventStoreClient(http_client, settings)

            def _conn_factory():
                return db_mod.get_connection(db_file)

            task = asyncio.create_task(
                pull_loop_mod.run(stop_event, client, _conn_factory, settings)
            )
            # Let the loop drain both batches. Poll until depth reaches 100.
            for _ in range(200):
                conn = db_mod.get_connection(db_file)
                try:
                    depth = db_mod.queue_depth(conn)
                finally:
                    conn.close()
                if depth >= 100:
                    break
                await asyncio.sleep(0.01)
            stop_event.set()
            await asyncio.wait_for(task, timeout=2.0)

    # Verify the final state.
    conn = db_mod.get_connection(db_file)
    try:
        assert db_mod.queue_depth(conn) == 100
        pending = db_mod.iter_pending(conn, limit=200)
        assert len(pending) == 100
        # All envelope_json round-trips and preserves payload.
        for row in pending[:5]:
            env = json.loads(row["envelope_json"])
            assert env["payload"]["car_id"] == "car-1"
        # Cursor advanced.
        pulled, _ = db_mod.cursor_state_get(conn)
        assert pulled == all_envelopes[-1]["event_id"]
    finally:
        conn.close()
