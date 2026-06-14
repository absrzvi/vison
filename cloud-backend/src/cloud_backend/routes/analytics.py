"""Analytics REST endpoints for E3-S1: five date-range-aware endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.analytics import (
    AppDetailItem,
    CoachPeak,
    ConnectivityInfo,
    ConradFlag,
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
from ..api.auth import get_current_user
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", dependencies=[Security(get_current_user)])

_VALID_RANGES = {"7d", "14d", "30d"}
_RANGE_MAP = {"7d": timedelta(days=7), "14d": timedelta(days=14), "30d": timedelta(days=30)}
_HEATMAP_HOURS = [f"{h:02d}:00" for h in range(5, 24)]  # 05:00 to 23:00


def _parse_range(range_param: str) -> timedelta:
    if range_param not in _VALID_RANGES:
        raise ValueError(range_param)
    return _RANGE_MAP[range_param]


def _cutoff_dt(delta: timedelta) -> datetime:
    """UTC datetime passed as timestamptz bind parameter (asyncpg requires datetime, not str)."""
    return datetime.now(UTC) - delta


def _invalid_range_response() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "INVALID_RANGE",
            "detail": "range must be one of: 7d, 14d, 30d",
            "recoverable": True,
        },
    )


# ── GET /api/v1/analytics/exceptions ─────────────────────────────────────────

@router.get("/exceptions", response_model=None)
async def get_exceptions(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | list[ExceptionRecord]:
    try:
        delta = _parse_range(range_param)
    except ValueError:
        return _invalid_range_response()
    cutoff = _cutoff_dt(delta)

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
              AND CAST(timestamp AS timestamptz) >= :cutoff
            ORDER BY CAST(timestamp AS timestamptz) DESC
        """),
        {"cutoff": cutoff},
    )

    records: list[ExceptionRecord] = []
    for row in rows:
        p = row.payload if isinstance(row.payload, dict) else {}
        coach_peaks = [
            CoachPeak(
                coach_id=str(cp.get("coach_id", "")),
                peak_pct=float(cp.get("peak_pct") or 0),
            )
            for cp in (p.get("coach_peaks") or [])
            if isinstance(cp, dict)
        ]
        raw_trend = p.get("trend") or []
        trend_vals: list[float] = []
        for v in raw_trend:
            try:
                trend_vals.append(float(v))
            except (TypeError, ValueError):
                trend_vals.append(0.0)
        # Spec requires exactly 7 daily peak values
        if len(trend_vals) > 7:
            trend_vals = trend_vals[-7:]
        elif len(trend_vals) < 7:
            trend_vals = ([0.0] * (7 - len(trend_vals))) + trend_vals

        raw_flag = p.get("conrad_flag")
        conrad_flag: ConradFlag | None = None
        if isinstance(raw_flag, dict) and raw_flag.get("flag_id"):
            conrad_flag = ConradFlag(
                flag_id=str(raw_flag["flag_id"]),
                note=str(raw_flag["note"]) if raw_flag.get("note") else None,
            )

        records.append(
            ExceptionRecord(
                exception_id=row.event_id,
                route=p.get("route", ""),
                train_id=row.vehicle_id,
                departure=p.get("departure", ""),
                date=str(row.timestamp)[:10] if row.timestamp else "",
                status=p.get("status", "unreviewed"),
                severity=row.severity,
                coach_peaks=coach_peaks,
                trend=trend_vals,
                conrad_flag=conrad_flag,
            )
        )
    return records


# ── GET /api/v1/analytics/occupancy-heatmap ───────────────────────────────────

@router.get("/occupancy-heatmap", response_model=None)
async def get_occupancy_heatmap(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | HeatmapResponse:
    try:
        delta = _parse_range(range_param)
    except ValueError:
        return _invalid_range_response()
    cutoff = _cutoff_dt(delta)

    rows = await db.execute(
        text(r"""
            SELECT
                j.route_name,
                EXTRACT(HOUR FROM CAST(e.timestamp AS TIMESTAMPTZ)) AS hour,
                AVG(NULLIF(e.payload->>'occupancy_pct', '')::float)  AS avg_pct
            FROM events e
            JOIN journeys j ON j.journey_id = e.journey_id
            WHERE e.event_type = 'OCCUPANCY_UPDATE'
              AND CAST(e.timestamp AS timestamptz) >= :cutoff
              AND e.payload->>'occupancy_pct' IS NOT NULL
              AND e.payload->>'occupancy_pct' ~ '^-?[0-9]+(\.[0-9]+)?$'
              AND e.timestamp ~ '^\d{4}-\d{2}-\d{2}T'
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

@router.get("/dwell-time", response_model=None)
async def get_dwell_time(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | list[DwellStationRecord]:
    try:
        delta = _parse_range(range_param)
    except ValueError:
        return _invalid_range_response()
    cutoff = _cutoff_dt(delta)

    rows = await db.execute(
        text("""
            SELECT
                payload->>'station'                                          AS station,
                AVG(NULLIF(payload->>'scheduled_sec', '')::float)           AS scheduled_sec,
                AVG(NULLIF(payload->>'actual_sec', '')::float)              AS actual_sec,
                COUNT(*) FILTER (
                    WHERE payload->>'breach' IN ('true', '1', 'yes', 'True')
                )                                                            AS breach_count,
                AVG(NULLIF(payload->>'occupancy_pct', '')::float)           AS occupancy_pct
            FROM events
            WHERE event_type = 'DWELL_EVENT'
              AND CAST(timestamp AS timestamptz) >= :cutoff
              AND payload->>'station' IS NOT NULL
            GROUP BY payload->>'station'
            ORDER BY AVG(NULLIF(payload->>'actual_sec', '')::float) DESC
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

@router.get("/detection-quality", response_model=None)
async def get_detection_quality(
    range_param: str = Query(default="7d", alias="range"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | DetectionQualityResponse:
    try:
        delta = _parse_range(range_param)
    except ValueError:
        return _invalid_range_response()
    cutoff = _cutoff_dt(delta)

    # KPI aggregates
    kpi_row = await db.execute(
        text("""
            SELECT
                COUNT(*)                                                      AS total_events,
                COUNT(*) FILTER (
                    WHERE payload->>'fp_flag' IN ('true', '1', 'yes', 'True')
                )                                                             AS total_fp,
                AVG(NULLIF(payload->>'confidence', '')::float)               AS avg_confidence
            FROM events
            WHERE event_type = 'INFERENCE_RESULT'
              AND CAST(timestamp AS timestamptz) >= :cutoff
        """),
        {"cutoff": cutoff},
    )
    kpi = kpi_row.fetchone()
    total_events = int(kpi.total_events or 0) if kpi is not None else 0
    total_fp = int(kpi.total_fp or 0) if kpi is not None else 0
    avg_confidence = (
        float(kpi.avg_confidence) if kpi is not None and kpi.avg_confidence is not None else None
    )

    # fp_rate: null iff total_events == 0
    fp_rate: float | None = None
    if total_events > 0:
        fp_rate = total_fp / total_events

    # Fleet uptime — journeys within range that had at least one INFERENCE_RESULT
    uptime_row = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT j.journey_id)                     AS total_journeys,
                COUNT(DISTINCT e.journey_id)                     AS active_journeys
            FROM journeys j
            LEFT JOIN events e
                ON e.journey_id = j.journey_id
               AND e.event_type = 'INFERENCE_RESULT'
               AND CAST(e.timestamp AS timestamptz) >= :cutoff
            WHERE j.start_time IS NULL
               OR CAST(j.start_time AS timestamptz) >= :cutoff
        """),
        {"cutoff": cutoff},
    )
    up = uptime_row.fetchone()
    total_j = int(up.total_journeys or 0) if up is not None else 0
    active_j = int(up.active_journeys or 0) if up is not None else 0
    fleet_uptime_pct = (active_j / total_j * 100.0) if total_j > 0 else None

    # Daily bars — group by UTC date prefix
    daily_rows = await db.execute(
        text("""
            SELECT
                CAST(CAST(timestamp AS timestamptz) AT TIME ZONE 'UTC' AS DATE)::text AS date,
                COUNT(*)                                                       AS total_events,
                COUNT(*) FILTER (
                    WHERE payload->>'fp_flag' IN ('true', '1', 'yes', 'True')
                )                                                                      AS fp_count
            FROM events
            WHERE event_type = 'INFERENCE_RESULT'
              AND CAST(timestamp AS timestamptz) >= :cutoff
            GROUP BY 1
            ORDER BY 1 ASC
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

    # Per-train uptime — join journeys so trains with no events appear
    train_rows = await db.execute(
        text("""
            SELECT
                j.vehicle_id,
                COUNT(DISTINCT j.journey_id)                     AS total_journeys,
                COUNT(DISTINCT e.journey_id)                     AS active_journeys
            FROM journeys j
            LEFT JOIN events e
                ON e.journey_id = j.journey_id
               AND e.event_type = 'INFERENCE_RESULT'
               AND CAST(e.timestamp AS timestamptz) >= :cutoff
            WHERE j.start_time IS NULL
               OR CAST(j.start_time AS timestamptz) >= :cutoff
            GROUP BY j.vehicle_id
            ORDER BY j.vehicle_id
        """),
        {"cutoff": cutoff},
    )
    per_train = [
        PerTrainUptime(
            train_id=row.vehicle_id,
            uptime_pct=(
                int(row.active_journeys) / int(row.total_journeys) * 100.0
                if int(row.total_journeys) > 0 else 0.0
            ),
        )
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
    # Latest SYSTEM_HEALTH event per vehicle (DISTINCT ON requires timestamptz sort)
    rows = await db.execute(
        text(r"""
            SELECT DISTINCT ON (vehicle_id)
                vehicle_id,
                journey_id,
                payload,
                timestamp
            FROM events
            WHERE event_type = 'SYSTEM_HEALTH'
              AND timestamp ~ '^\d{4}-\d{2}-\d{2}T'
            ORDER BY vehicle_id, CAST(timestamp AS timestamptz) DESC
        """),
    )

    records: list[TrainHealthRecord] = []
    for row in rows:
        p = row.payload if isinstance(row.payload, dict) else {}

        app_detail = [
            AppDetailItem(
                container=str(item.get("container", "")),
                status=str(item.get("status", "unknown")),
                last_healthy=str(item.get("last_healthy") or str(row.timestamp or "")),
            )
            for item in (p.get("appDetail") or [])
            if isinstance(item, dict)
        ]

        device_detail = [
            DeviceDetailItem(
                device=str(item.get("device", "")),
                status=str(item.get("status", "unknown")),
                temperature_c=(
                    float(item["temperature_c"])
                    if item.get("temperature_c") is not None
                    and str(item["temperature_c"]).replace(".", "", 1).lstrip("-").isdigit()
                    else None
                ),
            )
            for item in (p.get("deviceDetail") or [])
            if isinstance(item, dict)
        ]

        conn_raw = p.get("connectivity") or {}
        if not isinstance(conn_raw, dict):
            conn_raw = {}
        connectivity = ConnectivityInfo(
            lte_status=str(conn_raw.get("lte_status", "unknown")),
            wifi_status=str(conn_raw.get("wifi_status", "unknown")),
            last_sync=str(conn_raw.get("last_sync") or str(row.timestamp or "")),
        )

        # last_healthy: prefer explicit payload field, then event timestamp; never fabricate
        last_healthy = p.get("last_healthy") or str(row.timestamp or "")

        records.append(
            TrainHealthRecord(
                train_id=row.vehicle_id,
                journey_id=row.journey_id,
                cctvStatus=str(p.get("cctvStatus", "unknown")),
                appStatus=str(p.get("appStatus", "unknown")),
                deviceStatus=str(p.get("deviceStatus", "unknown")),
                connectivityStatus=str(p.get("connectivityStatus", "unknown")),
                last_healthy=last_healthy,
                appDetail=app_detail,
                deviceDetail=device_detail,
                connectivity=connectivity,
            )
        )
    return records
