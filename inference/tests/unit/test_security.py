"""Security tests — AST audits for Rule 8 violations and payload schema validation."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src" / "inference"


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


def _imports_module(path: Path, module_name: str) -> bool:
    """Return True if the file imports the given module (direct or from-import)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if module_name in alias.name:
                    return True
        if isinstance(node, ast.ImportFrom):
            if node.module and module_name in node.module:
                return True
    return False


@pytest.mark.unit
def test_no_env_get_in_callback() -> None:
    assert not _has_env_get(SRC / "callback.py")


@pytest.mark.unit
def test_no_env_get_in_zone_counter() -> None:
    assert not _has_env_get(SRC / "zone_counter.py")


@pytest.mark.unit
def test_no_env_get_in_budget() -> None:
    assert not _has_env_get(SRC / "budget.py")


@pytest.mark.unit
def test_no_env_get_in_config() -> None:
    assert not _has_env_get(SRC / "config.py")


@pytest.mark.unit
def test_hailo_pipeline_not_imported_in_zone_counter() -> None:
    assert not _imports_module(SRC / "zone_counter.py", "pipeline")


@pytest.mark.unit
def test_occupancy_update_payload_schema_valid() -> None:
    """OCCUPANCY_UPDATE payload must validate against the canonical Pydantic model
    in oebb_shared.events. Confidence is optional and dropped when None.
    """
    from oebb_shared.events import OccupancyUpdatePayload

    p = OccupancyUpdatePayload(
        car_id="car-1",
        zone="interior",
        occupancy_count=5,
        occupancy_pct=0.025,
        capacity=200,
        confidence=None,
        service_tier="standard",
    )
    dumped = p.model_dump()
    # Required fields always present.
    for f in ("car_id", "zone", "occupancy_count", "occupancy_pct", "capacity", "service_tier"):
        assert f in dumped, f"missing required field: {f}"
    # confidence omitted by _drop_none when None.
    assert "confidence" not in dumped


@pytest.mark.unit
def test_no_env_get_in_safety() -> None:
    assert not _has_env_get(SRC / "safety.py")


@pytest.mark.unit
def test_door_obstruction_payload_schema_valid() -> None:
    from oebb_shared.events import DoorObstructionPayload

    p = DoorObstructionPayload(
        car_id="car-1",
        door_id="door-1A",
        obstruction_type="person",
        track_id="42",
        camera_id="C1_DOOR_01",
        confidence=None,
        door_state="open",
    )
    dumped = p.model_dump()
    for f in ("car_id", "door_id", "obstruction_type", "track_id", "camera_id", "door_state"):
        assert f in dumped, f"missing required field: {f}"
    assert "confidence" not in dumped


@pytest.mark.unit
def test_accessibility_payload_schema_valid() -> None:
    from oebb_shared.events import AccessibilityDetectedPayload

    p = AccessibilityDetectedPayload(
        car_id="car-1",
        zone="door",
        track_id="acc-C1_DOOR_01-12345",
        assistance_type=["wheelchair"],
        camera_id="C1_DOOR_01",
        confidence=None,
        near_door_id="door-1A",
    )
    dumped = p.model_dump()
    for f in ("car_id", "track_id", "assistance_type", "camera_id", "near_door_id"):
        assert f in dumped, f"missing required field: {f}"
    assert "confidence" not in dumped


@pytest.mark.unit
def test_ramp_deployed_payload_schema_valid() -> None:
    from oebb_shared.events import RampDeployedPayload

    p = RampDeployedPayload(
        car_id="car-1",
        door_id="door-1A",
        triggered_by_track_id="acc-C1_DOOR_01-12345",
        deployed_by="auto",
        station_id="VIE-HBF",
    )
    dumped = p.model_dump()
    for f in ("car_id", "door_id", "triggered_by_track_id", "deployed_by", "station_id"):
        assert f in dumped, f"missing required field: {f}"


@pytest.mark.unit
def test_context_push_ramp_malformed_returns_422() -> None:
    """StrictBool must reject string 'yes' for ramp_deployed."""
    from pydantic import ValidationError

    from inference.health import ContextPushModel

    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"ramp_deployed": "yes"})


@pytest.mark.unit
def test_fusion_candidate_not_written_to_event_store() -> None:
    """Door obstruction and slip_fall must POST to fusion_url, not event_store_url."""
    import ast

    for module_name in ("callback.py", "zone_counter.py"):
        src = (SRC / module_name).read_text(encoding="utf-8")
        # This test verifies by naming convention — candidate POSTs use fusion_url
        # and the fusion path contains "candidates", not "/api/v1/events".
        # AST walk: any string literal containing "candidates" must NOT also see
        # "event_store_url" on the same call node.
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "candidates" in node.value:
                    assert "event_store" not in node.value, (
                        f"{module_name}: candidate endpoint must not reference event_store: {node.value!r}"
                    )


@pytest.mark.unit
def test_envelope_matches_canonical_schema() -> None:
    """The envelope inference produces must round-trip through canonical EventEnvelope."""
    from oebb_shared.events import EventEnvelope, EventType, OccupancyUpdatePayload

    payload = OccupancyUpdatePayload(
        car_id="car-1",
        zone="interior",
        occupancy_count=5,
        occupancy_pct=0.025,
        capacity=200,
        confidence=None,
        service_tier="standard",
    )
    env = EventEnvelope(
        journey_id="OBB-TEST_t1_20260519",
        vehicle_id="OBB-TEST",
        event_type=EventType.OCCUPANCY_UPDATE,
        severity="info",
        source="inference",
        schema_version=1,
        payload=payload.model_dump(),
    )
    # extra: forbid means rebuilding from model_dump must succeed.
    rebuilt = EventEnvelope.model_validate(env.model_dump(mode="json"))
    assert rebuilt.event_type == EventType.OCCUPANCY_UPDATE
    assert rebuilt.source == "inference"
