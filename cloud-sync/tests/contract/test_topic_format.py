"""Contract test (AC11): every emitted topic matches the strict allowlist regex."""
from __future__ import annotations

import re

import pytest

from cloud_sync.mqtt_client import build_topic

_TOPIC_RE = re.compile(r"^oebb/events/[A-Za-z0-9-]+/[A-Z_]+$")


@pytest.mark.contract
@pytest.mark.parametrize(
    "vehicle_id,event_type",
    [
        ("OBB-TEST", "OCCUPANCY_UPDATE"),
        ("V001", "ALERT_RAISED"),
        ("R5001C-031", "RAMP_DEPLOYED"),
        ("V-001", "JOURNEY_ENDED"),
    ],
)
def test_topic_matches_allowlist_regex(vehicle_id: str, event_type: str) -> None:
    topic = build_topic("oebb/events", vehicle_id, event_type)
    assert _TOPIC_RE.match(topic), f"topic {topic!r} does not match {_TOPIC_RE.pattern}"


@pytest.mark.contract
@pytest.mark.parametrize(
    "malicious_vehicle_id",
    ["V#001", "V+001", "V/001", "V 001", "; rm -rf /", "../../etc/passwd", "V$001"],
)
def test_malicious_vehicle_id_slugified_to_safe_topic(malicious_vehicle_id: str) -> None:
    """Topic stays well-formed even when vehicle_id contains injection chars."""
    topic = build_topic("oebb/events", malicious_vehicle_id, "OCCUPANCY_UPDATE")
    assert _TOPIC_RE.match(topic), f"unsafe topic emitted: {topic!r}"
    # No MQTT wildcards.
    assert "#" not in topic
    assert "+" not in topic
    # No path traversal.
    middle = topic.split("/")[2]
    assert ".." not in middle
