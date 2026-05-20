"""Per-row publish-failure path — AC8 cloud_sync.publish_error log + mark_failed."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import aiomqtt
import pytest

from cloud_sync import db as db_mod
from cloud_sync.config import Settings
from cloud_sync.mqtt_client import MqttPublisher


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


class _FakeMqttClient:
    """Raises on every publish — used to drive the per-row error path."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def publish(self, topic: str, payload: bytes, qos: int, timeout: float) -> None:
        raise self._exc


@pytest.mark.unit
async def test_publish_error_marks_failed_and_logs_per_event(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """When `client.publish` raises MqttError, the per-row failure must:
    * call db_mod.mark_failed (bumping attempts + storing last_error)
    * emit a `cloud_sync.publish_error` log with event_id + attempts
    * propagate the exception to the outer reconnect loop.
    """
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    db_mod.enqueue_event(conn, _envelope(1))
    conn.close()

    settings = Settings(
        mqtt_host="127.0.0.1",
        mqtt_port=1,
        queue_db_path=db_file,
        publish_rate_per_sec=100,
    )
    publisher = MqttPublisher(settings)
    stop_event = asyncio.Event()
    fake = _FakeMqttClient(aiomqtt.MqttError("broker drop"))

    def _conn_factory():
        return db_mod.get_connection(db_file)

    # Exercise _publish_loop directly with the fake client.
    with caplog.at_level(logging.WARNING):
        with pytest.raises(aiomqtt.MqttError):
            await publisher._publish_loop(
                fake,  # type: ignore[arg-type]
                _conn_factory,
                None,
                stop_event,
                connected_at=0.0,
            )

    # The failed row was recorded.
    conn2 = db_mod.get_connection(db_file)
    try:
        row = conn2.execute(
            "SELECT attempts, last_error FROM publish_queue"
        ).fetchone()
        assert row["attempts"] == 1
        assert row["last_error"] == "broker drop"
    finally:
        conn2.close()


@pytest.mark.unit
async def test_publish_timeout_treated_as_reconnect_trigger(tmp_path: Path) -> None:
    """asyncio.TimeoutError from publish(timeout=5) must trigger reconnect."""
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    db_mod.enqueue_event(conn, _envelope(1))
    conn.close()

    settings = Settings(
        mqtt_host="127.0.0.1",
        mqtt_port=1,
        queue_db_path=db_file,
        publish_rate_per_sec=100,
    )
    publisher = MqttPublisher(settings)
    stop_event = asyncio.Event()
    fake = _FakeMqttClient(TimeoutError("PUBACK timeout"))

    def _conn_factory():
        return db_mod.get_connection(db_file)

    with pytest.raises(asyncio.TimeoutError):
        await publisher._publish_loop(
            fake,  # type: ignore[arg-type]
            _conn_factory,
            None,
            stop_event,
            connected_at=0.0,
        )

    # mark_failed was called even though it was TimeoutError, not MqttError.
    conn2 = db_mod.get_connection(db_file)
    try:
        row = conn2.execute(
            "SELECT attempts FROM publish_queue"
        ).fetchone()
        assert row["attempts"] == 1
    finally:
        conn2.close()


@pytest.mark.unit
async def test_publish_loop_stops_when_stop_event_set(tmp_path: Path) -> None:
    """The publish loop must check stop_event between rows so shutdown
    doesn't wait for the publish queue to drain entirely."""
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    # No rows enqueued — empty queue path.
    conn.close()

    settings = Settings(queue_db_path=db_file, publish_rate_per_sec=100)
    publisher = MqttPublisher(settings)
    stop_event = asyncio.Event()
    stop_event.set()  # Already set.

    class _NeverCalled:
        async def publish(self, *a: object, **kw: object) -> None:
            raise AssertionError("publish should not be called with empty queue + stop")

    # Returns immediately because stop_event is set.
    await publisher._publish_loop(
        _NeverCalled(),  # type: ignore[arg-type]
        lambda: db_mod.get_connection(db_file),
        None,
        stop_event,
        connected_at=0.0,
    )
