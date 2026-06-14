"""Pydantic response models for the AI-quality resolution-rates endpoint (10-5 AC1).

Two orthogonal rates per alert class — never an aggregated single number (AC3).
Each rate is float|None (None when resolved_total == 0, the divide-by-zero guard)
and is reported with its integer count denominator so small-sample noise is visible.

D1: explicit_fp_rate is keyed on the SHIPPED `false_alarm` canonical action tag, not a
    new `false_positive` tag (none exists — see story Decisions).
D2: there is deliberately NO auto_resolved_before_ack rate — nothing auto-resolves an
    escalation before acknowledgement in the shipped lifecycle, so that rate would be
    structurally undefined.
"""
from __future__ import annotations

from pydantic import BaseModel


class AlertQualityRates(BaseModel):
    """Per-alert-class resolution-quality rates over a rolling window."""

    alert_code: str
    resolved_total: int
    no_action_count: int
    no_action_rate: float | None
    false_alarm_count: int
    explicit_fp_rate: float | None
