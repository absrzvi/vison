"""Maintenance ticket endpoint — E3-S7."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from fastapi import APIRouter, Security
from pydantic import BaseModel

from ..api.auth import require_api_key

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/maintenance",
    dependencies=[Security(require_api_key)],
)


class TicketRequest(BaseModel):
    train_id: str
    issue_summary: str
    raised_by: str


class TicketResponse(BaseModel):
    ticket_id: str
    created_at: str


@router.post("/tickets", response_model=TicketResponse, status_code=201)
async def raise_ticket(body: TicketRequest) -> TicketResponse:
    ticket_id = f"REF#{uuid4().hex[:5].upper()}"
    created_at = datetime.now(UTC).isoformat()
    log.info(
        "maintenance_ticket_raised",
        ticket_id=ticket_id,
        train_id=body.train_id,
        issue_summary=body.issue_summary,
        raised_by=body.raised_by,
    )
    return TicketResponse(ticket_id=ticket_id, created_at=created_at)
