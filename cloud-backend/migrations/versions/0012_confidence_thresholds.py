"""add confidence_thresholds KV table (E11-S5 mutable thresholds)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-15

New table only — no DEFAULT on existing tables, safe under concurrent reads
(mirrors 0004_alert_class_state). A key-value store so the 5 per-class thresholds
AND the scalar degraded-banner floor live in one table without a column-per-value:
  config_key TEXT PK  — 'per_class:<alert_code>' (x5) or 'degraded_banner_floor'
  value      DOUBLE PRECISION NOT NULL, CHECK 0.0 <= value <= 1.0
  updated_by TEXT      — the admin username that last set it (NULL for the seed)
  updated_at TIMESTAMPTZ

SEED with the current hardcoded `# CALIBRATE` defaults (confidence_thresholds.py)
so behaviour is UNCHANGED on first deploy. An empty/unseeded store, or any
missing/un-parseable row, falls back to the hardcoded defaults in the reader
(ThresholdStore) — the gate fails SAFE, never open. Downgrade drops the table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# The seed MUST match config/confidence_thresholds.py's hardcoded defaults so a
# fresh migration leaves behaviour unchanged. Kept in sync by
# test_seed_matches_hardcoded_defaults (unit) + the migration idempotency test.
_SEED: dict[str, float] = {
    "per_class:unattended_bag": 0.75,
    "per_class:door_obstruction": 0.85,
    "per_class:accessibility_detected": 0.70,
    "per_class:slip_fall": 0.75,
    "per_class:luggage_rack_saturation": 0.70,
    "degraded_banner_floor": 0.60,
}


def upgrade() -> None:
    op.create_table(
        "confidence_thresholds",
        sa.Column("config_key", sa.Text, primary_key=True),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("updated_by", sa.Text, nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "value >= 0.0 AND value <= 1.0",
            name="ck_confidence_thresholds_range",
        ),
    )
    op.bulk_insert(
        sa.table(
            "confidence_thresholds",
            sa.column("config_key", sa.Text),
            sa.column("value", sa.Float),
        ),
        [{"config_key": k, "value": v} for k, v in _SEED.items()],
    )


def downgrade() -> None:
    op.drop_table("confidence_thresholds")
