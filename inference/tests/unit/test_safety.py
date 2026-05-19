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
async def test_on_ramp_deployed_uses_last_track() -> None:
    """triggered_by_track_id is taken from _last_track_ids when available."""
    handler = _make_handler()
    handler.update_last_track("C1_DOOR_01", "acc-C1_DOOR_01-99999")

    await handler.on_ramp_deployed(door_id="door-1A", station_id="VIE-HBF")

    call_kwargs = handler._client.post.call_args
    json_body = call_kwargs[1].get("json", {})
    payload = json_body.get("payload", {})
    assert payload.get("triggered_by_track_id") == "acc-C1_DOOR_01-99999"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_on_ramp_deployed_no_track_uses_unknown() -> None:
    """triggered_by_track_id is 'unknown' when no accessibility track is recorded."""
    handler = _make_handler()

    await handler.on_ramp_deployed(door_id="door-1A", station_id="VIE-HBF")

    call_kwargs = handler._client.post.call_args
    json_body = call_kwargs[1].get("json", {})
    payload = json_body.get("payload", {})
    assert payload.get("triggered_by_track_id") == "unknown"


@pytest.mark.unit
def test_update_last_track_stores_track_id() -> None:
    handler = _make_handler()
    handler.update_last_track("cam-1", "acc-cam-1-12345")
    assert handler._last_track_ids["cam-1"] == "acc-cam-1-12345"


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
