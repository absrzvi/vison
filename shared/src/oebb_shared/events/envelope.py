from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .types import EventType

_JOURNEY_ID_RE = re.compile(r"^[^_]+_[^_]+_\d{8}$")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Event:
    journey_id: str
    vehicle_id: str
    event_type: EventType
    severity: Literal["critical", "warning", "info"]
    source: Literal["inference", "fusion", "vlan-pollers"]
    payload: dict[str, Any]
    event_id: str = field(default_factory=_new_uuid)
    timestamp: str = field(default_factory=_utc_now)
    schema_version: int = 1


class EventEnvelope(BaseModel):
    """Canonical Pydantic model for all event payloads.

    journey_id must follow the pattern {vehicle_id}_{trip_number}_{YYYYMMDD}.
    Unrecognised event_type values raise ValidationError — no silent coercion.
    """

    event_id: str = Field(default_factory=_new_uuid)
    journey_id: str
    vehicle_id: str
    timestamp: str = Field(default_factory=_utc_now)
    event_type: EventType
    severity: Literal["critical", "warning", "info"]
    source: Literal["inference", "fusion", "vlan-pollers"]
    schema_version: int = 1
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True}

    @field_validator("journey_id")
    @classmethod
    def _validate_journey_id(cls, v: str) -> str:
        if not _JOURNEY_ID_RE.match(v):
            raise ValueError(
                f"journey_id must match {{vehicle_id}}_{{trip_number}}_{{YYYYMMDD}}, got: {v!r}"
            )
        return v


# Backwards-compatible alias used by E1-S1 event-store code
EventModel = EventEnvelope

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})
