"""Delay-minutes-avoided KPI computation (E10-S4 AC4).

Sums seconds_to_departure / 60 over escalations that were resolved IN-TIME —
i.e. reached status='resolved' within the trailing window, carry a non-NULL
seconds_to_departure (the alert was pre-departure when raised), and whose
resolve happened before the scheduled departure:

    t_resolve < t_fired + (seconds_to_departure seconds)

The window is computed entirely in SQL against the DB clock (NOW()), matching
the escalation-audit funnel's skew-proof pattern: defaulting the upper bound to
a Python now() would drop rows whose t_resolve was stamped by Postgres if the
app and DB clocks skew. NULL-seconds rows are excluded by the WHERE, so a
feed-degraded alert never counts as a zero-minute save.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def delay_minutes_avoided(db: AsyncSession, *, window_hours: int) -> float:
    """Return the fleet-wide delay-minutes avoided over the trailing window."""
    row = await db.execute(
        text("""
            SELECT COALESCE(SUM(seconds_to_departure) / 60.0, 0.0) AS minutes
            FROM escalations
            WHERE status = 'resolved'
              AND seconds_to_departure IS NOT NULL
              AND t_resolve IS NOT NULL
              AND t_resolve >= NOW() - make_interval(hours => :window_hours)
              AND t_resolve < t_fired + make_interval(secs => seconds_to_departure)
        """),
        {"window_hours": window_hours},
    )
    return float(row.scalar_one())
