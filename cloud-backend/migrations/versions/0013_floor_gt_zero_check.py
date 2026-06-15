"""forbid degraded_banner_floor = 0.0 at the DB layer (E11-S5 code-review R1)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-15

Defence-in-depth for the fail-OPEN closed in E11-S5 review: a floor of 0.0 makes
the degraded-banner gate (`mean < floor`, confidence ∈ [0,1]) never fire, silently
disabling the banner fleet-wide. The app layer now rejects it (config.py
_check_floor → 422; ThresholdStore._valid(floor=True) → fail-safe to the default),
and this row-scoped CHECK is the last line so a raw write can't introduce it
either. Per-class thresholds legitimately allow 0.0, so the CHECK is PARTIAL —
scoped to the floor row only.

No data change — the seeded floor is 0.60, which satisfies the new constraint.
Downgrade drops the added constraint (the 0012 range CHECK remains).
"""
from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_CK_NAME = "ck_confidence_thresholds_floor_gt_zero"


def upgrade() -> None:
    op.create_check_constraint(
        _CK_NAME,
        "confidence_thresholds",
        "config_key <> 'degraded_banner_floor' OR value > 0.0",
    )


def downgrade() -> None:
    op.drop_constraint(_CK_NAME, "confidence_thresholds", type_="check")
