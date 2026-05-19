"""Unit tests for health.py — readiness, liveness, context dispatch."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from inference.budget import Budget
from inference.models import JourneyHolder, ReadinessHolder


def make_budget() -> MagicMock:
    return MagicMock(spec=Budget)


def make_client(
    ready: bool,
    budget: MagicMock | None = None,
    journey_holder: JourneyHolder | None = None,
    camera_id: str = "C1",
) -> TestClient:
    from inference.health import build_app

    readiness = [ReadinessHolder(camera_id=camera_id, ready=ready)]
    return TestClient(
        build_app(
            readiness=readiness,
            budget=budget or make_budget(),
            journey_holder=journey_holder or JourneyHolder(journey_id="OBB-TEST_t1_20260519"),
        )
    )


@pytest.mark.unit
def test_ready_returns_200() -> None:
    client = make_client(ready=True)
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "cameras" in body


@pytest.mark.unit
def test_not_ready_returns_503() -> None:
    client = make_client(ready=False)
    r = client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert body["recoverable"] is False


@pytest.mark.unit
def test_readiness_reflects_holder_flip() -> None:
    """When the holder flips, /health/ready reflects the new state — no static capture."""
    from inference.health import build_app

    holder = ReadinessHolder(camera_id="C1", ready=True)
    client = TestClient(
        build_app(
            readiness=[holder],
            budget=make_budget(),
            journey_holder=JourneyHolder(journey_id="OBB-TEST_t1_20260519"),
        )
    )
    assert client.get("/health/ready").status_code == 200
    holder.ready = False
    assert client.get("/health/ready").status_code == 503


@pytest.mark.unit
def test_degraded_when_partial_cameras_ready() -> None:
    """F2: partial camera failure produces degraded (200), not not_ready (503)."""
    from inference.health import build_app

    readiness = [
        ReadinessHolder(camera_id="C1", ready=True),
        ReadinessHolder(camera_id="C2", ready=False),
    ]
    client = TestClient(
        build_app(
            readiness=readiness,
            budget=make_budget(),
            journey_holder=JourneyHolder(journey_id="OBB-TEST_t1_20260519"),
        )
    )
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"


@pytest.mark.unit
def test_context_push_updates_journey_holder() -> None:
    """M13: POST /context with a journey_id mutates the shared holder so subsequent
    envelopes pick up the new trip."""
    journey = JourneyHolder(journey_id="OBB-TEST_t1_20260519")
    client = make_client(ready=True, journey_holder=journey)
    r = client.post(
        "/context",
        json={"p2_throttled": False, "journey_id": "OBB-TEST_t2_20260520"},
    )
    assert r.status_code == 200
    assert journey.journey_id == "OBB-TEST_t2_20260520"


@pytest.mark.unit
def test_live_always_200() -> None:
    client = make_client(ready=False)
    r = client.get("/health/live")
    assert r.status_code == 200


@pytest.mark.unit
def test_context_dispatch_calls_budget() -> None:
    budget = make_budget()
    client = make_client(ready=True, budget=budget)
    r = client.post("/context", json={"p2_throttled": True})
    assert r.status_code == 200
    budget.on_context_update.assert_called_once()
    payload = budget.on_context_update.call_args.args[0]
    assert payload["p2_throttled"] is True


@pytest.mark.unit
def test_context_malformed_returns_422() -> None:
    client = make_client(ready=True)
    r = client.post(
        "/context",
        content=b"not-json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422


@pytest.mark.unit
def test_context_non_bool_p2_throttled_returns_422() -> None:
    """Pydantic strict bool — string 'false' must fail validation, not flip throttle."""
    client = make_client(ready=True)
    r = client.post("/context", json={"p2_throttled": "false"})
    assert r.status_code == 422
