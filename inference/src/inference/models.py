"""Domain models for inference container."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum


class DetectionClass(StrEnum):
    """Classes forwarded from the GStreamer pipeline to zone_counter."""

    PERSON = "person"


@dataclass
class ZoneMask:
    """Static polygon mask for a seating zone (ADR-16)."""

    name: str
    polygon: list[list[int]]  # list of [x, y] vertices


@dataclass
class ReadinessHolder:
    """Mutable readiness flag flipped by main.py after pipeline init."""

    ready: bool = False


@dataclass
class LoopHolder:
    """Mutable asyncio loop reference set by main.py once the uvicorn loop is running.

    The GStreamer streaming thread reads `loop` synchronously to schedule async work.
    """

    loop: asyncio.AbstractEventLoop | None = None


@dataclass
class OccupancyState:
    """Per-car occupancy state maintained by ZoneCounter."""

    car_id: str
    occupancy_count: int = 0
    occupancy_pct: float = 0.0
    capacity: int = 200
    zone: str = "interior"
    # track_ids currently in the zone (excluding None)
    active_tracks: set[int] = field(default_factory=set)
