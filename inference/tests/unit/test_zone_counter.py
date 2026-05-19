"""Unit tests for zone_counter.py — rate limit, threshold crossing, no-duplicate guard."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inference.config import Settings
from inference.models import OccupancyState


@pytest.fixture
def settings() -> Settings:
    return Settings(occupancy_threshold_pct=0.80, occupancy_capacity_default=200)


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(return_value=MagicMock(status_code=201))
    return client


@pytest.fixture
def cameras() -> list[dict[str, object]]:
    return [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
            "seat_zones": [{"name": "seating-fwd", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}],
        }
    ]


@pytest.fixture
def zone_counter(settings: Settings, mock_client: AsyncMock, cameras: list[dict[str, object]]) -> object:
    from inference.zone_counter import ZoneCounter

    return ZoneCounter(cameras=cameras, settings=settings, event_store_client=mock_client)


@pytest.mark.unit
@pytest.mark.anyio
async def test_update_posts_occupancy_event(
    zone_counter: object, mock_client: AsyncMock
) -> None:
    detections = [{"track_id": 1, "label": "person", "bbox": (0, 0, 100, 100)}]
    await zone_counter.update("car-1", detections)  # type: ignore[attr-defined]
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["json"]
    assert payload["event_type"] == "OCCUPANCY_UPDATE"


@pytest.mark.unit
@pytest.mark.anyio
async def test_rate_limit_1hz(zone_counter: object, mock_client: AsyncMock) -> None:
    """Second update within 1 second must be skipped."""
    detections = [{"track_id": 1, "label": "person", "bbox": (0, 0, 100, 100)}]
    await zone_counter.update("car-1", detections)  # type: ignore[attr-defined]
    await zone_counter.update("car-1", detections)  # type: ignore[attr-defined]
    assert mock_client.post.call_count == 1


@pytest.mark.unit
@pytest.mark.anyio
async def test_rate_limit_independent_per_car(
    settings: Settings, mock_client: AsyncMock
) -> None:
    """Rate limit is per car_id — two cars can emit independently."""
    from inference.zone_counter import ZoneCounter

    cameras = [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
            "seat_zones": [{"name": "s", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}],
        },
        {
            "camera_id": "C2_DOOR_01",
            "coach_id": "car-2",
            "zone": "door",
            "priority": "P1",
            "capacity": 200,
            "seat_zones": [{"name": "s", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}],
        },
    ]
    zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=mock_client)
    d = [{"track_id": 1, "label": "person", "bbox": (0, 0, 100, 100)}]
    await zc.update("car-1", d)
    await zc.update("car-2", d)
    assert mock_client.post.call_count == 2  # each car emits once


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_rising_emits_event(
    zone_counter: object, mock_client: AsyncMock
) -> None:
    """Crossing 80% in rising direction emits OCCUPANCY_THRESHOLD_CROSSED."""
    # Patch time so rate limit doesn't block

    # Set last_emit_time far in the past so first update goes through
    zc = zone_counter  # type: ignore[assignment]
    zc._last_emit: dict[str, float] = {"car-1": 0.0}  # type: ignore[attr-defined]

    # 161/200 = 80.5% > threshold
    detections = [{"track_id": i, "label": "person", "bbox": (0, 0, 10, 10)} for i in range(161)]
    await zc.update("car-1", detections)

    calls = [c for c in mock_client.post.call_args_list]
    event_types = []
    for c in calls:
        j = c.kwargs.get("json") or (c.args[1] if len(c.args) > 1 else {})
        event_types.append(j.get("event_type", ""))
    assert "OCCUPANCY_THRESHOLD_CROSSED" in event_types


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_no_duplicate_same_direction(
    zone_counter: object, mock_client: AsyncMock
) -> None:
    """Second crossing in same direction must not emit a duplicate event."""
    zc = zone_counter  # type: ignore[assignment]
    zc._last_emit = {"car-1": 0.0}  # type: ignore[attr-defined]

    detections_high = [{"track_id": i, "label": "person", "bbox": (0, 0, 10, 10)} for i in range(161)]
    await zc.update("car-1", detections_high)
    threshold_calls_1 = sum(
        1
        for c in mock_client.post.call_args_list
        if (c.kwargs.get("json") or {}).get("event_type") == "OCCUPANCY_THRESHOLD_CROSSED"
    )

    # Reset rate limit and emit again at same high occupancy
    zc._last_emit = {"car-1": 0.0}  # type: ignore[attr-defined]
    await zc.update("car-1", detections_high)
    threshold_calls_2 = sum(
        1
        for c in mock_client.post.call_args_list
        if (c.kwargs.get("json") or {}).get("event_type") == "OCCUPANCY_THRESHOLD_CROSSED"
    )
    assert threshold_calls_2 == threshold_calls_1  # no duplicate


@pytest.mark.unit
@pytest.mark.anyio
async def test_threshold_falling_emits_event(
    zone_counter: object, mock_client: AsyncMock
) -> None:
    """Dropping below threshold in falling direction emits OCCUPANCY_THRESHOLD_CROSSED."""
    zc = zone_counter  # type: ignore[assignment]
    # Manually set state to already be above threshold
    zc._states["car-1"].occupancy_pct = 0.85
    zc._threshold_state[("car-1", 0.80)] = "rising"  # already crossed rising
    zc._last_emit = {"car-1": 0.0}

    # Drop below threshold (1 person / 200 = 0.5%)
    detections = [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}]
    await zc.update("car-1", detections)

    event_types = [
        (c.kwargs.get("json") or {}).get("event_type", "")
        for c in mock_client.post.call_args_list
    ]
    assert "OCCUPANCY_THRESHOLD_CROSSED" in event_types


@pytest.mark.unit
@pytest.mark.anyio
async def test_update_unknown_car_id_is_noop(
    settings: Settings, mock_client: AsyncMock, cameras: list[dict[str, object]]
) -> None:
    from inference.zone_counter import ZoneCounter

    zc = ZoneCounter(cameras=cameras, settings=settings, event_store_client=mock_client)
    await zc.update("car-999", [{"track_id": 1, "label": "person", "bbox": (0, 0, 10, 10)}])
    mock_client.post.assert_not_called()


@pytest.mark.unit
def test_fire_threshold_event_no_event_loop(
    zone_counter: object,
) -> None:
    """RuntimeError from get_event_loop must be swallowed gracefully."""

    zc = zone_counter  # type: ignore[assignment]
    with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
        # Should not raise
        zc._fire_threshold_event("car-1", "rising", 0.80)  # type: ignore[attr-defined]


@pytest.mark.unit
def test_build_occupancy_payload_has_all_fields() -> None:
    from inference.zone_counter import ZoneCounter

    state = OccupancyState(car_id="car-1", occupancy_count=10, occupancy_pct=0.5, capacity=200)
    payload = ZoneCounter.build_occupancy_payload(state, confidence=1.0)
    for field in ("car_id", "zone", "occupancy_count", "occupancy_pct", "capacity", "confidence", "service_tier"):
        assert field in payload, f"Missing: {field}"
