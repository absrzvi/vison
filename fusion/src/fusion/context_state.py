"""In-memory ContextState owned by the fusion container.

Holds the latest snapshot pushed by vlan-pollers plus a TTL-bounded record of
recent ACCESSIBILITY_DETECTED tracks. State is intentionally not persisted —
fusion restarts pick up the next context push within a few seconds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Final

import structlog

from fusion.models import ContextPushModel

log = structlog.get_logger(__name__)

_DOOR_KEY_SEP: Final[str] = ":"


def _door_key(car_id: str, door_id: str) -> str:
    return f"{car_id}{_DOOR_KEY_SEP}{door_id}"


@dataclass
class ContextState:
    """Mutable snapshot of vlan-pollers context plus fusion-local accessibility log."""

    journey_id: str | None = None
    vehicle_id: str | None = None
    speed_kmh: float | None = None
    station_approach: bool = False
    maintenance_mode: bool = False
    depot_mode: bool = False
    gps_valid: bool = True
    door_release: dict[str, bool] = field(default_factory=dict)
    door_state: dict[str, str] = field(default_factory=dict)
    reservations: dict[str, int] = field(default_factory=dict)
    consist: dict[str, str] = field(default_factory=dict)

    # car_id → door_id_or_zone → (track_id, monotonic_timestamp)
    _recent_accessibility: dict[str, dict[str, tuple[str, float]]] = field(default_factory=dict)

    def update_from_push(self, model: ContextPushModel) -> None:
        """Overwrite mutable fields from a validated POST /context body."""
        before = (
            self.maintenance_mode,
            self.depot_mode,
            self.gps_valid,
            self.station_approach,
        )
        if model.journey_id is not None:
            self.journey_id = model.journey_id
        if model.vehicle_id is not None:
            self.vehicle_id = model.vehicle_id
        if model.speed_kmh is not None:
            self.speed_kmh = model.speed_kmh
        self.station_approach = model.station_approach
        self.maintenance_mode = model.maintenance_mode
        self.depot_mode = model.depot_mode
        self.gps_valid = model.gps_valid
        if model.door_release:
            self.door_release = dict(model.door_release)
        if model.door_state:
            self.door_state = dict(model.door_state)
        if model.reservations:
            self.reservations = dict(model.reservations)
        if model.consist:
            self.consist = dict(model.consist)
        after = (
            self.maintenance_mode,
            self.depot_mode,
            self.gps_valid,
            self.station_approach,
        )
        if before != after:
            log.info(
                "context_state.suppression_flags_changed",
                maintenance_mode=self.maintenance_mode,
                depot_mode=self.depot_mode,
                gps_valid=self.gps_valid,
                station_approach=self.station_approach,
            )

    def resolve_car_id(self, idx: str | int) -> str:
        """R3 — best-effort coach index resolution. Returns the input unchanged
        when the consist map is empty or the index is missing.
        """
        key = str(idx)
        resolved = self.consist.get(key)
        if resolved is None:
            log.debug("context_state.resolve_car_id.passthrough", input=key)
            return key
        return resolved

    def door_state_for(self, car_id: str, door_id: str) -> str:
        return self.door_state.get(_door_key(car_id, door_id), "unknown")

    def note_accessibility(
        self,
        car_id: str,
        door_id_or_zone: str,
        track_id: str,
        *,
        now: float | None = None,
    ) -> None:
        stamp = now if now is not None else time.monotonic()
        self._recent_accessibility.setdefault(car_id, {})[door_id_or_zone] = (track_id, stamp)

    def find_recent_accessibility(
        self,
        car_id: str,
        door_id: str,
        window_s: float,
        *,
        now: float | None = None,
    ) -> str | None:
        """Return the most recent track_id for (car_id, door_id) within window_s.

        Lazy GC: stale entries (>window_s old) are dropped on access.
        """
        current = now if now is not None else time.monotonic()
        per_car = self._recent_accessibility.get(car_id)
        if not per_car:
            return None
        # Lazy GC.
        stale = [k for k, (_, ts) in per_car.items() if current - ts > window_s]
        for k in stale:
            del per_car[k]
        entry = per_car.get(door_id)
        if entry is None:
            return None
        track_id, ts = entry
        if current - ts > window_s:
            del per_car[door_id]
            return None
        return track_id
