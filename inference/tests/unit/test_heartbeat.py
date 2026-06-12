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
    client = MagicMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    # First call fails, subsequent succeed — loop must keep going.
    client.post = AsyncMock(side_effect=[httpx.ConnectError("down"), resp, resp, resp])
    emitter = _make_emitter(client, interval=0.01)

    task = asyncio.create_task(emitter.run())
    await asyncio.sleep(0.06)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert client.post.await_count >= 2
