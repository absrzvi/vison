"""Unit tests for TripwireHandler — gangway inter-wagon crossing detection.

No Hailo-8 or GStreamer required. All HTTP calls mocked via respx.
Async tests use pytest-asyncio.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
import respx

from inference.budget import Budget
from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder
from inference.tripwire import TripwireHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides: Any) -> Settings:
    # Unused helper — Settings accepts env-var names directly via pydantic-settings
    _ = overrides
    return Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )


def _make_camera(
    zone: str = "gangway-fwd",
    coach_from: str = "car-3",
    coach_to: str = "car-4",
    direction_axis: str = "x",
    tripwire_polygon: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Build a minimal gangway camera dict."""
    cam: dict[str, Any] = {
        "camera_id": "C3_GANGWAY_FWD",
        "coach_id": coach_from,
        "zone": zone,
        "priority": "P1",
        "coach_from": coach_from,
        "coach_to": coach_to,
        "direction_axis": direction_axis,
        "tripwire": {
            "tripwire_polygon": tripwire_polygon or [[320, 0], [320, 480]],
        },
    }
    return cam


def _make_handler(
    camera: dict[str, Any] | None = None,
    settings: Settings | None = None,
    event_store_client: httpx.AsyncClient | None = None,
    loop_holder: LoopHolder | None = None,
    journey_holder: JourneyHolder | None = None,
) -> TripwireHandler:
    if camera is None:
        camera = _make_camera()
    if settings is None:
        settings = Settings(
            INFERENCE_EVENT_STORE_URL="http://event-store:8000",
            INFERENCE_FUSION_URL="http://fusion:8090",
            INFERENCE_VEHICLE_ID="OBB-TEST",
            INFERENCE_JOURNEY_ID="OBB-TEST_001_20260520",
        )
    if event_store_client is None:
        event_store_client = httpx.AsyncClient()
    if loop_holder is None:
        loop_holder = LoopHolder()
    if journey_holder is None:
        journey_holder = JourneyHolder(journey_id="OBB-TEST_001_20260520")
    return TripwireHandler(
        camera=camera,
        settings=settings,
        event_store_client=event_store_client,
        loop_holder=loop_holder,
        journey_holder=journey_holder,
    )


# Centroid LEFT of tripwire x=320 → coach_from side → no crossing yet
_BBOX_FROM_SIDE: tuple[float, float, float, float] = (100.0, 100.0, 200.0, 300.0)  # cx=150
# Centroid RIGHT of tripwire x=320 → coach_to side → crossing
_BBOX_TO_SIDE: tuple[float, float, float, float] = (400.0, 100.0, 500.0, 300.0)  # cx=450


# ---------------------------------------------------------------------------
# Test 1: No emission when centroid stays on coach_from side
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_emission_when_centroid_on_from_side() -> None:
    """Centroid stays on coach_from side — no WAGON_EXIT posted."""
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)

        with respx.mock(assert_all_called=False) as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(201, json={})
            await handler._handle_detection(
                track_id=1,
                bbox=_BBOX_FROM_SIDE,
                confidence=0.95,
            )
            # No crossing detected — event-store must NOT have been called
            assert not mock.calls


# ---------------------------------------------------------------------------
# Test 2: WAGON_EXIT emitted when centroid crosses to coach_to side
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wagon_exit_emitted_on_crossing() -> None:
    """Centroid crosses tripwire to coach_to side → WAGON_EXIT POSTed."""
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)

        with respx.mock() as mock:
            exit_route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "abc", "stored": True}}
            )
            # First frame: from-side (no crossing)
            await handler._handle_detection(
                track_id=42, bbox=_BBOX_FROM_SIDE, confidence=0.90
            )
            # Second frame: to-side (crossing!)
            await handler._handle_detection(
                track_id=42, bbox=_BBOX_TO_SIDE, confidence=0.90
            )

        assert exit_route.called
        body = exit_route.calls[0].request
        import json
        payload_data = json.loads(body.content)
        assert payload_data["event_type"] == "WAGON_EXIT"
        assert payload_data["payload"]["track_id"] == 42
        assert payload_data["payload"]["coach_from"] == "car-3"
        assert payload_data["payload"]["coach_to"] == "car-4"
        assert payload_data["payload"]["confidence"] == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# Test 3: WAGON_ENTRY emitted on adjacent camera crossing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wagon_entry_emitted_on_adjacent_camera() -> None:
    """Same track_id seen on gangway-aft camera → WAGON_ENTRY POSTed."""
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        # gangway-fwd handler: emits WAGON_EXIT
        fwd_cam = _make_camera(zone="gangway-fwd", coach_from="car-3", coach_to="car-4")
        fwd_handler = _make_handler(
            camera=fwd_cam, settings=settings, event_store_client=client
        )

        # gangway-aft handler on adjacent coach: emits WAGON_ENTRY
        aft_cam = _make_camera(zone="gangway-aft", coach_from="car-3", coach_to="car-4")
        aft_cam["camera_id"] = "C4_GANGWAY_AFT"
        aft_handler = _make_handler(
            camera=aft_cam, settings=settings, event_store_client=client
        )

        with respx.mock() as mock:
            route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "xyz", "stored": True}}
            )

            # fwd: crossing → WAGON_EXIT
            await fwd_handler._handle_detection(track_id=99, bbox=_BBOX_FROM_SIDE, confidence=0.85)
            await fwd_handler._handle_detection(track_id=99, bbox=_BBOX_TO_SIDE, confidence=0.85)

            # aft: same track_id seen crossing → WAGON_ENTRY
            await aft_handler._handle_detection(track_id=99, bbox=_BBOX_FROM_SIDE, confidence=0.88)
            await aft_handler._handle_detection(track_id=99, bbox=_BBOX_TO_SIDE, confidence=0.88)

        import json
        event_types = [
            json.loads(c.request.content)["event_type"] for c in route.calls
        ]
        assert "WAGON_EXIT" in event_types
        assert "WAGON_ENTRY" in event_types


# ---------------------------------------------------------------------------
# Test 4: Low-confidence suppression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_suppresses_emission() -> None:
    """Confidence < 0.70 → no POST, structlog DEBUG event with reason: low_confidence."""
    import structlog.testing

    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)

        with respx.mock(assert_all_called=False) as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(201, json={})

            with structlog.testing.capture_logs() as captured:
                # First: from-side (no crossing)
                await handler._handle_detection(track_id=7, bbox=_BBOX_FROM_SIDE, confidence=0.60)
                # Second: to-side crossing but confidence too low
                await handler._handle_detection(track_id=7, bbox=_BBOX_TO_SIDE, confidence=0.60)

            assert not mock.calls

    assert any(
        e.get("reason") == "low_confidence" or "low_confidence" in str(e.get("event", ""))
        for e in captured
    )


# ---------------------------------------------------------------------------
# Test 5: Orphaned exit — WARNING log + fusion notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphaned_exit_logs_warning_and_notifies_fusion() -> None:
    """No WAGON_ENTRY within timeout → structlog WARNING + POST to fusion /context."""
    import structlog.testing

    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)
        # Shorten timeout for test speed
        handler._orphan_timeout_s = 0.05

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            fusion_route = mock.post("http://fusion:8090/context").respond(200, json={})

            with structlog.testing.capture_logs() as captured:
                # from-side then to-side → triggers WAGON_EXIT + orphan timer
                await handler._handle_detection(track_id=55, bbox=_BBOX_FROM_SIDE, confidence=0.80)
                await handler._handle_detection(track_id=55, bbox=_BBOX_TO_SIDE, confidence=0.80)
                # Wait for orphan timer to fire
                await asyncio.sleep(0.15)

    assert fusion_route.called
    assert any(
        e.get("reason") == "orphaned_exit" or "orphaned_exit" in str(e.get("event", ""))
        for e in captured
    )


# ---------------------------------------------------------------------------
# Test 6: Missing tripwire field → RuntimeError at construction
# ---------------------------------------------------------------------------

def test_missing_tripwire_field_raises_runtime_error() -> None:
    """Camera with gangway zone but no tripwire field → RuntimeError."""
    cam = _make_camera()
    del cam["tripwire"]

    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    with pytest.raises(RuntimeError, match="tripwire"):
        _make_handler(camera=cam, settings=settings)


# ---------------------------------------------------------------------------
# Test 8: Wrong zone raises RuntimeError
# ---------------------------------------------------------------------------

def test_wrong_zone_raises_runtime_error() -> None:
    """Camera with non-gangway zone passed to TripwireHandler → RuntimeError."""
    cam = _make_camera()
    cam["zone"] = "interior"
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    with pytest.raises(RuntimeError, match="gangway-fwd/aft"):
        _make_handler(camera=cam, settings=settings)


# ---------------------------------------------------------------------------
# Test 9: process_frame catches RuntimeError on shutdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_frame_logs_on_shutdown() -> None:
    """RuntimeError from run_coroutine_threadsafe on shutdown is caught and logged."""
    import structlog.testing

    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)
        closed_loop = asyncio.new_event_loop()
        closed_loop.close()

        with structlog.testing.capture_logs() as captured:
            handler.process_frame(
                track_id=1, bbox=_BBOX_TO_SIDE, confidence=0.90, loop=closed_loop
            )

    assert any("shutdown" in str(e.get("event", "")) for e in captured)


# ---------------------------------------------------------------------------
# Test 10: Degenerate tripwire polygon (< 2 points) → "from" side
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_centroid_side_degenerate_polygon() -> None:
    """Tripwire polygon with < 2 points returns 'from' (defensive fallback)."""
    cam = _make_camera(tripwire_polygon=[[320, 240]])
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(camera=cam, settings=settings, event_store_client=client)
        side = handler._centroid_side(450.0, 240.0)
        assert side == "from"


# ---------------------------------------------------------------------------
# Test 11: Fusion notify failure on orphaned exit → logged, not raised
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_fusion_failure_logged() -> None:
    """Fusion /context POST failure during orphan handling is caught and logged."""
    import structlog.testing

    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
    )
    async with httpx.AsyncClient() as client:
        handler = _make_handler(settings=settings, event_store_client=client)
        handler._orphan_timeout_s = 0.05

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            mock.post("http://fusion:8090/context").respond(500)

            with structlog.testing.capture_logs() as captured:
                await handler._handle_detection(track_id=77, bbox=_BBOX_FROM_SIDE, confidence=0.85)
                await handler._handle_detection(track_id=77, bbox=_BBOX_TO_SIDE, confidence=0.85)
                await asyncio.sleep(0.15)

    assert any("fusion_notify_failed" in str(e.get("event", "")) for e in captured)


# ---------------------------------------------------------------------------
# Test 7: Gangway camera is P1 → never throttled by Budget
# ---------------------------------------------------------------------------

def test_gangway_p1_never_throttled_by_budget() -> None:
    """Budget.should_process always returns True for P1 even when P2 throttled."""
    settings = Settings(
        INFERENCE_EVENT_STORE_URL="http://event-store:8000",
        INFERENCE_FUSION_URL="http://fusion:8090",
        INFERENCE_TOPS_TOTAL=0.001,  # force throttle
        INFERENCE_TOPS_BUDGET_PCT_THRESHOLD=0.0,
    )
    budget = Budget(settings=settings)
    # Simulate P2 throttled state
    budget._p2_throttled = True  # noqa: SLF001

    assert budget.should_process("C3_GANGWAY_FWD", "P1") is True
    assert budget.should_process("C3_INT_01", "P2") is False
