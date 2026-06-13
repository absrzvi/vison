"""add escalations table (E10-S6 escalation lifecycle persistence)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-13

New table only — safe under concurrent reads.

escalation_id is the ALERT_RAISED event's envelope event_id (uuid, matches
events.event_id) — this is the id the Control Centre uses in its
acknowledge/resolve URLs. alert_id holds the payload alert_id for ALERT_RESOLVED
pairing. Empty table means no escalation has been acknowledged/resolved yet.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "escalations",
        sa.Column("escalation_id", UUID(as_uuid=False), primary_key=True),
        sa.Column("alert_id", sa.Text, nullable=False),
        sa.Column("alert_event_id", UUID(as_uuid=False), nullable=False),
        sa.Column("alert_code", sa.Text, nullable=False),
        sa.Column("journey_id", sa.Text, nullable=False),
        sa.Column("vehicle_id", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default="unacknowledged",
        ),
        sa.Column("t_fired", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("t_ack", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("t_resolve", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ack_operator_id", sa.Text, nullable=True),
        sa.Column("resolve_operator_id", sa.Text, nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),
        sa.Column("action_tags", JSONB, nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("confidence_basis", sa.Text, nullable=True),
        sa.Column("model_versions", JSONB, nullable=True),
        sa.CheckConstraint(
            "status IN ('unacknowledged', 'acknowledged', 'resolved')",
            name="ck_escalations_status_valid",
        ),
    )
    op.create_index("ix_escalations_status", "escalations", ["status"])
    op.create_index("ix_escalations_alert_code", "escalations", ["alert_code"])
    op.create_index("ix_escalations_t_fired", "escalations", ["t_fired"])


def downgrade() -> None:
    op.drop_index("ix_escalations_t_fired", table_name="escalations")
    op.drop_index("ix_escalations_alert_code", table_name="escalations")
    op.drop_index("ix_escalations_status", table_name="escalations")
    op.drop_table("escalations")
