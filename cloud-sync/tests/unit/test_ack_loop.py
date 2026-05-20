"""Ack loop — tick logic + run loop driver."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from cloud_sync import ack_loop
from cloud_sync import db as db_mod
from cloud_sync.config import Settings


class _FakeClient:
    """Stand-in for EventStoreClient — captures calls + returns scripted bodies."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[str] = []

    async def ack_cursor(self, last_event_id: str) -> dict[str, Any]:
        self.calls.append(last_event_id)
        return self.response


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


def _make_queue(tmp_path: Path) -> str:
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()
    return db_file


@pytest.mark.unit
async def test_tick_no_published_rows_is_noop(tmp_path: Path) -> None:
    db_file = _make_queue(tmp_path)
    conn = db_mod.get_connection(db_file)
    try:
        db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
        # No mark_published — nothing to ack.
        client = _FakeClient({"data": {"acked": "e1", "truncated_journeys": 0}})
        settings = Settings(queue_db_path=db_file)
        await ack_loop.tick(client, conn, settings)
        assert client.calls == []  # never called
    finally:
        conn.close()


@pytest.mark.unit
async def test_tick_idempotent_when_already_acked(tmp_path: Path) -> None:
    db_file = _make_queue(tmp_path)
    conn = db_mod.get_connection(db_file)
    try:
        db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
        db_mod.mark_published(conn, "e1")
        db_mod.cursor_state_set_acked(conn, "e1")
        client = _FakeClient({"data": {"acked": "e1", "truncated_journeys": 0}})
        settings = Settings(queue_db_path=db_file)
        await ack_loop.tick(client, conn, settings)
        # No HTTP call — already at this cursor.
        assert client.calls == []
    finally:
        conn.close()


@pytest.mark.unit
async def test_tick_advances_and_deletes_rows(tmp_path: Path) -> None:
    db_file = _make_queue(tmp_path)
    conn = db_mod.get_connection(db_file)
    try:
        db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
        db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:02Z"))
        db_mod.mark_published(conn, "e1")
        db_mod.mark_published(conn, "e2")
        client = _FakeClient({"data": {"acked": "e2", "truncated_journeys": 1}})
        settings = Settings(queue_db_path=db_file)
        await ack_loop.tick(client, conn, settings)
        assert client.calls == ["e2"]
        # Rows up to and including e2 are deleted.
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM publish_queue"
        ).fetchone()["n"]
        assert remaining == 0
        _, last_acked = db_mod.cursor_state_get(conn)
        assert last_acked == "e2"
    finally:
        conn.close()


@pytest.mark.unit
async def test_tick_handles_cursor_drift_response(tmp_path: Path) -> None:
    """When event-store returns ``acked=None`` (cursor drift), tick advances
    last_acked LOCALLY past the drifted cursor + purges local rows so the
    next tick doesn't re-issue the same drift forever (code-review 2026-05-20).
    """
    db_file = _make_queue(tmp_path)
    conn = db_mod.get_connection(db_file)
    try:
        db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
        db_mod.mark_published(conn, "e1")
        client = _FakeClient({"data": {"acked": None, "truncated_journeys": 0}})
        settings = Settings(queue_db_path=db_file)
        await ack_loop.tick(client, conn, settings)
        # HTTP call WAS made, then local cursor advanced past the drift.
        assert client.calls == ["e1"]
        _, last_acked = db_mod.cursor_state_get(conn)
        assert last_acked == "e1"
        # Local rows up to and including the drifted cursor are purged.
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM publish_queue"
        ).fetchone()["n"]
        assert remaining == 0
    finally:
        conn.close()


@pytest.mark.unit
async def test_run_loop_stops_when_stop_event_set(tmp_path: Path) -> None:
    """The run() loop must exit promptly when stop_event is set."""
    db_file = _make_queue(tmp_path)

    def _conn_factory():
        return db_mod.get_connection(db_file)

    client = _FakeClient({"data": {"acked": None, "truncated_journeys": 0}})
    settings = Settings(queue_db_path=db_file, ack_interval_s=0.05)
    stop_event = asyncio.Event()

    task = asyncio.create_task(ack_loop.run(stop_event, client, _conn_factory, settings))
    # Let the loop spin a few times.
    await asyncio.sleep(0.2)
    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done()


class _FailingClient:
    """Raises httpx.HTTPError on every ack_cursor call."""

    async def ack_cursor(self, last_event_id: str) -> dict[str, Any]:
        import httpx

        raise httpx.ConnectError("event-store down")


@pytest.mark.unit
async def test_tick_handles_httpx_error_without_raising(tmp_path: Path) -> None:
    """When ack_cursor raises httpx.HTTPError, tick logs + returns cleanly."""
    db_file = _make_queue(tmp_path)
    conn = db_mod.get_connection(db_file)
    try:
        db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:01Z"))
        db_mod.mark_published(conn, "e1")
        settings = Settings(queue_db_path=db_file)
        # Should NOT raise.
        await ack_loop.tick(_FailingClient(), conn, settings)
        # Cursor unchanged because event-store rejected.
        _, last_acked = db_mod.cursor_state_get(conn)
        assert last_acked is None
    finally:
        conn.close()
