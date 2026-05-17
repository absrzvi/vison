"""initial schema: journeys + events

Revision ID: 001
Revises:
Create Date: 2026-05-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journeys",
        sa.Column("journey_id", sa.Text, primary_key=True),
        sa.Column("vehicle_id", sa.Text, nullable=False),
        sa.Column("trip_number", sa.Text, nullable=False),
        sa.Column("route_name", sa.Text),
        sa.Column("origin", sa.Text),
        sa.Column("destination", sa.Text),
        sa.Column("start_time", sa.Text),
        sa.Column("end_time", sa.Text),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("journey_id", sa.Text, nullable=False, index=True),
        sa.Column("vehicle_id", sa.Text, nullable=False),
        sa.Column("timestamp", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "severity",
            sa.Text,
            sa.CheckConstraint("severity IN ('critical', 'warning', 'info')"),
            nullable=False,
        ),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column(
            "ingested_at",
            sa.Text,
            nullable=False,
            server_default=sa.text("(now() AT TIME ZONE 'utc')::text"),
        ),
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("journeys")
