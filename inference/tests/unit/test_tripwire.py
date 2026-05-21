"""Unit tests for TripwireHandler — gangway inter-wagon crossing detection.

No Hailo-8 or GStreamer required. All HTTP calls mocked via respx.
Async tests use pytest-asyncio.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx

from inference.budget import Budget
from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder
from inference.tripwire import _LAST_SIDE_MAX_SIZE, TripwireHandler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_camera(
    zone: str = "gangway-fwd",
    coach_from: str = "car-3",
    coach_to: str = "car-4",
    direction_axis: str = "x",
    traversal: str = "from_to",
    tripwire_polygon: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Build a minimal gangway camera dict."""
    return {
        "camera_id": "C3_GANGWAY_FWD",
        "coach_id": coach_from,
        "zone": zone,
        "priority": "P1",
        "coach_from": coach_from,
        "coach_to": coach_to,
        "direction_axis": direction_axis,
        "traversal": traversal,
        "tripwire": {
            "tripwire_polygon": tripwire_polygon or [[320, 0], [320, 480]],
        },
    }


def _make_settings(**kwargs: Any) -> Settings:
    defaults: dict[str, Any] = {
        "INFERENCE_EVENT_STORE_URL": "http://event-store:8000",
        "INFERENCE_FUSION_URL": "http://fusion:8090",
        "INFERENCE_VEHICLE_ID": "OBB-TEST",
        "INFERENCE_JOURNEY_ID": "OBB-TEST_001_20260520",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


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
        settings = _make_settings()
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
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock(assert_all_called=False) as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(201, json={})
            await handler._handle_detection(track_id=1, bbox=_BBOX_FROM_SIDE, confidence=0.95)
            assert not mock.calls


# ---------------------------------------------------------------------------
# Test 2: WAGON_EXIT emitted on from_to crossing — traversal field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wagon_exit_emitted_on_crossing() -> None:
    """Centroid crosses tripwire from_to → WAGON_EXIT POSTed with traversal field."""
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock() as mock:
            exit_route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "abc", "stored": True}}
            )
            await handler._handle_detection(track_id=42, bbox=_BBOX_FROM_SIDE, confidence=0.90)
            await handler._handle_detection(track_id=42, bbox=_BBOX_TO_SIDE, confidence=0.90)

        assert exit_route.called
        payload_data = json.loads(exit_route.calls[0].request.content)
        assert payload_data["event_type"] == "WAGON_EXIT"
        assert payload_data["payload"]["track_id"] == 42
        assert payload_data["payload"]["coach_from"] == "car-3"
        assert payload_data["payload"]["coach_to"] == "car-4"
        assert payload_data["payload"]["traversal"] == "from_to"
        assert payload_data["payload"]["expect_orphan"] is False
        assert payload_data["payload"]["confidence"] == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# Test 2b: to_from crossing emits expect_orphan=True, no orphan timer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_to_from_crossing_expect_orphan_no_timer() -> None:
    """to_from crossing on fwd camera → WAGON_EXIT with expect_orphan=True, no timer armed."""
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)
        handler._orphan_timeout_s = 0.05

        with respx.mock(assert_all_called=False) as mock:
            route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            fusion_route = mock.post("http://fusion:8090/context").respond(200, json={})
            # to-side first (no crossing), then from-side → to_from crossing
            await handler._handle_detection(track_id=10, bbox=_BBOX_TO_SIDE, confidence=0.90)
            await handler._handle_detection(track_id=10, bbox=_BBOX_FROM_SIDE, confidence=0.90)
            # Wait to confirm no orphan timer fires
            await asyncio.sleep(0.15)

            assert route.called
            payload_data = json.loads(route.calls[0].request.content)
            assert payload_data["payload"]["traversal"] == "to_from"
            assert payload_data["payload"]["expect_orphan"] is True
            # No orphan notification to fusion — timer was NOT armed
            assert not fusion_route.called
            assert 10 not in handler._pending_exits


# ---------------------------------------------------------------------------
# Test 3: WAGON_ENTRY emitted on adjacent aft camera crossing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wagon_entry_emitted_on_adjacent_camera() -> None:
    """Same track_id seen on gangway-aft camera → WAGON_ENTRY POSTed."""
    settings = _make_settings()
    async with httpx.AsyncClient() as client:
        fwd_cam = _make_camera(zone="gangway-fwd")
        fwd_handler = _make_handler(camera=fwd_cam, settings=settings, event_store_client=client)

        aft_cam = _make_camera(zone="gangway-aft")
        aft_cam["camera_id"] = "C4_GANGWAY_AFT"
        aft_handler = _make_handler(camera=aft_cam, settings=settings, event_store_client=client)

        with respx.mock() as mock:
            route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "xyz", "stored": True}}
            )
            await fwd_handler._handle_detection(track_id=99, bbox=_BBOX_FROM_SIDE, confidence=0.85)
            await fwd_handler._handle_detection(track_id=99, bbox=_BBOX_TO_SIDE, confidence=0.85)
            await aft_handler._handle_detection(track_id=99, bbox=_BBOX_FROM_SIDE, confidence=0.88)
            await aft_handler._handle_detection(track_id=99, bbox=_BBOX_TO_SIDE, confidence=0.88)

        event_types = [json.loads(c.request.content)["event_type"] for c in route.calls]
        assert "WAGON_EXIT" in event_types
        assert "WAGON_ENTRY" in event_types


# ---------------------------------------------------------------------------
# Test 4: Low-confidence suppression — side state NOT mutated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_confidence_suppresses_emission_and_preserves_side() -> None:
    """Confidence < 0.70 → no POST, structlog DEBUG, _last_side not teleported (P4)."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock(assert_all_called=False) as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(201, json={})

            with structlog.testing.capture_logs() as captured:
                # First: from-side (establishes state)
                await handler._handle_detection(track_id=7, bbox=_BBOX_FROM_SIDE, confidence=0.90)
                # Low-confidence crossing — should NOT update side
                await handler._handle_detection(track_id=7, bbox=_BBOX_TO_SIDE, confidence=0.60)
                # Side should still be "from" — high-conf detection from from-side should NOT cross
                await handler._handle_detection(track_id=7, bbox=_BBOX_FROM_SIDE, confidence=0.90)

            assert not mock.calls

    assert any(
        e.get("reason") == "low_confidence" or "low_confidence" in str(e.get("event", ""))
        for e in captured
    )
    # Confirm side was preserved — track_id=7 last side should still be "from"
    assert handler._last_side.get(7) == "from"


# ---------------------------------------------------------------------------
# Test 5: Orphaned exit — WARNING log + fusion notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphaned_exit_logs_warning_and_notifies_fusion() -> None:
    """No WAGON_ENTRY within timeout → structlog WARNING + POST to fusion /context."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)
        handler._orphan_timeout_s = 0.05

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            fusion_route = mock.post("http://fusion:8090/context").respond(200, json={})

            with structlog.testing.capture_logs() as captured:
                await handler._handle_detection(track_id=55, bbox=_BBOX_FROM_SIDE, confidence=0.80)
                await handler._handle_detection(track_id=55, bbox=_BBOX_TO_SIDE, confidence=0.80)
                await asyncio.sleep(0.15)

    assert fusion_route.called
    assert any(
        e.get("reason") == "orphaned_exit" or "orphaned_exit" in str(e.get("event", ""))
        for e in captured
    )


# ---------------------------------------------------------------------------
# Test 5b: Re-crossing within orphan window cancels prior timer (P1/P2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recrossing_cancels_prior_orphan_timer() -> None:
    """Second from_to crossing before timeout cancels first orphan timer — no double-orphan."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)
        handler._orphan_timeout_s = 0.10

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            fusion_route = mock.post("http://fusion:8090/context").respond(200, json={})

            with structlog.testing.capture_logs() as captured:
                # First crossing → orphan timer T1 armed
                await handler._handle_detection(track_id=20, bbox=_BBOX_FROM_SIDE, confidence=0.85)
                await handler._handle_detection(track_id=20, bbox=_BBOX_TO_SIDE, confidence=0.85)
                # Return before T1 fires
                await handler._handle_detection(track_id=20, bbox=_BBOX_FROM_SIDE, confidence=0.85)
                # Second crossing → T1 must be cancelled, T2 armed
                await handler._handle_detection(track_id=20, bbox=_BBOX_TO_SIDE, confidence=0.85)
                # Wait for T2 to fire — only ONE orphan notification expected
                await asyncio.sleep(0.25)

    orphan_warnings = [
        e for e in captured
        if e.get("reason") == "orphaned_exit" or "orphaned_exit" in str(e.get("event", ""))
    ]
    assert len(orphan_warnings) == 1, f"Expected 1 orphan, got {len(orphan_warnings)}"
    assert fusion_route.call_count == 1


# ---------------------------------------------------------------------------
# Test 6: Missing tripwire field → RuntimeError at construction
# ---------------------------------------------------------------------------

def test_missing_tripwire_field_raises_runtime_error() -> None:
    """Camera with gangway zone but no tripwire field → RuntimeError."""
    cam = _make_camera()
    del cam["tripwire"]
    with pytest.raises(RuntimeError, match="tripwire"):
        _make_handler(camera=cam)


# ---------------------------------------------------------------------------
# Test 6b: Missing coach_from/coach_to/direction_axis → RuntimeError (P7)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", ["coach_from", "coach_to", "direction_axis"])
def test_missing_required_config_field_raises_runtime_error(missing_field: str) -> None:
    """Missing coach_from, coach_to, or direction_axis raises RuntimeError at construction (P7/AC1)."""
    cam = _make_camera()
    del cam[missing_field]
    with pytest.raises(RuntimeError, match=missing_field):
        _make_handler(camera=cam)


# ---------------------------------------------------------------------------
# Test 7: Gangway camera is P1 → never throttled by Budget
# ---------------------------------------------------------------------------

def test_gangway_p1_never_throttled_by_budget() -> None:
    """Budget.should_process always returns True for P1 even when P2 throttled."""
    settings = _make_settings(
        INFERENCE_TOPS_TOTAL=0.001,
        INFERENCE_TOPS_BUDGET_PCT_THRESHOLD=0.0,
    )
    budget = Budget(settings=settings)
    budget._p2_throttled = True  # noqa: SLF001

    assert budget.should_process("C3_GANGWAY_FWD", "P1") is True
    assert budget.should_process("C3_INT_01", "P2") is False


# ---------------------------------------------------------------------------
# Test 8: Wrong zone raises RuntimeError
# ---------------------------------------------------------------------------

def test_wrong_zone_raises_runtime_error() -> None:
    """Camera with non-gangway zone passed to TripwireHandler → RuntimeError."""
    cam = _make_camera()
    cam["zone"] = "interior"
    with pytest.raises(RuntimeError, match="gangway-fwd/aft"):
        _make_handler(camera=cam)


# ---------------------------------------------------------------------------
# Test 9: process_frame catches RuntimeError on shutdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_frame_logs_on_shutdown() -> None:
    """RuntimeError from run_coroutine_threadsafe on shutdown is caught and logged."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)
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
    async with httpx.AsyncClient() as client:
        handler = _make_handler(camera=cam, event_store_client=client)
        side = handler._centroid_side(450.0, 240.0)
        assert side == "from"


# ---------------------------------------------------------------------------
# Test 11: Fusion notify failure on orphaned exit → logged, not raised
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orphan_fusion_failure_logged() -> None:
    """Fusion /context POST failure during orphan handling is caught and logged."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)
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
# Test 12: to_from crossing (backward traversal) — AC7 backward crossing test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_to_from_crossing_emits_wagon_exit_backward() -> None:
    """to_from crossing on fwd camera emits WAGON_EXIT with traversal=to_from (P6/AC7)."""
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock() as mock:
            route = mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "b1", "stored": True}}
            )
            # Start on to-side, cross to from-side → to_from traversal
            await handler._handle_detection(track_id=88, bbox=_BBOX_TO_SIDE, confidence=0.90)
            await handler._handle_detection(track_id=88, bbox=_BBOX_FROM_SIDE, confidence=0.90)

        assert route.called
        payload_data = json.loads(route.calls[0].request.content)
        assert payload_data["event_type"] == "WAGON_EXIT"
        assert payload_data["payload"]["traversal"] == "to_from"
        assert payload_data["payload"]["expect_orphan"] is True


# ---------------------------------------------------------------------------
# Test 13: _last_side eviction when max size exceeded (P5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_last_side_eviction_on_overflow() -> None:
    """_last_side is pruned when it exceeds _LAST_SIDE_MAX_SIZE (P5)."""
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock(assert_all_called=False):
            # Fill _last_side beyond the cap
            for tid in range(_LAST_SIDE_MAX_SIZE + 10):
                handler._last_side[tid] = "from"
            # Trigger eviction via _maybe_evict_last_side
            handler._maybe_evict_last_side()

        assert len(handler._last_side) <= _LAST_SIDE_MAX_SIZE


# ---------------------------------------------------------------------------
# E4-S9 AC10 — fire-and-forget POST to fusion candidates after event-store POST
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wagon_exit_fires_to_fusion_candidate_endpoint() -> None:
    """After event-store success, payload is POSTed to fusion /candidates/wagon_exit."""
    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            fusion_route = mock.post(
                "http://fusion:8090/candidates/wagon_exit"
            ).respond(202, json={"received": True})

            await handler._handle_detection(track_id=900, bbox=_BBOX_FROM_SIDE, confidence=0.9)
            await handler._handle_detection(track_id=900, bbox=_BBOX_TO_SIDE, confidence=0.9)

        assert fusion_route.called
        sent = json.loads(fusion_route.calls[0].request.content)
        assert sent["track_id"] == 900
        assert sent["coach_from"] == "car-3"
        assert sent["coach_to"] == "car-4"


@pytest.mark.asyncio
async def test_wagon_exit_fusion_unreachable_logs_warning_only() -> None:
    """Fusion candidate POST 5xx is logged WARNING; does not raise."""
    import structlog.testing

    async with httpx.AsyncClient() as client:
        handler = _make_handler(event_store_client=client)

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e1", "stored": True}}
            )
            mock.post("http://fusion:8090/candidates/wagon_exit").respond(503)

            with structlog.testing.capture_logs() as captured:
                await handler._handle_detection(track_id=901, bbox=_BBOX_FROM_SIDE, confidence=0.9)
                await handler._handle_detection(track_id=901, bbox=_BBOX_TO_SIDE, confidence=0.9)

    assert any(
        e.get("reason") == "fusion_unreachable" for e in captured
    )


@pytest.mark.asyncio
async def test_wagon_entry_fires_to_fusion_candidate_endpoint() -> None:
    async with httpx.AsyncClient() as client:
        aft_cam = _make_camera(zone="gangway-aft")
        aft_cam["camera_id"] = "C4_GANGWAY_AFT"
        handler = _make_handler(camera=aft_cam, event_store_client=client)

        with respx.mock() as mock:
            mock.post("http://event-store:8000/api/v1/events").respond(
                201, json={"data": {"event_id": "e2", "stored": True}}
            )
            fusion_route = mock.post(
                "http://fusion:8090/candidates/wagon_entry"
            ).respond(202, json={"received": True})

            await handler._handle_detection(track_id=910, bbox=_BBOX_FROM_SIDE, confidence=0.9)
            await handler._handle_detection(track_id=910, bbox=_BBOX_TO_SIDE, confidence=0.9)

        assert fusion_route.called
