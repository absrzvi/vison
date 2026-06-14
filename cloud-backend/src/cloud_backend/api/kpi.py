"""Pydantic response model for the delay-minutes-avoided KPI (E10-S4 AC4)."""
from __future__ import annotations

from pydantic import BaseModel


class DelayMinutesAvoided(BaseModel):
    """Fleet-wide delay-minutes avoided over a trailing window.

    `delay_minutes_avoided` is the sum of seconds_to_departure / 60 over
    escalations that reached `resolved` within the window AND were resolved
    before their scheduled departure (an in-time action). NULL-seconds rows
    (alert not pre-departure, or PIS feed degraded) are excluded, not counted
    as zero saves."""

    delay_minutes_avoided: float
    window_hours: int
