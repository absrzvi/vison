"""In-memory ContextState owned by the fusion container.

Holds the latest snapshot pushed by vlan-pollers plus a TTL-bounded record of
recent ACCESSIBILITY_DETECTED tracks. State is intentionally not persisted —
fusion restarts pick up the next context push within a few seconds.

Push semantics (code-review 2026-05-20 decisions 2 + 5 + 8):
  * Each field on ``ContextPushModel`` is ``Optional``. ``None`` means absent
    in this push → keep current state. An explicit value (including ``{}``)
    replaces prior state.
  * ``ramp_deployed`` is tracked here so the FastAPI layer can edge-trigger the
    RAMP_DEPLOYED emit only on the false→true transition.
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
    # E10-S4: scheduled departure (ISO-UTC string) from vlan-pollers PIS feed.
    # Already on the /context wire (vlan-pollers _state_to_dict["pis"]) — fusion
    # now keeps it so enrichment can derive seconds_to_departure. "" / None = unknown.
    scheduled_departure: str | None = None
    maintenance_mode: bool = False
    depot_mode: bool = False
    gps_valid: bool = True
    door_release: dict[str, bool] = field(default_factory=dict)
    door_state: dict[str, str] = field(default_factory=dict)
    reservations: dict[str, int] = field(default_factory=dict)
    consist: dict[str, str] = field(default_factory=dict)

    # E10-S1 AC9: door controller firmware version sourced from vlan-pollers SNMP;
    # joins fused-basis model_versions on door_obstruction alerts.
    door_firmware_version: str = "unknown"

    # R4: ramp edge-trigger tracking. We record the *previously observed* value
    # so the FastAPI layer can detect a false→true transition.
    ramp_deployed: bool = False

    # E4-S10: station_approach edge tracking — mirrors ramp_deployed pattern.
    # Set by observe_station_approach_edge after the field has been updated by
    # update_from_push, so callers always observe transitions against the
    # PRIOR value.
    _prev_station_approach: bool = False

    # car_id → door_id_or_zone → (track_id, monotonic_timestamp)
    _recent_accessibility: dict[str, dict[str, tuple[str, float]]] = field(default_factory=dict)

    def update_from_push(self, model: ContextPushModel) -> None:
        """Apply a push using "present replaces, absent keeps" semantics.

        Every field that is not ``None`` is written verbatim (including empty
        dicts, which explicitly clear prior state). ``None`` fields are left
        untouched.
        """
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
        if model.station_approach is not None:
            self.station_approach = model.station_approach
        if model.maintenance_mode is not None:
            self.maintenance_mode = model.maintenance_mode
        if model.depot_mode is not None:
            self.depot_mode = model.depot_mode
        if model.gps_valid is not None:
            self.gps_valid = model.gps_valid
        if model.door_release is not None:
            self.door_release = dict(model.door_release)
        if model.door_state is not None:
            self.door_state = dict(model.door_state)
        if model.reservations is not None:
            self.reservations = dict(model.reservations)
        if model.consist is not None:
            self.consist = dict(model.consist)
        if model.door_firmware_version is not None:
            self.door_firmware_version = model.door_firmware_version
        if model.scheduled_departure is not None:
            self.scheduled_departure = model.scheduled_departure
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

    def observe_ramp_signal(self, ramp_deployed: bool) -> bool:
        """Record ``ramp_deployed`` and return True only on a false→true edge.

        Callers use the return value to debounce RAMP_DEPLOYED emits — a stuck
        ``ramp_deployed=true`` signal repeating across pushes only emits once.
        """
        edge = (not self.ramp_deployed) and ramp_deployed
        self.ramp_deployed = ramp_deployed
        return edge

    def observe_station_approach_edge(self) -> bool:
        """Return True only on a false→true transition of ``station_approach``.

        Mirrors :meth:`observe_ramp_signal`. The caller invokes this AFTER
        :meth:`update_from_push` has applied the new ``station_approach`` value;
        the method then compares against ``_prev_station_approach`` and updates
        the prior so the next call sees the new baseline.

        E4-S10: used by the /context handler to drive the station_approach
        COACH_COMFORT_INDEX emit (AC2).
        """
        edge = (not self._prev_station_approach) and self.station_approach
        self._prev_station_approach = self.station_approach
        return edge

    def peek_station_approach_edge(self) -> bool:
        """Return True if a false→true edge is pending WITHOUT consuming it.

        D3 fix: separates edge detection from state commitment. The caller
        checks the edge, consults the suppression gate, and only calls
        :meth:`consume_station_approach_edge` if the gate allows the emit.
        Under suppression the prior is not advanced, so the edge re-fires on
        the next /context push after the gate re-opens.
        """
        return (not self._prev_station_approach) and self.station_approach

    def consume_station_approach_edge(self) -> None:
        """Commit the edge by advancing ``_prev_station_approach``.

        Must be called after a successful station-edge emit. Do NOT call under
        suppression — leave the prior unchanged so the edge re-fires.
        """
        self._prev_station_approach = self.station_approach

    def resolve_car_id(self, idx: str | int) -> str:
        """R3 — best-effort coach index resolution. Returns the input unchanged
        when the consist map is empty, the index is missing, or the mapping is
        an empty string.
        """
        key = str(idx)
        resolved = self.consist.get(key)
        if not resolved:  # None or empty string → passthrough
            log.debug("context_state.resolve_car_id.passthrough", input=key)
            return key
        return resolved

    def door_state_for(self, car_id: str, door_id: str) -> str:
        return self.door_state.get(_door_key(car_id, door_id), "unknown")

    def car_id_for_door(self, door_id: str) -> str | None:
        """Resolve car_id from a door_id using ``consist``-aware logic.

        Strategy: scan ``door_state`` keys looking for an exact ``:door_id``
        suffix where the *prefix is a known car_id* (either present in
        ``consist`` values or used as a door_state prefix). Returns ``None``
        when no deterministic match exists — callers can then default to
        ``"unknown"`` explicitly rather than relying on first-match heuristics.
        """
        suffix = f"{_DOOR_KEY_SEP}{door_id}"
        candidates = [k[: -len(suffix)] for k in self.door_state if k.endswith(suffix)]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        # Multiple cars expose the same door_id — prefer one that is also in
        # consist values; otherwise log ambiguity and return None.
        known_cars = set(self.consist.values())
        narrowed = [c for c in candidates if c in known_cars]
        if len(narrowed) == 1:
            return narrowed[0]
        log.warning(
            "context_state.car_id_for_door.ambiguous",
            door_id=door_id,
            candidates=candidates,
        )
        return None

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
