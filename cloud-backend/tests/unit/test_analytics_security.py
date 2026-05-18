"""Security and validation tests for E3-S1 analytics endpoints — RED phase."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cloud_backend.config import get_settings
from cloud_backend.main import app

_API_KEY = get_settings().api_key
_HEADERS = {"X-API-Key": _API_KEY}

_ANALYTICS_ENDPOINTS = [
    "/api/v1/analytics/exceptions",
    "/api/v1/analytics/occupancy-heatmap",
    "/api/v1/analytics/dwell-time",
    "/api/v1/analytics/detection-quality",
    "/api/v1/analytics/system-health",
]

_RANGE_ENDPOINTS = [
    "/api/v1/analytics/exceptions",
    "/api/v1/analytics/occupancy-heatmap",
    "/api/v1/analytics/dwell-time",
    "/api/v1/analytics/detection-quality",
]


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _ANALYTICS_ENDPOINTS)
def test_unauthenticated_returns_401(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(endpoint)
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert detail["error"] == "UNAUTHORIZED"
    assert detail["recoverable"] is False


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _ANALYTICS_ENDPOINTS)
def test_wrong_api_key_returns_401(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(endpoint, headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _RANGE_ENDPOINTS)
def test_invalid_range_returns_422(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(endpoint, headers=_HEADERS, params={"range": "90d"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "INVALID_RANGE"
    assert "7d" in body["detail"]
    assert body["recoverable"] is True


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _RANGE_ENDPOINTS)
def test_invalid_range_value_foo_returns_422(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(endpoint, headers=_HEADERS, params={"range": "foo"})
    assert r.status_code == 422
    assert r.json()["error"] == "INVALID_RANGE"
