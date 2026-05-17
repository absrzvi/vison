"""Tests for shared/adapters/apc — APCAdapter Protocol + MockAPCAdapter."""
from __future__ import annotations

import asyncio

import pytest

from oebb_shared.adapters.apc import APCAdapter, DoorState, MockAPCAdapter, OccupancyReading


# ---------------------------------------------------------------------------
# Package-level import AC5
# ---------------------------------------------------------------------------

def test_package_exports_protocol() -> None:
    assert APCAdapter is not None


def test_package_exports_mock() -> None:
    assert MockAPCAdapter is not None


# ---------------------------------------------------------------------------
# OccupancyReading / DoorState dataclasses
# ---------------------------------------------------------------------------

def test_occupancy_reading_fields() -> None:
    r = OccupancyReading(car_id="car-1", count=10, timestamp="2026-05-17T10:00:00Z")
    assert r.car_id == "car-1"
    assert r.count == 10
    assert r.timestamp == "2026-05-17T10:00:00Z"


def test_door_state_fields() -> None:
    d = DoorState(car_id="car-2", is_open=True, timestamp="2026-05-17T10:00:00Z")
    assert d.car_id == "car-2"
    assert d.is_open is True


# ---------------------------------------------------------------------------
# MockAPCAdapter — occupancy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("car_id,expected_count", [
    ("car-1", 45),
    ("car-2", 182),
    ("car-3", 71),
    ("car-4", 120),
    ("car-5", 33),
])
def test_mock_get_occupancy_known_cars(car_id: str, expected_count: int) -> None:
    adapter = MockAPCAdapter()
    result = asyncio.run(adapter.get_occupancy(car_id))
    assert isinstance(result, OccupancyReading)
    assert result.car_id == car_id
    assert result.count == expected_count


def test_mock_get_occupancy_unknown_car_raises() -> None:
    adapter = MockAPCAdapter()
    with pytest.raises(KeyError, match="Unknown car_id"):
        asyncio.run(adapter.get_occupancy("car-99"))


# ---------------------------------------------------------------------------
# MockAPCAdapter — door state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("car_id", ["car-1", "car-2", "car-3", "car-4", "car-5"])
def test_mock_get_door_state(car_id: str) -> None:
    adapter = MockAPCAdapter()
    result = asyncio.run(adapter.get_door_state(car_id))
    assert isinstance(result, DoorState)
    assert result.car_id == car_id
    assert result.is_open is False


# ---------------------------------------------------------------------------
# Protocol structural subtyping — AC3
# ---------------------------------------------------------------------------

def test_mock_satisfies_protocol_type_hint() -> None:
    """MockAPCAdapter must be accepted where APCAdapter is type-hinted (runtime check)."""

    def use_adapter(a: APCAdapter) -> None:  # type: ignore[misc]
        pass

    use_adapter(MockAPCAdapter())  # must not raise


def test_runtime_protocol_check_passes() -> None:
    """The module-level _assert_protocol() call in mock.py already verified this at import time."""
    from oebb_shared.adapters.apc.mock import _assert_protocol  # type: ignore[attr-defined]

    _assert_protocol()  # should not raise


# ---------------------------------------------------------------------------
# AC4 — no hardware dependency
# ---------------------------------------------------------------------------

def test_no_hardware_needed() -> None:
    """MockAPCAdapter completes all calls without any network or VLAN access."""
    adapter = MockAPCAdapter()
    occ = asyncio.run(adapter.get_occupancy("car-1"))
    door = asyncio.run(adapter.get_door_state("car-1"))
    assert occ.count > 0
    assert door.car_id == "car-1"
