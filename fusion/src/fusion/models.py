"""Pydantic models for inbound fusion endpoints.

ContextPushModel mirrors inference/health.py:ContextPushModel — strict bool so
truthiness can't flip suppression. extra='forbid' so unknown fields fail at
validation time (422), not silently swallowed.

Push semantics (decided in code-review 2026-05-20):
  - All suppression-relevant flags use ``Optional[StrictBool] = None`` so an
    omitted field means "keep prior state" rather than "reset to default".
  - All dict fields use ``Optional[dict] = None`` so an empty `{}` push means
    "clear" and an absent field means "keep prior state".

SlipFallCandidate matches the dict shape inference posts at
``{fusion_url}/candidates/alert_raised`` — see inference/src/inference/zone_counter.py.
The ``track_id`` is ``int`` because inference produces it as a hailotracker
integer id; the contract test replays the exact int type.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool


class PisPush(BaseModel):
    """Nested `pis` object inside the vlan-pollers full-delta push (E6-S4).

    fusion only consumes ``scheduled_departure`` (for E10-S4 seconds_to_departure).
    ``extra='ignore'`` tolerates the other PisState fields (next_station, platform,
    delay_min, …) without listing them, so a new PisState field never 422s fusion.
    """

    model_config = ConfigDict(extra="ignore")

    scheduled_departure: str | None = None


class ContextPushModel(BaseModel):
    """POST /context body. Every field is optional with ``None`` meaning
    "absent in this push — keep current ContextState value". This is the
    resolved contract from code-review decision 2 + 5 (2026-05-20).

    E6-S4: declares the full vlan-pollers `_state_to_dict` key set so the real
    full-delta push is ACCEPTED (200) instead of 422'd. `extra='forbid'` is
    retained so a genuinely-unknown/typo'd field still fails loudly. fusion only
    READS the keys it needs (pis.scheduled_departure, speed, station_approach,
    reservations, suppression flags, …); `trip_number`/`alarms`/`occupancy` are
    accepted-and-ignored (fusion gets occupancy via /candidates/occupancy_update,
    not the context push — comfort_index.py D4).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    journey_id: str | None = None
    vehicle_id: str | None = None
    speed_kmh: float | None = None

    # Bool flags use Optional so omitted ≠ reset (code-review decision 5).
    station_approach: StrictBool | None = None
    maintenance_mode: StrictBool | None = None
    depot_mode: StrictBool | None = None
    gps_valid: StrictBool | None = None

    # Dict fields use Optional so absent ≠ {} (code-review decision 2).
    # An empty dict explicitly clears prior state; absent keeps it.
    # key: "{car_id}:{door_id}"
    door_release: dict[str, StrictBool] | None = None
    door_state: dict[str, str] | None = None

    reservations: dict[str, int] | None = None
    # car_index → car_id (R3 — per-coach resolution lives in fusion).
    consist: dict[str, str] | None = None

    # R4 ramp signal — fusion correlates with recent ACCESSIBILITY_DETECTED.
    # Optional so absent ≠ ramp_deployed=false (only an explicit value triggers).
    ramp_deployed: StrictBool | None = None
    ramp_door_id: str | None = None
    ramp_station_id: str | None = None

    # E10-S1 AC9: door controller firmware version from SNMP (absent keeps prior).
    door_firmware_version: str | None = None

    # E10-S4 (rewired by E6-S4): scheduled departure for seconds_to_departure now
    # arrives NESTED inside the full-delta push's `pis` object (the canonical wire);
    # update_from_push reads pis.scheduled_departure. The flat top-level field +
    # targeted update_pis push from E10-S4 are removed (single source of truth).
    pis: PisPush | None = None

    # E6-S4 accept-and-ignore: present in the real vlan-pollers full-delta body but
    # NOT consumed by fusion (occupancy → /candidates/occupancy_update; alarms →
    # diagnostics path; trip_number → unused). Declared so the push validates;
    # never written to ContextState (no speculative plumbing).
    trip_number: str | None = None
    alarms: list[dict[str, Any]] | None = None
    occupancy: dict[str, Any] | None = None


class SlipFallCandidate(BaseModel):
    """Body shape inference posts to /candidates/alert_raised.

    Inference does NOT use a shared Pydantic model on its end — it posts a plain
    dict. ``track_id`` is ``int`` because the inference source emits an integer
    hailotracker id; the contract test must replay this exact type.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    alert_type: Literal["slip_fall"]
    car_id: str
    track_id: int
    camera_id: str
    # E10-S1 AC9: detector confidence + provenance for the ALERT_RAISED metadata.
    # Optional so legacy producers without the fields still validate.
    confidence: float | None = None
    model_versions: dict[str, str] | None = None
