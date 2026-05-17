from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .types import EventType

if TYPE_CHECKING:
    from .payloads import _BasePayload

# {vehicle_id}_{trip_number}_{YYYYMMDD}
# vehicle_id and trip_number may contain hyphens and digits but not underscores.
# The date segment must be exactly 8 digits (calendar validity checked separately).
_JOURNEY_ID_RE = re.compile(r"^[^_]+_[^_]+_(\d{8})$")

# ISO-8601 UTC with Z suffix, optional sub-second precision.
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


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

    - journey_id must match {vehicle_id}_{trip_number}_{YYYYMMDD}
      (vehicle_id and trip_number may not contain underscores).
    - timestamp must be ISO-8601 UTC with Z suffix.
    - event_id must be a UUID v4 string.
    - schema_version must be in SUPPORTED_SCHEMA_VERSIONS.
    - payload is validated against PAYLOAD_MODELS when non-empty.
    - Unrecognised event_type raises ValidationError.
    - Extra fields are forbidden.
    """

    event_id: str = Field(default_factory=_new_uuid)
    journey_id: str
    vehicle_id: str
    timestamp: str = Field(default_factory=_utc_now)
    event_type: EventType
    severity: Literal["critical", "warning", "info"]
    source: Literal["inference", "fusion", "vlan-pollers"]
    schema_version: int = Field(default=1, ge=1)
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"use_enum_values": True, "extra": "forbid"}

    @field_validator("journey_id")
    @classmethod
    def _validate_journey_id(cls, v: str) -> str:
        m = _JOURNEY_ID_RE.fullmatch(v)
        if not m:
            raise ValueError(
                f"journey_id must match {{vehicle_id}}_{{trip_number}}_{{YYYYMMDD}} "
                f"(no underscores in vehicle_id or trip_number), got: {v!r}"
            )
        date_part = m.group(1)
        try:
            datetime.strptime(date_part, "%Y%m%d")
        except ValueError:
            raise ValueError(f"journey_id date segment {date_part!r} is not a valid calendar date")
        return v

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, v: str) -> str:
        if not _TIMESTAMP_RE.fullmatch(v):
            raise ValueError(
                f"timestamp must be ISO-8601 UTC with Z suffix (e.g. 2026-05-17T10:00:00Z), got: {v!r}"
            )
        return v

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, v: str) -> str:
        if not _UUID_RE.fullmatch(v):
            raise ValueError(f"event_id must be a UUID v4 string, got: {v!r}")
        return v

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, v: int) -> int:
        if v not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {v} not supported; supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            )
        return v

    @model_validator(mode="after")
    def _validate_payload_shape(self) -> "EventEnvelope":
        if not self.payload:
            return self
        # Import here to avoid circular import at module load time.
        from .payloads import PAYLOAD_MODELS  # noqa: PLC0415

        event_type = EventType(self.event_type)
        model_cls: type[_BasePayload] | None = PAYLOAD_MODELS.get(event_type)
        if model_cls is not None:
            model_cls.model_validate(self.payload)
        return self


# Backwards-compatible alias used by E1-S1 event-store code
EventModel = EventEnvelope
