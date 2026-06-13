"""Escalation lifecycle endpoints — story 10-6.

The authoritative server-side acknowledge/resolve transitions for escalations
(the backend half of E2-S5, which shipped frontend-only). Each transition
updates the `escalations` row and fans out an ESCALATION_UPDATED frame to SSE
subscribers so other operators' open panels converge.

escalation_id is the ALERT_RAISED event's envelope event_id — the id the
Control Centre uses in these URLs.
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..api.escalations import ACTION_TAG_KEYS, AckRequest, ResolveRequest
from ..database import get_db
from ..routes.alerts_sse import publish_alert

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/escalations", dependencies=[Security(require_api_key)])


def _publish_lifecycle(escalation_id: str, status: str) -> None:
    """Fan out an ESCALATION_UPDATED frame so other operators' panels converge.

    `event_id`/`event_type` are required by the SSE frame builder (alerts_sse).
    `id` is what the Control Centre consumer matches on (FleetContext keys
    escalations by `payload.id`); without it the UI never converges.
    """
    publish_alert(
        {
            "event_id": escalation_id,
            "event_type": "ESCALATION_UPDATED",
            "id": escalation_id,
            "escalation_id": escalation_id,
            "status": status,
        }
    )


async def _get_status(db: AsyncSession, escalation_id: str) -> str | None:
    row = (
        await db.execute(
            text("SELECT status FROM escalations WHERE escalation_id = :id"),
            {"id": escalation_id},
        )
    ).first()
    return row[0] if row else None


@router.post("/{escalation_id}/acknowledge")
async def acknowledge_escalation(
    escalation_id: str,
    body: AckRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    status = await _get_status(db, escalation_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"detail": "escalation not found"})

    # Idempotent: only the first acknowledge transitions and records the operator.
    if status == "unacknowledged":
        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            text("""
                UPDATE escalations
                SET status = 'acknowledged', t_ack = NOW(), ack_operator_id = :op
                WHERE escalation_id = :id AND status = 'unacknowledged'
            """),
            {"id": escalation_id, "op": body.operator_id},
        )
        await db.commit()
        # Review R1: only fan out + log when this request actually transitioned the
        # row. Under a concurrent ack race the loser matches 0 rows — no duplicate
        # SSE frame, no duplicate log.
        if result.rowcount == 1:
            _publish_lifecycle(escalation_id, "acknowledged")
            log.info(
                "escalation_acknowledged",
                escalation_id=escalation_id,
                operator_id=body.operator_id,
            )

    return {"escalation_id": escalation_id, "status": "acknowledged"}


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    status = await _get_status(db, escalation_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"detail": "escalation not found"})
    if status == "unacknowledged":
        raise HTTPException(
            status_code=409, detail={"detail": "escalation must be acknowledged before resolve"}
        )

    # Map UI labels → canonical keys; reject anything outside the taxonomy.
    try:
        keys = [ACTION_TAG_KEYS[t] for t in body.action_tags]
    except KeyError as exc:
        raise HTTPException(
            status_code=422, detail={"detail": f"invalid action_tag: {exc.args[0]}"}
        ) from exc

    # Idempotent: only transition while still acknowledged.
    if status == "acknowledged":
        result: CursorResult[tuple[()]] = await db.execute(  # type: ignore[assignment]
            text("""
                UPDATE escalations
                SET status = 'resolved', t_resolve = NOW(),
                    resolve_operator_id = :op, outcome = :outcome, action_tags = :tags
                WHERE escalation_id = :id AND status = 'acknowledged'
            """),
            {
                "id": escalation_id,
                "op": body.operator_id,
                "outcome": body.outcome,
                "tags": json.dumps(keys),
            },
        )
        await db.commit()
        # Review R1: fan out + log only when this request transitioned the row.
        if result.rowcount == 1:
            _publish_lifecycle(escalation_id, "resolved")
            log.info(
                "escalation_resolved",
                escalation_id=escalation_id,
                operator_id=body.operator_id,
            )

    return {"escalation_id": escalation_id, "status": "resolved"}
