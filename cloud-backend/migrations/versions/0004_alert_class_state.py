"""add alert_class_state table (E10-S1 kill-switch)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-12

New table only — no DEFAULT on existing tables, safe under concurrent reads.
Empty table means every alert_code defaults to 'enabled'.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_class_state",
        sa.Column("alert_code", sa.Text, primary_key=True),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("disabled_by", sa.Text, nullable=True),
        sa.Column("disabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("enabled_by", sa.Text, nullable=True),
        sa.Column("enabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('enabled', 'disabled')",
            name="ck_alert_class_state_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("alert_class_state")
