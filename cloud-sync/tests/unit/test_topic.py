"""Topic format + slugification — AC4, security bullet."""
from __future__ import annotations

import pytest

from cloud_sync.mqtt_client import build_topic, slugify_vehicle_id


@pytest.mark.unit
def test_slugify_strips_mqtt_wildcards() -> None:
    assert slugify_vehicle_id("V#001") == "V-001"
    assert slugify_vehicle_id("V+001") == "V-001"
    assert slugify_vehicle_id("V/001") == "V-001"
    assert slugify_vehicle_id("V 001") == "V-001"


@pytest.mark.unit
def test_slugify_preserves_safe_chars() -> None:
    assert slugify_vehicle_id("V001") == "V001"
    assert slugify_vehicle_id("V-001") == "V-001"
    assert slugify_vehicle_id("OBB-TEST-01") == "OBB-TEST-01"


@pytest.mark.unit
def test_build_topic_happy_path() -> None:
    topic = build_topic("oebb/events", "OBB-TEST", "OCCUPANCY_UPDATE")
    assert topic == "oebb/events/OBB-TEST/OCCUPANCY_UPDATE"


@pytest.mark.unit
def test_build_topic_unknown_event_type_slugified() -> None:
    # An unknown event_type still produces a publishable topic.
    topic = build_topic("oebb/events", "V001", "UNKNOWN_TYPE")
    # UNKNOWN_TYPE isn't in the StrEnum but is alphanumeric+underscore so
    # passes the slug regex unchanged.
    assert topic == "oebb/events/V001/UNKNOWN_TYPE"


@pytest.mark.unit
def test_build_topic_strips_injection_attempt() -> None:
    """Security: a malicious vehicle_id like '; rm -rf /' is slugified out."""
    topic = build_topic("oebb/events", "; rm -rf /", "OCCUPANCY_UPDATE")
    # Every non-allowlist char became '-'. No slashes / spaces / semicolons.
    assert "/" not in topic.removeprefix("oebb/events/").removesuffix("/OCCUPANCY_UPDATE")
    assert ";" not in topic
    assert " " not in topic


@pytest.mark.unit
def test_known_event_types_pass_through() -> None:
    from oebb_shared.events import EventType

    for et in (EventType.ALERT_RAISED, EventType.OCCUPANCY_UPDATE,
               EventType.JOURNEY_ENDED, EventType.RAMP_DEPLOYED):
        topic = build_topic("oebb/events", "V001", et.value)
        assert topic == f"oebb/events/V001/{et.value}"
