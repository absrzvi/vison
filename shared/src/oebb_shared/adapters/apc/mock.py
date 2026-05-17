from .adapter import APCAdapter, DoorState, OccupancyReading

_MOCK_OCCUPANCY: dict[str, OccupancyReading] = {
    "car-1": OccupancyReading(car_id="car-1", count=45, timestamp="2026-05-17T10:00:00Z"),
    "car-2": OccupancyReading(car_id="car-2", count=182, timestamp="2026-05-17T10:00:00Z"),
    "car-3": OccupancyReading(car_id="car-3", count=71, timestamp="2026-05-17T10:00:00Z"),
    "car-4": OccupancyReading(car_id="car-4", count=120, timestamp="2026-05-17T10:00:00Z"),
    "car-5": OccupancyReading(car_id="car-5", count=33, timestamp="2026-05-17T10:00:00Z"),
}


class MockAPCAdapter:
    """Deterministic test double for APCAdapter. Satisfies the APCAdapter Protocol."""

    async def get_occupancy(self, car_id: str) -> OccupancyReading:
        if car_id not in _MOCK_OCCUPANCY:
            raise KeyError(f"Unknown car_id: {car_id}")
        return _MOCK_OCCUPANCY[car_id]

    async def get_door_state(self, car_id: str) -> DoorState:
        return DoorState(car_id=car_id, is_open=False, timestamp="2026-05-17T10:00:00Z")


# Runtime check: MockAPCAdapter must satisfy APCAdapter Protocol
def _assert_protocol() -> None:
    _: APCAdapter = MockAPCAdapter()


_assert_protocol()
