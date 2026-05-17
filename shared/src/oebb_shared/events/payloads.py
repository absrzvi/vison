"""Pydantic payload models for all 17 OEBB event types.

Field names and types match event-payload-schemas.md exactly.
Optional fields (e.g. confidence) are excluded from serialisation when not set.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, model_serializer

from .types import EventType


class _BasePayload(BaseModel):
    model_config = {"populate_by_name": True}


def _drop_none_confidence(data: dict[str, Any]) -> dict[str, Any]:
    """Remove 'confidence' key when its value is None."""
    if data.get("confidence") is None:
        data.pop("confidence", None)
    return data


# ---------------------------------------------------------------------------
# Occupancy
# ---------------------------------------------------------------------------


class OccupancyUpdatePayload(_BasePayload):
    """OCCUPANCY_UPDATE — source: inference, ~1 Hz per car."""

    car_id: str
    zone: str | None = None
    occupancy_count: int
    occupancy_pct: float
    capacity: int
    confidence: float | None = None
    service_tier: str

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none_confidence(handler(self))


class OccupancyThresholdCrossedPayload(_BasePayload):
    """OCCUPANCY_THRESHOLD_CROSSED — fired when pct crosses configured threshold."""

    car_id: str
    zone: str | None = None
    threshold_pct: float
    direction: Literal["rising", "falling"]
    occupancy_pct: float
    occupancy_count: int
    capacity: int
    service_tier: str


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class AlertRaisedPayload(_BasePayload):
    """ALERT_RAISED — source: fusion. alert_id pairs with ALERT_RESOLVED."""

    alert_id: str
    alert_code: str
    car_id: str
    zone: str | None = None
    description: str
    auto_resolve_after_s: int | None = None
    priority: Literal["escalated", "normal"] | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        d: dict[str, Any] = handler(self)
        if d.get("priority") is None:
            d.pop("priority", None)
        return d


class AlertResolvedPayload(_BasePayload):
    """ALERT_RESOLVED — alert_id must match a prior ALERT_RAISED."""

    alert_id: str
    alert_code: str
    car_id: str
    zone: str | None = None
    resolve_reason: Literal["manual", "auto", "condition_cleared"]


# ---------------------------------------------------------------------------
# Congestion & Luggage
# ---------------------------------------------------------------------------


class VestibuleCongestionPayload(_BasePayload):
    """VESTIBULE_CONGESTION — fired when congestion score crosses threshold."""

    car_id: str
    vestibule_id: str
    congestion_score: float
    person_count: int
    dwell_time_avg_s: float
    threshold_score: float


class LuggageRackSaturationPayload(_BasePayload):
    """LUGGAGE_RACK_SATURATION — fired once per saturation event."""

    car_id: str
    rack_id: str
    fill_pct: float
    item_count: int
    confidence: float | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none_confidence(handler(self))


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class UnattendedBagPayload(_BasePayload):
    """UNATTENDED_BAG — dwell_s is elapsed time since owner last detected near bag."""

    car_id: str
    zone: str | None = None
    track_id: str
    dwell_s: float
    bbox: dict[str, int]
    camera_id: str
    confidence: float | None = None

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none_confidence(handler(self))


class DoorObstructionPayload(_BasePayload):
    """DOOR_OBSTRUCTION — clearance triggers ALERT_RESOLVED."""

    car_id: str
    door_id: str
    obstruction_type: Literal["person", "object", "unknown"]
    track_id: str
    camera_id: str
    confidence: float | None = None
    door_state: Literal["open", "closing", "closed"]

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none_confidence(handler(self))


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------

AssistanceType = Literal["wheelchair", "pram", "crutches", "visual_impairment", "other"]


class AccessibilityDetectedPayload(_BasePayload):
    """ACCESSIBILITY_DETECTED — triggers downstream ramp/staff workflow."""

    car_id: str
    zone: str | None = None
    track_id: str
    assistance_type: list[AssistanceType]
    camera_id: str
    confidence: float | None = None
    near_door_id: str

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none_confidence(handler(self))


class RampDeployedPayload(_BasePayload):
    """RAMP_DEPLOYED — emitted after ACCESSIBILITY_DETECTED + ramp actuation confirmed."""

    car_id: str
    door_id: str
    triggered_by_track_id: str
    deployed_by: Literal["auto", "manual"]
    station_id: str


# ---------------------------------------------------------------------------
# TCMS / Alarms
# ---------------------------------------------------------------------------

AlarmType = Literal["emergency_brake", "fire", "passenger_call", "intrusion", "other"]


class AlarmActivePayload(_BasePayload):
    """ALARM_ACTIVE — alarm_id pairs with ALARM_CLEARED."""

    alarm_id: str
    alarm_type: AlarmType
    car_id: str
    zone: str | None = None
    hardware_code: str
    triggered_by: Literal["passenger", "automatic", "unknown"]


class AlarmClearedPayload(_BasePayload):
    """ALARM_CLEARED — alarm_id must match a prior ALARM_ACTIVE."""

    alarm_id: str
    alarm_type: AlarmType
    car_id: str
    cleared_by: Literal["crew", "automatic", "unknown"]
    duration_s: float


# ---------------------------------------------------------------------------
# Journey
# ---------------------------------------------------------------------------


class JourneyStartedPayload(_BasePayload):
    """JOURNEY_STARTED — emitted once on departure."""

    trip_number: str
    origin_station_id: str
    scheduled_departure: str
    actual_departure: str
    consist: list[str]
    service_class: str


class JourneyEndedPayload(_BasePayload):
    """JOURNEY_ENDED — journey_id in envelope must match JOURNEY_STARTED."""

    trip_number: str
    destination_station_id: str
    scheduled_arrival: str
    actual_arrival: str
    total_duration_s: float
    peak_occupancy_pct: float


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

DegradationType = Literal["offline", "low_fps", "blur", "occlusion", "night_failure"]


class CameraDegradedPayload(_BasePayload):
    """CAMERA_DEGRADED — must pair with CAMERA_RECOVERED."""

    camera_id: str
    car_id: str
    degradation_type: DegradationType
    fps_actual: float
    fps_expected: float
    quality_score: float
    affected_zones: list[str]


class CameraRecoveredPayload(_BasePayload):
    """CAMERA_RECOVERED — camera_id must match a prior CAMERA_DEGRADED."""

    camera_id: str
    car_id: str
    downtime_s: float
    fps_actual: float
    quality_score: float


SyncType = Literal["ntp", "config", "firmware"]


class SyncCompletedPayload(_BasePayload):
    """SYNC_COMPLETED — emitted after successful clock/config sync cycle."""

    sync_type: SyncType
    nodes_synced: int
    nodes_failed: int
    max_skew_ms: float
    skew_by_node: dict[str, float]
    sync_server: str


# ---------------------------------------------------------------------------
# Registry: EventType → payload model class
# ---------------------------------------------------------------------------

PAYLOAD_MODELS: dict[EventType, type[_BasePayload]] = {
    EventType.OCCUPANCY_UPDATE: OccupancyUpdatePayload,
    EventType.OCCUPANCY_THRESHOLD_CROSSED: OccupancyThresholdCrossedPayload,
    EventType.ALERT_RAISED: AlertRaisedPayload,
    EventType.ALERT_RESOLVED: AlertResolvedPayload,
    EventType.VESTIBULE_CONGESTION: VestibuleCongestionPayload,
    EventType.LUGGAGE_RACK_SATURATION: LuggageRackSaturationPayload,
    EventType.UNATTENDED_BAG: UnattendedBagPayload,
    EventType.DOOR_OBSTRUCTION: DoorObstructionPayload,
    EventType.ACCESSIBILITY_DETECTED: AccessibilityDetectedPayload,
    EventType.RAMP_DEPLOYED: RampDeployedPayload,
    EventType.ALARM_ACTIVE: AlarmActivePayload,
    EventType.ALARM_CLEARED: AlarmClearedPayload,
    EventType.JOURNEY_STARTED: JourneyStartedPayload,
    EventType.JOURNEY_ENDED: JourneyEndedPayload,
    EventType.CAMERA_DEGRADED: CameraDegradedPayload,
    EventType.CAMERA_RECOVERED: CameraRecoveredPayload,
    EventType.SYNC_COMPLETED: SyncCompletedPayload,
}
