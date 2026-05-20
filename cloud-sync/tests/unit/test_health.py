"""GET /health endpoint."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cloud_sync import db as db_mod
from cloud_sync.health import router as health_router


class _FakeMqtt:
    """Minimal stub satisfying the broker_connected.is_set() contract."""

    def __init__(self, connected: bool) -> None:
        self._evt = asyncio.Event()
        if connected:
            self._evt.set()

    @property
    def broker_connected(self) -> asyncio.Event:
        return self._evt


def _make_app(db_path: str, *, connected: bool) -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.state.queue_db_path = db_path
    app.state.mqtt = _FakeMqtt(connected)
    return app


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


@pytest.mark.unit
def test_health_returns_expected_shape(tmp_path: Path) -> None:
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    db_mod.enqueue_event(conn, _envelope("e2", "2026-05-17T10:00:01Z"))
    conn.close()

    app = _make_app(db_file, connected=True)
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["broker_connected"] is True
    assert body["queue_depth"] == 2
    assert body["last_publish_utc"] is None


@pytest.mark.unit
def test_health_broker_disconnected_when_event_not_set(tmp_path: Path) -> None:
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    conn.close()

    app = _make_app(db_file, connected=False)
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["broker_connected"] is False
    assert body["queue_depth"] == 0


@pytest.mark.unit
def test_health_last_publish_utc_set_after_publish(tmp_path: Path) -> None:
    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    db_mod.enqueue_event(conn, _envelope("e1", "2026-05-17T10:00:00Z"))
    db_mod.mark_published(conn, "e1")
    conn.close()

    app = _make_app(db_file, connected=True)
    with TestClient(app) as c:
        r = c.get("/health")
    body = r.json()
    assert body["last_publish_utc"] is not None
    assert body["last_publish_utc"].endswith("Z")
    # Once e1 is published, queue depth (pending) is 0.
    assert body["queue_depth"] == 0
