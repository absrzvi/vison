"""Tests for shared/adapters/apc — APCAdapter Protocol + MockAPCAdapter."""
from __future__ import annotations

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
    assert d.timestamp == "2026-05-17T10:00:00Z"


# ---------------------------------------------------------------------------
# MockAPCAdapter — occupancy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("car_id,expected_count", [
    ("car-1", 45),
    ("car-2", 182),
    ("car-3", 71),
    ("car-4", 120),
    ("car-5", 33),
])
async def test_mock_get_occupancy_known_cars(car_id: str, expected_count: int) -> None:
    adapter = MockAPCAdapter()
    result = await adapter.get_occupancy(car_id)
    assert isinstance(result, OccupancyReading)
    assert result.car_id == car_id
    assert result.count == expected_count


@pytest.mark.asyncio
async def test_mock_get_occupancy_unknown_car_raises() -> None:
    adapter = MockAPCAdapter()
    with pytest.raises(KeyError, match="Unknown car_id"):
        await adapter.get_occupancy("car-99")


# ---------------------------------------------------------------------------
# MockAPCAdapter — door state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("car_id", ["car-1", "car-2", "car-3", "car-4", "car-5"])
async def test_mock_get_door_state(car_id: str) -> None:
    adapter = MockAPCAdapter()
    result = await adapter.get_door_state(car_id)
    assert isinstance(result, DoorState)
    assert result.car_id == car_id
    assert result.is_open is False


@pytest.mark.asyncio
async def test_mock_get_door_state_unknown_car_raises() -> None:
    adapter = MockAPCAdapter()
    with pytest.raises(KeyError, match="Unknown car_id"):
        await adapter.get_door_state("car-99")


@pytest.mark.asyncio
async def test_mock_get_door_state_open_path() -> None:
    """DoorState.is_open=True is constructible — mock always returns False but the field exists."""
    d = DoorState(car_id="car-1", is_open=True, timestamp="2026-05-17T10:00:00Z")
    assert d.is_open is True


# ---------------------------------------------------------------------------
# Protocol structural subtyping — AC3
# ---------------------------------------------------------------------------

def test_mock_satisfies_protocol_isinstance() -> None:
    """@runtime_checkable allows isinstance checks against APCAdapter."""
    assert isinstance(MockAPCAdapter(), APCAdapter)


def test_mock_satisfies_protocol_type_hint() -> None:
    def use_adapter(a: APCAdapter) -> None:  # type: ignore[misc]
        pass

    use_adapter(MockAPCAdapter())


# ---------------------------------------------------------------------------
# AC4 — no hardware dependency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_hardware_needed() -> None:
    adapter = MockAPCAdapter()
    occ = await adapter.get_occupancy("car-1")
    door = await adapter.get_door_state("car-1")
    assert occ.count > 0
    assert door.car_id == "car-1"
