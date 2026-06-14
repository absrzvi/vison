"""Unit tests for E3-S7: POST /api/v1/maintenance/tickets."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from cloud_backend.main import app

from .conftest import auth_header

_HEADERS = auth_header()
_VALID_BODY = {"train_id": "4011", "issue_summary": "CCTV degraded", "raised_by": "op-1"}


@pytest.mark.unit
def test_no_api_key_returns_401() -> None:
    with TestClient(app) as client:
        r = client.post("/api/v1/maintenance/tickets", json=_VALID_BODY)
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "UNAUTHORIZED"


@pytest.mark.unit
def test_wrong_api_key_returns_401() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/maintenance/tickets",
            json=_VALID_BODY,
            headers={"X-API-Key": "wrong-key"},
        )
    assert r.status_code == 401


@pytest.mark.unit
def test_raise_ticket_returns_201() -> None:
    with TestClient(app) as client:
        r = client.post("/api/v1/maintenance/tickets", json=_VALID_BODY, headers=_HEADERS)
    assert r.status_code == 201
    body = r.json()
    assert re.match(r"REF#[0-9A-F]{5}$", body["ticket_id"]), (
        f"Unexpected ticket_id: {body['ticket_id']}"
    )
    assert "created_at" in body
    assert body["created_at"]  # non-empty


@pytest.mark.unit
def test_ticket_id_unique_across_calls() -> None:
    with TestClient(app) as client:
        r1 = client.post("/api/v1/maintenance/tickets", json=_VALID_BODY, headers=_HEADERS)
        r2 = client.post("/api/v1/maintenance/tickets", json=_VALID_BODY, headers=_HEADERS)
    assert r1.json()["ticket_id"] != r2.json()["ticket_id"]


@pytest.mark.unit
def test_missing_train_id_returns_422() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/maintenance/tickets",
            json={"issue_summary": "CCTV degraded", "raised_by": "op-1"},
            headers=_HEADERS,
        )
    assert r.status_code == 422


@pytest.mark.unit
def test_missing_issue_summary_returns_422() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/maintenance/tickets",
            json={"train_id": "4011", "raised_by": "op-1"},
            headers=_HEADERS,
        )
    assert r.status_code == 422
