"""Escalation-audit funnel endpoint (E10-S2 AC3).

GET /api/v1/escalations-audit?from=<iso>&to=<iso>&alert_code=<code>
Aggregates the append-only escalation_audit rows into per-alert_code lifecycle
funnels: transition counts, ack-latency percentiles, and the action-tag
distribution. All params optional; default window is the last 7 days.
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query, Security
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..api.escalations_audit import AlertFunnel
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/escalations-audit", dependencies=[Security(require_api_key)]
)


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 instant; tolerate a trailing Z. Raises ValueError on bad input."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Bind as timezone-aware UTC so the comparison against timestamptz is unambiguous.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _invalid_range_response() -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "INVALID_RANGE",
            "detail": "from/to must be ISO-8601 timestamps; from must not be after to",
            "recoverable": True,
        },
    )


@router.get("", response_model=None)
async def get_escalation_funnels(
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    alert_code: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse | list[AlertFunnel]:
    # Parse explicit bounds if given; otherwise leave NULL and let the window
    # default to the DB clock in SQL (COALESCE below). Defaulting `to` to a
    # Python now() would drop rows whose t_event was stamped by Postgres NOW()
    # if the app and DB clocks skew by a few ms — so the default window is
    # computed entirely in SQL to stay skew-proof.
    try:
        dt_from = _parse_iso(from_) if from_ is not None else None
        dt_to = _parse_iso(to) if to is not None else None
    except ValueError:
        return _invalid_range_response()
    if dt_from is not None and dt_to is not None and dt_from > dt_to:
        return _invalid_range_response()

    # WHERE: window is [COALESCE(:from, NOW()-7d), COALESCE(:to, NOW())].
    window_clause = (
        "t_event >= COALESCE(:from, NOW() - INTERVAL '7 days') "
        "AND t_event <= COALESCE(:to, NOW())"
    )
    params: dict[str, object | None] = {"from": dt_from, "to": dt_to}
    code_clause = ""
    if alert_code is not None:
        code_clause = "AND alert_code = :alert_code"
        params["alert_code"] = alert_code

    # Per-alert_code transition counts + ack-latency percentiles. PERCENTILE_CONT is
    # an ordered-set aggregate; FILTER restricts it to the acknowledged rows whose
    # latency = t_event - t_fired. Returns NULL when no acknowledged row is in window.
    funnel_rows = await db.execute(
        text(f"""
            SELECT
                alert_code,
                COUNT(*) FILTER (WHERE transition = 'raised')             AS count_raised,
                COUNT(*) FILTER (WHERE transition = 'acknowledged')       AS count_acknowledged,
                COUNT(*) FILTER (WHERE transition = 'resolved')           AS count_resolved,
                COUNT(*) FILTER (WHERE transition = 'silently_dismissed') AS count_dismissed,
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (t_event - t_fired))
                ) FILTER (WHERE transition = 'acknowledged')             AS median_t_ack,
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (t_event - t_fired))
                ) FILTER (WHERE transition = 'acknowledged')             AS p95_t_ack
            FROM escalation_audit
            WHERE {window_clause}
              {code_clause}
            GROUP BY alert_code
            ORDER BY alert_code
        """),
        params,
    )

    # action_tag_distribution: unnest the resolved rows' action_tags JSONB array and
    # count per canonical key. Separate query (nested aggregation can't live in the
    # GROUP BY alert_code row); rolled up in Python.
    tag_rows = await db.execute(
        text(f"""
            SELECT alert_code, tag, COUNT(*) AS n
            FROM escalation_audit,
                 LATERAL jsonb_array_elements_text(action_tags) AS tag
            WHERE transition = 'resolved'
              AND action_tags IS NOT NULL
              AND {window_clause}
              {code_clause}
            GROUP BY alert_code, tag
        """),
        params,
    )
    tag_dist: dict[str, dict[str, int]] = {}
    for row in tag_rows:
        tag_dist.setdefault(row.alert_code, {})[row.tag] = int(row.n)

    funnels = [
        AlertFunnel(
            alert_code=row.alert_code,
            count_raised=int(row.count_raised),
            count_acknowledged=int(row.count_acknowledged),
            count_resolved=int(row.count_resolved),
            count_silently_dismissed=int(row.count_dismissed),
            median_t_ack_seconds=float(row.median_t_ack) if row.median_t_ack is not None else None,
            p95_t_ack_seconds=float(row.p95_t_ack) if row.p95_t_ack is not None else None,
            action_tag_distribution=tag_dist.get(row.alert_code, {}),
        )
        for row in funnel_rows
    ]
    return funnels
