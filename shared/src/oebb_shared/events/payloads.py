"""Pydantic payload models for all 23 OEBB event types.

Field names and types match event-payload-schemas.md exactly.
Optional fields (e.g. confidence) are excluded from serialisation when not set.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from .envelope import TIMESTAMP_RE
from .types import EventType


class _BasePayload(BaseModel):
    model_config = {"populate_by_name": True, "extra": "forbid"}


# Reusable annotated types
_ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]
_NonNegFloat = Annotated[float, Field(ge=0.0)]
_NonNegInt = Annotated[int, Field(ge=0)]
_NonEmptyStr = Annotated[str, Field(min_length=1)]


class BoundingBox(BaseModel):
    """Pixel-space bounding box. All coordinates are non-negative integers."""

    model_config = {"extra": "forbid"}

    x: _NonNegInt
    y: _NonNegInt
    w: _NonNegInt
    h: _NonNegInt


def _drop_none(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a new dict with `key` removed when its value is None."""
    if data.get(key) is None:
        return {k: v for k, v in data.items() if k != key}
    return data


# ---------------------------------------------------------------------------
# Occupancy
# ---------------------------------------------------------------------------


class OccupancyUpdatePayload(_BasePayload):
    """OCCUPANCY_UPDATE — source: inference, ~1 Hz per car."""

    car_id: _NonEmptyStr
    zone: str | None = None
    occupancy_count: _NonNegInt
    occupancy_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    capacity: Annotated[int, Field(ge=1)]
    confidence: _ConfidenceScore | None = None
    service_tier: _NonEmptyStr
    model_versions: dict[str, str]  # E10-S1: producer provenance, stamped by inference

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none(handler(self), "confidence")


class OccupancyThresholdCrossedPayload(_BasePayload):
    """OCCUPANCY_THRESHOLD_CROSSED — fired when pct crosses configured threshold."""

    car_id: _NonEmptyStr
    zone: str | None = None
    threshold_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    direction: Literal["rising", "falling"]
    occupancy_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    occupancy_count: _NonNegInt
    capacity: Annotated[int, Field(ge=1)]
    service_tier: _NonEmptyStr


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class AlertRaisedPayload(_BasePayload):
    """ALERT_RAISED — source: fusion. alert_id pairs with ALERT_RESOLVED.

    E10-S1: confidence_score/confidence_basis/model_versions are required.
    Per-basis invariants enforced by _validate_confidence — no silent coercion.
    """

    alert_id: _NonEmptyStr
    alert_code: _NonEmptyStr
    car_id: _NonEmptyStr
    zone: str | None = None
    description: _NonEmptyStr
    auto_resolve_after_s: _NonNegInt | None = None
    priority: Literal["escalated", "normal"] | None = None
    confidence_score: float | None
    confidence_basis: Literal["model", "sensor", "fused"]
    model_versions: dict[str, str]

    @model_validator(mode="after")
    def _validate_confidence(self) -> AlertRaisedPayload:
        basis = self.confidence_basis
        score = self.confidence_score
        if basis == "sensor":
            if score is not None:
                raise ValueError("confidence_score must be None when confidence_basis == 'sensor'")
            if self.model_versions:
                raise ValueError("model_versions must be empty when confidence_basis == 'sensor'")
        else:
            if score is None or not (0.0 <= score <= 1.0):
                raise ValueError(
                    f"confidence_score must be a float in [0.0, 1.0] when "
                    f"confidence_basis == {basis!r}"
                )
            if basis == "model" and not self.model_versions:
                raise ValueError(
                    "model_versions must be non-empty when confidence_basis == 'model'"
                )
            if basis == "fused" and len(self.model_versions) < 2:
                raise ValueError(
                    "model_versions must have >= 2 entries when confidence_basis == 'fused'"
                )
        return self

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none(handler(self), "priority")


class AlertResolvedPayload(_BasePayload):
    """ALERT_RESOLVED — alert_id must match a prior ALERT_RAISED."""

    alert_id: _NonEmptyStr
    alert_code: _NonEmptyStr
    car_id: _NonEmptyStr
    zone: str | None = None
    resolve_reason: Literal["manual", "auto", "condition_cleared"]


# ---------------------------------------------------------------------------
# Congestion & Luggage
# ---------------------------------------------------------------------------


class VestibuleCongestionPayload(_BasePayload):
    """VESTIBULE_CONGESTION — fired when congestion score crosses threshold."""

    car_id: _NonEmptyStr
    vestibule_id: _NonEmptyStr
    congestion_score: Annotated[float, Field(ge=0.0, le=1.0)]
    person_count: _NonNegInt
    dwell_time_avg_s: _NonNegFloat
    threshold_score: Annotated[float, Field(ge=0.0, le=1.0)]


class LuggageRackSaturationPayload(_BasePayload):
    """LUGGAGE_RACK_SATURATION — fired once per saturation event."""

    car_id: _NonEmptyStr
    rack_id: _NonEmptyStr
    fill_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    item_count: _NonNegInt
    confidence: _ConfidenceScore | None = None
    model_versions: dict[str, str]  # E10-S1

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none(handler(self), "confidence")


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class UnattendedBagPayload(_BasePayload):
    """UNATTENDED_BAG — dwell_s is elapsed time since owner last detected near bag.

    bbox and camera_id are Optional so the edge-egress anonymiser
    (oebb_shared.events.anonymise) can DROP them on the train→cloud boundary —
    pixel coordinates + camera locality narrow re-identification and no cloud
    consumer reads them. On-train producers (inference) ALWAYS populate both;
    the None case exists only for the redacted cloud copy.
    """

    car_id: _NonEmptyStr
    zone: str | None = None
    track_id: _NonEmptyStr
    dwell_s: _NonNegFloat
    bbox: BoundingBox | None = None
    camera_id: _NonEmptyStr | None = None
    confidence: _ConfidenceScore | None = None
    model_versions: dict[str, str]  # E10-S1

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        data = _drop_none(handler(self), "confidence")
        data = _drop_none(data, "bbox")
        return _drop_none(data, "camera_id")


class DoorObstructionPayload(_BasePayload):
    """DOOR_OBSTRUCTION — clearance triggers ALERT_RESOLVED.

    camera_id is Optional so the edge-egress anonymiser can drop it on the
    train→cloud boundary (camera locality, unread by any cloud consumer).
    On-train producers always populate it.
    """

    car_id: _NonEmptyStr
    door_id: _NonEmptyStr
    obstruction_type: Literal["person", "object", "unknown"]
    track_id: _NonEmptyStr
    camera_id: _NonEmptyStr | None = None
    confidence: _ConfidenceScore | None = None
    door_state: Literal["open", "closing", "closed", "unknown"]
    model_versions: dict[str, str]  # E10-S1

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        data = _drop_none(handler(self), "confidence")
        return _drop_none(data, "camera_id")


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------

AssistanceType = Literal["wheelchair", "pram", "crutches", "visual_impairment", "other"]


class AccessibilityDetectedPayload(_BasePayload):
    """ACCESSIBILITY_DETECTED — triggers downstream ramp/staff workflow."""

    car_id: _NonEmptyStr
    zone: str | None = None
    track_id: _NonEmptyStr
    assistance_type: Annotated[list[AssistanceType], Field(min_length=1)]
    camera_id: _NonEmptyStr
    confidence: _ConfidenceScore | None = None
    near_door_id: _NonEmptyStr
    model_versions: dict[str, str]  # E10-S1

    @model_serializer(mode="wrap")
    def _serialize(self, handler: Any) -> dict[str, Any]:
        return _drop_none(handler(self), "confidence")


class RampDeployedPayload(_BasePayload):
    """RAMP_DEPLOYED — emitted after ACCESSIBILITY_DETECTED + ramp actuation confirmed."""

    car_id: _NonEmptyStr
    door_id: _NonEmptyStr
    triggered_by_track_id: _NonEmptyStr
    deployed_by: Literal["auto", "manual"]
    station_id: _NonEmptyStr


# ---------------------------------------------------------------------------
# TCMS / Alarms
# ---------------------------------------------------------------------------

AlarmType = Literal["emergency_brake", "fire", "passenger_call", "intrusion", "other"]


class AlarmActivePayload(_BasePayload):
    """ALARM_ACTIVE — alarm_id pairs with ALARM_CLEARED."""

    alarm_id: _NonEmptyStr
    alarm_type: AlarmType
    car_id: _NonEmptyStr
    zone: str | None = None
    hardware_code: _NonEmptyStr
    triggered_by: Literal["passenger", "automatic", "unknown"]


class AlarmClearedPayload(_BasePayload):
    """ALARM_CLEARED — alarm_id must match a prior ALARM_ACTIVE."""

    alarm_id: _NonEmptyStr
    alarm_type: AlarmType
    car_id: _NonEmptyStr
    cleared_by: Literal["crew", "automatic", "unknown"]
    duration_s: _NonNegFloat


# ---------------------------------------------------------------------------
# Journey
# ---------------------------------------------------------------------------


def _validate_iso_utc(v: object) -> str:
    """Reject naive datetimes and non-UTC offsets. Requires Z suffix per NFR9."""
    if not isinstance(v, str):
        raise ValueError(
            f"timestamp must be a string, got {type(v).__name__!r}"
        )
    if not TIMESTAMP_RE.fullmatch(v):
        raise ValueError(
            f"timestamp must be ISO-8601 UTC with Z suffix (e.g. 2026-05-16T06:00:00Z), got: {v!r}"
        )
    return v


class JourneyStartedPayload(_BasePayload):
    """JOURNEY_STARTED — emitted once on departure."""

    trip_number: _NonEmptyStr
    origin_station_id: _NonEmptyStr
    scheduled_departure: _NonEmptyStr
    actual_departure: _NonEmptyStr
    consist: Annotated[list[_NonEmptyStr], Field(min_length=1)]
    service_class: _NonEmptyStr

    @field_validator("scheduled_departure", "actual_departure", mode="before")
    @classmethod
    def _validate_departure_timestamps(cls, v: str) -> str:
        return _validate_iso_utc(v)


class JourneyEndedPayload(_BasePayload):
    """JOURNEY_ENDED — journey_id in envelope must match JOURNEY_STARTED."""

    trip_number: _NonEmptyStr
    destination_station_id: _NonEmptyStr
    scheduled_arrival: _NonEmptyStr
    actual_arrival: _NonEmptyStr
    total_duration_s: _NonNegFloat
    peak_occupancy_pct: Annotated[float, Field(ge=0.0, le=1.0)]

    @field_validator("scheduled_arrival", "actual_arrival", mode="before")
    @classmethod
    def _validate_arrival_timestamps(cls, v: str) -> str:
        return _validate_iso_utc(v)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

DegradationType = Literal["offline", "low_fps", "blur", "occlusion", "night_failure"]


class CameraDegradedPayload(_BasePayload):
    """CAMERA_DEGRADED — must pair with CAMERA_RECOVERED."""

    camera_id: _NonEmptyStr
    car_id: _NonEmptyStr
    degradation_type: DegradationType
    fps_actual: _NonNegFloat
    fps_expected: _NonNegFloat
    quality_score: Annotated[float, Field(ge=0.0, le=1.0)]
    affected_zones: Annotated[list[str], Field(min_length=1)]


class CameraRecoveredPayload(_BasePayload):
    """CAMERA_RECOVERED — camera_id must match a prior CAMERA_DEGRADED."""

    camera_id: _NonEmptyStr
    car_id: _NonEmptyStr
    downtime_s: _NonNegFloat
    fps_actual: _NonNegFloat
    quality_score: Annotated[float, Field(ge=0.0, le=1.0)]


SyncType = Literal["ntp", "config", "firmware"]


class SyncCompletedPayload(_BasePayload):
    """SYNC_COMPLETED — emitted after successful clock/config sync cycle."""

    sync_type: SyncType
    nodes_synced: _NonNegInt
    nodes_failed: _NonNegInt
    max_skew_ms: _NonNegFloat
    skew_by_node: dict[str, float]
    sync_server: _NonEmptyStr


# ---------------------------------------------------------------------------
# ADR-17 — Inter-wagon movement payloads
# ---------------------------------------------------------------------------

TraversalStr = Literal["from_to", "to_from"]
# "from_to" = centroid crossed from coach_from side to coach_to side.
# "to_from" = reverse crossing. Named from camera-frame perspective, not
# train-direction-of-travel, because the edge has no runtime heading signal
# (push-pull trains reverse; cab-active SNMP OID TBD with Stadler).
# Runtime direction enrichment deferred to post-PoC (see deferred-work.md W-traversal).


class WagonExitPayload(_BasePayload):
    """WAGON_EXIT — person tracked crossing from one coach to the next."""

    track_id: int
    coach_from: _NonEmptyStr
    coach_to: _NonEmptyStr
    camera_id: _NonEmptyStr
    traversal: TraversalStr
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    expect_orphan: bool = False  # True when crossing is known to be unreconcilable (e.g. to_from on fwd camera)


class WagonEntryPayload(_BasePayload):
    """WAGON_ENTRY — same track_id confirmed entering adjacent coach."""

    track_id: int
    coach_from: _NonEmptyStr
    coach_to: _NonEmptyStr
    camera_id: _NonEmptyStr
    traversal: TraversalStr
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class LedgerDriftObservationPayload(_BasePayload):
    """LEDGER_DRIFT_OBSERVATION — diagnostic telemetry; ledger vs camera disagreement.

    Renamed from LEDGER_DRIFT_ALERT (party-mode 2026-05-21 D5) — no validated
    operator playbook exists yet. surface_to_operator gates future promotion to
    an operator-visible alert without changing this payload contract.
    """

    car_id: _NonEmptyStr
    camera_count: int
    ledger_count: int
    delta: int
    threshold: int
    surface_to_operator: bool = False


# ---------------------------------------------------------------------------
# ADR-15 — APC calibration drift payload
# ---------------------------------------------------------------------------


class CalibrationDriftPayload(_BasePayload):
    """CALIBRATION_DRIFT — camera vs APC delta exceeds threshold."""

    car_id: _NonEmptyStr
    camera_count: int
    apc_count: int
    delta: int
    threshold: int


# ---------------------------------------------------------------------------
# ADR-18 — Comfort scoring and stream priority payloads
# ---------------------------------------------------------------------------


class CoachComfortIndexPayload(_BasePayload):
    """COACH_COMFORT_INDEX — composite comfort score for a coach."""

    car_id: _NonEmptyStr
    comfort_score: Annotated[float, Field(ge=0.0, le=1.0)]
    occupancy_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    temperature_c: float | None = None
    noise_db: float | None = None


class StreamPriorityPayload(_BasePayload):
    """STREAM_PRIORITY — internal signal only; never written to event-store."""

    camera_ids: list[str]
    priority: Literal["P1", "P2", "P3"]
    duration_s: float
    reason: _NonEmptyStr


# ---------------------------------------------------------------------------
# E10-S1 — AI pipeline health + alert-class kill-switch payloads
# ---------------------------------------------------------------------------


class InferenceHeartbeatPayload(_BasePayload):
    """INFERENCE_HEARTBEAT — source: inference, every 60s independent of detections.

    Consumer notes (E10-S1 review R1):
    - hailo_device_ok is a camera-pipeline-readiness proxy (any pipeline ready),
      NOT a direct Hailo device-handle check — the handle is not reachable
      off-device. A true handle check is deferred to hardware bring-up.
    - last_inference_at is seeded at container start, so a pipeline that has
      never produced a frame reports a fresh timestamp with
      frames_processed_window == 0. Treat frames==0 + a young timestamp as
      "not yet inferring", not as proof of health.
    """

    train_id: _NonEmptyStr
    model_versions: dict[str, str]
    frames_processed_window: _NonNegInt  # frames processed since last heartbeat
    last_inference_at: datetime  # ISO-8601 UTC, with Z suffix
    hailo_device_ok: bool

    @field_validator("last_inference_at")
    @classmethod
    def _require_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError("last_inference_at must be ISO-8601 UTC with Z suffix")
        return v

    @field_serializer("last_inference_at")
    def _serialize_last_inference_at(self, v: datetime) -> str:
        return v.isoformat().replace("+00:00", "Z")


class AlertClassStatePayload(_BasePayload):
    """ALERT_CLASS_DISABLED / ALERT_CLASS_REENABLED — source: cloud-backend admin API."""

    alert_code: _NonEmptyStr
    actor_name: _NonEmptyStr
    source_ip: _NonEmptyStr


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
    # ADR-17
    EventType.WAGON_EXIT: WagonExitPayload,
    EventType.WAGON_ENTRY: WagonEntryPayload,
    EventType.LEDGER_DRIFT_OBSERVATION: LedgerDriftObservationPayload,
    # ADR-15
    EventType.CALIBRATION_DRIFT: CalibrationDriftPayload,
    # ADR-18
    EventType.COACH_COMFORT_INDEX: CoachComfortIndexPayload,
    EventType.STREAM_PRIORITY: StreamPriorityPayload,
    # E10-S1
    EventType.INFERENCE_HEARTBEAT: InferenceHeartbeatPayload,
    EventType.ALERT_CLASS_DISABLED: AlertClassStatePayload,
    EventType.ALERT_CLASS_REENABLED: AlertClassStatePayload,
}
