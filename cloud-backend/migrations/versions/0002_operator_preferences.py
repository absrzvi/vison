"""add operator_preferences table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_preferences",
        sa.Column("operator_id", sa.Text, primary_key=True),
        sa.Column(
            "threshold_sec",
            sa.Integer,
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "staleness_threshold_sec",
            sa.Integer,
            nullable=False,
            server_default="120",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "threshold_sec IN (30, 60, 90, 120)",
            name="ck_threshold_sec_valid",
        ),
        sa.CheckConstraint(
            "staleness_threshold_sec IN (60, 120, 180, 300)",
            name="ck_staleness_threshold_sec_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("operator_preferences")
