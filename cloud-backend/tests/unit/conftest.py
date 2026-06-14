"""Shared unit-test auth fixtures (E11-S1 JWT cutover; E11-S2 liveness).

After the JWT cutover, protected routes require a Bearer token instead of
X-API-Key. A fixed JWT_SECRET is set for the whole unit-test session so tokens
mint and verify deterministically; `auth_header()` returns a ready Bearer header
for an operator (or admin) token. Tests that previously sent `_HEADERS` now use
this.

E11-S2: the liveness check made get_current_user / get_current_user_from_query
depend on a real DB (`SELECT is_active ...` after token verification). Unit tests
run against the shared `app` WITHOUT a real Postgres, and they assert route
behaviour for an authenticated, ACTIVE user — not deactivation. So an autouse
fixture overrides the liveness DB dependency (`get_db`) on the shared app with an
always-active stub for the unit tier. Deactivation/missing-user liveness is
covered for real in tests/integration/test_user_management.py against Postgres.
"""
from __future__ import annotations

import os
from collections.abc import Generator

import pytest

# Set BEFORE cloud_backend.config is imported anywhere so get_settings() picks it
# up. A 32+ byte secret avoids PyJWT's short-key warning.
os.environ.setdefault("JWT_SECRET", "unit-test-secret-0123456789abcdef0123456789")
os.environ.setdefault("JWT_ISSUER", "oebb-cloud-backend")


def auth_header(role: str = "operator", *, username: str = "tester") -> dict[str, str]:
    """Return an Authorization: Bearer header for a freshly minted token."""
    from cloud_backend.api.auth import create_access_token

    token = create_access_token(user_id=f"u-{role}", username=username, role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _bypass_liveness_in_unit_tests() -> Generator[None, None, None]:
    """E11-S2: the liveness gate makes get_current_user / get_current_user_from_query
    depend on a real DB (`SELECT is_active ...`). Unit tests run without Postgres and
    assert route behaviour for an authenticated, ACTIVE user. Overriding `get_db`
    here is fragile — many unit db-mocks answer by call-INDEX, and inserting a
    liveness query first shifts every subsequent index. So instead we override the
    two EXTRACTOR dependencies on the shared app to verify the token but SKIP the DB
    liveness hit (returning an active user's CurrentUser). This leaves each test's own
    get_db mock untouched. Real liveness/deactivation is covered against Postgres in
    tests/integration/test_user_management.py.

    A test that installs its OWN override for these extractors replaces ours; we
    restore prior state on teardown so nothing leaks across tests."""
    from fastapi import Security
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

    from cloud_backend.api.auth import (
        CurrentUser,
        _verify_token,
        get_current_user,
        get_current_user_from_query,
    )
    from cloud_backend.main import app

    # Security-aware shims: verify the token (so invalid-token tests still 401) but
    # skip the liveness DB lookup.
    _bearer = HTTPBearer(auto_error=False)

    async def _hdr_shim(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ) -> CurrentUser:
        return _verify_token(creds.credentials if creds else None)

    async def _qry_shim(token: str | None = None) -> CurrentUser:
        return _verify_token(token)

    prev_hdr = app.dependency_overrides.get(get_current_user)
    prev_qry = app.dependency_overrides.get(get_current_user_from_query)
    app.dependency_overrides[get_current_user] = _hdr_shim
    app.dependency_overrides[get_current_user_from_query] = _qry_shim
    try:
        yield
    finally:
        for dep, prev in (
            (get_current_user, prev_hdr),
            (get_current_user_from_query, prev_qry),
        ):
            if prev is None:
                app.dependency_overrides.pop(dep, None)
            else:
                app.dependency_overrides[dep] = prev
