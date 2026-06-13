"""Pydantic response model for the escalation-audit funnel (E10-S2 AC3)."""
from __future__ import annotations

from pydantic import BaseModel


class AlertFunnel(BaseModel):
    """Per-alert_code lifecycle funnel over the requested window.

    Counts are per-transition (escalation_audit is append-only, one row per
    transition). Ack-latency percentiles are seconds between t_fired and the
    acknowledged transition's t_event; null when no acknowledged rows fall in the
    window. action_tag_distribution maps canonical action-tag keys → count over
    the resolved rows (display labels are never used, so historical funnels
    survive UI re-wording)."""

    alert_code: str
    count_raised: int
    count_acknowledged: int
    count_resolved: int
    count_silently_dismissed: int
    median_t_ack_seconds: float | None
    p95_t_ack_seconds: float | None
    action_tag_distribution: dict[str, int]
