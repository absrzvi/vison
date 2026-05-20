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


@pytest.mark.unit
def test_context_push_ramp_deployed_invokes_safety_handler() -> None:
    """R19 (2026-05-20): POST /context with ramp_deployed=True schedules
    safety_handler.on_ramp_deployed onto the loop_holder loop."""
    import asyncio
    import threading

    from inference.health import build_app
    from inference.models import LoopHolder

    # Spin up a real asyncio loop in a background thread so run_coroutine_threadsafe
    # has a target. Mirrors the lifespan pattern used in main.py.
    loop_started = threading.Event()
    holder = LoopHolder(loop=None)

    def _runner() -> None:
        lp = asyncio.new_event_loop()
        asyncio.set_event_loop(lp)
        holder.loop = lp
        loop_started.set()
        lp.run_forever()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    try:
        loop_started.wait(timeout=2.0)
        assert holder.loop is not None

        # Track invocations against the safety_handler stub.
        seen: list[tuple[str, str]] = []
        done = threading.Event()

        class _StubSafety:
            async def on_ramp_deployed(self, door_id: str, station_id: str) -> None:
                seen.append((door_id, station_id))
                done.set()

        safety = _StubSafety()

        client = TestClient(
            build_app(
                readiness=[ReadinessHolder(camera_id="C1", ready=True)],
                budget=make_budget(),
                journey_holder=JourneyHolder(journey_id="OBB-TEST_t1_20260519"),
                safety_handler=safety,  # type: ignore[arg-type]
                loop_holder=holder,
            )
        )
        r = client.post(
            "/context",
            json={
                "p2_throttled": False,
                "ramp_deployed": True,
                "ramp_door_id": "door-1A",
                "ramp_station_id": "VIE-HBF",
            },
        )
        assert r.status_code == 200

        # Wait for the scheduled coroutine to actually run on the background loop.
        assert done.wait(timeout=2.0), "safety_handler.on_ramp_deployed never called"
        assert seen == [("door-1A", "VIE-HBF")]
    finally:
        if holder.loop is not None:
            holder.loop.call_soon_threadsafe(holder.loop.stop)
        t.join(timeout=2.0)


@pytest.mark.unit
def test_context_push_ramp_non_bool_returns_422() -> None:
    """StrictBool also applies to ramp_deployed."""
    client = make_client(ready=True)
    r = client.post("/context", json={"p2_throttled": False, "ramp_deployed": "yes"})
    assert r.status_code == 422
