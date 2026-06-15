"""re-key operator_preferences from API-key string to users.user_id FK (E11-S3)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-15

Re-key migration on EXISTING data (Tier 3). Before E11-S1 cut the routers over
to JWT, operator_preferences.operator_id was a plain TEXT primary key holding
the *shared API-key string* — every "operator" was the same key, so there was
never any real per-user preference data.

DROP/SEED, NOT a mapping (Decision D1, party-mode unanimous): the pre-existing
rows are keyed by the now-retired shared API-key string. There is no honest
mapping from one shared key to N distinct users — any mapping would invent
per-user data that never existed. So this migration DELETEs all existing rows
and re-keys the column to a real UUID FK on users(user_id). New rows are created
on demand by the PATCH upsert, keyed by the token's user_id. This deletion is
IRREVERSIBLE; the deleted row count is logged (below) so the act is in the
migration record, not silent.

ORDERING IS LOAD-BEARING (Decision D3): the DELETE runs BEFORE the ALTER. The
old rows hold non-UUID TEXT (e.g. 'dev-insecure-key'); `operator_id::uuid` would
raise invalid_text_representation on real defunct data if the ALTER ran first.
The `USING operator_id::uuid` clause is REQUIRED (Postgres has no implicit
text->uuid cast in ALTER COLUMN TYPE), and safe because no rows remain to fail
the cast. The whole migration runs in one transaction (Alembic env.py wraps it),
so a failure rolls back atomically — no half-migrated state.

ON DELETE CASCADE: chosen so a future user hard-delete (none exists today — see
E11-S2) cannot orphan a prefs row. Revisit if operator_preferences ever holds
audit-relevant data, where RESTRICT (force the deleter to look) would be safer.

Downgrade restores the *schema* (TEXT column, FK dropped) but NOT the rows —
they were deleted on upgrade and cannot be reconstructed (consistent with the
0009/0010 downgrades). Lock scope is operator_preferences only (a ~0-few-row
PoC table) — no lock on events/alerts.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_FK_NAME = "fk_operator_preferences_user"
log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    conn = op.get_bind()
    # D1: drop the defunct API-key-keyed rows (no honest re-key mapping exists).
    # Log the count so the deliberate, irreversible deletion is in the migration
    # record (not silent) — a pilot/security reviewer can see it happened.
    deleted = conn.execute(sa.text("DELETE FROM operator_preferences")).rowcount
    log.warning(
        "E11-S3 0011: deleted %d defunct operator_preferences row(s) keyed by the "
        "retired shared API-key string (Decision D1, irreversible)",
        deleted,
    )
    # D3: retype to UUID — DELETE above guarantees no row fails the ::uuid cast.
    op.alter_column(
        "operator_preferences",
        "operator_id",
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using="operator_id::uuid",
    )
    op.create_foreign_key(
        _FK_NAME,
        "operator_preferences",
        "users",
        ["operator_id"],
        ["user_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Drop the FK before the type change. Rows are NOT restored (deleted on upgrade).
    op.drop_constraint(_FK_NAME, "operator_preferences", type_="foreignkey")
    op.alter_column(
        "operator_preferences",
        "operator_id",
        type_=sa.Text(),
        postgresql_using="operator_id::text",
    )
