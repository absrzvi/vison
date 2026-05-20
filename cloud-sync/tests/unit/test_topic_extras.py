"""Additional topic-builder edge cases — trailing slash, empty vehicle, lowercase event type."""
from __future__ import annotations

import pytest

from cloud_sync.mqtt_client import build_topic, slugify_vehicle_id


@pytest.mark.unit
def test_slugify_empty_vehicle_id_returns_unknown() -> None:
    """Empty vehicle_id → "unknown" so topic stays well-formed."""
    assert slugify_vehicle_id("") == "unknown"


@pytest.mark.unit
def test_slugify_all_stripped_vehicle_id_returns_unknown() -> None:
    """Non-ASCII vehicle_id that slugifies to nothing → 'unknown'."""
    assert slugify_vehicle_id("列車") == "unknown"


@pytest.mark.unit
def test_build_topic_trailing_slash_in_prefix_stripped() -> None:
    topic = build_topic("oebb/events/", "V001", "OCCUPANCY_UPDATE")
    assert topic == "oebb/events/V001/OCCUPANCY_UPDATE"
    # No double slash anywhere.
    assert "//" not in topic


@pytest.mark.unit
def test_build_topic_lowercase_event_type_uppercased() -> None:
    """Unknown event_type slug path now uppercases (code-review 2026-05-20)."""
    topic = build_topic("oebb/events", "V001", "occupancy_update")
    # `occupancy_update` is NOT a member of EventType StrEnum → slugify path.
    # Result is uppercased so subscribers using uppercase filters match.
    assert topic == "oebb/events/V001/OCCUPANCY_UPDATE"


@pytest.mark.unit
def test_build_topic_with_empty_vehicle_id() -> None:
    """Empty vehicle_id → topic contains "unknown" not empty level."""
    topic = build_topic("oebb/events", "", "OCCUPANCY_UPDATE")
    assert topic == "oebb/events/unknown/OCCUPANCY_UPDATE"
    assert "//" not in topic
