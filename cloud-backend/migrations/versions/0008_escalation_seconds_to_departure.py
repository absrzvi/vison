"""add seconds_to_departure to escalations (E10-S4 delay-minutes-avoided KPI)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-14

Additive nullable column only — safe under concurrent reads (no table rewrite,
no default backfill). Holds the AlertRaisedPayload.seconds_to_departure stamped
by fusion at raise time; NULL when the alert was not pre-departure or the PIS
feed was degraded. The delay-minutes-avoided KPI sums this column over
escalations resolved before their scheduled departure (D3).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "escalations",
        sa.Column("seconds_to_departure", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("escalations", "seconds_to_departure")
