from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AlarmType = Literal["emergency_brake", "fire", "passenger_call", "intrusion", "other"]


@dataclass
class AlarmEntry:
    alarm_id: str
    description: str
    severity: Literal["critical", "warning", "info"]
    active: bool
    # Fields required by AlarmActivePayload / AlarmClearedPayload in shared
    alarm_type: AlarmType = "other"
    car_id: str = ""
    hardware_code: str = "SNMP"


@dataclass
class TripInfo:
    trip_number: str
    journey_id: str


@dataclass
class PisState:
    next_station: str = ""
    next_station_arrival_utc: str = ""  # ISO-8601 UTC with Z suffix, empty = unknown


@dataclass
class VehicleState:
    speed_kmh: float = 0.0
    pis: PisState = field(default_factory=PisState)


@dataclass
class ContextState:
    journey_id: str = ""
    trip_number: str = ""
    vehicle_id: str = ""
    speed_kmh: float = 0.0
    station_approach: bool = False
    door_release: dict[str, bool] = field(default_factory=dict)  # car_id → bool
    alarms: dict[str, AlarmEntry] = field(default_factory=dict)  # alarm_id → AlarmEntry
    pis: PisState = field(default_factory=PisState)
