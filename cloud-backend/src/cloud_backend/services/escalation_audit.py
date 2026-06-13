"""escalation_audit write hooks — story 10-2 (operator behavioural telemetry).

Append-only: one row per lifecycle transition. These helpers are called from
the transition points that 10-6 owns — `routes/ingest.py` (raised) and
`routes/escalations.py` (acknowledged / resolved / silently_dismissed) — inside
the same DB transaction, only after the escalations row has actually
transitioned (the rowcount==1 guard). The funnel endpoint aggregates these rows,
so each row denormalises t_fired / alert_code / confidence_* / model_versions
from the escalations row at transition time (no join back to events).

For acknowledged/resolved we INSERT ... SELECT straight from the escalations row
so the transition timestamp (t_ack / t_resolve, written by the same UPDATE) and
the denormalised columns are read atomically — no extra round trip, no stale
read between the UPDATE and the audit write.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# t_ack / t_resolve column on escalations that holds this transition's timestamp.
_TRANSITION_TIME_COLUMN = {"acknowledged": "t_ack", "resolved": "t_resolve"}


async def record_raised(
    db: AsyncSession,
    *,
    escalation_id: str,
    alert_code: str,
    t_fired: datetime,
    confidence_score: float | None,
    confidence_basis: str | None,
    model_versions: dict[str, Any],
) -> None:
    """Append the 'raised' audit row. operator_id is NULL; t_event == t_fired."""
    await db.execute(
        text("""
            INSERT INTO escalation_audit
                (audit_id, escalation_id, transition, operator_id, alert_code,
                 t_event, t_fired, action_tags, dwell_focus_ms,
                 confidence_score, confidence_basis, model_versions)
            VALUES
                (:audit_id, :escalation_id, 'raised', NULL, :alert_code,
                 :t_fired, :t_fired, NULL, NULL,
                 :confidence_score, :confidence_basis, :model_versions)
        """),
        {
            "audit_id": str(uuid.uuid4()),
            "escalation_id": escalation_id,
            "alert_code": alert_code,
            "t_fired": t_fired,
            "confidence_score": confidence_score,
            "confidence_basis": confidence_basis,
            "model_versions": json.dumps(model_versions),
        },
    )


async def record_transition(
    db: AsyncSession,
    *,
    escalation_id: str,
    transition: str,
    operator_id: str,
) -> None:
    """Append an 'acknowledged' or 'resolved' audit row.

    Denormalises alert_code / t_fired / confidence_* / model_versions and reads
    the transition time (t_ack or t_resolve) directly from the just-updated
    escalations row. action_tags is carried over only for 'resolved' (it is NULL
    on the escalations row until resolve writes it).
    """
    t_event_col = _TRANSITION_TIME_COLUMN[transition]
    action_tags_expr = "action_tags" if transition == "resolved" else "NULL"
    await db.execute(
        text(f"""
            INSERT INTO escalation_audit
                (audit_id, escalation_id, transition, operator_id, alert_code,
                 t_event, t_fired, action_tags, dwell_focus_ms,
                 confidence_score, confidence_basis, model_versions)
            SELECT
                :audit_id, escalation_id, :transition, :operator_id, alert_code,
                {t_event_col}, t_fired, {action_tags_expr}, NULL,
                confidence_score, confidence_basis, model_versions
            FROM escalations
            WHERE escalation_id = :escalation_id
        """),
        {
            "audit_id": str(uuid.uuid4()),
            "transition": transition,
            "operator_id": operator_id,
            "escalation_id": escalation_id,
        },
    )


async def record_silently_dismissed(
    db: AsyncSession,
    *,
    escalation_id: str,
    operator_id: str,
    t_event: datetime,
    dwell_focus_ms: int,
) -> None:
    """Append a 'silently_dismissed' audit row.

    A non-action: the operator viewed an unacknowledged escalation and left
    without acknowledging. Denormalises alert_code / t_fired / confidence_* /
    model_versions from the escalations row; carries the client-measured
    focus-time dwell. action_tags stays NULL.

    The `status = 'unacknowledged'` predicate makes the write atomic: if a
    concurrent acknowledge commits between the route's status read and this
    insert, the SELECT matches 0 rows and no dismissal row is appended — so an
    escalation can never carry both an `acknowledged` and a later
    `silently_dismissed` audit row (review D-2 / TOCTOU).
    """
    await db.execute(
        text("""
            INSERT INTO escalation_audit
                (audit_id, escalation_id, transition, operator_id, alert_code,
                 t_event, t_fired, action_tags, dwell_focus_ms,
                 confidence_score, confidence_basis, model_versions)
            SELECT
                :audit_id, escalation_id, 'silently_dismissed', :operator_id, alert_code,
                :t_event, t_fired, NULL, :dwell_focus_ms,
                confidence_score, confidence_basis, model_versions
            FROM escalations
            WHERE escalation_id = :escalation_id
              AND status = 'unacknowledged'
        """),
        {
            "audit_id": str(uuid.uuid4()),
            "operator_id": operator_id,
            "escalation_id": escalation_id,
            "t_event": t_event,
            "dwell_focus_ms": dwell_focus_ms,
        },
    )
