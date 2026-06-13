"""Tests for EventEnvelope and all payload models (E1-S2; extended E10-S1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from oebb_shared.events import (
    PAYLOAD_MODELS,
    EventEnvelope,
    EventType,
    BoundingBox,
    OccupancyUpdatePayload,
    AccessibilityDetectedPayload,
    AlertRaisedPayload,
    AlertResolvedPayload,
    AlarmActivePayload,
    AlarmClearedPayload,
    CameraDegradedPayload,
    CameraRecoveredPayload,
    DoorObstructionPayload,
    JourneyEndedPayload,
    JourneyStartedPayload,
    LuggageRackSaturationPayload,
    OccupancyThresholdCrossedPayload,
    RampDeployedPayload,
    SyncCompletedPayload,
    UnattendedBagPayload,
    VestibuleCongestionPayload,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_ENVELOPE_DATA: dict[str, object] = {
    "journey_id": "R5001C-031_RJ-0847_20260516",
    "vehicle_id": "R5001C-031",
    "event_type": "OCCUPANCY_UPDATE",
    "severity": "info",
    "source": "inference",
    "payload": {},
}


def _make_envelope(**overrides: object) -> EventEnvelope:
    data = {**_VALID_ENVELOPE_DATA, **overrides}
    return EventEnvelope(**data)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC1 — EventType has exactly the expected members
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_event_type_has_expected_members() -> None:
    expected = {
        "OCCUPANCY_UPDATE",
        "OCCUPANCY_THRESHOLD_CROSSED",
        "ALERT_RAISED",
        "ALERT_RESOLVED",
        "VESTIBULE_CONGESTION",
        "LUGGAGE_RACK_SATURATION",
        "UNATTENDED_BAG",
        "DOOR_OBSTRUCTION",
        "ACCESSIBILITY_DETECTED",
        "RAMP_DEPLOYED",
        "ALARM_ACTIVE",
        "ALARM_CLEARED",
        "JOURNEY_STARTED",
        "JOURNEY_ENDED",
        "CAMERA_DEGRADED",
        "CAMERA_RECOVERED",
        "SYNC_COMPLETED",
        # ADR-17
        "WAGON_EXIT",
        "WAGON_ENTRY",
        "LEDGER_DRIFT_OBSERVATION",
        # ADR-15
        "CALIBRATION_DRIFT",
        # ADR-18
        "COACH_COMFORT_INDEX",
        "STREAM_PRIORITY",
        # E10-S1
        "INFERENCE_HEARTBEAT",
        "ALERT_CLASS_DISABLED",
        "ALERT_CLASS_REENABLED",
    }
    assert {e.value for e in EventType} == expected
    assert len(EventType) == 26


# ---------------------------------------------------------------------------
# AC2 — EventEnvelope validates a well-formed envelope
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_envelope_valid() -> None:
    env = _make_envelope()
    assert env.vehicle_id == "R5001C-031"
    assert env.severity == "info"
    assert env.source == "inference"
    assert env.schema_version == 1
    # event_id is auto-generated UUID string
    assert len(env.event_id) == 36
    assert env.event_id.count("-") == 4


@pytest.mark.unit
def test_envelope_journey_id_pattern_valid() -> None:
    env = _make_envelope(journey_id="V001_RJ-0001_20260101")
    assert env.journey_id == "V001_RJ-0001_20260101"


@pytest.mark.unit
def test_envelope_journey_id_pattern_invalid() -> None:
    with pytest.raises(ValidationError, match="journey_id"):
        _make_envelope(journey_id="bad-format")


@pytest.mark.unit
def test_envelope_journey_id_missing_date_part() -> None:
    with pytest.raises(ValidationError):
        _make_envelope(journey_id="V001_RJ-0001")


# ---------------------------------------------------------------------------
# AC3 — Unrecognised event_type raises ValidationError
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_envelope_unrecognised_event_type_raises() -> None:
    with pytest.raises(ValidationError):
        _make_envelope(event_type="DOES_NOT_EXIST")


@pytest.mark.unit
def test_envelope_invalid_severity_raises() -> None:
    with pytest.raises(ValidationError):
        _make_envelope(severity="high")


@pytest.mark.unit
def test_envelope_invalid_source_raises() -> None:
    with pytest.raises(ValidationError):
        _make_envelope(source="unknown-service")


# ---------------------------------------------------------------------------
# AC4 — PAYLOAD_MODELS registry has one entry per EventType
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_payload_models_registry_complete() -> None:
    assert set(PAYLOAD_MODELS.keys()) == set(EventType)
    assert len(PAYLOAD_MODELS) == 26


# ---------------------------------------------------------------------------
# AC5 — OCCUPANCY_UPDATE: confidence omitted when not provided
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_occupancy_update_confidence_omitted_when_absent() -> None:
    p = OccupancyUpdatePayload(
        car_id="car-3",
        zone=None,
        occupancy_count=142,
        occupancy_pct=0.71,
        capacity=200,
        service_tier="business",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    dumped = p.model_dump()
    assert "confidence" not in dumped


@pytest.mark.unit
def test_occupancy_update_confidence_present_when_set() -> None:
    p = OccupancyUpdatePayload(
        car_id="car-3",
        zone=None,
        occupancy_count=142,
        occupancy_pct=0.71,
        capacity=200,
        confidence=0.94,
        service_tier="business",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    dumped = p.model_dump()
    assert dumped["confidence"] == pytest.approx(0.94)


# ---------------------------------------------------------------------------
# AC8 — model_json_schema() works
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_envelope_json_schema() -> None:
    schema = EventEnvelope.model_json_schema()
    assert "properties" in schema
    assert "journey_id" in schema["properties"]


# ---------------------------------------------------------------------------
# Payload model round-trip tests (spot checks per category)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_alert_raised_payload() -> None:
    p = AlertRaisedPayload(
        alert_id="a3f1c2d4-89ab-4ef0-b123-000000000001",
        alert_code="OVERCROWDING",
        car_id="car-2",
        zone="vestibule-b",
        description="Occupancy exceeded 90% for more than 60 seconds.",
        auto_resolve_after_s=300,
        confidence_score=0.91,
        confidence_basis="model",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert p.alert_code == "OVERCROWDING"
    d = p.model_dump()
    assert "priority" not in d


@pytest.mark.unit
def test_alert_raised_payload_with_priority() -> None:
    p = AlertRaisedPayload(
        alert_id="a3f1c2d4-89ab-4ef0-b123-000000000001",
        alert_code="OVERCROWDING",
        car_id="car-2",
        zone=None,
        description="Overcrowding.",
        priority="escalated",
        confidence_score=0.91,
        confidence_basis="model",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    d = p.model_dump()
    assert d["priority"] == "escalated"


@pytest.mark.unit
def test_alert_resolved_payload() -> None:
    p = AlertResolvedPayload(
        alert_id="a3f1c2d4-89ab-4ef0-b123-000000000001",
        alert_code="OVERCROWDING",
        car_id="car-2",
        zone="vestibule-b",
        resolve_reason="manual",
    )
    assert p.resolve_reason == "manual"


@pytest.mark.unit
def test_vestibule_congestion_payload() -> None:
    p = VestibuleCongestionPayload(
        car_id="car-4",
        vestibule_id="vestibule-a",
        congestion_score=0.87,
        person_count=11,
        dwell_time_avg_s=42.5,
        threshold_score=0.75,
    )
    assert p.congestion_score == pytest.approx(0.87)


@pytest.mark.unit
def test_luggage_rack_saturation_confidence_omitted() -> None:
    p = LuggageRackSaturationPayload(
        car_id="car-2",
        rack_id="car-2-rack-upper-left",
        fill_pct=0.95,
        item_count=7,
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert "confidence" not in p.model_dump()


@pytest.mark.unit
def test_unattended_bag_payload() -> None:
    p = UnattendedBagPayload(
        car_id="car-3",
        zone="seating-mid",
        track_id="bag-0042",
        dwell_s=180.0,
        bbox={"x": 412, "y": 308, "w": 64, "h": 48},
        camera_id="cam-3-02",
        confidence=0.91,
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert p.model_dump()["confidence"] == pytest.approx(0.91)


@pytest.mark.unit
def test_door_obstruction_payload() -> None:
    p = DoorObstructionPayload(
        car_id="car-1",
        door_id="car-1-door-L-2",
        obstruction_type="person",
        track_id="person-0117",
        camera_id="cam-1-door-L2",
        door_state="closing",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert "confidence" not in p.model_dump()


@pytest.mark.unit
def test_accessibility_detected_payload() -> None:
    p = AccessibilityDetectedPayload(
        car_id="car-2",
        zone="vestibule-b",
        track_id="person-0204",
        assistance_type=["wheelchair"],
        camera_id="cam-2-vest-b",
        confidence=0.89,
        near_door_id="car-2-door-R-1",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert p.assistance_type == ["wheelchair"]
    assert p.model_dump()["confidence"] == pytest.approx(0.89)


@pytest.mark.unit
def test_ramp_deployed_payload() -> None:
    p = RampDeployedPayload(
        car_id="car-2",
        door_id="car-2-door-R-1",
        triggered_by_track_id="person-0204",
        deployed_by="auto",
        station_id="Wien Hauptbahnhof",
    )
    assert p.deployed_by == "auto"


@pytest.mark.unit
def test_alarm_active_payload() -> None:
    p = AlarmActivePayload(
        alarm_id="hw-alarm-00391",
        alarm_type="passenger_call",
        car_id="car-5",
        zone="seating-rear",
        hardware_code="PC-04",
        triggered_by="passenger",
    )
    assert p.alarm_type == "passenger_call"


@pytest.mark.unit
def test_alarm_cleared_payload() -> None:
    p = AlarmClearedPayload(
        alarm_id="hw-alarm-00391",
        alarm_type="passenger_call",
        car_id="car-5",
        cleared_by="crew",
        duration_s=47.2,
    )
    assert p.duration_s == pytest.approx(47.2)


@pytest.mark.unit
def test_journey_started_payload() -> None:
    p = JourneyStartedPayload(
        trip_number="RJ-0847",
        origin_station_id="Wien Hbf",
        scheduled_departure="2026-05-16T06:00:00Z",
        actual_departure="2026-05-16T06:02:14Z",
        consist=["car-1", "car-2", "car-3", "car-4", "car-5"],
        service_class="railjet",
    )
    assert len(p.consist) == 5


@pytest.mark.unit
def test_journey_ended_payload() -> None:
    p = JourneyEndedPayload(
        trip_number="RJ-0847",
        destination_station_id="Salzburg Hbf",
        scheduled_arrival="2026-05-16T08:50:00Z",
        actual_arrival="2026-05-16T08:53:41Z",
        total_duration_s=10287.0,
        peak_occupancy_pct=0.91,
    )
    assert p.peak_occupancy_pct == pytest.approx(0.91)


@pytest.mark.unit
def test_camera_degraded_payload() -> None:
    p = CameraDegradedPayload(
        camera_id="cam-3-02",
        car_id="car-3",
        degradation_type="low_fps",
        fps_actual=3.2,
        fps_expected=25.0,
        quality_score=0.21,
        affected_zones=["seating-mid"],
    )
    assert p.degradation_type == "low_fps"


@pytest.mark.unit
def test_camera_recovered_payload() -> None:
    p = CameraRecoveredPayload(
        camera_id="cam-3-02",
        car_id="car-3",
        downtime_s=214.5,
        fps_actual=24.8,
        quality_score=0.93,
    )
    assert p.downtime_s == pytest.approx(214.5)


@pytest.mark.unit
def test_sync_completed_payload() -> None:
    p = SyncCompletedPayload(
        sync_type="ntp",
        nodes_synced=12,
        nodes_failed=0,
        max_skew_ms=4.7,
        skew_by_node={"cam-1-01": 1.2, "cam-2-01": 4.7, "cam-3-02": -0.3},
        sync_server="192.168.10.1",
    )
    assert p.nodes_synced == 12


@pytest.mark.unit
def test_occupancy_threshold_crossed_payload() -> None:
    p = OccupancyThresholdCrossedPayload(
        car_id="car-1",
        zone=None,
        threshold_pct=0.80,
        direction="rising",
        occupancy_pct=0.82,
        occupancy_count=164,
        capacity=200,
        service_tier="standard",
    )
    assert p.direction == "rising"


# ---------------------------------------------------------------------------
# Constraint edge cases (added in code review)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_envelope_timestamp_must_have_z_suffix() -> None:
    with pytest.raises(ValidationError, match="timestamp"):
        _make_envelope(timestamp="2026-05-17T10:00:00")  # no Z


@pytest.mark.unit
def test_envelope_timestamp_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError, match="timestamp"):
        _make_envelope(timestamp="2026-05-17 10:00:00Z")  # space separator


@pytest.mark.unit
def test_envelope_event_id_must_be_uuid_v4() -> None:
    with pytest.raises(ValidationError, match="event_id"):
        _make_envelope(event_id="not-a-uuid")


@pytest.mark.unit
def test_envelope_schema_version_unsupported_raises() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        _make_envelope(schema_version=99)


@pytest.mark.unit
def test_envelope_journey_id_trailing_newline_rejected() -> None:
    with pytest.raises(ValidationError, match="journey_id"):
        _make_envelope(journey_id="R5001C-031_RJ-0847_20260516\n")


@pytest.mark.unit
def test_envelope_journey_id_invalid_date_rejected() -> None:
    with pytest.raises(ValidationError, match="journey_id"):
        _make_envelope(journey_id="R5001C-031_RJ-0847_20261399")


@pytest.mark.unit
def test_envelope_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(**{**_VALID_ENVELOPE_DATA, "unexpected_field": "oops"})  # type: ignore[arg-type]


@pytest.mark.unit
def test_envelope_payload_validated_against_registry() -> None:
    with pytest.raises(ValidationError):
        _make_envelope(
            event_type="OCCUPANCY_UPDATE",
            payload={"car_id": "car-1"},  # missing required fields
        )


@pytest.mark.unit
def test_occupancy_negative_count_rejected() -> None:
    with pytest.raises(ValidationError):
        OccupancyUpdatePayload(
            car_id="car-1",
            occupancy_count=-1,
            occupancy_pct=0.5,
            capacity=200,
            service_tier="standard",
        )


@pytest.mark.unit
def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        OccupancyUpdatePayload(
            car_id="car-1",
            occupancy_count=100,
            occupancy_pct=0.5,
            capacity=200,
            confidence=1.5,
            service_tier="standard",
        )


@pytest.mark.unit
def test_occupancy_pct_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        OccupancyUpdatePayload(
            car_id="car-1",
            occupancy_count=100,
            occupancy_pct=1.5,
            capacity=200,
            service_tier="standard",
        )


@pytest.mark.unit
def test_empty_car_id_rejected() -> None:
    with pytest.raises(ValidationError):
        OccupancyUpdatePayload(
            car_id="",
            occupancy_count=100,
            occupancy_pct=0.5,
            capacity=200,
            service_tier="standard",
        )


@pytest.mark.unit
def test_bbox_missing_required_key_rejected() -> None:
    with pytest.raises(ValidationError):
        UnattendedBagPayload(
            car_id="car-3",
            track_id="bag-001",
            dwell_s=60.0,
            bbox={"x": 10, "y": 20},  # missing w, h
            camera_id="cam-3-01",
        )


@pytest.mark.unit
def test_accessibility_empty_assistance_type_rejected() -> None:
    with pytest.raises(ValidationError):
        AccessibilityDetectedPayload(
            car_id="car-2",
            track_id="person-001",
            assistance_type=[],  # must have at least one
            camera_id="cam-2-01",
            near_door_id="car-2-door-R-1",
        )


@pytest.mark.unit
def test_payload_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        OccupancyUpdatePayload(
            car_id="car-1",
            occupancy_count=100,
            occupancy_pct=0.5,
            capacity=200,
            service_tier="standard",
            typo_field="oops",
        )


@pytest.mark.unit
def test_confidence_omitted_in_json_serialisation() -> None:
    p = OccupancyUpdatePayload(
        car_id="car-1",
        occupancy_count=100,
        occupancy_pct=0.5,
        capacity=200,
        service_tier="standard",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    import json
    parsed = json.loads(p.model_dump_json())
    assert "confidence" not in parsed
