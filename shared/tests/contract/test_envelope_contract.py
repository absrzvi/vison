"""Contract tests for the OEBB event envelope and payload models.

AC1: Envelope/EventType contract — every EventType roundtrips through EventEnvelope;
     deliberate violations raise ValidationError; container files use the canonical import.
AC2: Coverage gate — this file runs under the `contract` marker so CI includes it.
AC4: C2 timestamp validator fires at CI time via bad fixture.

These tests are hermetic: container files are discovered by filesystem search only —
no container modules are imported (avoids needing container deps installed).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from oebb_shared.events import PAYLOAD_MODELS, EventEnvelope, EventType
from oebb_shared.events.payloads import (
    JourneyEndedPayload,
    JourneyStartedPayload,
)

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parents[3]  # shared/tests/contract → repo root

_CONTAINER_DIRS = [
    "rtsp-ingest",
    "vlan-pollers",
    "inference",
    "event-store",
    "cloud-backend",
]

_SENTINEL_NAMES = {"EventEnvelope", "EventModel", "EventType"}

# ---------------------------------------------------------------------------
# Minimal valid payload dicts for every EventType (sourced from schemas doc).
# Used for roundtrip tests — passed as dicts so EventEnvelope._validate_payload_shape
# exercises the PAYLOAD_MODELS registry.
# ---------------------------------------------------------------------------

_MINIMAL_PAYLOADS: dict[str, dict] = {
    "OCCUPANCY_UPDATE": {
        "car_id": "car-1",
        "zone": None,
        "occupancy_count": 100,
        "occupancy_pct": 0.5,
        "capacity": 200,
        "service_tier": "standard",
    },
    "OCCUPANCY_THRESHOLD_CROSSED": {
        "car_id": "car-1",
        "zone": None,
        "threshold_pct": 0.80,
        "direction": "rising",
        "occupancy_pct": 0.82,
        "occupancy_count": 164,
        "capacity": 200,
        "service_tier": "standard",
    },
    "ALERT_RAISED": {
        "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
        "alert_code": "OVERCROWDING",
        "car_id": "car-2",
        "zone": None,
        "description": "Occupancy exceeded 90%.",
    },
    "ALERT_RESOLVED": {
        "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
        "alert_code": "OVERCROWDING",
        "car_id": "car-2",
        "zone": None,
        "resolve_reason": "manual",
    },
    "VESTIBULE_CONGESTION": {
        "car_id": "car-4",
        "vestibule_id": "vestibule-a",
        "congestion_score": 0.87,
        "person_count": 11,
        "dwell_time_avg_s": 42.5,
        "threshold_score": 0.75,
    },
    "LUGGAGE_RACK_SATURATION": {
        "car_id": "car-2",
        "rack_id": "car-2-rack-upper-left",
        "fill_pct": 0.95,
        "item_count": 7,
    },
    "UNATTENDED_BAG": {
        "car_id": "car-3",
        "zone": None,
        "track_id": "bag-0042",
        "dwell_s": 180.0,
        "bbox": {"x": 412, "y": 308, "w": 64, "h": 48},
        "camera_id": "cam-3-02",
    },
    "DOOR_OBSTRUCTION": {
        "car_id": "car-1",
        "door_id": "car-1-door-L-2",
        "obstruction_type": "person",
        "track_id": "person-0117",
        "camera_id": "cam-1-door-L2",
        "door_state": "closing",
    },
    "ACCESSIBILITY_DETECTED": {
        "car_id": "car-2",
        "zone": None,
        "track_id": "person-0204",
        "assistance_type": ["wheelchair"],  # min_length=1
        "camera_id": "cam-2-vest-b",
        "near_door_id": "car-2-door-R-1",
    },
    "RAMP_DEPLOYED": {
        "car_id": "car-2",
        "door_id": "car-2-door-R-1",
        "triggered_by_track_id": "person-0204",
        "deployed_by": "auto",
        "station_id": "Wien Hauptbahnhof",
    },
    "ALARM_ACTIVE": {
        "alarm_id": "hw-alarm-00391",
        "alarm_type": "passenger_call",
        "car_id": "car-5",
        "zone": None,
        "hardware_code": "PC-04",
        "triggered_by": "passenger",
    },
    "ALARM_CLEARED": {
        "alarm_id": "hw-alarm-00391",
        "alarm_type": "passenger_call",
        "car_id": "car-5",
        "cleared_by": "crew",
        "duration_s": 47.2,
    },
    "JOURNEY_STARTED": {
        "trip_number": "RJ-0847",
        "origin_station_id": "Wien Hbf",
        "scheduled_departure": "2026-05-16T06:00:00Z",
        "actual_departure": "2026-05-16T06:02:14Z",
        "consist": ["car-1", "car-2", "car-3"],  # min_length=1
        "service_class": "railjet",
    },
    "JOURNEY_ENDED": {
        "trip_number": "RJ-0847",
        "destination_station_id": "Salzburg Hbf",
        "scheduled_arrival": "2026-05-16T08:50:00Z",
        "actual_arrival": "2026-05-16T08:53:41Z",
        "total_duration_s": 10287.0,
        "peak_occupancy_pct": 0.91,
    },
    "CAMERA_DEGRADED": {
        "camera_id": "cam-3-02",
        "car_id": "car-3",
        "degradation_type": "low_fps",
        "fps_actual": 3.2,
        "fps_expected": 25.0,
        "quality_score": 0.21,
        "affected_zones": ["seating-mid"],  # min_length=1
    },
    "CAMERA_RECOVERED": {
        "camera_id": "cam-3-02",
        "car_id": "car-3",
        "downtime_s": 214.5,
        "fps_actual": 24.8,
        "quality_score": 0.93,
    },
    "SYNC_COMPLETED": {
        "sync_type": "ntp",
        "nodes_synced": 12,
        "nodes_failed": 0,
        "max_skew_ms": 4.7,
        "skew_by_node": {"cam-1-01": 1.2},
        "sync_server": "192.168.10.1",
    },
    "WAGON_EXIT": {
        "track_id": 312,
        "coach_from": "car-3",
        "coach_to": "car-4",
        "camera_id": "cam-3-gangway-fwd",
        "traversal": "from_to",
        "confidence": 0.88,
        "expect_orphan": False,
    },
    "WAGON_ENTRY": {
        "track_id": 312,
        "coach_from": "car-3",
        "coach_to": "car-4",
        "camera_id": "cam-4-gangway-aft",
        "traversal": "from_to",
        "confidence": 0.91,
    },
    "LEDGER_DRIFT_OBSERVATION": {
        "car_id": "car-1",
        "camera_count": 50,
        "ledger_count": 55,
        "delta": 5,
        "threshold": 10,
        "surface_to_operator": False,
    },
    "CALIBRATION_DRIFT": {
        "car_id": "car-3",
        "camera_count": 47,
        "apc_count": 58,
        "delta": 11,
        "threshold": 10,
    },
    "COACH_COMFORT_INDEX": {
        "car_id": "car-2",
        "comfort_score": 0.72,
        "occupancy_pct": 0.65,
    },
    # STREAM_PRIORITY: internal signal only — never written to event-store or published
    # via MQTT per ADR-18, but the model exists and roundtrip must not raise.
    "STREAM_PRIORITY": {
        "camera_ids": ["cam-2-door-L1"],
        "priority": "P1",
        "duration_s": 120.0,
        "reason": "door_release",
    },
}

# Fail fast with a clear message if a new EventType is added without a fixture entry.
# Without this guard, test_every_event_type_roundtrips would raise a confusing KeyError.
_MISSING_FIXTURES = {e.value for e in EventType} - set(_MINIMAL_PAYLOADS)
assert not _MISSING_FIXTURES, (
    f"_MINIMAL_PAYLOADS is missing entries for: {_MISSING_FIXTURES}. "
    "Add a minimal valid payload dict for each new EventType."
)

_VALID_BASE = {
    "journey_id": "R5001C-031_RJ-0847_20260516",
    "vehicle_id": "R5001C-031",
    "severity": "info",
    "source": "inference",
}


def _make_envelope(event_type: str, payload: dict | None = None) -> EventEnvelope:
    return EventEnvelope(
        **_VALID_BASE,
        event_type=event_type,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# AC1.3 — PAYLOAD_MODELS registry completeness
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_payload_models_covers_every_event_type() -> None:
    """Every EventType member must have an entry in PAYLOAD_MODELS."""
    missing = set(EventType) - set(PAYLOAD_MODELS.keys())
    assert not missing, f"EventTypes without a payload model: {missing}"
    assert len(PAYLOAD_MODELS) == len(EventType)


# ---------------------------------------------------------------------------
# AC1.4 — Every EventType roundtrips through EventEnvelope without error
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize("event_type_value", [e.value for e in EventType])
def test_every_event_type_roundtrips(event_type_value: str) -> None:
    """Constructing EventEnvelope with a valid payload for each EventType must not raise."""
    payload = _MINIMAL_PAYLOADS[event_type_value]
    env = _make_envelope(event_type_value, payload)
    assert env.event_type == event_type_value


# ---------------------------------------------------------------------------
# AC1.5 — Deliberate envelope violations raise ValidationError
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_missing_journey_id_raises() -> None:
    with pytest.raises(ValidationError, match="journey_id"):
        EventEnvelope(
            vehicle_id="R5001C-031",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
        )


@pytest.mark.contract
def test_missing_vehicle_id_raises() -> None:
    with pytest.raises(ValidationError, match="vehicle_id"):
        EventEnvelope(
            journey_id="R5001C-031_RJ-0847_20260516",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
            source="inference",
        )


@pytest.mark.contract
def test_invalid_event_type_raises() -> None:
    with pytest.raises(ValidationError):
        _make_envelope("DOES_NOT_EXIST")


@pytest.mark.contract
@pytest.mark.parametrize("door_state", ["open", "closing", "closed", "unknown"])
def test_door_obstruction_door_state_literal_accepts_all_values(door_state: str) -> None:
    """Contract guard for the DoorObstructionPayload.door_state Literal.

    Story 4-5 (2026-05-20) extended the Literal from ["open","closing","closed"] to
    include "unknown" because inference posts candidates to fusion before ZFR has
    cross-referenced the door state. Pin all 4 valid values so a future contraction
    breaks CI loudly (cloud-backend and event-store both deserialise this payload).
    """
    from oebb_shared.events.payloads import DoorObstructionPayload

    p = DoorObstructionPayload(
        car_id="car-1",
        door_id="car-1-door-L-2",
        obstruction_type="person",
        track_id="person-0117",
        camera_id="cam-1-door-L2",
        door_state=door_state,  # type: ignore[arg-type]
    )
    assert p.model_dump()["door_state"] == door_state


@pytest.mark.contract
def test_door_obstruction_door_state_rejects_unknown_literal() -> None:
    """door_state outside the Literal set must ValidationError, not silently coerce."""
    from oebb_shared.events.payloads import DoorObstructionPayload

    with pytest.raises(ValidationError, match="door_state"):
        DoorObstructionPayload(
            car_id="car-1",
            door_id="car-1-door-L-2",
            obstruction_type="person",
            track_id="person-0117",
            camera_id="cam-1-door-L2",
            door_state="ajar",  # type: ignore[arg-type]
        )


@pytest.mark.contract
def test_missing_severity_raises() -> None:
    with pytest.raises(ValidationError, match="severity"):
        EventEnvelope(
            journey_id="R5001C-031_RJ-0847_20260516",
            vehicle_id="R5001C-031",
            event_type="OCCUPANCY_UPDATE",
            source="inference",
        )


@pytest.mark.contract
def test_missing_source_raises() -> None:
    with pytest.raises(ValidationError, match="source"):
        EventEnvelope(
            journey_id="R5001C-031_RJ-0847_20260516",
            vehicle_id="R5001C-031",
            event_type="OCCUPANCY_UPDATE",
            severity="info",
        )


@pytest.mark.contract
def test_invalid_payload_shape_raises() -> None:
    """OCCUPANCY_UPDATE payload missing required fields must raise."""
    with pytest.raises(ValidationError):
        _make_envelope("OCCUPANCY_UPDATE", {"car_id": "car-1"})  # missing many fields


@pytest.mark.contract
def test_extra_envelope_field_raises() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(
            **_VALID_BASE,
            event_type="OCCUPANCY_UPDATE",
            payload={},
            unexpected_field="oops",
        )


# ---------------------------------------------------------------------------
# AC1.1 / AC1.2 — Container files use canonical oebb_shared.events import
# ---------------------------------------------------------------------------


# Word-boundary pattern: matches the sentinel as a standalone identifier, not as a
# substring of a longer name (e.g. avoids "MyEventType", "EventTypeRegistry").
_SENTINEL_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in sorted(_SENTINEL_NAMES)) + r")\b"
)


def _find_event_construction_files() -> list[Path]:
    """Return Python files in any container that reference OEBB event sentinels."""
    found: list[Path] = []
    for container in _CONTAINER_DIRS:
        container_path = _REPO_ROOT / container
        if not container_path.exists():
            continue
        for py_file in container_path.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if _SENTINEL_RE.search(source):
                found.append(py_file)
    return found


# Matches `from <non-oebb_shared> import EventEnvelope|EventModel|EventType`
# or `from . import EventEnvelope|EventModel|EventType` (relative shadow).
# Deliberately does NOT match `from oebb_shared* import ...`.
_LOCAL_SHADOW_RE = re.compile(
    r"^from\s+(?!oebb_shared\b)(?:\.|[\w.]+)\s+import\s+[^\n]*"
    r"\b(?:EventEnvelope|EventModel|EventType)\b",
    re.MULTILINE,
)


@pytest.mark.contract
def test_container_files_discovered() -> None:
    """At least one container file must reference event sentinels."""
    files = _find_event_construction_files()
    assert files, (
        f"No container files referencing {_SENTINEL_NAMES} found under "
        f"{[str(_REPO_ROOT / d) for d in _CONTAINER_DIRS]}"
    )


@pytest.mark.contract
def test_container_event_imports_are_canonical() -> None:
    """Any container file importing EventEnvelope/EventModel/EventType must use
    the oebb_shared package, not a local shadow module."""
    files = _find_event_construction_files()
    violations: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        if _LOCAL_SHADOW_RE.search(source):
            violations.append(str(path.relative_to(_REPO_ROOT)))
    assert not violations, (
        "Container files import event types from a non-canonical path "
        f"(expected oebb_shared.events.*): {violations}"
    )


# ---------------------------------------------------------------------------
# AC3 / AC4 — ISO-8601 UTC validator on journey payload timestamp fields
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_journey_started_valid_timestamps_pass() -> None:
    p = JourneyStartedPayload(
        trip_number="RJ-0847",
        origin_station_id="Wien Hbf",
        scheduled_departure="2026-05-16T06:00:00Z",
        actual_departure="2026-05-16T06:02:14.123Z",
        consist=["car-1"],
        service_class="railjet",
    )
    assert p.scheduled_departure == "2026-05-16T06:00:00Z"
    assert p.actual_departure == "2026-05-16T06:02:14.123Z"


@pytest.mark.contract
def test_journey_ended_valid_timestamps_pass() -> None:
    p = JourneyEndedPayload(
        trip_number="RJ-0847",
        destination_station_id="Salzburg Hbf",
        scheduled_arrival="2026-05-16T08:50:00Z",
        actual_arrival="2026-05-16T08:53:41Z",
        total_duration_s=10287.0,
        peak_occupancy_pct=0.91,
    )
    assert p.scheduled_arrival == "2026-05-16T08:50:00Z"


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_ts",
    [
        "2026-05-17T10:00:00",          # naive — no Z
        "2026-05-17T12:00:00+02:00",    # non-UTC offset
        "2026-05-17 10:00:00Z",         # space separator instead of T
        "2026/05/17T10:00:00Z",         # wrong date separator
        "not-a-timestamp",
        "",
    ],
)
def test_journey_started_naive_or_non_utc_scheduled_departure_raises(bad_ts: str) -> None:
    with pytest.raises(ValidationError):
        JourneyStartedPayload(
            trip_number="RJ-0847",
            origin_station_id="Wien Hbf",
            scheduled_departure=bad_ts,
            actual_departure="2026-05-16T06:02:14Z",
            consist=["car-1"],
            service_class="railjet",
        )


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_ts",
    [
        "2026-05-16T06:02:14",          # naive
        "2026-05-16T06:02:14+01:00",    # non-UTC offset
        "2026-05-16 06:02:14Z",         # space separator
    ],
)
def test_journey_started_naive_or_non_utc_actual_departure_raises(bad_ts: str) -> None:
    with pytest.raises(ValidationError):
        JourneyStartedPayload(
            trip_number="RJ-0847",
            origin_station_id="Wien Hbf",
            scheduled_departure="2026-05-16T06:00:00Z",
            actual_departure=bad_ts,
            consist=["car-1"],
            service_class="railjet",
        )


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_ts",
    [
        "2026-05-16T08:50:00",          # naive
        "2026-05-16T08:50:00+02:00",    # non-UTC offset
        "2026-05-16 08:50:00Z",         # space separator
        "",                              # empty string
    ],
)
def test_journey_ended_naive_or_non_utc_scheduled_arrival_raises(bad_ts: str) -> None:
    with pytest.raises(ValidationError):
        JourneyEndedPayload(
            trip_number="RJ-0847",
            destination_station_id="Salzburg Hbf",
            scheduled_arrival=bad_ts,
            actual_arrival="2026-05-16T08:53:41Z",
            total_duration_s=10287.0,
            peak_occupancy_pct=0.91,
        )


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_ts",
    [
        "2026-05-16T08:53:41",          # naive
        "2026-05-16T08:53:41+01:00",    # non-UTC offset
        "2026-05-16 08:53:41Z",         # space separator
        "",                              # empty string
    ],
)
def test_journey_ended_naive_or_non_utc_actual_arrival_raises(bad_ts: str) -> None:
    with pytest.raises(ValidationError):
        JourneyEndedPayload(
            trip_number="RJ-0847",
            destination_station_id="Salzburg Hbf",
            scheduled_arrival="2026-05-16T08:50:00Z",
            actual_arrival=bad_ts,
            total_duration_s=10287.0,
            peak_occupancy_pct=0.91,
        )


# ---------------------------------------------------------------------------
# P8 — Pin the deliberate NFR9 Z-suffix-only contract: +00:00 is semantically UTC
# but is explicitly rejected. This test documents and locks that design decision.
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        (
            "scheduled_departure",
            {
                "trip_number": "RJ-0847",
                "origin_station_id": "Wien Hbf",
                "scheduled_departure": "2026-05-16T06:00:00+00:00",
                "actual_departure": "2026-05-16T06:02:14Z",
                "consist": ["car-1"],
                "service_class": "railjet",
            },
        ),
        (
            "actual_departure",
            {
                "trip_number": "RJ-0847",
                "origin_station_id": "Wien Hbf",
                "scheduled_departure": "2026-05-16T06:00:00Z",
                "actual_departure": "2026-05-16T06:02:14+00:00",
                "consist": ["car-1"],
                "service_class": "railjet",
            },
        ),
        (
            "scheduled_arrival",
            {
                "trip_number": "RJ-0847",
                "destination_station_id": "Salzburg Hbf",
                "scheduled_arrival": "2026-05-16T08:50:00+00:00",
                "actual_arrival": "2026-05-16T08:53:41Z",
                "total_duration_s": 10287.0,
                "peak_occupancy_pct": 0.91,
            },
        ),
        (
            "actual_arrival",
            {
                "trip_number": "RJ-0847",
                "destination_station_id": "Salzburg Hbf",
                "scheduled_arrival": "2026-05-16T08:50:00Z",
                "actual_arrival": "2026-05-16T08:53:41+00:00",
                "total_duration_s": 10287.0,
                "peak_occupancy_pct": 0.91,
            },
        ),
    ],
)
def test_plus_zero_offset_rejected(field_name: str, kwargs: dict) -> None:
    """NFR9 requires Z suffix only; +00:00 (semantically UTC) is deliberately rejected."""
    departure_fields = ("scheduled_departure", "actual_departure")
    cls = JourneyStartedPayload if field_name in departure_fields else JourneyEndedPayload
    with pytest.raises(ValidationError):
        cls(**kwargs)  # type: ignore[arg-type]


