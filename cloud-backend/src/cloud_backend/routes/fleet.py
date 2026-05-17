from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Security
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/fleet", dependencies=[Security(require_api_key)])

_SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}
_ALERT_TYPES = {"ALARM_ACTIVE", "ALERT_RAISED", "VESTIBULE_CONGESTION", "DOOR_OBSTRUCTION", "UNATTENDED_BAG"}


class CarSummary(BaseModel):
    car_id: str
    occupancy_pct: float | None = None
    worst_severity: str


class TrainSummary(BaseModel):
    journey_id: str
    vehicle_id: str
    trip_number: str
    worst_severity: str
    cars: list[CarSummary]


class FleetOverview(BaseModel):
    trains: list[TrainSummary]
    total: int


@router.get("/overview", response_model=FleetOverview)
async def fleet_overview(db: AsyncSession = Depends(get_db)) -> FleetOverview:
    # Latest OCCUPANCY_UPDATE per (journey_id, car_id)
    occ_rows = await db.execute(
        text("""
            SELECT DISTINCT ON (e.journey_id, (e.payload->>'car_id'))
                e.journey_id,
                e.payload->>'car_id'   AS car_id,
                (e.payload->>'occupancy_pct')::float AS occupancy_pct
            FROM events e
            WHERE e.event_type = 'OCCUPANCY_UPDATE'
            ORDER BY e.journey_id, (e.payload->>'car_id'), e.source_timestamp DESC
        """)
    )
    occ_by_journey: dict[str, dict[str, float | None]] = {}
    for row in occ_rows:
        occ_by_journey.setdefault(row.journey_id, {})[row.car_id] = row.occupancy_pct

    # Worst severity per (journey_id, car_id) from unresolved alerts
    sev_rows = await db.execute(
        text("""
            SELECT e.journey_id,
                   e.payload->>'car_id' AS car_id,
                   e.severity
            FROM events e
            WHERE e.event_type = ANY(ARRAY['ALARM_ACTIVE','ALERT_RAISED',
                                           'VESTIBULE_CONGESTION','DOOR_OBSTRUCTION',
                                           'UNATTENDED_BAG'])
        """)
    )
    sev_by_journey: dict[str, dict[str, str]] = {}
    for row in sev_rows:
        car_id = row.car_id or "unknown"
        cur = sev_by_journey.setdefault(row.journey_id, {}).get(car_id, "info")
        if _SEVERITY_RANK.get(row.severity, 0) > _SEVERITY_RANK.get(cur, 0):
            sev_by_journey[row.journey_id][car_id] = row.severity

    # Active journeys
    journey_rows = await db.execute(
        text("""
            SELECT journey_id, vehicle_id, trip_number
            FROM journeys
            WHERE end_time IS NULL
            ORDER BY start_time DESC
        """)
    )
    journeys = list(journey_rows)

    trains: list[TrainSummary] = []
    for j in journeys:
        car_occ = occ_by_journey.get(j.journey_id, {})
        car_sev = sev_by_journey.get(j.journey_id, {})
        all_cars = set(car_occ) | set(car_sev)
        cars = [
            CarSummary(
                car_id=car_id,
                occupancy_pct=car_occ.get(car_id),
                worst_severity=car_sev.get(car_id, "info"),
            )
            for car_id in sorted(all_cars)
        ]
        worst: str = max(
            (c.worst_severity for c in cars),
            key=lambda s: _SEVERITY_RANK.get(s, 0),
            default="info",
        )
        trains.append(
            TrainSummary(
                journey_id=j.journey_id,
                vehicle_id=j.vehicle_id,
                trip_number=j.trip_number,
                worst_severity=worst,
                cars=cars,
            )
        )

    return FleetOverview(trains=trains, total=len(trains))
