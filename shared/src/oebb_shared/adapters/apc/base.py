from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class OccupancyReading:
    car_id: str
    count: int
    timestamp: str  # ISO-8601 UTC with Z


@dataclass
class DoorState:
    car_id: str
    is_open: bool
    timestamp: str  # ISO-8601 UTC with Z


class APCAdapter(Protocol):
    async def get_occupancy(self, car_id: str) -> OccupancyReading: ...

    async def get_door_state(self, car_id: str) -> DoorState: ...
