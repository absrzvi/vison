"""Shared integration-test auth fixtures (E11-S1 JWT cutover).

Protected routes now require a Bearer token instead of X-API-Key. A fixed
JWT_SECRET is set for the integration session so tokens mint/verify
deterministically; `auth_header()` returns a ready Bearer header. Existing
integration tests that sent `{"X-API-Key": ...}` use this instead.

NOTE: tests that mint a token need JWT_SECRET set BEFORE get_settings() reads it.
This module sets it at import time (conftest is imported before test modules).
"""
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "integration-test-secret-0123456789abcdef0123456789")
os.environ.setdefault("JWT_ISSUER", "oebb-cloud-backend")


# Stable synthetic identities behind auth_header(). E11-S2 added a liveness check
# (SELECT is_active ...) to the auth dependencies, so these user_ids must EXIST and
# be active in the test DB or every protected call 401s. seed_auth_users() inserts
# them once per module after the schema is created (call it from pg_url). The
# user_id column is UUID-typed, so these are fixed, valid UUIDs (not 'u-operator'
# sentinels) shared between the minted token's `sub` and the seeded row.
_AUTH_USER_IDS = {
    "operator": "00000000-0000-0000-0000-0000000000a1",
    "admin": "00000000-0000-0000-0000-0000000000ad",
}


def auth_header(role: str = "operator", *, username: str = "tester") -> dict[str, str]:
    from cloud_backend.api.auth import create_access_token

    token = create_access_token(
        user_id=_AUTH_USER_IDS.get(role, "00000000-0000-0000-0000-0000000000ff"),
        username=username,
        role=role,
    )
    return {"Authorization": f"Bearer {token}"}


def seed_auth_users(pg_url: str) -> None:
    """Insert the synthetic auth users (operator + admin) used by auth_header() so
    the E11-S2 liveness check passes. Sync (psycopg2) so it runs inside the sync
    pg_url fixture. Idempotent (ON CONFLICT DO NOTHING).

    Creates a minimal `users` table IF NOT EXISTS first: most integration modules
    run Alembic head (which creates the real table), but a few build their schema
    ad-hoc with CREATE TABLE and never make `users` — there the liveness SELECT
    would error on a missing table. The IF NOT EXISTS shape is a subset of 0009
    sufficient for the liveness column; Alembic-backed modules already have the
    full table and skip creation."""
    import psycopg2

    sync_url = pg_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    conn = psycopg2.connect(sync_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  user_id UUID PRIMARY KEY,"
            "  username TEXT NOT NULL,"
            "  password_hash TEXT NOT NULL,"
            "  role TEXT NOT NULL,"
            "  is_active BOOLEAN NOT NULL DEFAULT true,"
            "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
            "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            ")"
        )
        for role, uid in _AUTH_USER_IDS.items():
            cur.execute(
                "INSERT INTO users (user_id, username, password_hash, role, is_active) "
                "VALUES (%s, %s, %s, %s, true) ON CONFLICT (user_id) DO NOTHING",
                (uid, f"synthetic-{role}", "x", role),
            )
        conn.commit()
    finally:
        conn.close()


def api_key_header() -> dict[str, str]:
    """X-API-Key header for the machine-to-machine ingest endpoint, which stays on
    the shared-key scheme (E11-S1 code-review Decision 1). All other routes use
    auth_header() (Bearer)."""
    from cloud_backend.config import get_settings

    return {"X-API-Key": get_settings().api_key}
