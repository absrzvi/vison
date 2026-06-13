"""Request models + action-tag taxonomy for escalation lifecycle endpoints (E10-S6).

The Control Centre resolve picker sends human-readable labels; we persist the
canonical key so re-wording a UI label never re-buckets historical funnel data
in 10-2. This dict is the single source of truth — keys are the contract,
labels are display-only. PoC default pending ÖBB confirmation (D3).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# UI label → canonical key. Landside Fleet Manager outcomes only (no conductor,
# no police/station). false_alarm + no_action_needed = the false-positive signal.
ACTION_TAG_KEYS: dict[str, str] = {
    "Resolved remotely": "resolved_remotely",
    "Field team dispatched": "field_team_dispatched",
    "False alarm": "false_alarm",
    "No action needed": "no_action_needed",
}


class AckRequest(BaseModel):
    operator_id: str = Field(min_length=1)


class ResolveRequest(BaseModel):
    outcome: str = Field(min_length=1, max_length=200)
    action_tags: list[str] = Field(min_length=1)
    operator_id: str = Field(min_length=1)


class SilentlyDismissedRequest(BaseModel):
    """Telemetry beacon (E10-S2 AC2) — the operator viewed an unacknowledged
    escalation and left without acknowledging. dwell_focus_ms is tab-focused time
    (visibilitychange-gated), not wall-clock; t_viewed/t_dismissed are the
    client-side view window, retained for context."""

    operator_id: str = Field(min_length=1)
    t_viewed: datetime
    t_dismissed: datetime
    dwell_focus_ms: int = Field(ge=0)
