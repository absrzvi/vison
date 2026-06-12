"""add train_inference_heartbeat table (E10-S1 AI pipeline health)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-12

New table only — safe under concurrent reads.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "train_inference_heartbeat",
        sa.Column("train_id", sa.Text, primary_key=True),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("model_versions", JSONB, nullable=False),
        sa.Column("hailo_device_ok", sa.Boolean, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("train_inference_heartbeat")
