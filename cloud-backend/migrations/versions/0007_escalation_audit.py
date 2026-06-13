"""add escalation_audit table (E10-S2 operator behavioural telemetry)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13

New table only — safe under concurrent reads.

Append-only audit log: one row per escalation lifecycle transition
(raised / acknowledged / resolved / silently_dismissed). A full lifecycle is
3+ rows. The funnel endpoint (GET /api/v1/escalations-audit) aggregates these
with GROUP BY alert_code, so latency math and counts denormalise t_fired,
alert_code, confidence_*, model_versions from the escalations row at transition
time — no join back to escalations or events is needed.

escalation_id is a FK to escalations.escalation_id, which 0006 created as
UUID(as_uuid=False) (the ALERT_RAISED event_id). This column matches that type.
dwell_focus_ms is populated only on silently_dismissed; action_tags only on
resolved; operator_id is NULL for the raised transition.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "escalation_audit",
        sa.Column("audit_id", sa.Text, primary_key=True),
        sa.Column(
            "escalation_id",
            UUID(as_uuid=False),
            sa.ForeignKey("escalations.escalation_id"),
            nullable=False,
        ),
        sa.Column("transition", sa.Text, nullable=False),
        sa.Column("operator_id", sa.Text, nullable=True),
        sa.Column("alert_code", sa.Text, nullable=False),
        sa.Column("t_event", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("t_fired", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("action_tags", JSONB, nullable=True),
        sa.Column("dwell_focus_ms", sa.Integer, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("confidence_basis", sa.Text, nullable=True),
        sa.Column("model_versions", JSONB, nullable=True),
        sa.CheckConstraint(
            "transition IN ('raised', 'acknowledged', 'resolved', 'silently_dismissed')",
            name="ck_escalation_audit_transition_valid",
        ),
    )
    op.create_index("ix_escalation_audit_alert_code", "escalation_audit", ["alert_code"])
    op.create_index("ix_escalation_audit_operator_id", "escalation_audit", ["operator_id"])
    op.create_index("ix_escalation_audit_t_fired", "escalation_audit", ["t_fired"])


def downgrade() -> None:
    op.drop_index("ix_escalation_audit_t_fired", table_name="escalation_audit")
    op.drop_index("ix_escalation_audit_operator_id", table_name="escalation_audit")
    op.drop_index("ix_escalation_audit_alert_code", table_name="escalation_audit")
    op.drop_table("escalation_audit")
