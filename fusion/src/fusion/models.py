"""Pydantic models for inbound fusion endpoints.

ContextPushModel mirrors inference/health.py:ContextPushModel — strict bool so
truthiness can't flip suppression. extra='forbid' so unknown fields fail at
validation time (422), not silently swallowed.

SlipFallCandidate matches the dict shape inference posts at
``{fusion_url}/candidates/alert_raised`` — see inference/src/inference/zone_counter.py.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ContextPushModel(BaseModel):
    """POST /context body. All suppression-relevant fields are optional with
    safe defaults so vlan-pollers can phase them in without breaking fusion.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    journey_id: str | None = None
    vehicle_id: str | None = None
    speed_kmh: float | None = None
    station_approach: StrictBool = False
    maintenance_mode: StrictBool = False
    depot_mode: StrictBool = False
    gps_valid: StrictBool = True

    # key: "{car_id}:{door_id}"
    door_release: dict[str, StrictBool] = Field(default_factory=dict)
    door_state: dict[str, str] = Field(default_factory=dict)

    reservations: dict[str, int] = Field(default_factory=dict)
    # car_index → car_id (R3 — per-coach resolution lives in fusion).
    consist: dict[str, str] = Field(default_factory=dict)

    # R4 ramp signal — fusion correlates with recent ACCESSIBILITY_DETECTED.
    ramp_deployed: StrictBool = False
    ramp_door_id: str | None = None
    ramp_station_id: str | None = None


class SlipFallCandidate(BaseModel):
    """Body shape inference posts to /candidates/alert_raised.

    Inference does NOT use a shared Pydantic model on its end — it posts a plain
    dict. Fusion validates strictly here. Adding new alert_type values is a
    deliberate contract change.
    """

    model_config = ConfigDict(strict=False, extra="forbid")

    alert_type: Literal["slip_fall"]
    car_id: str
    track_id: str
    camera_id: str
