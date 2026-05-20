"""Unit tests for SafetyHandler — ramp deployment event emitter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from inference.config import Settings
from inference.models import JourneyHolder
from inference.safety import SafetyHandler


def _make_handler(event_store_url: str = "http://event-store:8000") -> SafetyHandler:
    settings = Settings(event_store_url=event_store_url)
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    jh = JourneyHolder(journey_id="OBB-T_001_20260519")
    return SafetyHandler(settings=settings, event_store_client=client, journey_holder=jh)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_on_ramp_deployed_posts_event() -> None:
    """on_ramp_deployed posts RAMP_DEPLOYED envelope to event-store."""
    handler = _make_handler()

    await handler.on_ramp_deployed(door_id="door-1A", station_id="VIE-HBF")

    handler._client.post.assert_called_once()
    call_kwargs = handler._client.post.call_args
    url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
    assert "event-store" in url or "/api/v1/events" in str(call_kwargs)
    json_body = call_kwargs[1].get("json", {}) if call_kwargs[1] else {}
    assert json_body.get("event_type") == "RAMP_DEPLOYED" or "RAMP_DEPLOYED" in str(json_body)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_on_ramp_deployed_triggered_by_track_id_is_always_unknown() -> None:
    """R4 (2026-05-20): triggered_by_track_id is always 'unknown' from inference.

    Fusion (E4-S6) owns ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation. The
    inference-side per-camera last-track dict was removed because the multi-camera
    selection was arbitrary and the read/write race was real.
    """
    handler = _make_handler()

    await handler.on_ramp_deployed(door_id="door-1A", station_id="VIE-HBF")

    call_kwargs = handler._client.post.call_args
    json_body = call_kwargs[1].get("json", {})
    payload = json_body.get("payload", {})
    assert payload.get("triggered_by_track_id") == "unknown"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_on_ramp_deployed_empty_door_id_uses_unknown() -> None:
    """Empty door_id falls back to 'unknown' (non-empty str required by schema)."""
    handler = _make_handler()

    await handler.on_ramp_deployed(door_id="", station_id="VIE-HBF")

    call_kwargs = handler._client.post.call_args
    json_body = call_kwargs[1].get("json", {})
    payload = json_body.get("payload", {})
    assert payload.get("door_id") == "unknown"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_on_ramp_deployed_car_id_uses_vehicle_id() -> None:
    """R3 (2026-05-20): car_id is sourced from vehicle_id as a PoC simplification.

    vlan-pollers /context push carries no per-coach signal today. Documented in
    safety.py docstring and deferred-work.md.
    """
    handler = _make_handler()

    await handler.on_ramp_deployed(door_id="door-1A", station_id="VIE-HBF")

    call_kwargs = handler._client.post.call_args
    json_body = call_kwargs[1].get("json", {})
    payload = json_body.get("payload", {})
    assert payload.get("car_id") == "OBB-TEST"
