"""add user_audit table (E11-S2 user management)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-14

New table only — safe under concurrent reads (no rewrite, no lock on existing
tables). Local audit trail for admin user-management actions (create, role
change, deactivate/reactivate, password reset). Decision D1 (party-mode,
unanimous): user-account audit is a landside-LOCAL concern that never crosses
the onboard→landside egress/anonymise boundary, so it does NOT go through the
cross-service event envelope (no USER_* EventType / shared schema change /
contract-test cascade). "Queryable like the kill-switch audit" is satisfied by
a queryable table + structured log.

actor_user_id / target_user_id are the JWT `sub` (users.user_id). detail holds
a short human-readable summary (e.g. "role: operator -> admin"); it NEVER holds
a password or hash (password-reset rows record only the action).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_audit",
        sa.Column("audit_id", UUID(as_uuid=False), primary_key=True),
        sa.Column("actor_user_id", UUID(as_uuid=False), nullable=False),
        sa.Column("target_user_id", UUID(as_uuid=False), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('create', 'role_change', 'deactivate', 'reactivate', "
            "'password_reset')",
            name="ck_user_audit_action_valid",
        ),
    )
    # Queryable by who-did-it and who-it-was-done-to (the two forensic lookups).
    op.create_index("ix_user_audit_target", "user_audit", ["target_user_id"])
    op.create_index("ix_user_audit_actor", "user_audit", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_audit_actor", table_name="user_audit")
    op.drop_index("ix_user_audit_target", table_name="user_audit")
    op.drop_table("user_audit")
