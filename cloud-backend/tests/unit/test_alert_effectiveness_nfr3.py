"""Unit tests for the NFR3 breach flag in the weekly report (10-5 AC6) — no DB.

_nfr3_breaches is pure over already-aggregated _Funnel rows, so the flag/no-flag/
zero-resolve cases are checkable without Postgres."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cloud_backend.services.alert_effectiveness_report import (
    _NFR3_FP_THRESHOLD,
    _nfr3_breaches,
    _render,
)


def _funnel(alert_code: str, resolved: int, false_alarm: int):  # type: ignore[no-untyped-def]
    fp_rate = (false_alarm / resolved) if resolved > 0 else None
    return {
        "alert_code": alert_code,
        "raised": resolved,
        "acknowledged": resolved,
        "resolved": resolved,
        "dismissed": 0,
        "false_alarm": false_alarm,
        "ack_rate": 1.0 if resolved else None,
        "explicit_fp_rate": fp_rate,
        "median_ack_s": None,
        "p95_ack_s": None,
    }


@pytest.mark.unit
def test_class_at_or_above_5pct_is_flagged() -> None:
    # 2 false alarms of 10 resolved = 20% >= 5% → breach.
    breaches = _nfr3_breaches([_funnel("slip_fall", resolved=10, false_alarm=2)])
    assert [b["alert_code"] for b in breaches] == ["slip_fall"]


@pytest.mark.unit
def test_class_below_5pct_is_not_flagged() -> None:
    # 3 of 71 = 4.2% < 5% → not a breach.
    assert _nfr3_breaches([_funnel("door_obstruction", resolved=71, false_alarm=3)]) == []


@pytest.mark.unit
def test_exactly_5pct_is_flagged() -> None:
    # boundary: 1 of 20 = 5.0% → flagged (>= threshold).
    breaches = _nfr3_breaches([_funnel("door_fault", resolved=20, false_alarm=1)])
    assert len(breaches) == 1
    assert breaches[0]["explicit_fp_rate"] == pytest.approx(_NFR3_FP_THRESHOLD)


@pytest.mark.unit
def test_zero_resolves_is_not_flagged_and_does_not_divide_by_zero() -> None:
    # raised but never resolved → explicit_fp_rate None → not a breach, no error.
    assert _nfr3_breaches([_funnel("fire", resolved=0, false_alarm=0)]) == []


# ── _render NFR3 section (AC6 end-to-end markdown) ──────────────────────────────

_FROM = datetime(2026, 6, 8, tzinfo=UTC)
_TO = datetime(2026, 6, 15, tzinfo=UTC)


@pytest.mark.unit
def test_render_lists_breaching_class_excludes_below_threshold() -> None:
    funnels = [
        _funnel("slip_fall", resolved=10, false_alarm=2),       # 20% → breach
        _funnel("door_obstruction", resolved=71, false_alarm=3),  # 4.2% → not
        _funnel("fire", resolved=0, false_alarm=0),              # no resolves → not
    ]
    md = _render(2026, 24, _FROM, _TO, funnels, [])  # type: ignore[arg-type]
    assert "## NFR3 breaches (explicit false-positive rate ≥ 5%)" in md
    # the breaching class appears in the breach table with its counts
    assert "| slip_fall | 20% | 2 | 10 |" in md
    # a non-breaching class is NOT listed in the breach section
    breach_section = md.split("## NFR3 breaches")[1].split("## ")[0]
    assert "door_obstruction" not in breach_section
    assert "fire" not in breach_section


@pytest.mark.unit
def test_render_empty_state_when_no_breaches() -> None:
    funnels = [_funnel("door_obstruction", resolved=71, false_alarm=3)]  # 4.2%
    md = _render(2026, 24, _FROM, _TO, funnels, [])  # type: ignore[arg-type]
    assert "_No alert class breached NFR3 this window._" in md
