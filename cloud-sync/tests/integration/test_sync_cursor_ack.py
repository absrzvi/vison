"""End-to-end ack loop test: cloud-sync POSTs to event-store's sync route."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from event_store.database import (
    get_connection as es_get_connection,
)
from event_store.database import (
    get_sync_cursor,
    insert_event,
)
from event_store.database import (
    init_db as es_init_db,
)
from event_store.main import app as event_store_app
from fastapi.testclient import TestClient
from pydantic import SecretStr

from cloud_sync import ack_loop
from cloud_sync import db as db_mod
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
        "payload": "{}",  # event-store insert_event JSON-dumps if dict; string is fine here
    }


@pytest.mark.integration
async def test_ack_loop_advances_event_store_cursor(tmp_path: Path) -> None:
    """Real event-store TestClient + cloud-sync's ack_loop._tick.

    Seeds 3 events in event-store + cloud-sync's queue. Mark them published
    locally. Run one ack tick. Assert event-store's sync_cursor advances
    AND cloud-sync's queue has the rows deleted.
    """
    # Event-store DB
    es_db_file = str(tmp_path / "events.db")
    es_conn = es_get_connection(es_db_file)
    es_init_db(es_conn)
    es_conn.execute(
        "INSERT OR IGNORE INTO journeys (journey_id, vehicle_id, trip_number) "
        "VALUES (?, ?, ?)",
        ("V001_RJ-0001_20260517", "V001", "RJ-0001"),
    )
    es_conn.commit()
    eid1 = "11111111-1111-4111-8111-111111111111"
    eid2 = "22222222-2222-4222-8222-222222222222"
    eid3 = "33333333-3333-4333-8333-333333333333"
    for i, eid in enumerate((eid1, eid2, eid3)):
        insert_event(
            es_conn,
            {
                "event_id": eid,
                "journey_id": "V001_RJ-0001_20260517",
                "vehicle_id": "V001",
                "timestamp": f"2026-05-17T10:00:0{i}Z",
                "event_type": "OCCUPANCY_UPDATE",
                "severity": "info",
                "source": "inference",
                "schema_version": 1,
                "payload": "{}",
            },
        )
    es_conn.close()

    # cloud-sync queue
    cs_db_file = str(tmp_path / "queue.db")
    cs_conn = db_mod.get_connection(cs_db_file)
    db_mod.init_db(cs_conn)
    for i, eid in enumerate((eid1, eid2, eid3)):
        db_mod.enqueue_event(
            cs_conn,
            {
                "event_id": eid,
                "journey_id": "V001_RJ-0001_20260517",
                "vehicle_id": "V001",
                "timestamp": f"2026-05-17T10:00:0{i}Z",
                "event_type": "OCCUPANCY_UPDATE",
                "severity": "info",
                "source": "inference",
                "schema_version": 1,
                "payload": {"car_id": "car-1"},
            },
        )
    # Pretend all 3 have been published.
    for eid in (eid1, eid2, eid3):
        db_mod.mark_published(cs_conn, eid)
    cs_conn.close()

    # Run the ack tick against the in-process event-store via ASGI transport.
    with patch("event_store.database.settings.db_path", es_db_file), \
         patch("event_store.auth.settings.api_key", SecretStr("test-key")):
        with TestClient(event_store_app, raise_server_exceptions=False):
            transport = httpx.ASGITransport(app=event_store_app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://event-store-test"
            ) as http_client:
                settings = Settings(
                    event_store_url="http://event-store-test",
                    event_store_api_key=SecretStr("test-key"),
                    queue_db_path=cs_db_file,
                )
                client = EventStoreClient(http_client, settings)
                cs_conn2 = db_mod.get_connection(cs_db_file)
                try:
                    await ack_loop.tick(client, cs_conn2, settings)
                finally:
                    cs_conn2.close()

    # Verify event-store cursor advanced to the last id.
    es_conn2 = es_get_connection(es_db_file)
    try:
        assert get_sync_cursor(es_conn2) == eid3
    finally:
        es_conn2.close()

    # Verify cloud-sync queue rows deleted.
    cs_conn3 = db_mod.get_connection(cs_db_file)
    try:
        remaining = cs_conn3.execute(
            "SELECT COUNT(*) AS n FROM publish_queue"
        ).fetchone()["n"]
        assert remaining == 0
        _, last_acked = db_mod.cursor_state_get(cs_conn3)
        assert last_acked == eid3
    finally:
        cs_conn3.close()
