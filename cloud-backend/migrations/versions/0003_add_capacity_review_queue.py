"""add capacity_review_queue table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capacity_review_queue",
        sa.Column("id", sa.Text, primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("exception_id", sa.Text, nullable=False, unique=True),
        sa.Column("route", sa.Text, nullable=False),
        sa.Column("train_id", sa.Text, nullable=False),
        sa.Column("departure_date", sa.Text, nullable=False),
        sa.Column("priority", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("queued_by", sa.Text, nullable=False),
        sa.Column(
            "queued_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="in_review"),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_crq_priority_valid",
        ),
        sa.CheckConstraint(
            "status IN ('in_review', 'dismissed', 'unreviewed')",
            name="ck_crq_status_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("capacity_review_queue")
