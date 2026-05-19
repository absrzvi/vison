"""Domain models for inference container."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class DetectionClass(StrEnum):
    """Classes forwarded from the GStreamer pipeline to zone_counter."""

    PERSON = "person"
    SUITCASE = "suitcase"
    BICYCLE = "bicycle"


@dataclass
class ZoneMask:
    """Static polygon mask for a seating zone (ADR-16)."""

    name: str
    polygon: list[list[int]]  # list of [x, y] vertices


@dataclass
class OccupancyState:
    """Per-car occupancy state maintained by ZoneCounter."""

    car_id: str
    occupancy_count: int = 0
    occupancy_pct: float = 0.0
    capacity: int = 200
    zone: str = "interior"
    service_tier: str = "standard"
    # track_ids currently in the zone
    active_tracks: set[int] = field(default_factory=set)
