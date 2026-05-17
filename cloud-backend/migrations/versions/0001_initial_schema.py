"""initial schema: journeys + events tables

Revision ID: 0001
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_JOURNEY_ID_COMMENT = (
    "journey_start_date is anchored at trip_number first-seen by vlan-pollers; "
    "stable across midnight crossings"
)


def upgrade() -> None:
    op.create_table(
        "journeys",
        sa.Column("journey_id", sa.Text, primary_key=True, comment=_JOURNEY_ID_COMMENT),
        sa.Column("vehicle_id", sa.Text, nullable=False),
        sa.Column("trip_number", sa.Text, nullable=False),
        sa.Column("route_name", sa.Text, nullable=True),
        sa.Column("origin", sa.Text, nullable=True),
        sa.Column("destination", sa.Text, nullable=True),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # Column-level comment for journey_id (also via COMMENT ON COLUMN for PG compatibility)
    op.execute(
        f"COMMENT ON COLUMN journeys.journey_id IS '{_JOURNEY_ID_COMMENT}'"
    )

    op.create_table(
        "events",
        sa.Column(
            "event_id",
            UUID(as_uuid=False),
            primary_key=True,
        ),
        sa.Column(
            "journey_id",
            sa.Text,
            sa.ForeignKey("journeys.journey_id", ondelete="CASCADE"),
            nullable=False,
            comment=_JOURNEY_ID_COMMENT,
        ),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("source_timestamp", sa.TIMESTAMP(timezone=True), nullable=False),
    )
    op.execute(
        f"COMMENT ON COLUMN events.journey_id IS '{_JOURNEY_ID_COMMENT}'"
    )

    # Idempotency constraint: same event from same source at same time = duplicate
    op.create_unique_constraint(
        "uq_events_journey_type_source_ts",
        "events",
        ["journey_id", "event_type", "source_timestamp"],
    )

    # Index on journey_id for fast event lookups per journey
    op.create_index("ix_events_journey_id", "events", ["journey_id"])


def downgrade() -> None:
    op.drop_index("ix_events_journey_id", table_name="events")
    op.drop_constraint("uq_events_journey_type_source_ts", "events", type_="unique")
    op.drop_table("events")
    op.drop_table("journeys")
