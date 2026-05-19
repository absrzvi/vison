"""Unit tests for zone_counter.py — rate limit, threshold crossing, envelope correctness.

Uses respx.mock to mock httpx at the transport layer (Rule 13) — payloads and URLs
are real-tested rather than asserting against AsyncMock call_args.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from inference.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        occupancy_threshold_pct=0.80,
        occupancy_capacity_default=200,
        event_store_url="http://event-store.test",
    )


@pytest.fixture
def cameras() -> list[dict[str, Any]]:
    return [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
        }
    ]


@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient() as c:
        yield c


@pytest.mark.unit
@pytest.mark.anyio
async def test_update_posts_occupancy_event(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
        assert route.called
        body = route.calls[0].request.content
        # Body must be valid JSON parseable as a canonical envelope.
        import json
        env = json.loads(body)
        assert env["event_type"] == "OCCUPANCY_UPDATE"
        assert env["source"] == "inference"
        assert "journey_id" in env
        assert "vehicle_id" in env
        assert env["schema_version"] == 1
        # confidence is omitted by OccupancyUpdatePayload._drop_none when None.
        assert "confidence" not in env["payload"]
        assert env["payload"]["service_tier"] == "standard"


@pytest.mark.unit
@pytest.mark.anyio
async def test_rate_limit_1hz(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        d = [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}]
        await zc.update("car-1", d)
        await zc.update("car-1", d)
        # Second call within 1s suppressed; only one OCCUPANCY_UPDATE.
        assert route.call_count == 1


@pytest.mark.unit
@pytest.mark.anyio
async def test_rate_limit_independent_per_car(
    settings: Settings, client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    cameras = [
        {"camera_id": "C1", "coach_id": "car-1", "zone": "d", "priority": "P1", "capacity": 200},
        {"camera_id": "C2", "coach_id": "car-2", "zone": "d", "priority": "P1", "capacity": 200},
    ]
    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        d = [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}]
        await zc.update("car-1", d)
        await zc.update("car-2", d)
        assert route.call_count == 2


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_rising_emits_event(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """P-M10: rising fires when count crosses threshold + deadband.

    threshold=0.80, capacity=200 → threshold_count=160; deadband default=3 → rising_at=163.
    """
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        zc._last_emit = {"car-1": 0.0}
        # 163 people — exactly threshold_count + deadband, crosses the rising line.
        detections = [
            {"track_id": i, "label": "person", "bbox": (0, 0, 10, 10)} for i in range(163)
        ]
        await zc.update("car-1", detections)
        import json
        event_types = [json.loads(c.request.content)["event_type"] for c in route.calls]
        assert "OCCUPANCY_UPDATE" in event_types
        assert "OCCUPANCY_THRESHOLD_CROSSED" in event_types


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_deadband_suppresses_flap(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """P-M10: at the boundary, oscillation 161↔162 must NOT emit threshold events.

    Without deadband, 160↔161 would emit rising/falling/rising every second. With
    deadband=3, the [157, 163] zone is stable — no events emitted in this range.
    """
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        zc._last_emit = {"car-1": 0.0}

        # Walk through 159 → 160 → 161 → 162 — all inside deadband zone, no threshold events.
        import json
        for count in (159, 160, 161, 162):
            zc._last_emit["car-1"] = 0.0  # reset rate limit per step
            zc._in_flight["car-1"] = False
            await zc.update(
                "car-1",
                [{"track_id": i, "label": "person", "bbox": (0, 0, 10, 10)} for i in range(count)],
            )
        threshold_events = [
            c for c in route.calls
            if json.loads(c.request.content)["event_type"] == "OCCUPANCY_THRESHOLD_CROSSED"
        ]
        assert threshold_events == [], "deadband zone must not emit threshold-crossed"


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_no_duplicate_same_direction(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        zc._last_emit = {"car-1": 0.0}

        high = [{"track_id": i, "label": "person", "bbox": (0, 0, 10, 10)} for i in range(163)]
        await zc.update("car-1", high)
        import json
        crossed_1 = sum(
            1 for c in route.calls
            if json.loads(c.request.content)["event_type"] == "OCCUPANCY_THRESHOLD_CROSSED"
        )

        zc._last_emit = {"car-1": 0.0}
        zc._in_flight["car-1"] = False
        await zc.update("car-1", high)
        crossed_2 = sum(
            1 for c in route.calls
            if json.loads(c.request.content)["event_type"] == "OCCUPANCY_THRESHOLD_CROSSED"
        )
        assert crossed_2 == crossed_1, "no duplicate threshold-crossed in same direction"


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_falling_emits_event(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """P-M10: falling fires when count crosses threshold - deadband from above.

    capacity=200, threshold=0.80, deadband=3 → falling_at=157. Need prev_count >=158
    and new_count <= 157.
    """
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        # Start above threshold so falling can fire.
        zc._states["car-1"].occupancy_count = 170
        zc._states["car-1"].occupancy_pct = 0.85
        zc._threshold_state[("car-1", 0.80)] = "rising"
        zc._last_emit = {"car-1": 0.0}

        # 1 person — well below falling_at=157.
        await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])

        import json
        event_types = [json.loads(c.request.content)["event_type"] for c in route.calls]
        assert "OCCUPANCY_THRESHOLD_CROSSED" in event_types


@pytest.mark.unit
@pytest.mark.anyio
async def test_update_unknown_car_id_is_noop(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test", assert_all_called=False) as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        await zc.update("car-999", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
        assert not route.called


@pytest.mark.unit
@pytest.mark.anyio
async def test_none_track_id_filtered(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """None track_ids must not inflate the count (defence in depth — callback also filters)."""
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        # Three detections, none with valid track_ids — count must be zero.
        await zc.update(
            "car-1",
            [
                {"track_id": None, "label": "person", "bbox": (0, 0, 10, 10)},
                {"track_id": None, "label": "person", "bbox": (10, 10, 20, 20)},
                {"track_id": None, "label": "person", "bbox": (20, 20, 30, 30)},
            ],
        )
        import json
        env = json.loads(route.calls[0].request.content)
        assert env["payload"]["occupancy_count"] == 0


@pytest.mark.unit
@pytest.mark.anyio
async def test_5xx_response_raises_after_retry(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """M15: raise_for_status surfaces 5xx so DEFAULT_RETRY actually retries.

    Now also asserts call_count > 1 — without this the test would pass even if
    `@DEFAULT_RETRY` were removed (the single failing POST would still raise).
    """
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(500))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        with pytest.raises(httpx.HTTPStatusError):
            await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
        # DEFAULT_RETRY does 5 attempts; assert retry actually fired.
        assert route.call_count >= 2, (
            f"DEFAULT_RETRY should have retried; got call_count={route.call_count}"
        )


@pytest.mark.unit
def test_capacity_zero_refuses_to_start(settings: Settings, client: httpx.AsyncClient) -> None:
    """capacity <= 0 is a config error — container must refuse to start."""
    from inference.zone_counter import ZoneCounter

    bad = [{"camera_id": "C", "coach_id": "car-1", "zone": "d", "priority": "P1", "capacity": 0}]
    with pytest.raises(ValueError, match="must be > 0"):
        ZoneCounter(cameras=bad, settings=settings, event_store_client=client)


@pytest.mark.unit
def test_capacity_non_int_refuses_to_start(
    settings: Settings, client: httpx.AsyncClient
) -> None:
    from inference.zone_counter import ZoneCounter

    bad = [
        {"camera_id": "C", "coach_id": "car-1", "zone": "d", "priority": "P1", "capacity": None}
    ]
    with pytest.raises(ValueError, match="Invalid capacity"):
        ZoneCounter(cameras=bad, settings=settings, event_store_client=client)


@pytest.mark.unit
def test_capacity_bool_refused(settings: Settings, client: httpx.AsyncClient) -> None:
    """M17: bool is a subclass of int — int(True)=1 would silently produce
    capacity=1 and trip the threshold on any single person. Must reject."""
    from inference.zone_counter import ZoneCounter

    bad = [
        {"camera_id": "C", "coach_id": "car-1", "zone": "d", "priority": "P1", "capacity": True}
    ]
    with pytest.raises(ValueError, match="bool"):
        ZoneCounter(cameras=bad, settings=settings, event_store_client=client)


@pytest.mark.unit
@pytest.mark.anyio
async def test_journey_holder_updates_envelope(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """M13: outbound envelopes pick up the live journey_id from the holder,
    not the static Settings.journey_id captured at construction."""
    from inference.models import JourneyHolder
    from inference.zone_counter import ZoneCounter

    holder = JourneyHolder(journey_id="OBB-TEST_t1_20260519")
    with respx.mock(base_url="http://event-store.test") as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(
            cameras=cameras,
            settings=settings,
            event_store_client=client,
            journey_holder=holder,
        )
        await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])

        import json
        env_1 = json.loads(route.calls[0].request.content)
        assert env_1["journey_id"] == "OBB-TEST_t1_20260519"

        # Mid-flight trip change — next emit must use the new journey_id.
        zc.update_journey_id("OBB-TEST_t2_20260519")
        zc._last_emit["car-1"] = 0.0  # reset rate limit
        zc._in_flight["car-1"] = False
        await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
        env_2 = json.loads(route.calls[1].request.content)
        assert env_2["journey_id"] == "OBB-TEST_t2_20260519"


@pytest.mark.unit
@pytest.mark.anyio
async def test_in_flight_skip_during_retries(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """M9: while a previous POST chain (retries included) is draining, new
    update() calls past the rate-limit gate must be skipped to prevent pile-up."""
    from inference.zone_counter import ZoneCounter

    with respx.mock(base_url="http://event-store.test", assert_all_called=False) as mock:
        route = mock.post("/api/v1/events").mock(return_value=httpx.Response(201))
        zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
        # Force in_flight True without an actual POST in progress.
        zc._in_flight["car-1"] = True
        zc._last_emit["car-1"] = 0.0
        await zc.update("car-1", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
        assert not route.called  # skipped, no parallel POST


@pytest.mark.unit
@pytest.mark.anyio
async def test_per_car_lock_exists(
    settings: Settings, cameras: list[dict[str, Any]], client: httpx.AsyncClient
) -> None:
    """M4: ZoneCounter must create one asyncio.Lock per car_id at construction."""
    import asyncio

    from inference.zone_counter import ZoneCounter

    zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=client)
    assert "car-1" in zc._locks
    assert isinstance(zc._locks["car-1"], asyncio.Lock)


@pytest.mark.unit
@pytest.mark.anyio
async def test_multi_coach_each_tracked(settings: Settings, client: httpx.AsyncClient) -> None:
    """M3: cameras with distinct coach_ids each create their own OccupancyState.

    Previously all 3 cameras in cameras.json had coach_id='car-1', causing ZoneCounter
    to silently drop cameras 2 and 3.
    """
    from inference.zone_counter import ZoneCounter

    multi_cameras = [
        {
            "camera_id": "C1",
            "coach_id": "car-1",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
        },
        {
            "camera_id": "C2",
            "coach_id": "car-2",
            "zone": "interior",
            "priority": "P2",
            "capacity": 180,
        },
        {
            "camera_id": "C3",
            "coach_id": "car-3",
            "zone": "exterior",
            "priority": "P3",
            "capacity": 50,
        },
    ]
    zc = ZoneCounter(cameras=multi_cameras, settings=settings, event_store_client=client)
    assert set(zc._states.keys()) == {"car-1", "car-2", "car-3"}
    assert zc._states["car-2"].capacity == 180
    assert zc._states["car-3"].capacity == 50
