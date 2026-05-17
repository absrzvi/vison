from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .types import EventType


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


class EventModel(BaseModel):
    """Pydantic variant for FastAPI request/response body validation."""

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


SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})
