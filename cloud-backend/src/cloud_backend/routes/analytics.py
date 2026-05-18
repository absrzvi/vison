"""Analytics REST endpoints for E3-S1: five date-range-aware endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.analytics import (
    AppDetailItem,
    CoachPeak,
    ConnectivityInfo,
    DailyBar,
    DetectionKpi,
    DetectionQualityResponse,
    DeviceDetailItem,
    DwellStationRecord,
    ExceptionRecord,
    HeatmapResponse,
    PerTrainUptime,
    TrainHealthRecord,
)
from ..api.auth import require_api_key
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", dependencies=[Security(require_api_key)])

_VALID_RANGES = {"7d", "14d", "30d"}
_RANGE_MAP = {"7d": timedelta(days=7), "14d": timedelta(days=14), "30d": timedelta(days=30)}
_HEATMAP_HOURS = [f"{h:02d}:00" for h in range(5, 24)]  # 05:00 … 23:00


def _parse_range(range_param: str) -> timedelta:
    if range_param not in _VALID_RANGES:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INVALID_RANGE",
                "detail": "range must be one of: 7d, 14d, 30d",
                "recoverable": True,
            },
        )
    return _RANGE_MAP[range_param]


def _cutoff(delta: timedelta) -> str:
    """ISO-8601 UTC string for (now - delta), used in DB text timestamp comparisons."""
    return (datetime.now(UTC) - delta).isoformat()


# ── GET /api/v1/analytics/exceptions ─────────────────────────────────────────

@router.get("/exceptions", response_model=list[ExceptionRecord])
async def get_exceptions(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> list[ExceptionRecord]:
    delta = _parse_range(range_param)
    cutoff = _cutoff(delta)

    rows = await db.execute(
        text("""
            SELECT
                event_id,
                journey_id,
                vehicle_id,
                severity,
                payload,
                timestamp
            FROM events
            WHERE event_type = 'CAPACITY_EXCEPTION'
              AND timestamp >= :cutoff
            ORDER BY timestamp DESC
        """),
        {"cutoff": cutoff},
    )

    records: list[ExceptionRecord] = []
    for row in rows:
        p = row.payload if isinstance(row.payload, dict) else {}
        coach_peaks = [
            CoachPeak(coach_id=cp.get("coach_id", ""), peak_pct=float(cp.get("peak_pct", 0)))
            for cp in (p.get("coach_peaks") or [])
        ]
        records.append(
            ExceptionRecord(
                exception_id=row.event_id,
                route=p.get("route", ""),
                train_id=row.vehicle_id,
                departure=p.get("departure", ""),
                date=row.timestamp[:10] if row.timestamp else "",
                status=p.get("status", "unreviewed"),
                severity=row.severity,
                coach_peaks=coach_peaks,
                trend=[float(v) for v in (p.get("trend") or [])],
                conrad_flag=None,
            )
        )
    return records


# ── GET /api/v1/analytics/occupancy-heatmap ───────────────────────────────────

@router.get("/occupancy-heatmap", response_model=HeatmapResponse)
async def get_occupancy_heatmap(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    delta = _parse_range(range_param)
    cutoff = _cutoff(delta)

    rows = await db.execute(
        text("""
            SELECT
                j.route_name,
                EXTRACT(HOUR FROM CAST(e.timestamp AS TIMESTAMPTZ)) AS hour,
                AVG((e.payload->>'occupancy_pct')::float) AS avg_pct
            FROM events e
            JOIN journeys j ON j.journey_id = e.journey_id
            WHERE e.event_type = 'OCCUPANCY_UPDATE'
              AND e.timestamp >= :cutoff
              AND e.payload->>'occupancy_pct' IS NOT NULL
            GROUP BY j.route_name, hour
        """),
        {"cutoff": cutoff},
    )

    # Build route x hour map
    data: dict[str, dict[int, float]] = {}
    for row in rows:
        route = row.route_name or "unknown"
        hour = int(row.hour)
        data.setdefault(route, {})[hour] = float(row.avg_pct)

    routes = sorted(data.keys())
    cells: list[list[float | None]] = []
    for route in routes:
        row_cells: list[float | None] = []
        for h in range(5, 24):
            val = data[route].get(h)
            row_cells.append(round(val, 1) if val is not None else None)
        cells.append(row_cells)

    return HeatmapResponse(routes=routes, hours=_HEATMAP_HOURS, cells=cells)


# ── GET /api/v1/analytics/dwell-time ─────────────────────────────────────────

@router.get("/dwell-time", response_model=list[DwellStationRecord])
async def get_dwell_time(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> list[DwellStationRecord]:
    delta = _parse_range(range_param)
    cutoff = _cutoff(delta)

    rows = await db.execute(
        text("""
            SELECT
                payload->>'station'                             AS station,
                AVG((payload->>'scheduled_sec')::float)        AS scheduled_sec,
                AVG((payload->>'actual_sec')::float)           AS actual_sec,
                COUNT(*) FILTER (
                    WHERE (payload->>'breach')::boolean IS TRUE
                )                                              AS breach_count,
                AVG((payload->>'occupancy_pct')::float)        AS occupancy_pct
            FROM events
            WHERE event_type = 'DWELL_EVENT'
              AND timestamp >= :cutoff
              AND payload->>'station' IS NOT NULL
            GROUP BY payload->>'station'
            ORDER BY AVG((payload->>'actual_sec')::float) DESC
        """),
        {"cutoff": cutoff},
    )

    return [
        DwellStationRecord(
            station=row.station,
            scheduled_sec=float(row.scheduled_sec or 0),
            actual_sec=float(row.actual_sec or 0),
            breach_count=int(row.breach_count or 0),
            occupancy_pct=float(row.occupancy_pct) if row.occupancy_pct is not None else None,
        )
        for row in rows
    ]


# ── GET /api/v1/analytics/detection-quality ──────────────────────────────────

@router.get("/detection-quality", response_model=DetectionQualityResponse)
async def get_detection_quality(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> DetectionQualityResponse:
    delta = _parse_range(range_param)
    cutoff = _cutoff(delta)

    # KPI aggregates
    kpi_row = await db.execute(
        text("""
            SELECT
                COUNT(*)                                          AS total_events,
                COUNT(*) FILTER (
                    WHERE (payload->>'fp_flag')::boolean IS TRUE
                )                                                 AS total_fp,
                AVG((payload->>'confidence')::float)             AS avg_confidence
            FROM events
            WHERE event_type = 'INFERENCE_RESULT'
              AND timestamp >= :cutoff
        """),
        {"cutoff": cutoff},
    )
    kpi = kpi_row.fetchone()
    total_events = int(kpi.total_events or 0) if kpi is not None else 0
    total_fp = int(kpi.total_fp or 0) if kpi is not None else 0
    avg_confidence = (
        float(kpi.avg_confidence) if kpi is not None and kpi.avg_confidence is not None else None
    )

    # fp_rate: null iff both totals are zero
    fp_rate: float | None = None
    if total_events > 0:
        fp_rate = total_fp / total_events

    # Fleet uptime — fraction of active journeys with at least one INFERENCE_RESULT in range
    uptime_row = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT j.journey_id)                     AS total_journeys,
                COUNT(DISTINCT e.journey_id)                     AS active_journeys
            FROM journeys j
            LEFT JOIN events e
                ON e.journey_id = j.journey_id
               AND e.event_type = 'INFERENCE_RESULT'
               AND e.timestamp >= :cutoff
        """),
        {"cutoff": cutoff},
    )
    up = uptime_row.fetchone()
    total_j = int(up.total_journeys or 0) if up is not None else 0
    active_j = int(up.active_journeys or 0) if up is not None else 0
    fleet_uptime_pct = (active_j / total_j * 100.0) if total_j > 0 else None

    # Daily bars
    daily_rows = await db.execute(
        text("""
            SELECT
                LEFT(timestamp, 10)                              AS date,
                COUNT(*)                                         AS total_events,
                COUNT(*) FILTER (
                    WHERE (payload->>'fp_flag')::boolean IS TRUE
                )                                                AS fp_count
            FROM events
            WHERE event_type = 'INFERENCE_RESULT'
              AND timestamp >= :cutoff
            GROUP BY LEFT(timestamp, 10)
            ORDER BY date ASC
        """),
        {"cutoff": cutoff},
    )
    daily_bars = [
        DailyBar(
            date=row.date,
            total_events=int(row.total_events),
            fp_count=int(row.fp_count),
        )
        for row in daily_rows
    ]

    # Per-train uptime
    train_rows = await db.execute(
        text("""
            SELECT
                vehicle_id,
                CASE
                    WHEN COUNT(DISTINCT journey_id) = 0 THEN 0.0
                    ELSE COUNT(DISTINCT CASE WHEN event_type = 'INFERENCE_RESULT'
                                              AND timestamp >= :cutoff
                                         THEN journey_id END)::float
                       / COUNT(DISTINCT journey_id) * 100.0
                END AS uptime_pct
            FROM events
            WHERE timestamp >= :cutoff
            GROUP BY vehicle_id
            ORDER BY vehicle_id
        """),
        {"cutoff": cutoff},
    )
    per_train = [
        PerTrainUptime(train_id=row.vehicle_id, uptime_pct=float(row.uptime_pct or 0))
        for row in train_rows
    ]

    return DetectionQualityResponse(
        kpi=DetectionKpi(
            total_events=total_events,
            fp_rate=fp_rate,
            avg_confidence=avg_confidence,
            fleet_uptime_pct=fleet_uptime_pct,
        ),
        daily_bars=daily_bars,
        per_train_uptime=per_train,
    )


# ── GET /api/v1/analytics/system-health ──────────────────────────────────────

@router.get("/system-health", response_model=list[TrainHealthRecord])
async def get_system_health(
    db: AsyncSession = Depends(get_db),
) -> list[TrainHealthRecord]:
    # Latest SYSTEM_HEALTH event per vehicle
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (vehicle_id)
                vehicle_id,
                journey_id,
                payload,
                timestamp
            FROM events
            WHERE event_type = 'SYSTEM_HEALTH'
            ORDER BY vehicle_id, timestamp DESC
        """),
    )

    records: list[TrainHealthRecord] = []
    for row in rows:
        p = row.payload if isinstance(row.payload, dict) else {}

        app_detail = [
            AppDetailItem(
                container=item.get("container", ""),
                status=item.get("status", "unknown"),
                last_healthy=item.get("last_healthy", row.timestamp or ""),
            )
            for item in (p.get("appDetail") or [])
        ]

        device_detail = [
            DeviceDetailItem(
                device=item.get("device", ""),
                status=item.get("status", "unknown"),
                temperature_c=(
                    float(item["temperature_c"]) if item.get("temperature_c") is not None else None
                ),
            )
            for item in (p.get("deviceDetail") or [])
        ]

        conn_raw = p.get("connectivity") or {}
        connectivity = ConnectivityInfo(
            lte_status=conn_raw.get("lte_status", "unknown"),
            wifi_status=conn_raw.get("wifi_status", "unknown"),
            last_sync=conn_raw.get("last_sync", row.timestamp or ""),
        )

        last_healthy = (
            p.get("last_healthy") or row.timestamp or datetime.now(UTC).isoformat()
        )

        records.append(
            TrainHealthRecord(
                train_id=row.vehicle_id,
                journey_id=row.journey_id,
                cctvStatus=p.get("cctvStatus", "unknown"),
                appStatus=p.get("appStatus", "unknown"),
                deviceStatus=p.get("deviceStatus", "unknown"),
                connectivityStatus=p.get("connectivityStatus", "unknown"),
                last_healthy=last_healthy,
                appDetail=app_detail,
                deviceDetail=device_detail,
                connectivity=connectivity,
            )
        )
    return records
