"""Unit tests for vestibule congestion detection in ZoneCounter."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from inference.config import Settings
from inference.models import JourneyHolder
from inference.zone_counter import ZoneCounter


def _make_zone_counter(
    zone: str = "door",
    threshold: int = 8,
    score_threshold: float = 0.75,
) -> ZoneCounter:
    settings = Settings(
        vestibule_congestion_threshold=threshold,
        vestibule_congestion_score_threshold=score_threshold,
        fusion_url="http://fusion:8090",
    )
    cameras = [
        {
            "camera_id": "C1_DOOR_01",
            "coach_id": "car-1",
            "zone": zone,
            "capacity": 50,
            "seat_zones": [{"name": "z1", "polygon": [[0, 0], [640, 0], [640, 480], [0, 480]]}],
        }
    ]
    client = AsyncMock()
    resp = AsyncMock()
    resp.raise_for_status = AsyncMock()
    client.post = AsyncMock(return_value=resp)
    jh = JourneyHolder(journey_id="OBB-T_001_20260519")
    return ZoneCounter(cameras=cameras, settings=settings, event_store_client=client, journey_holder=jh)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vestibule_congestion_threshold_crossing() -> None:
    """person_count > threshold → VESTIBULE_CONGESTION POSTed to event-store.

    R1 (2026-05-20): vestibule_id is composed from car_id + the camera's zone
    (here "door"), so a door camera produces "car-1-door". Configure cameras.json
    with zone="vestibule" if you want the literal "-vestibule" suffix.
    """
    zc = _make_zone_counter(zone="door", threshold=8, score_threshold=0.75)

    await zc._check_vestibule_congestion(
        "car-1", person_count=10, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]

    zc._client.post.assert_called_once()
    call_args = zc._client.post.call_args
    url = call_args[0][0]
    assert "/api/v1/events" in url
    json_body = call_args[1]["json"]
    assert json_body["event_type"] == "VESTIBULE_CONGESTION"
    payload = json_body["payload"]
    assert payload["car_id"] == "car-1"
    assert payload["vestibule_id"] == "car-1-door"
    assert payload["person_count"] == 10
    assert payload["congestion_score"] == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vestibule_congestion_below_score_threshold() -> None:
    """person_count at or below score threshold → no emit."""
    zc = _make_zone_counter(zone="door", threshold=8, score_threshold=0.75)

    await zc._check_vestibule_congestion(
        "car-1", person_count=5, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]

    zc._client.post.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vestibule_congestion_rate_limit() -> None:
    """Second emit within 10s is suppressed."""
    zc = _make_zone_counter(zone="door", threshold=8, score_threshold=0.75)

    await zc._check_vestibule_congestion(
        "car-1", person_count=10, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]
    await zc._check_vestibule_congestion(
        "car-1", person_count=10, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]

    assert zc._client.post.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_interior_zone_no_congestion_emit() -> None:
    """Interior zone cameras never emit VESTIBULE_CONGESTION."""
    zc = _make_zone_counter(zone="interior", threshold=8, score_threshold=0.75)

    await zc._check_vestibule_congestion(
        "car-1", person_count=100, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]

    zc._client.post.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vestibule_congestion_score_calculation() -> None:
    """congestion_score = person_count / threshold, capped at 1.0."""
    zc = _make_zone_counter(zone="door", threshold=8, score_threshold=0.75)

    await zc._check_vestibule_congestion(
        "car-1", person_count=8, camera_id="C1_DOOR_01"
    )  # type: ignore[attr-defined]

    # score = 8/8 = 1.0 > 0.75, should emit
    zc._client.post.assert_called_once()
    payload = zc._client.post.call_args[1]["json"]["payload"]
    assert payload["congestion_score"] == pytest.approx(1.0)
    assert payload["threshold_score"] == pytest.approx(0.75)
    assert payload["dwell_time_avg_s"] == pytest.approx(0.0)
