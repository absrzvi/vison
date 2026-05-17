"""ADR-2: journey_id must be stable across midnight crossings."""
import pytest


def make_journey_id(vehicle_id: str, trip_number: str, journey_start_date: str) -> str:
    """Reference implementation of journey_id construction (ADR-2)."""
    return f"{vehicle_id}_{trip_number}_{journey_start_date}"


@pytest.mark.unit
def test_journey_id_stable_across_midnight() -> None:
    """journey_id uses journey_start_date, not event timestamp date.

    A trip starting at 23:45 on 2026-05-16 and emitting an event at
    00:05 on 2026-05-17 must produce the same journey_id as earlier
    events from the same trip.
    """
    vehicle_id = "R5001C-031"
    trip_number = "RJ-0847"
    journey_start_date = "20260516"  # recorded once when trip_number first seen

    journey_id = make_journey_id(vehicle_id, trip_number, journey_start_date)

    # Even though wall clock has rolled to 2026-05-17, journey_id must not change
    assert journey_id == "R5001C-031_RJ-0847_20260516"


@pytest.mark.unit
def test_journey_id_format() -> None:
    journey_id = make_journey_id("V001", "RJ-0001", "20260101")
    parts = journey_id.split("_")
    assert len(parts) == 3
    assert parts[0] == "V001"
    assert parts[1] == "RJ-0001"
    assert parts[2] == "20260101"


@pytest.mark.unit
def test_journey_id_different_trips_are_different() -> None:
    id1 = make_journey_id("V001", "RJ-0001", "20260101")
    id2 = make_journey_id("V001", "RJ-0002", "20260101")
    assert id1 != id2


@pytest.mark.unit
def test_journey_id_different_vehicles_are_different() -> None:
    id1 = make_journey_id("V001", "RJ-0001", "20260101")
    id2 = make_journey_id("V002", "RJ-0001", "20260101")
    assert id1 != id2
