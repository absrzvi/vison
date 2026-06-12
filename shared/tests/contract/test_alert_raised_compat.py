"""Contract tests for story 10-1 AC1/AC2/AC4/AC14.

AC1: AlertRaisedPayload gains confidence_score / confidence_basis / model_versions
     with a model_validator enforcing the per-basis invariants.
AC2: Five detection payloads gain required model_versions.
AC14: ALERT_CLASS_DISABLED / ALERT_CLASS_REENABLED event types + shared payload shape.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from oebb_shared.events import PAYLOAD_MODELS, EventEnvelope, EventType
from oebb_shared.events.payloads import (
    AccessibilityDetectedPayload,
    AlertClassStatePayload,
    AlertRaisedPayload,
    DoorObstructionPayload,
    LuggageRackSaturationPayload,
    OccupancyUpdatePayload,
    UnattendedBagPayload,
)

_ALERT_BASE: dict[str, Any] = {
    "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
    "alert_code": "OVERCROWDING",
    "car_id": "car-2",
    "zone": None,
    "description": "Occupancy exceeded 90%.",
}

_MODEL_VERSIONS = {
    "detector_arch": "yolox_s_leaky",
    "detector_hef": "yolox_s_leaky.hef@ab12cd34ef56",
}

_VALID_COMBOS: list[tuple[str, float | None, dict[str, str]]] = [
    ("model", 0.91, {"detector_arch": "yolox_s_leaky"}),
    ("sensor", None, {}),
    ("fused", 0.66, {**_MODEL_VERSIONS, "door_sensor_firmware": "fw-2.4.1"}),
]

_INVALID_COMBOS: list[tuple[str, float | None, dict[str, str]]] = [
    ("model", None, {"detector_arch": "yolox"}),  # model requires a score
    ("model", 0.9, {}),                            # model requires non-empty versions
    ("model", 1.5, {"detector_arch": "yolox"}),    # score out of [0,1]
    ("sensor", 0.5, {}),                           # sensor forbids a score
    ("sensor", None, {"detector_arch": "yolox"}),  # sensor forbids versions
    ("fused", 0.7, {"only_one": "v1"}),            # fused requires >= 2 versions
    ("fused", None, _MODEL_VERSIONS),              # fused requires a score
    ("fused", -0.1, _MODEL_VERSIONS),              # score out of [0,1]
]


def _alert(basis: str, score: float | None, versions: dict[str, str]) -> AlertRaisedPayload:
    return AlertRaisedPayload(
        **_ALERT_BASE,
        confidence_basis=basis,  # type: ignore[arg-type]
        confidence_score=score,
        model_versions=versions,
    )


# ---------------------------------------------------------------------------
# AC1 — valid combos round-trip
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize("basis,score,versions", _VALID_COMBOS)
def test_valid_combo_roundtrips(
    basis: str, score: float | None, versions: dict[str, str]
) -> None:
    p = _alert(basis, score, versions)
    dumped = p.model_dump()
    restored = AlertRaisedPayload.model_validate(dumped)
    assert restored.confidence_basis == basis
    assert restored.confidence_score == score
    assert restored.model_versions == versions


@pytest.mark.contract
@pytest.mark.parametrize("basis,score,versions", _VALID_COMBOS)
def test_valid_combo_roundtrips_via_envelope(
    basis: str, score: float | None, versions: dict[str, str]
) -> None:
    payload = {
        **_ALERT_BASE,
        "confidence_basis": basis,
        "confidence_score": score,
        "model_versions": versions,
    }
    env = EventEnvelope(
        journey_id="R5001C-031_RJ-0847_20260516",
        vehicle_id="R5001C-031",
        event_type="ALERT_RAISED",
        severity="warning",
        source="fusion",
        payload=payload,
    )
    assert env.payload["confidence_basis"] == basis


# ---------------------------------------------------------------------------
# AC1 — invalid combos raise ValidationError (no silent coercion)
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize("basis,score,versions", _INVALID_COMBOS)
def test_invalid_combo_raises(
    basis: str, score: float | None, versions: dict[str, str]
) -> None:
    with pytest.raises(ValidationError):
        _alert(basis, score, versions)


@pytest.mark.contract
def test_confidence_basis_is_required() -> None:
    with pytest.raises(ValidationError, match="confidence_basis"):
        AlertRaisedPayload(
            **_ALERT_BASE,
            confidence_score=0.9,
            model_versions=_MODEL_VERSIONS,
        )


@pytest.mark.contract
def test_unknown_basis_raises() -> None:
    with pytest.raises(ValidationError):
        _alert("vibes", 0.9, _MODEL_VERSIONS)


# ---------------------------------------------------------------------------
# AC2 — detection payloads require model_versions
# ---------------------------------------------------------------------------

_DETECTION_FIXTURES: list[tuple[type, dict[str, Any]]] = [
    (
        DoorObstructionPayload,
        {
            "car_id": "car-1",
            "door_id": "car-1-door-L-2",
            "obstruction_type": "person",
            "track_id": "person-0117",
            "camera_id": "cam-1-door-L2",
            "door_state": "closing",
        },
    ),
    (
        UnattendedBagPayload,
        {
            "car_id": "car-3",
            "zone": None,
            "track_id": "bag-0042",
            "dwell_s": 180.0,
            "bbox": {"x": 412, "y": 308, "w": 64, "h": 48},
            "camera_id": "cam-3-02",
        },
    ),
    (
        AccessibilityDetectedPayload,
        {
            "car_id": "car-2",
            "zone": None,
            "track_id": "person-0204",
            "assistance_type": ["wheelchair"],
            "camera_id": "cam-2-vest-b",
            "near_door_id": "car-2-door-R-1",
        },
    ),
    (
        OccupancyUpdatePayload,
        {
            "car_id": "car-1",
            "zone": None,
            "occupancy_count": 100,
            "occupancy_pct": 0.5,
            "capacity": 200,
            "service_tier": "standard",
        },
    ),
    (
        LuggageRackSaturationPayload,
        {
            "car_id": "car-2",
            "rack_id": "car-2-rack-upper-left",
            "fill_pct": 0.95,
            "item_count": 7,
        },
    ),
]


@pytest.mark.contract
@pytest.mark.parametrize(
    "cls,fixture", _DETECTION_FIXTURES, ids=[c.__name__ for c, _ in _DETECTION_FIXTURES]
)
def test_detection_payload_requires_model_versions(cls: type, fixture: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="model_versions"):
        cls(**fixture)


@pytest.mark.contract
@pytest.mark.parametrize(
    "cls,fixture", _DETECTION_FIXTURES, ids=[c.__name__ for c, _ in _DETECTION_FIXTURES]
)
def test_detection_payload_with_model_versions_roundtrips(
    cls: type, fixture: dict[str, Any]
) -> None:
    p = cls(**fixture, model_versions=_MODEL_VERSIONS)
    restored = cls.model_validate(p.model_dump())
    assert restored.model_versions == _MODEL_VERSIONS


# ---------------------------------------------------------------------------
# AC14 — admin kill-switch event types
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.parametrize(
    "member", ["ALERT_CLASS_DISABLED", "ALERT_CLASS_REENABLED", "INFERENCE_HEARTBEAT"]
)
def test_new_event_types_exist_and_dispatch(member: str) -> None:
    et = EventType(member)
    assert et in PAYLOAD_MODELS


@pytest.mark.contract
@pytest.mark.parametrize("event_type", ["ALERT_CLASS_DISABLED", "ALERT_CLASS_REENABLED"])
def test_alert_class_state_payload_roundtrips(event_type: str) -> None:
    payload = {
        "alert_code": "UNATTENDED_BAG",
        "actor_name": "nomad-oncall",
        "source_ip": "10.0.0.7",
    }
    AlertClassStatePayload.model_validate(payload)
    env = EventEnvelope(
        journey_id="LANDSIDE_admin_20260612",
        vehicle_id="LANDSIDE",
        event_type=event_type,
        severity="info",
        source="cloud-backend",
        payload=payload,
    )
    assert env.event_type == event_type


@pytest.mark.contract
def test_alert_class_state_payload_rejects_empty_actor() -> None:
    with pytest.raises(ValidationError):
        AlertClassStatePayload(alert_code="X", actor_name="", source_ip="10.0.0.7")
