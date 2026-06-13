"""Unit tests for story 10-1 AC7 — 60s INFERENCE_HEARTBEAT loop."""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from inference.config import Settings
from inference.heartbeat import HeartbeatEmitter
from inference.models import JourneyHolder, ReadinessHolder

pytestmark = pytest.mark.unit

_MODEL_VERSIONS = {
    "detector_arch": "yolox_s_leaky",
    "detector_hef": "yolox_s_leaky.hef@ab12cd34ef56",
    "detector_code": "git:9d4a60df",
    "detector_labels": "labels@12ab34cd56ef",
}


def _make_emitter(
    client: Any,
    *,
    interval: float = 0.01,
    ready: bool = True,
) -> HeartbeatEmitter:
    settings = Settings(
        heartbeat_interval_s=interval,
        vehicle_id="OBB-4711",
        journey_id="OBB-4711_RJ-0847_20260612",
    )
    return HeartbeatEmitter(
        settings=settings,
        client=client,
        journey_holder=JourneyHolder(journey_id=settings.journey_id),
        model_versions=_MODEL_VERSIONS,
        readiness=[ReadinessHolder(camera_id="cam-1", ready=ready)],
    )


def _ok_client() -> MagicMock:
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_emit_once_posts_heartbeat_envelope() -> None:
    client = _ok_client()
    emitter = _make_emitter(client)
    emitter.record_frames(42)

    await emitter.emit_once()

    assert client.post.await_count == 1
    url = client.post.await_args.args[0]
    assert url.endswith("/api/v1/events")
    body = client.post.await_args.kwargs["json"]
    assert body["event_type"] == "INFERENCE_HEARTBEAT"
    assert body["source"] == "inference"
    assert body["payload"]["train_id"] == "OBB-4711"
    assert body["payload"]["frames_processed_window"] == 42
    assert body["payload"]["model_versions"] == _MODEL_VERSIONS
    assert body["payload"]["hailo_device_ok"] is True
    assert body["payload"]["last_inference_at"].endswith("Z")
    # Envelope must be JSON-serialisable as POSTed
    json.dumps(body)


@pytest.mark.asyncio
async def test_counter_resets_after_successful_emit() -> None:
    client = _ok_client()
    emitter = _make_emitter(client)
    emitter.record_frames(10)

    await emitter.emit_once()
    assert client.post.await_args.kwargs["json"]["payload"]["frames_processed_window"] == 10

    emitter.record_frames(3)
    await emitter.emit_once()
    assert client.post.await_args.kwargs["json"]["payload"]["frames_processed_window"] == 3


@pytest.mark.asyncio
async def test_hailo_device_ok_false_when_no_camera_ready() -> None:
    client = _ok_client()
    emitter = _make_emitter(client, ready=False)

    await emitter.emit_once()
    assert client.post.await_args.kwargs["json"]["payload"]["hailo_device_ok"] is False


@pytest.mark.asyncio
async def test_event_store_unreachable_does_not_raise() -> None:
    client = MagicMock()
    client.post = AsyncMock(side_effect=httpx.ConnectError("event-store down"))
    emitter = _make_emitter(client)
    emitter.record_frames(5)

    await emitter.emit_once()  # must not raise

    # Counter is NOT reset on failure — frames accumulate into the next window.
    client.post = AsyncMock(side_effect=httpx.ConnectError("still down"))
    emitter.record_frames(2)
    await emitter.emit_once()
    assert client.post.await_args.kwargs["json"]["payload"]["frames_processed_window"] == 7


@pytest.mark.asyncio
async def test_run_loop_honours_cadence_and_survives_errors() -> None:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    # First call fails, all subsequent succeed — loop must keep going and must
    # not exhaust a finite side_effect (which would raise StopIteration and kill
    # the task, masking the very resilience this test checks).
    calls = {"n": 0}

    async def _post(*_a: object, **_k: object) -> MagicMock:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("down")
        return resp

    client = MagicMock()
    client.post = _post
    emitter = _make_emitter(client, interval=0.01)

    task = asyncio.create_task(emitter.run())
    await asyncio.sleep(0.06)
    assert not task.done()  # loop survived the first-call failure
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cadence: at ~10ms interval over ~60ms we expect several emits, not one.
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_emit_once_survives_envelope_validation_error() -> None:
    """A heartbeat that fails payload/envelope construction (not just the POST)
    must be swallowed too — the loop is the fleet-health signal and must outlive
    any single bad heartbeat."""
    client = _ok_client()
    emitter = _make_emitter(client)
    # Force envelope construction to raise by corrupting the journey_id to an
    # invalid pattern the strict EventEnvelope rejects.
    emitter._journey_holder.journey_id = "not-a-valid-journey-id"

    await emitter.emit_once()  # must not raise

    assert client.post.await_count == 0  # failed before the POST


def test_heartbeat_interval_must_be_positive() -> None:
    """heartbeat_interval_s <= 0 would busy-loop the emitter; config rejects it."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        Settings(heartbeat_interval_s=0)
    with pytest.raises(pydantic.ValidationError):
        Settings(heartbeat_interval_s=-1.0)
