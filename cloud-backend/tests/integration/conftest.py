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


def auth_header(role: str = "operator", *, username: str = "tester") -> dict[str, str]:
    from cloud_backend.api.auth import create_access_token

    token = create_access_token(user_id=f"u-{role}", username=username, role=role)
    return {"Authorization": f"Bearer {token}"}
