"""Security tests for E3-S2 capacity review endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cloud_backend.main import app

_POST_ENDPOINTS = [
    "/api/v1/analytics/exceptions/ex-1/review",
    "/api/v1/analytics/exceptions/ex-1/dismiss",
    "/api/v1/analytics/exceptions/ex-1/reopen",
]
_GET_ENDPOINTS = [
    "/api/v1/capacity-review-queue/export",
]


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _POST_ENDPOINTS)
def test_unauthenticated_post_returns_401(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(endpoint, json={})
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert detail["error"] == "UNAUTHORIZED"
    assert detail["recoverable"] is False


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", _GET_ENDPOINTS)
def test_unauthenticated_get_returns_401(endpoint: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(endpoint)
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert detail["error"] == "UNAUTHORIZED"


@pytest.mark.unit
def test_wrong_key_review_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/analytics/exceptions/ex-1/review",
            json={"priority": "high"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert r.status_code == 401
