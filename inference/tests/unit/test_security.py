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
    """OCCUPANCY_UPDATE payload must include all required schema fields."""
    required_fields = {
        "car_id",
        "zone",
        "occupancy_count",
        "occupancy_pct",
        "capacity",
        "confidence",
        "service_tier",
    }
    # Import ZoneCounter and inspect what it builds — done by checking the build_payload helper
    # ZoneCounter.build_occupancy_payload must return a dict with all required keys
    from inference.models import OccupancyState  # noqa: PLC0415
    from inference.zone_counter import ZoneCounter  # noqa: PLC0415

    state = OccupancyState(car_id="car-1", occupancy_count=5, occupancy_pct=0.5, capacity=200)
    payload = ZoneCounter.build_occupancy_payload(state, confidence=1.0)
    assert required_fields.issubset(payload.keys()), (
        f"Missing fields: {required_fields - payload.keys()}"
    )
