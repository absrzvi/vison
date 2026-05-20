"""Security tests — AST audits for Rule 8 (no os.environ.get) + payload schema checks."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src" / "fusion"

MODULES = (
    "config.py",
    "models.py",
    "context_state.py",
    "suppression.py",
    "door_obstruction.py",
    "occupancy.py",
    "accessibility.py",
    "enrichment.py",
    "health.py",
    "main.py",
)


def _has_env_get(path: Path) -> bool:
    """Return True if the file contains os.environ.get() calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
        ):
            return True
    return False


@pytest.mark.unit
@pytest.mark.parametrize("module", MODULES)
def test_no_env_get_in_module(module: str) -> None:
    assert not _has_env_get(SRC / module), f"{module} must not call os.environ.get (Rule 8)"


@pytest.mark.unit
def test_alert_raised_payload_schema_valid() -> None:
    from oebb_shared.events import AlertRaisedPayload

    p = AlertRaisedPayload(
        alert_id="11111111-1111-4111-8111-111111111111",
        alert_code="door_obstruction",
        car_id="car-1",
        zone=None,
        description="Door obstruction detected",
        priority="normal",
    )
    dumped = p.model_dump()
    for f in ("alert_id", "alert_code", "car_id", "description"):
        assert f in dumped


@pytest.mark.unit
def test_ramp_deployed_payload_schema_valid() -> None:
    from oebb_shared.events import RampDeployedPayload

    p = RampDeployedPayload(
        car_id="car-1",
        door_id="door-1A",
        triggered_by_track_id="42",
        deployed_by="auto",
        station_id="VIE-HBF",
    )
    dumped = p.model_dump()
    for f in ("car_id", "door_id", "triggered_by_track_id", "deployed_by", "station_id"):
        assert f in dumped


@pytest.mark.unit
def test_envelope_source_field_includes_fusion() -> None:
    """EventEnvelope must accept source='fusion'."""
    from oebb_shared.events import EventEnvelope, EventType

    env = EventEnvelope(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        event_type=EventType.ALERT_RAISED,
        severity="warning",
        source="fusion",
        schema_version=1,
        payload={
            "alert_id": "11111111-1111-4111-8111-111111111111",
            "alert_code": "door_obstruction",
            "car_id": "car-1",
            "description": "Door obstruction detected",
        },
    )
    assert env.source == "fusion"


@pytest.mark.unit
def test_context_push_maintenance_mode_malformed_returns_422() -> None:
    """StrictBool must reject string 'yes' for maintenance_mode."""
    from pydantic import ValidationError

    from fusion.models import ContextPushModel

    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"maintenance_mode": "yes"})


@pytest.mark.unit
def test_context_push_extra_field_returns_422() -> None:
    from pydantic import ValidationError

    from fusion.models import ContextPushModel

    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"unknown_field": True})


@pytest.mark.unit
def test_slip_fall_candidate_alert_type_literal() -> None:
    from pydantic import ValidationError

    from fusion.models import SlipFallCandidate

    # Wrong literal value rejected.
    with pytest.raises(ValidationError):
        SlipFallCandidate.model_validate(
            {
                "alert_type": "unknown",
                "car_id": "car-1",
                "track_id": "42",
                "camera_id": "C1_DOOR_01",
            }
        )
    # Correct shape accepted.
    SlipFallCandidate.model_validate(
        {
            "alert_type": "slip_fall",
            "car_id": "car-1",
            "track_id": "42",
            "camera_id": "C1_DOOR_01",
        }
    )
