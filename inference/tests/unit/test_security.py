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
