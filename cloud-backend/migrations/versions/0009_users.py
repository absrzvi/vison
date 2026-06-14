"""add users table (E11-S1 JWT auth foundation)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-14

New table only — safe under concurrent reads (no rewrite, no lock on existing
tables). Local credential store for self-contained JWT auth (ADR-23): one row
per Control Centre operator/admin. password_hash is a bcrypt hash (the
`bcrypt` library directly — passlib was dropped, see story Change Log 1);
role is constrained to admin|operator. user_id (uuid) is the stable identity
used as the JWT `sub` claim and, from E11-S3, the operator_preferences FK.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=False), primary_key=True),
        sa.Column("username", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'operator')",
            name="ck_users_role_valid",
        ),
    )
    op.create_index("uq_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_username", table_name="users")
    op.drop_table("users")
