"""Security + unit tests for E2-S8: per-operator configurable alert threshold.

Security tests written first (RED phase) — they will fail until the router exists.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.config import get_settings
from cloud_backend.main import app

_API_KEY = get_settings().api_key
_HEADERS = {"X-API-Key": _API_KEY}

# ── Security Tests ─────────────────────────────────────────────────────────

# SEC3: GET without API key → 401
@pytest.mark.unit
def test_get_preferences_no_api_key_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/operators/me/preferences")
    assert r.status_code == 401


# SEC4: PATCH without API key → 401
@pytest.mark.unit
def test_patch_preferences_no_api_key_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch("/api/v1/operators/me/preferences", json={"threshold_sec": 60})
    assert r.status_code == 401


# SEC1: PATCH with out-of-range threshold_sec → 422
@pytest.mark.unit
def test_patch_preferences_invalid_threshold_returns_422() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/operators/me/preferences",
            json={"threshold_sec": 999},
            headers=_HEADERS,
        )
    assert r.status_code == 422
    body = r.json()
    assert body["detail"]["error"] == "INVALID_PREFERENCE"
    assert body["detail"]["recoverable"] is True


# SEC2: operator_id in request body is ignored — derived from API key server-side
@pytest.mark.unit
def test_patch_preferences_body_operator_id_ignored() -> None:
    """Even if the client sends operator_id in the body, the server ignores it
    and uses the API key to derive the real operator_id."""
    mock_row = MagicMock()
    mock_row.operator_id = _API_KEY
    mock_row.threshold_sec = 60
    mock_row.staleness_threshold_sec = 120

    async def _fake_gen():
        session = AsyncMock()
        result = MagicMock()
        result.fetchone = MagicMock(return_value=mock_row)
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        yield session

    from cloud_backend.database import get_db
    app.dependency_overrides[get_db] = _fake_gen

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.patch(
                "/api/v1/operators/me/preferences",
                # attempt to spoof a different operator
                json={"threshold_sec": 60, "operator_id": "evil-operator"},
                headers=_HEADERS,
            )
        # Request should succeed (200) and operator_id in response must equal
        # the API key, not "evil-operator"
        assert r.status_code == 200
        body = r.json()
        assert body["operator_id"] != "evil-operator"
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Unit Tests ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_preferences_returns_404_when_no_row() -> None:
    async def _fake_gen():
        session = AsyncMock()
        result = MagicMock()
        result.fetchone = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result)
        yield session

    from cloud_backend.database import get_db
    app.dependency_overrides[get_db] = _fake_gen

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/v1/operators/me/preferences", headers=_HEADERS)
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["error"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.unit
def test_get_preferences_returns_200_with_row() -> None:
    mock_row = MagicMock()
    mock_row.operator_id = _API_KEY
    mock_row.threshold_sec = 90
    mock_row.staleness_threshold_sec = 180

    async def _fake_gen():
        session = AsyncMock()
        result = MagicMock()
        result.fetchone = MagicMock(return_value=mock_row)
        session.execute = AsyncMock(return_value=result)
        yield session

    from cloud_backend.database import get_db
    app.dependency_overrides[get_db] = _fake_gen

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.get("/api/v1/operators/me/preferences", headers=_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["threshold_sec"] == 90
        assert body["staleness_threshold_sec"] == 180
        assert body["operator_id"] == _API_KEY
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.unit
def test_patch_preferences_valid_threshold_returns_200() -> None:
    mock_row = MagicMock()
    mock_row.operator_id = _API_KEY
    mock_row.threshold_sec = 30
    mock_row.staleness_threshold_sec = 120
    mock_row.updated_at = "2026-05-18T10:00:00+00:00"

    async def _fake_gen():
        session = AsyncMock()
        result = MagicMock()
        result.fetchone = MagicMock(return_value=mock_row)
        session.execute = AsyncMock(return_value=result)
        session.commit = AsyncMock()
        yield session

    from cloud_backend.database import get_db
    app.dependency_overrides[get_db] = _fake_gen

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            r = client.patch(
                "/api/v1/operators/me/preferences",
                json={"threshold_sec": 30},
                headers=_HEADERS,
            )
        assert r.status_code == 200
        body = r.json()
        assert body["threshold_sec"] == 30
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.unit
def test_patch_preferences_invalid_staleness_returns_422() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/operators/me/preferences",
            json={"staleness_threshold_sec": 45},
            headers=_HEADERS,
        )
    assert r.status_code == 422
