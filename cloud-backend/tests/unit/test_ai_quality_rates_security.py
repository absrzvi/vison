"""Unit tests for the AI-quality resolution-rates endpoint (10-5 AC1/AC7) — no DB.

Auth is enforced before any query runs, so it is checkable with TestClient and
no Postgres (mirrors test_escalations_audit_security.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cloud_backend.main import app

from .conftest import auth_header

_HEADERS = auth_header()
_ENDPOINT = "/api/v1/ai-quality/resolution-rates"


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
