"""create events table

Revision ID: 001
Revises:
Create Date: 2026-05-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.create_table(
        "events",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("journey_id", sa.Text, nullable=False, index=True),
        sa.Column("vehicle_id", sa.Text, nullable=False),
        sa.Column("timestamp", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON, nullable=False),
    )
    op.execute(
        "SELECT create_hypertable('events', 'timestamp', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    op.drop_table("events")
