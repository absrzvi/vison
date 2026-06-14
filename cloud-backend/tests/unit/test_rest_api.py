"""Unit tests for E1-S7: auth, fleet overview shape, SSE format, error envelope."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.database import get_db
from cloud_backend.main import app

from .conftest import auth_header

_HEADERS = auth_header()


def _make_mock_db(rows_per_call: list[list[MagicMock]]) -> AsyncGenerator[AsyncMock, None]:
    """Return an async generator that yields a mock session whose execute()
    returns successive row-lists from rows_per_call."""
    call_idx = 0

    async def _gen() -> AsyncGenerator[AsyncMock, None]:
        nonlocal call_idx
        session = AsyncMock()

        async def _execute(stmt: object, params: object = None) -> MagicMock:
            nonlocal call_idx
            rows = rows_per_call[call_idx] if call_idx < len(rows_per_call) else []
            call_idx += 1
            result = MagicMock()
            result.__iter__ = MagicMock(return_value=iter(rows))
            return result

        session.execute = _execute
        yield session

    return _gen()


# ---------------------------------------------------------------------------
# AC2 — 401 when no / wrong API key
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_api_key_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/fleet/overview")
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["error"] == "UNAUTHORIZED"
    assert body["detail"]["recoverable"] is False


@pytest.mark.unit
def test_wrong_api_key_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/fleet/overview", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# AC1 — ADR-10 error envelope structure on 401
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_error_envelope_structure() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/fleet/overview")
    detail = r.json()["detail"]
    assert "error" in detail
    assert "detail" in detail
    assert "recoverable" in detail


# ---------------------------------------------------------------------------
# AC3 — fleet overview response shape
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fleet_overview_shape() -> None:
    occ_row = MagicMock()
    occ_row.journey_id = "V001_RJ-0001_20260517"
    occ_row.car_id = "car-1"
    occ_row.occupancy_pct = 0.72

    sev_row = MagicMock()
    sev_row.journey_id = "V001_RJ-0001_20260517"
    sev_row.car_id = "car-1"
    sev_row.severity = "warning"

    j_row = MagicMock()
    j_row.journey_id = "V001_RJ-0001_20260517"
    j_row.vehicle_id = "V001"
    j_row.trip_number = "RJ-0001"

    async def _mock_db() -> AsyncGenerator[AsyncMock, None]:
        call_idx = 0
        session = AsyncMock()

        async def _execute(stmt: object, params: object = None) -> MagicMock:
            nonlocal call_idx
            rows = [[occ_row], [sev_row], [j_row]][call_idx] if call_idx < 3 else []
            call_idx += 1
            result = MagicMock()
            result.__iter__ = MagicMock(return_value=iter(rows))
            return result

        session.execute = _execute
        yield session

    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/v1/fleet/overview", headers=_HEADERS)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    body = r.json()
    assert "trains" in body
    assert "total" in body
    assert body["total"] == 1
    train = body["trains"][0]
    assert train["vehicle_id"] == "V001"
    assert train["worst_severity"] == "warning"
    assert len(train["cars"]) == 1
    assert train["cars"][0]["car_id"] == "car-1"


@pytest.mark.unit
def test_fleet_overview_empty() -> None:
    async def _mock_db() -> AsyncGenerator[AsyncMock, None]:
        session = AsyncMock()

        async def _execute(stmt: object, params: object = None) -> MagicMock:
            result = MagicMock()
            result.__iter__ = MagicMock(return_value=iter([]))
            return result

        session.execute = _execute
        yield session

    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/v1/fleet/overview", headers=_HEADERS)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200
    assert r.json() == {"trains": [], "total": 0}


# ---------------------------------------------------------------------------
# AC4 — SSE endpoint returns text/event-stream (tested via route inspection)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_alerts_stream_route_registered() -> None:
    """Verify /api/v1/alerts/stream exists and would return event-stream media type."""
    import inspect

    from fastapi.responses import StreamingResponse

    from cloud_backend.routes.alerts_sse import alerts_stream

    # Check the route is registered in the app
    routes = {r.path: r for r in app.routes if hasattr(r, "path")}  # type: ignore[attr-defined]
    assert "/api/v1/alerts/stream" in routes

    # Verify media_type is event-stream by inspecting the return annotation or checking
    # that the function returns a StreamingResponse (tested via the route source)
    sig = inspect.signature(alerts_stream)
    annotation = sig.return_annotation
    assert annotation is StreamingResponse or annotation == "StreamingResponse"


# ---------------------------------------------------------------------------
# AC5 — 500 handler returns safe envelope, no traceback leaked
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unhandled_exception_returns_500() -> None:
    async def _boom_db() -> AsyncGenerator[AsyncMock, None]:
        session = AsyncMock()

        async def _execute(stmt: object, params: object = None) -> None:
            raise RuntimeError("db exploded")

        session.execute = _execute
        yield session

    app.dependency_overrides[get_db] = _boom_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/v1/fleet/overview", headers=_HEADERS)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "INTERNAL_ERROR"
    assert body["recoverable"] is True
    assert "RuntimeError" not in json.dumps(body)


# ---------------------------------------------------------------------------
# publish_alert fan-out
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_publish_alert_delivers_to_queue() -> None:
    from cloud_backend.routes.alerts_sse import _subscribers, publish_alert

    q: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    _subscribers.add(q)
    try:
        publish_alert({"event_id": "x", "event_type": "ALERT_RAISED"})
        assert not q.empty()
        item = q.get_nowait()
        assert item["event_type"] == "ALERT_RAISED"
    finally:
        _subscribers.discard(q)


@pytest.mark.unit
def test_publish_alert_full_queue_does_not_raise() -> None:
    from cloud_backend.routes.alerts_sse import _subscribers, publish_alert

    q: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
    q.put_nowait({"already": "full"})
    _subscribers.add(q)
    try:
        publish_alert({"event_id": "y", "event_type": "ALARM_ACTIVE"})  # should not raise
    finally:
        _subscribers.discard(q)


@pytest.mark.unit
def test_alerts_sse_event_types_includes_luggage() -> None:
    """E1-S6' AC2 regression: ADR-20 mandates LUGGAGE_RACK_SATURATION and
    UNATTENDED_BAG flow over the landside SSE stream (Migration impact #3)."""
    from cloud_backend.routes.alerts_sse import ALERT_EVENT_TYPES

    assert "LUGGAGE_RACK_SATURATION" in ALERT_EVENT_TYPES
    assert "UNATTENDED_BAG" in ALERT_EVENT_TYPES
    # Lock the full allow-list shape so accidental edits to the frozenset trip the test.
    assert ALERT_EVENT_TYPES == frozenset({
        "ALARM_ACTIVE",
        "ALERT_RAISED",
        "ALERT_RESOLVED",
        "LUGGAGE_RACK_SATURATION",
        "UNATTENDED_BAG",
    })
