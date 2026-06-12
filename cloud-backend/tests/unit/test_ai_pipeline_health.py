"""Story 10-1 AC19 — GET /api/v1/health/ai-pipeline per-train + fleet rules."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.config import get_settings
from cloud_backend.database import get_db
from cloud_backend.main import app

pytestmark = pytest.mark.unit

_HEADERS = {"X-API-Key": get_settings().api_key}
_NOW = datetime.now(UTC)
_MV = {"detector_arch": "yolox_s_leaky"}


def _hb_row(train_id: str, last_seen: datetime, ok: bool) -> MagicMock:
    row = MagicMock()
    row.train_id = train_id
    row.last_seen = last_seen
    row.model_versions = dict(_MV)
    row.hailo_device_ok = ok
    return row


def _active_row(vehicle_id: str) -> MagicMock:
    row = MagicMock()
    row.vehicle_id = vehicle_id
    return row


def _override_db(hb_rows: list[Any], active_rows: list[Any]) -> None:
    async def _gen() -> AsyncGenerator[Any, None]:
        session = MagicMock()
        call_idx = 0

        async def _execute(stmt: Any, params: Any = None) -> MagicMock:
            nonlocal call_idx
            rows = [hb_rows, active_rows][call_idx] if call_idx < 2 else []
            call_idx += 1
            result = MagicMock()
            result.__iter__ = MagicMock(return_value=iter(rows))
            return result

        session.execute = _execute
        yield session

    app.dependency_overrides[get_db] = _gen


@pytest.fixture(autouse=True)
def _clean() -> Any:
    yield
    app.dependency_overrides.pop(get_db, None)


def _get(client: TestClient) -> dict[str, Any]:
    r = client.get("/api/v1/health/ai-pipeline", headers=_HEADERS)
    assert r.status_code == 200
    return r.json()


def test_green_when_fresh_and_device_ok() -> None:
    _override_db([_hb_row("V001", _NOW - timedelta(seconds=30), True)], [_active_row("V001")])
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    assert body["fleet_state"] == "green"
    assert body["trains"][0]["state"] == "green"
    assert body["trains"][0]["model_versions"] == _MV
    assert body["trains"][0]["hailo_device_ok"] is True


def test_amber_when_fresh_but_device_not_ok() -> None:
    _override_db([_hb_row("V001", _NOW - timedelta(seconds=30), False)], [_active_row("V001")])
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    assert body["trains"][0]["state"] == "amber"
    assert body["fleet_state"] == "amber"


def test_red_when_heartbeat_stale() -> None:
    _override_db([_hb_row("V001", _NOW - timedelta(minutes=5), True)], [_active_row("V001")])
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    assert body["trains"][0]["state"] == "red"
    assert body["fleet_state"] == "red"


def test_red_when_active_train_has_no_heartbeat_row() -> None:
    _override_db([], [_active_row("V002")])
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    trains = {t["train_id"]: t for t in body["trains"]}
    assert trains["V002"]["state"] == "red"
    assert body["fleet_state"] == "red"


def test_fleet_rollup_worst_case() -> None:
    _override_db(
        [
            _hb_row("V001", _NOW - timedelta(seconds=10), True),   # green
            _hb_row("V002", _NOW - timedelta(seconds=10), False),  # amber
        ],
        [_active_row("V001"), _active_row("V002")],
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    assert body["fleet_state"] == "amber"


def test_cold_state_empty_trains() -> None:
    _override_db([], [])
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get(client)
    assert body["trains"] == []
    assert body["fleet_state"] == "green"
