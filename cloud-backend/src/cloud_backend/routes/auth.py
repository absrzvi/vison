"""Auth endpoints — E11-S1 (ADR-23).

POST /api/v1/auth/login  — username+password → access token (unauthenticated).
GET  /api/v1/auth/me     — echo the caller's identity (requires a valid token).

login is the ONE protected-prefix exception that stays unauthenticated
(chicken-and-egg). It runs verify_password unconditionally — even when the user
is absent — against a constant dummy hash, so the response time does not leak
whether a username exists (Security Test 7 / AC1).
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth")

# Constant dummy hash of a random secret — used to spend the same bcrypt time on
# an unknown username as on a real one (no user-enumeration timing oracle).
_DUMMY_HASH = hash_password("non-existent-user-placeholder")

_UNAUTHORIZED = {
    "error": "UNAUTHORIZED",
    "detail": "Invalid username or password",
    "recoverable": False,
}


class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


async def create_user(
    db: AsyncSession, *, username: str, password: str, role: str
) -> str:
    """Real user-creation path (hash via the app's bcrypt, insert the row).

    The A3 integration test seeds through THIS — never a raw INSERT of a
    hand-computed hash — so a green test cannot pass while the real
    hash/verify pairing is broken. E11-S2 builds the admin HTTP surface on
    top of this helper.
    """
    user_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (user_id, username, password_hash, role) "
            "VALUES (:uid, :username, :pwhash, :role)"
        ),
        {
            "uid": user_id,
            "username": username,
            "pwhash": hash_password(password),
            "role": role,
        },
    )
    await db.commit()
    return user_id


@router.post("/login", response_model=TokenOut)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)) -> TokenOut:
    result = await db.execute(
        text(
            "SELECT user_id, username, password_hash, role, is_active "
            "FROM users WHERE username = :username"
        ),
        {"username": body.username},
    )
    row = result.fetchone()
    # Always verify against *some* hash (real or dummy) for uniform timing.
    candidate_hash = row.password_hash if row is not None else _DUMMY_HASH
    password_ok = verify_password(body.password, candidate_hash)

    if row is None or not password_ok or not row.is_active:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED)

    token = create_access_token(
        user_id=str(row.user_id), username=row.username, role=row.role
    )
    log.info("auth.login_success", user_id=str(row.user_id), role=row.role)
    return TokenOut(access_token=token)


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user
