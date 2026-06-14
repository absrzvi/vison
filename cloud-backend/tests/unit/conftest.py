"""Shared unit-test auth fixtures (E11-S1 JWT cutover).

After the JWT cutover, protected routes require a Bearer token instead of
X-API-Key. A fixed JWT_SECRET is set for the whole unit-test session so tokens
mint and verify deterministically; `auth_header()` returns a ready Bearer header
for an operator (or admin) token. Tests that previously sent `_HEADERS` now use
this.
"""
from __future__ import annotations

import os

# Set BEFORE cloud_backend.config is imported anywhere so get_settings() picks it
# up. A 32+ byte secret avoids PyJWT's short-key warning.
os.environ.setdefault("JWT_SECRET", "unit-test-secret-0123456789abcdef0123456789")
os.environ.setdefault("JWT_ISSUER", "oebb-cloud-backend")


def auth_header(role: str = "operator", *, username: str = "tester") -> dict[str, str]:
    """Return an Authorization: Bearer header for a freshly minted token."""
    from cloud_backend.api.auth import create_access_token

    token = create_access_token(user_id=f"u-{role}", username=username, role=role)
    return {"Authorization": f"Bearer {token}"}
