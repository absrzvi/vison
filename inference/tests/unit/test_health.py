"""Unit tests for health.py — readiness, liveness, context dispatch."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from inference.budget import Budget


def make_budget() -> MagicMock:
    return MagicMock(spec=Budget)


@pytest.fixture
def ready_client() -> TestClient:
    from inference.health import build_app

    return TestClient(build_app(pipeline_ready=True, budget=make_budget()))


@pytest.fixture
def not_ready_client() -> TestClient:
    from inference.health import build_app

    return TestClient(build_app(pipeline_ready=False, budget=make_budget()))


@pytest.mark.unit
def test_ready_returns_200(ready_client: TestClient) -> None:
    r = ready_client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["hailo_initialised"] is True


@pytest.mark.unit
def test_not_ready_returns_503(not_ready_client: TestClient) -> None:
    r = not_ready_client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["recoverable"] is False


@pytest.mark.unit
def test_live_always_200(not_ready_client: TestClient) -> None:
    r = not_ready_client.get("/health/live")
    assert r.status_code == 200


@pytest.mark.unit
def test_context_dispatch_calls_budget(ready_client: TestClient) -> None:
    from inference.health import build_app

    budget = make_budget()
    client = TestClient(build_app(pipeline_ready=True, budget=budget))
    r = client.post("/context", json={"p2_throttled": True})
    assert r.status_code == 200
    budget.on_context_update.assert_called_once_with({"p2_throttled": True})


@pytest.mark.unit
def test_context_malformed_returns_422(ready_client: TestClient) -> None:
    r = ready_client.post("/context", content=b"not-json", headers={"content-type": "application/json"})
    assert r.status_code == 422
