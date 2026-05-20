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

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool


class ContextPushModel(BaseModel):
    """POST /context body. Every field is optional with ``None`` meaning
    "absent in this push — keep current ContextState value". This is the
    resolved contract from code-review decision 2 + 5 (2026-05-20).
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
