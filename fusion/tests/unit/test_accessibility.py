"""Accessibility → Ramp correlation — AC8 (R4)."""
from __future__ import annotations

import httpx
import pytest
import respx
from oebb_shared.events import AccessibilityDetectedPayload, EventEnvelope, EventType

from fusion import accessibility as accessibility_mod
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment


def _settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
        accessibility_recent_window_s=60.0,
    )


@pytest.mark.unit
async def test_note_accessibility_records_track_under_near_door_and_zone() -> None:
    ctx = ContextState()
    payload = AccessibilityDetectedPayload(
        car_id="car-1",
        zone="door",
        track_id="trk-42",
        assistance_type=["wheelchair"],
        camera_id="C1_DOOR_01",
        confidence=None,
        near_door_id="door-1A",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    await accessibility_mod.note_accessibility_candidate(payload, ctx)
    assert ctx.find_recent_accessibility("car-1", "door-1A", window_s=60.0) == "trk-42"
    assert ctx.find_recent_accessibility("car-1", "door", window_s=60.0) == "trk-42"


@pytest.mark.unit
@respx.mock
async def test_ramp_with_recent_track_emits_with_track_id() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    ctx.note_accessibility("car-1", "door-1A", "trk-42")
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await accessibility_mod.handle_ramp_deployed(
            car_id="car-1",
            door_id="door-1A",
            station_id="VIE-HBF",
            ctx=ctx,
            enricher=enricher,
            settings=settings,
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.event_type == EventType.RAMP_DEPLOYED
    assert env.payload["triggered_by_track_id"] == "trk-42"
    assert env.payload["station_id"] == "VIE-HBF"


@pytest.mark.unit
@respx.mock
async def test_ramp_without_recent_track_uses_unknown_marker() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await accessibility_mod.handle_ramp_deployed(
            car_id="car-1",
            door_id="door-1A",
            station_id="VIE-HBF",
            ctx=ctx,
            enricher=enricher,
            settings=settings,
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["triggered_by_track_id"] == "unknown"


@pytest.mark.unit
@respx.mock
async def test_ramp_with_expired_track_uses_unknown() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520", vehicle_id="OBB-TEST")
    # Track recorded long ago.
    ctx.note_accessibility("car-1", "door-1A", "trk-42", now=0.0)
    settings = _settings()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        # The Enrichment path uses time.monotonic, which will be >> 0.
        await accessibility_mod.handle_ramp_deployed(
            car_id="car-1",
            door_id="door-1A",
            station_id="VIE-HBF",
            ctx=ctx,
            enricher=enricher,
            settings=settings,
        )
    env = EventEnvelope.model_validate_json(route.calls.last.request.content.decode())
    assert env.payload["triggered_by_track_id"] == "unknown"
