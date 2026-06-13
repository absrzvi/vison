"""Contract tests for edge-egress anonymisation (oebb_shared.events.anonymise).

Two contracts are pinned here because both cross the cloud-backend ↔ event-store
deserialisation boundary:

  1. anonymise_envelope behaviour — what crosses the train→cloud boundary must
     genuinely match the "anonymised at the edge" claim: no per-person track_id,
     no pixel bbox, no camera locality, no Article 9 ACCESSIBILITY_DETECTED.

  2. The bbox/camera_id field-type change (required → Optional on
     UnattendedBagPayload / DoorObstructionPayload). shared/CLAUDE.md requires a
     contract test for ANY schema field rename/removal/type change because both
     cloud-backend and event-store deserialise these. The redaction is only
     valid if a redacted payload (fields absent) still passes EventEnvelope
     re-validation on cloud-backend ingest — that is asserted directly.
"""
from __future__ import annotations

import pytest

from oebb_shared.events import EventEnvelope, anonymise_envelope
from oebb_shared.events.anonymise import (
    _DROP_EVENT_TYPES,
    _KNOWN_EVENT_TYPES,
    _PASS_THROUGH_EVENT_TYPES,
    _REDACT_IN_PLACE_EVENT_TYPES,
)
from oebb_shared.events.payloads import DoorObstructionPayload, UnattendedBagPayload
from oebb_shared.events.types import EventType

_KEY = b"contract-test-key"
_ALT_KEY = b"a-different-key"

_BASE = {
    "event_id": "11111111-1111-4111-8111-111111111111",
    "journey_id": "R5001C-031_RJ-0847_20260516",
    "vehicle_id": "R5001C-031",
    "timestamp": "2026-06-12T14:32:00Z",
    "severity": "warning",
    "source": "inference",
    "schema_version": 1,
}


def _env(event_type: str, payload: dict) -> dict:
    return {**_BASE, "event_type": event_type, "payload": payload}


_BAG_PAYLOAD = {
    "car_id": "car-3",
    "zone": None,
    "track_id": "bag-0042",
    "dwell_s": 180.0,
    "bbox": {"x": 412, "y": 308, "w": 64, "h": 48},
    "camera_id": "cam-3-02",
    "model_versions": {"detector_arch": "yolox_s_leaky"},
}

_DOOR_PAYLOAD = {
    "car_id": "car-1",
    "door_id": "car-1-door-L-2",
    "obstruction_type": "person",
    "track_id": "person-0117",
    "camera_id": "cam-1-door-L2",
    "door_state": "closing",
    "model_versions": {"detector_arch": "yolox_s_leaky"},
}

_ACCESSIBILITY_PAYLOAD = {
    "car_id": "car-2",
    "zone": None,
    "track_id": "person-0204",
    "assistance_type": ["wheelchair"],
    "camera_id": "cam-2-vest-b",
    "near_door_id": "car-2-door-R-1",
    "model_versions": {"detector_arch": "yolox_s_leaky"},
}

# WAGON traversal payloads carry an INT track_id from the producer; egress
# tokenises it to a str. Both shapes must survive EventEnvelope re-validation.
_WAGON_EXIT_PAYLOAD = {
    "track_id": 312,
    "coach_from": "car-3",
    "coach_to": "car-4",
    "camera_id": "cam-3-gangway-fwd",
    "traversal": "from_to",
    "confidence": 0.88,
    "expect_orphan": False,
}

_WAGON_ENTRY_PAYLOAD = {
    "track_id": 312,
    "coach_from": "car-3",
    "coach_to": "car-4",
    "camera_id": "cam-4-gangway-aft",
    "traversal": "from_to",
    "confidence": 0.91,
}


# ---------------------------------------------------------------------------
# Fail-closed drift guard (Round-2 P3): every EventType must have an explicit
# egress policy, so a new PII-bearing type cannot leak by default.
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_every_event_type_has_an_egress_policy() -> None:
    """Adding an EventType without classifying it (drop / pass-through /
    redact-in-place) must fail here, forcing a conscious egress decision.

    STREAM_PRIORITY is the only exemption — it is an internal command never
    written to event-store, so it never reaches the egress boundary."""
    classified = _KNOWN_EVENT_TYPES
    expected = {e.value for e in EventType} - {"STREAM_PRIORITY"}
    missing = expected - classified
    assert not missing, (
        f"EventType(s) with no egress anonymisation policy: {sorted(missing)}. "
        "Add each to a bucket in anonymise.py (drop / pass-through / drop-fields "
        "/ tokenise) after deciding what is cloud-safe."
    )


@pytest.mark.contract
def test_egress_policy_buckets_are_disjoint() -> None:
    """A type must live in exactly one bucket — overlapping policy is ambiguous."""
    assert _DROP_EVENT_TYPES.isdisjoint(_PASS_THROUGH_EVENT_TYPES)
    assert _DROP_EVENT_TYPES.isdisjoint(_REDACT_IN_PLACE_EVENT_TYPES)
    assert _PASS_THROUGH_EVENT_TYPES.isdisjoint(_REDACT_IN_PLACE_EVENT_TYPES)


@pytest.mark.contract
def test_unknown_event_type_is_withheld() -> None:
    """An event type with no policy fails closed (withheld), never passed raw."""
    env = _env("SOME_FUTURE_PII_EVENT", {"face_descriptor": [0.1, 0.2]})
    assert anonymise_envelope(env, secret=_KEY) is None


# ---------------------------------------------------------------------------
# Article 9 — special-category event must NOT cross the boundary
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_accessibility_detected_is_withheld() -> None:
    """ACCESSIBILITY_DETECTED (assistance_type bound to a track_id) is dropped
    entirely from the cloud egress."""
    env = _env("ACCESSIBILITY_DETECTED", _ACCESSIBILITY_PAYLOAD)
    assert anonymise_envelope(env, secret=_KEY) is None


# ---------------------------------------------------------------------------
# track_id → opaque keyed token
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize(
    "event_type,payload",
    [
        ("UNATTENDED_BAG", _BAG_PAYLOAD),
        ("DOOR_OBSTRUCTION", _DOOR_PAYLOAD),
        ("WAGON_EXIT", _WAGON_EXIT_PAYLOAD),
        ("WAGON_ENTRY", _WAGON_ENTRY_PAYLOAD),
    ],
)
def test_track_id_is_tokenised(event_type: str, payload: dict) -> None:
    """track_id (str or int) becomes an opaque tk_ token — never the raw value."""
    out = anonymise_envelope(_env(event_type, payload), secret=_KEY)
    assert out is not None
    token = out["payload"]["track_id"]
    assert isinstance(token, str) and token.startswith("tk_")
    assert token != str(payload["track_id"])


@pytest.mark.contract
def test_token_is_deterministic_per_key_and_journey() -> None:
    """Same (key, journey_id, track_id) → same token, so concurrent alerts about
    one track stay correlatable to the operator."""
    a = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_KEY)
    b = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_KEY)
    assert a is not None and b is not None
    assert a["payload"]["track_id"] == b["payload"]["track_id"]


@pytest.mark.contract
def test_token_is_salted_by_journey() -> None:
    """The same edge track_id in two journeys yields different tokens — no
    cross-journey re-identification."""
    j1 = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_KEY)
    other = {**_env("UNATTENDED_BAG", _BAG_PAYLOAD), "journey_id": "R5001C-031_RJ-0848_20260516"}
    j2 = anonymise_envelope(other, secret=_KEY)
    assert j1 is not None and j2 is not None
    assert j1["payload"]["track_id"] != j2["payload"]["track_id"]


@pytest.mark.contract
def test_token_depends_on_secret() -> None:
    """A different secret yields a different token — the map is keyed, not a
    plain hash anyone can recompute."""
    a = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_KEY)
    b = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_ALT_KEY)
    assert a is not None and b is not None
    assert a["payload"]["track_id"] != b["payload"]["track_id"]


# ---------------------------------------------------------------------------
# bbox / camera_id dropped; triggered_by_track_id blanked
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_bag_drops_bbox_and_camera_id() -> None:
    out = anonymise_envelope(_env("UNATTENDED_BAG", _BAG_PAYLOAD), secret=_KEY)
    assert out is not None
    assert "bbox" not in out["payload"]
    assert "camera_id" not in out["payload"]
    # Operational fields survive — the alert is still actionable.
    assert out["payload"]["car_id"] == "car-3"
    assert out["payload"]["dwell_s"] == 180.0


@pytest.mark.contract
def test_door_drops_camera_id() -> None:
    out = anonymise_envelope(_env("DOOR_OBSTRUCTION", _DOOR_PAYLOAD), secret=_KEY)
    assert out is not None
    assert "camera_id" not in out["payload"]


@pytest.mark.contract
def test_ramp_deployed_track_reference_blanked() -> None:
    payload = {
        "car_id": "car-2",
        "door_id": "car-2-door-R-1",
        "triggered_by_track_id": "person-0204",
        "deployed_by": "auto",
        "station_id": "Wien Hauptbahnhof",
    }
    out = anonymise_envelope(_env("RAMP_DEPLOYED", payload), secret=_KEY)
    assert out is not None
    assert out["payload"]["triggered_by_track_id"] == "redacted"


# ---------------------------------------------------------------------------
# No-op for non-PII events; input never mutated
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_occupancy_update_is_unchanged() -> None:
    payload = {
        "car_id": "car-1",
        "zone": None,
        "occupancy_count": 100,
        "occupancy_pct": 0.5,
        "capacity": 200,
        "service_tier": "standard",
        "model_versions": {"detector_arch": "yolox_s_leaky"},
    }
    out = anonymise_envelope(_env("OCCUPANCY_UPDATE", payload), secret=_KEY)
    assert out is not None
    assert out["payload"] == payload


@pytest.mark.contract
def test_input_envelope_not_mutated() -> None:
    env = _env("UNATTENDED_BAG", dict(_BAG_PAYLOAD))
    anonymise_envelope(env, secret=_KEY)
    assert env["payload"]["track_id"] == "bag-0042"
    assert "bbox" in env["payload"]
    assert "camera_id" in env["payload"]


# ---------------------------------------------------------------------------
# Schema field-type change: required → Optional. The redacted shape must still
# deserialise on the cloud-backend / event-store boundary (EventEnvelope).
# shared/CLAUDE.md mandates a contract test for this kind of change.
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_bag_bbox_and_camera_id_are_optional() -> None:
    """A redacted UNATTENDED_BAG (bbox + camera_id absent) must validate, or
    cloud-backend ingest would 422 every redacted event and sync would stall."""
    p = UnattendedBagPayload(
        car_id="car-3",
        track_id="tk_deadbeef",
        dwell_s=180.0,
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    dumped = p.model_dump()
    assert "bbox" not in dumped  # _drop_none keeps the absent shape honest
    assert "camera_id" not in dumped


@pytest.mark.contract
def test_door_camera_id_is_optional() -> None:
    p = DoorObstructionPayload(
        car_id="car-1",
        door_id="car-1-door-L-2",
        obstruction_type="person",
        track_id="tk_deadbeef",
        door_state="closing",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    assert "camera_id" not in p.model_dump()


@pytest.mark.contract
def test_full_fidelity_bag_still_serialises_bbox_and_camera_id() -> None:
    """On-train producers always populate bbox + camera_id; the Optional change
    must NOT drop them when present (only the None/redacted case omits them)."""
    p = UnattendedBagPayload(
        car_id="car-3",
        track_id="bag-0042",
        dwell_s=180.0,
        bbox={"x": 1, "y": 2, "w": 3, "h": 4},  # type: ignore[arg-type]
        camera_id="cam-3-02",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )
    dumped = p.model_dump()
    assert dumped["bbox"] == {"x": 1, "y": 2, "w": 3, "h": 4}
    assert dumped["camera_id"] == "cam-3-02"


@pytest.mark.contract
def test_redacted_payloads_pass_eventenvelope_revalidation() -> None:
    """End-to-end: the redacted bag + door envelopes must pass the SAME
    EventEnvelope validation cloud-backend applies on ingest."""
    for event_type, payload in (
        ("UNATTENDED_BAG", _BAG_PAYLOAD),
        ("DOOR_OBSTRUCTION", _DOOR_PAYLOAD),
        # WAGON events carry an int track_id that egress tokenises to a str —
        # the redacted str MUST still validate against the int|str field, or the
        # cloud-backend ingest batch 422s and cloud-sync stalls. (Round-2 P1.)
        ("WAGON_EXIT", _WAGON_EXIT_PAYLOAD),
        ("WAGON_ENTRY", _WAGON_ENTRY_PAYLOAD),
    ):
        red = anonymise_envelope(_env(event_type, payload), secret=_KEY)
        assert red is not None
        EventEnvelope(**red)  # raises if the redacted shape is invalid
