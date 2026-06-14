"""AI-quality resolution-rates computation (10-5 AC1).

Two orthogonal per-alert-class rates over the resolved escalation_audit rows in a
rolling window (default 7 days — calibration needs a longer window than the 1-hour
live tile):

    no_action_rate   = resolved-with-zero-action-tags / resolved_total
    explicit_fp_rate  = resolved-with-tag('false_alarm') / resolved_total

Both numerators and the denominator come from the SAME `escalation_audit` table the
10-2 funnel already aggregates — `transition = 'resolved'` rows carry the canonical
`action_tags` JSONB array written at resolve time. No join, no migration.

D1: `false_alarm` IS the shipped false-positive signal (cloud_backend.api.escalations
    ACTION_TAG_KEYS) — explicit_fp_rate keys on it; there is no `false_positive` tag.
D2: there is no auto-resolved-before-ack rate — resolve hard-requires a prior ack in
    the shipped lifecycle (409 otherwise), so nothing auto-resolves; that epic rate
    would be structurally 0/undefined and is intentionally absent.

The window is half-open [from, to); both bounds default in SQL (COALESCE against the
DB clock) to stay clock-skew-proof, exactly like routes/escalations_audit.py — a
Python-side now() default would drop rows stamped by Postgres NOW() under clock skew.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.ai_quality import AlertQualityRates

# Canonical key for the shipped false-positive signal (D1). Single source of truth
# is cloud_backend.api.escalations.ACTION_TAG_KEYS; duplicated as a literal here only
# to keep the SQL self-contained — a rename there is a contract change that would
# surface in that module's tests first.
_FALSE_ALARM_KEY = "false_alarm"


async def resolution_rates(
    db: AsyncSession,
    *,
    dt_from: datetime | None,
    dt_to: datetime | None,
) -> list[AlertQualityRates]:
    """Return per-alert-class no-action and explicit-FP rates over the window.

    Rows are ordered by alert_code. A class with resolved_total == 0 never appears
    (it has no resolved rows in window); a class that appears always has
    resolved_total >= 1, so the per-row rates are never None in practice — but the
    model keeps them Optional so an explicit zero-denominator (e.g. a future caller)
    is representable rather than a divide-by-zero.
    """
    window_clause = (
        "t_event >= COALESCE(:from, NOW() - INTERVAL '7 days') "
        "AND t_event < COALESCE(:to, NOW())"
    )
    rows = await db.execute(
        text(f"""
            SELECT
                alert_code,
                COUNT(*) AS resolved_total,
                COUNT(*) FILTER (
                    WHERE action_tags IS NULL
                       OR jsonb_typeof(action_tags) <> 'array'
                       OR jsonb_array_length(action_tags) = 0
                ) AS no_action_count,
                COUNT(*) FILTER (
                    WHERE action_tags IS NOT NULL
                      AND jsonb_typeof(action_tags) = 'array'
                      AND action_tags ? :false_alarm
                ) AS false_alarm_count
            FROM escalation_audit
            WHERE transition = 'resolved'
              AND {window_clause}
            GROUP BY alert_code
            ORDER BY alert_code
        """),
        {"from": dt_from, "to": dt_to, "false_alarm": _FALSE_ALARM_KEY},
    )

    out: list[AlertQualityRates] = []
    for r in rows:
        total = int(r.resolved_total)
        no_action = int(r.no_action_count)
        false_alarm = int(r.false_alarm_count)
        out.append(
            AlertQualityRates(
                alert_code=r.alert_code,
                resolved_total=total,
                no_action_count=no_action,
                # None only on a zero denominator (cannot occur from this GROUP BY,
                # but the guard keeps the contract honest — the NULL/zero-denominator
                # trap from deferred-work.md).
                no_action_rate=(no_action / total) if total > 0 else None,
                false_alarm_count=false_alarm,
                explicit_fp_rate=(false_alarm / total) if total > 0 else None,
            )
        )
    return out
