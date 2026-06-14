"""Unit tests for the escalation-audit funnel endpoint (E10-S2 AC3) — no DB.

Auth + ISO-range validation are enforced before any query runs, so they can be
checked with TestClient and no Postgres (mirrors test_analytics_security.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cloud_backend.main import app

from .conftest import auth_header

_HEADERS = auth_header()
_ENDPOINT = "/api/v1/escalations-audit"


@pytest.mark.unit
def test_unauthenticated_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(_ENDPOINT)
    assert r.status_code == 401


@pytest.mark.unit
def test_wrong_api_key_returns_401() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(_ENDPOINT, headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 401


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["not-a-date", "2026-13-01", "garbage"])
def test_invalid_from_returns_422(bad: str) -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(_ENDPOINT, headers=_HEADERS, params={"from": bad})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "INVALID_RANGE"
    assert body["recoverable"] is True


@pytest.mark.unit
def test_from_after_to_returns_422() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get(
            _ENDPOINT,
            headers=_HEADERS,
            params={"from": "2026-06-13T00:00:00Z", "to": "2026-06-01T00:00:00Z"},
        )
    assert r.status_code == 422
    assert r.json()["error"] == "INVALID_RANGE"
