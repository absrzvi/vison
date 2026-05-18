"""Synthetic VLAN mock service for local development.

Handles three routes:
  GET /apc/occupancy/{car_id}   → OccupancyReading JSON (VLAN 8)
  GET /pis/schedule             → PisState JSON (VLAN 3)
  GET /reservation/reservations → per-coach seat counts (VLAN 6)

Run via docker-compose.dev.yml mock-vlans service.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

app = FastAPI(title="OEBB VLAN Mock", version="0.1.0")

_OCCUPANCY: dict[str, dict[str, object]] = {
    "car-1": {"car_id": "car-1", "count": 45, "timestamp": "2026-05-19T10:00:00Z"},
    "car-2": {"car_id": "car-2", "count": 182, "timestamp": "2026-05-19T10:00:00Z"},
    "car-3": {"car_id": "car-3", "count": 71, "timestamp": "2026-05-19T10:00:00Z"},
    "car-4": {"car_id": "car-4", "count": 120, "timestamp": "2026-05-19T10:00:00Z"},
    "car-5": {"car_id": "car-5", "count": 33, "timestamp": "2026-05-19T10:00:00Z"},
}

_SCHEDULE: dict[str, object] = {
    "next_station": "Wien Hbf",
    "next_station_arrival_utc": "2026-05-19T12:00:00Z",
    "scheduled_departure": "2026-05-19T12:05:00Z",
    "actual_departure": "2026-05-19T12:05:00Z",
    "platform": "4",
    "delay_min": 0,
}

_RESERVATIONS: dict[str, int] = {
    "car-1": 38,
    "car-2": 160,
    "car-3": 60,
    "car-4": 110,
    "car-5": 25,
}


@app.get("/apc/occupancy/{car_id}")
async def get_occupancy(car_id: str) -> dict[str, object]:
    if car_id not in _OCCUPANCY:
        raise HTTPException(status_code=404, detail=f"Unknown car_id: {car_id}")
    return _OCCUPANCY[car_id]


@app.get("/pis/schedule")
async def get_schedule() -> dict[str, object]:
    return _SCHEDULE


@app.get("/reservation/reservations")
async def get_reservations() -> dict[str, int]:
    return _RESERVATIONS
