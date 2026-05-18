"""Pydantic response models for analytics endpoints (E3-S1)."""
from __future__ import annotations

from pydantic import BaseModel

# ── Exceptions (AC1) ────────────────────────────────────────────────────────

class CoachPeak(BaseModel):
    coach_id: str
    peak_pct: float


class ConradFlag(BaseModel):
    flag_id: str
    note: str | None = None


class ExceptionRecord(BaseModel):
    exception_id: str
    route: str
    train_id: str
    departure: str
    date: str
    status: str  # unreviewed | in_review | dismissed
    severity: str
    coach_peaks: list[CoachPeak]
    trend: list[float]
    conrad_flag: ConradFlag | None = None


# ── Occupancy heatmap (AC2) ──────────────────────────────────────────────────

class HeatmapResponse(BaseModel):
    routes: list[str]
    hours: list[str]
    cells: list[list[float | None]]


# ── Dwell time (AC3) ─────────────────────────────────────────────────────────

class DwellStationRecord(BaseModel):
    station: str
    scheduled_sec: float
    actual_sec: float
    breach_count: int
    occupancy_pct: float | None = None


# ── Detection quality (AC4) ──────────────────────────────────────────────────

class DetectionKpi(BaseModel):
    total_events: int
    fp_rate: float | None  # null when total_events == 0 AND total_fp == 0
    avg_confidence: float | None
    fleet_uptime_pct: float | None


class DailyBar(BaseModel):
    date: str
    total_events: int
    fp_count: int


class PerTrainUptime(BaseModel):
    train_id: str
    uptime_pct: float


class DetectionQualityResponse(BaseModel):
    kpi: DetectionKpi
    daily_bars: list[DailyBar]
    per_train_uptime: list[PerTrainUptime]


# ── System health (AC5) ──────────────────────────────────────────────────────

class AppDetailItem(BaseModel):
    container: str
    status: str
    last_healthy: str  # ISO-8601 UTC


class DeviceDetailItem(BaseModel):
    device: str
    status: str
    temperature_c: float | None = None


class ConnectivityInfo(BaseModel):
    lte_status: str
    wifi_status: str
    last_sync: str  # ISO-8601 UTC


class TrainHealthRecord(BaseModel):
    train_id: str
    journey_id: str
    cctvStatus: str
    appStatus: str
    deviceStatus: str
    connectivityStatus: str
    last_healthy: str  # ISO-8601 UTC
    appDetail: list[AppDetailItem]
    deviceDetail: list[DeviceDetailItem]
    connectivity: ConnectivityInfo
