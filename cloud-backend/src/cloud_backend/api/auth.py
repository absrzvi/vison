"""Authentication — E11-S1 self-contained JWT (ADR-23) + the legacy API-key scheme.

Verification seam (AC4): all token verification flows through the single private
`_verify_token(raw) -> CurrentUser` core, which reads issuer / algorithm / key
from Settings only. Two thin extractors feed it:
  - `get_current_user`            — pulls the bearer token from the Authorization header
  - `get_current_user_from_query` — pulls `?token=` (for SSE / EventSource, which
                                    cannot set a header; D8)
Because verification is config-driven and isolated, swapping in an external IdP
(RS256/JWKS) later means re-pointing Settings and `_verify_token`'s key source —
no protected route or extractor changes. That is the OIDC-swap guarantee.

`require_api_key` is the pre-E11 shared-key scheme. It stays importable while the
JWT cutover lands and because preferences.py still keys on it until E11-S3.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db

# ── Legacy shared-key scheme (pre-E11; removed when E11-S3 re-keys preferences) ──

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_header_scheme)) -> str:
    if not api_key or api_key != get_settings().api_key:
        raise HTTPException(
            status_code=401,
            detail={"error": "UNAUTHORIZED", "detail": "API key required", "recoverable": False},
        )
    return api_key


# ── E11-S1 JWT auth ──────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)

# Reused for every 401 from the JWT path (ADR-10 envelope).
_UNAUTHORIZED = {"error": "UNAUTHORIZED", "detail": "Valid token required", "recoverable": False}


class CurrentUser(BaseModel):
    user_id: str
    username: str
    role: str


def hash_password(password: str) -> str:
    """bcrypt hash. bcrypt only mixes the first 72 bytes; we truncate explicitly
    rather than letting the library raise, so over-long passwords hash
    deterministically (the same rule is applied on verify). The cost factor is
    config-driven (E11-S2 D6): prod stays 12, the test env lowers it so the
    real-path integration suite isn't taxed by cost-12 bcrypt on every user."""
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(
        password.encode("utf-8")[:72], bcrypt.gensalt(rounds=rounds)
    ).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("ascii"))


def create_access_token(*, user_id: str, username: str, role: str) -> str:
    """Mint a signed access token. Fails closed (ValueError) if jwt_secret is unset
    so a token can never be minted under an empty secret (AC7)."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise ValueError("jwt_secret is not configured")
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _verify_token(raw: str | None) -> CurrentUser:
    """THE verification seam (AC4). Decode + validate a raw token string into a
    CurrentUser, or raise 401. Issuer / algorithm / key come from Settings only —
    no hardcoded crypto at any call site. Any decode failure, a missing required
    claim, or an unset secret yields 401 (never 500)."""
    settings = get_settings()
    # Fail closed: with no secret, nothing verifies (AC7) — and never let the
    # empty key reach jwt.decode where an alg:none token could slip through.
    if not settings.jwt_secret or not raw:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    try:
        payload = jwt.decode(
            raw,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],  # explicit allow-list — alg:none defense
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.InvalidTokenError as exc:  # base of Expired/Signature/Issuer/etc.
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED) from exc
    return CurrentUser(
        user_id=str(payload["sub"]),
        # `or ""` (not `get(..., "")`) so a present-but-null username claim from an
        # external IdP becomes "" rather than the literal string "None".
        username=str(payload.get("username") or ""),
        role=str(payload["role"]),
    )


async def assert_user_active(user: CurrentUser, db: AsyncSession) -> CurrentUser:
    """Liveness gate (E11-S2 D2/AC3). After the token is cryptographically valid,
    confirm the principal is still ACTIVE in the local user store — so deactivating
    a user invalidates their EXISTING token mid-session, not only their next login.

    This is AUTHORIZATION (a local question), kept deliberately OUTSIDE the
    `_verify_token` crypto seam (authentication). The seam stays issuer/algorithm/
    key-driven (the AC4 OIDC-swap guarantee); this check survives a Keycloak swap
    unchanged (ÖBB still deactivates operators in our `users` table). A missing
    row (deleted / never-existed `sub`) is treated exactly like deactivated → 401.

    Do NOT fold this SELECT into `_verify_token` — that would couple the verifier
    to local state and break the seam (guarded by test_seam_liveness_survives_verifier_swap).
    """
    result = await db.execute(
        text("SELECT is_active FROM users WHERE user_id = :uid"),
        {"uid": user.user_id},
    )
    row = result.fetchone()
    if row is None or not row.is_active:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)
    return user


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Header extractor: Authorization: Bearer <token> → CurrentUser (or 401).
    Verifies the token (crypto seam) then applies the liveness gate (D2)."""
    return await assert_user_active(_verify_token(creds.credentials if creds else None), db)


async def get_current_user_from_query(
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """Query extractor for SSE/EventSource (?token=<jwt>), which cannot set an
    Authorization header (D8). Same verification core AND same liveness gate as
    the header path — a deactivated user must lose the live stream too (D2 trap)."""
    return await assert_user_active(_verify_token(token), db)


def require_role(*roles: str) -> Any:
    """Dependency factory: composes on get_current_user and enforces the role
    claim. 403 (not 401) when authenticated but under-privileged (AC3)."""

    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "detail": "Insufficient role",
                    "recoverable": False,
                },
            )
        return user

    return _checker
