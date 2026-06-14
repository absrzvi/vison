"""Fleet KPI endpoints (E10-S4 AC4).

GET /api/v1/kpi/delay-minutes-avoided — fleet-wide delay-minutes avoided over the
trailing 24h, computed from escalations resolved in-time (before scheduled
departure). Read-only; auth via X-API-Key like the escalation-audit funnel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import get_current_user
from ..api.kpi import DelayMinutesAvoided
from ..database import get_db
from ..services.delay_minutes_avoided import delay_minutes_avoided

router = APIRouter(prefix="/api/v1/kpi", dependencies=[Security(get_current_user)])

_WINDOW_HOURS = 24


@router.get("/delay-minutes-avoided", response_model=DelayMinutesAvoided)
async def get_delay_minutes_avoided(
    db: AsyncSession = Depends(get_db),
) -> DelayMinutesAvoided:
    minutes = await delay_minutes_avoided(db, window_hours=_WINDOW_HOURS)
    return DelayMinutesAvoided(
        delay_minutes_avoided=minutes,
        window_hours=_WINDOW_HOURS,
    )
