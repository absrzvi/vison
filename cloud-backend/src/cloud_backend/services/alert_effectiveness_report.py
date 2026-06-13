"""Weekly alert-effectiveness report (E10-S2 AC4 / D4).

A callable + thin CLI entrypoint. There is NO in-process scheduler in
cloud-backend (only a FastAPI startup hook), so scheduling is EXTERNAL: a GitLab
CI scheduled pipeline (Monday 06:00 UTC) invokes the CLI. See .gitlab-ci.yml.

The report summarises one ISO week of escalation_audit telemetry:
  - retune candidates (high raised volume, low ack rate),
  - median ack latency per alert_code,
  - alert_class_state disable/enable events in the window,
  - the silent-dismissal rate.

Idempotent: re-running the same week overwrites reports/alert-effectiveness-
{YYYY-WW}.md rather than appending.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()


class _Funnel(TypedDict):
    alert_code: str
    raised: int
    acknowledged: int
    resolved: int
    dismissed: int
    ack_rate: float | None
    median_ack_s: float | None


class _ClassStateEvent(TypedDict):
    alert_code: str
    state: str
    disabled_by: str | None
    disabled_at: datetime | None
    enabled_by: str | None
    enabled_at: datetime | None

# Repo-root-relative output dir (PoC). Resolved from this file: src/cloud_backend/
# services/ → up 4 → cloud-backend/, then reports/.
_REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"

_RETUNE_TOP_N = 5


def _iso_week_bounds(iso_year: int, iso_week: int) -> tuple[datetime, datetime]:
    """[Monday 00:00, next Monday 00:00) UTC for the given ISO week."""
    start = datetime.fromisocalendar(iso_year, iso_week, 1).replace(tzinfo=UTC)
    return start, start + timedelta(days=7)


async def _funnel_rows(
    db: AsyncSession, dt_from: datetime, dt_to: datetime
) -> list[_Funnel]:
    rows = await db.execute(
        text("""
            SELECT
                alert_code,
                COUNT(*) FILTER (WHERE transition = 'raised')             AS raised,
                COUNT(*) FILTER (WHERE transition = 'acknowledged')       AS acknowledged,
                COUNT(*) FILTER (WHERE transition = 'resolved')           AS resolved,
                COUNT(*) FILTER (WHERE transition = 'silently_dismissed') AS dismissed,
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY EXTRACT(EPOCH FROM (t_event - t_fired))
                ) FILTER (WHERE transition = 'acknowledged')             AS median_ack
            FROM escalation_audit
            WHERE t_event >= :from AND t_event < :to
            GROUP BY alert_code
        """),
        {"from": dt_from, "to": dt_to},
    )
    out: list[_Funnel] = []
    for r in rows:
        raised = int(r.raised)
        ack = int(r.acknowledged)
        out.append(_Funnel(
            alert_code=r.alert_code,
            raised=raised,
            acknowledged=ack,
            resolved=int(r.resolved),
            dismissed=int(r.dismissed),
            # ack_rate is None when nothing was raised (avoid divide-by-zero — the
            # NULL/zero-denominator trap from deferred-work.md).
            ack_rate=(ack / raised) if raised > 0 else None,
            median_ack_s=float(r.median_ack) if r.median_ack is not None else None,
        ))
    return out


async def _class_state_events(
    db: AsyncSession, dt_from: datetime, dt_to: datetime
) -> list[_ClassStateEvent]:
    rows = await db.execute(
        text("""
            SELECT alert_code, state, disabled_by, disabled_at, enabled_by, enabled_at
            FROM alert_class_state
            WHERE (disabled_at >= :from AND disabled_at < :to)
               OR (enabled_at  >= :from AND enabled_at  < :to)
            ORDER BY alert_code
        """),
        {"from": dt_from, "to": dt_to},
    )
    return [
        _ClassStateEvent(
            alert_code=r.alert_code,
            state=r.state,
            disabled_by=r.disabled_by,
            disabled_at=r.disabled_at,
            enabled_by=r.enabled_by,
            enabled_at=r.enabled_at,
        )
        for r in rows
    ]


def _fmt_pct(rate: float | None) -> str:
    return "—" if rate is None else f"{rate * 100:.0f}%"


def _fmt_secs(s: float | None) -> str:
    return "—" if s is None else f"{s:.0f}s"


def _render(
    iso_year: int,
    iso_week: int,
    dt_from: datetime,
    dt_to: datetime,
    funnels: list[_Funnel],
    state_events: list[_ClassStateEvent],
) -> str:
    total_raised = sum(f["raised"] for f in funnels)
    total_dismissed = sum(f["dismissed"] for f in funnels)
    dismissal_rate = (total_dismissed / total_raised) if total_raised > 0 else None

    # Retune candidates: rank by low ack rate, then high volume. Funnels with no
    # raised escalations (ack_rate is None) are not candidates.
    def _candidate_key(f: _Funnel) -> tuple[float, int]:
        rate = f["ack_rate"]
        return (rate if rate is not None else 1.0, -f["raised"])

    candidates = sorted(
        (f for f in funnels if f["ack_rate"] is not None),
        key=_candidate_key,
    )[:_RETUNE_TOP_N]

    lines: list[str] = []
    lines.append(f"# Alert Effectiveness — {iso_year}-W{iso_week:02d}")
    lines.append("")
    lines.append(
        f"Window: {dt_from.date().isoformat()} → {dt_to.date().isoformat()} (UTC, ISO week)"
    )
    lines.append("")
    lines.append(
        f"Total escalations raised: **{total_raised}** · "
        f"silent-dismissal rate: **{_fmt_pct(dismissal_rate)}** "
        f"({total_dismissed}/{total_raised})"
    )
    lines.append("")

    lines.append("## Retune candidates (high volume, low ack rate)")
    lines.append("")
    if candidates:
        lines.append("| Alert code | Raised | Ack rate | Median ack |")
        lines.append("|---|---:|---:|---:|")
        for f in candidates:
            lines.append(
                f"| {f['alert_code']} | {f['raised']} | "
                f"{_fmt_pct(f['ack_rate'])} | {_fmt_secs(f['median_ack_s'])} |"
            )
    else:
        lines.append("_No escalations raised in this window._")
    lines.append("")

    lines.append("## Median ack latency by alert class")
    lines.append("")
    if funnels:
        lines.append("| Alert code | Raised | Ack | Resolved | Dismissed | Median ack |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for f in sorted(funnels, key=lambda f: -f["raised"]):
            lines.append(
                f"| {f['alert_code']} | {f['raised']} | {f['acknowledged']} | "
                f"{f['resolved']} | {f['dismissed']} | {_fmt_secs(f['median_ack_s'])} |"
            )
    else:
        lines.append("_No data._")
    lines.append("")

    lines.append("## Alert-class enable/disable events in window")
    lines.append("")
    if state_events:
        lines.append("| Alert code | Current state | Disabled (by / at) | Enabled (by / at) |")
        lines.append("|---|---|---|---|")
        for e in state_events:
            disabled = (
                f"{e['disabled_by']} / {e['disabled_at'].isoformat()}"
                if e["disabled_at"] is not None
                else "—"
            )
            enabled = (
                f"{e['enabled_by']} / {e['enabled_at'].isoformat()}"
                if e["enabled_at"] is not None
                else "—"
            )
            lines.append(f"| {e['alert_code']} | {e['state']} | {disabled} | {enabled} |")
    else:
        lines.append("_No kill-switch activity in this window._")
    lines.append("")

    return "\n".join(lines)


async def generate_alert_effectiveness_report(
    db: AsyncSession, iso_year: int, iso_week: int
) -> Path:
    """Generate (idempotently overwrite) the weekly report for one ISO week.

    Returns the path written. The caller owns the DB session lifecycle."""
    dt_from, dt_to = _iso_week_bounds(iso_year, iso_week)
    funnels = await _funnel_rows(db, dt_from, dt_to)
    state_events = await _class_state_events(db, dt_from, dt_to)
    body = _render(iso_year, iso_week, dt_from, dt_to, funnels, state_events)

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _REPORTS_DIR / f"alert-effectiveness-{iso_year}-{iso_week:02d}.md"
    out_path.write_text(body, encoding="utf-8")
    log.info("alert_effectiveness_report_written", path=str(out_path), iso_week=iso_week)
    return out_path


async def _main() -> None:
    """CLI entrypoint: report for the most recently completed ISO week, or an
    explicit `<year> <week>` pair. Invoked by the GitLab CI scheduled pipeline."""
    import sys

    from ..database import get_session_factory

    if len(sys.argv) >= 3:
        iso_year, iso_week = int(sys.argv[1]), int(sys.argv[2])
    else:
        # Most recently completed ISO week = the week containing 7 days ago.
        y, w, _ = (datetime.now(UTC) - timedelta(days=7)).isocalendar()
        iso_year, iso_week = y, w

    factory = get_session_factory()
    async with factory() as session:
        path = await generate_alert_effectiveness_report(session, iso_year, iso_week)
    log.info("report_cli_complete", path=str(path))


if __name__ == "__main__":
    asyncio.run(_main())
