"""Admin user-management endpoints — E11-S2.

All endpoints are gated on `require_role("admin")` (per-router, matching the
E11-S1 pattern) — an operator token gets 403, a missing/invalid token 401.

Every mutation writes a `user_audit` row AND a structured log line IN THE SAME
transaction as the mutation (AC5) — no audit-without-mutation, no
mutation-without-audit. Audit transport is the dedicated local table (D1 Option
A), not the cross-service event envelope. A password-reset audit records the
action only — never the password or hash.

Lock-out guard (D3/AC6): the last active admin cannot be deactivated or demoted.
The check is atomic — performed under `SELECT ... FOR UPDATE` on the admin rows
inside the mutation's transaction — so two concurrent deactivations cannot both
pass a stale count and leave zero admins.
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import CurrentUser, hash_password, require_role
from ..api.users import PasswordReset, UserCreate, UserOut, UserPatch
from ..database import get_db

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/admin/users",
    dependencies=[Security(require_role("admin"))],
)

_CONFLICT = {"error": "CONFLICT", "detail": "Username is not available", "recoverable": True}
_NOT_FOUND = {"error": "NOT_FOUND", "detail": "User not found", "recoverable": False}
_LAST_ADMIN = {
    "error": "CONFLICT",
    "detail": "Cannot remove the last active admin",
    "recoverable": True,
}


async def _audit(
    db: AsyncSession,
    *,
    actor_user_id: str,
    target_user_id: str,
    action: str,
    detail: str | None,
) -> None:
    """Insert an audit row in the caller's transaction (committed with the mutation)."""
    await db.execute(
        text(
            "INSERT INTO user_audit (audit_id, actor_user_id, target_user_id, action, detail) "
            "VALUES (:aid, :actor, :target, :action, :detail)"
        ),
        {
            "aid": str(uuid.uuid4()),
            "actor": actor_user_id,
            "target": target_user_id,
            "action": action,
            "detail": detail,
        },
    )


async def _would_orphan_admins(db: AsyncSession, *, target_user_id: str) -> bool:
    """True if removing/demoting target_user_id would leave zero active admins.

    Locks the active-admin rows FOR UPDATE so a concurrent deactivation of the
    other last admin serializes behind this one — closing the TOCTOU race (D3)."""
    rows = await db.execute(
        text(
            "SELECT user_id FROM users "
            "WHERE role = 'admin' AND is_active = true FOR UPDATE"
        )
    )
    # Coerce to str: user_id comes back as a UUID object, target_user_id is a str.
    active_admin_ids = {str(r.user_id) for r in rows}
    # If the target is the only active admin, removing/demoting it orphans the system.
    return active_admin_ids == {target_user_id}


async def _load_user(db: AsyncSession, user_id: str) -> UserOut:
    result = await db.execute(
        text("SELECT user_id, username, role, is_active FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return UserOut(
        user_id=str(row.user_id),
        username=row.username,
        role=row.role,
        is_active=row.is_active,
    )


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    rows = await db.execute(
        text(
            "SELECT user_id, username, role, is_active FROM users "
            "ORDER BY created_at"
        )
    )
    return [
        UserOut(
            user_id=str(r.user_id),
            username=r.username,
            role=r.role,
            is_active=r.is_active,
        )
        for r in rows
    ]


@router.post("", response_model=UserOut, status_code=201)
async def create_user_endpoint(
    body: UserCreate,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    # Duplicate username → uniform conflict (no enumeration of which names exist
    # beyond the unavoidable conflict signal). Check before the unique-index raise
    # so we return the controlled ADR-10 envelope, not a DB integrity error.
    existing = await db.execute(
        text("SELECT 1 FROM users WHERE username = :u"), {"u": body.username}
    )
    if existing.fetchone() is not None:
        raise HTTPException(status_code=409, detail=_CONFLICT)

    # Real hash path (A3): the SAME bcrypt the app uses for login verification —
    # a green test cannot pass while the hash/verify pairing is broken. We do the
    # INSERT + audit here (not via the committing create_user helper) so the user
    # row and its audit row land in ONE transaction (AC5: no user without an audit).
    user_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (user_id, username, password_hash, role) "
            "VALUES (:uid, :username, :pwhash, :role)"
        ),
        {
            "uid": user_id,
            "username": body.username,
            "pwhash": hash_password(body.password),
            "role": body.role,
        },
    )
    await _audit(
        db,
        actor_user_id=current.user_id,
        target_user_id=user_id,
        action="create",
        detail=f"role={body.role}",
    )
    await db.commit()
    log.info(
        "admin.user_created",
        actor_user_id=current.user_id,
        target_user_id=user_id,
        role=body.role,
    )
    return await _load_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: str,
    body: UserPatch,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    target = await _load_user(db, user_id)  # 404 if absent

    # Lock-out guard (D3/AC6): if this change deactivates or demotes an admin, make
    # sure it isn't the last active admin — atomically (FOR UPDATE serializes
    # concurrent deactivations of the two last admins).
    deactivating = body.is_active is False
    demoting = body.role is not None and body.role != "admin" and target.role == "admin"
    if (deactivating and target.role == "admin") or demoting:
        if await _would_orphan_admins(db, target_user_id=user_id):
            raise HTTPException(status_code=409, detail=_LAST_ADMIN)

    sets: list[str] = []
    params: dict[str, object] = {"uid": user_id}
    audit_bits: list[str] = []
    if body.role is not None and body.role != target.role:
        sets.append("role = :role")
        params["role"] = body.role
        audit_bits.append(f"role: {target.role} -> {body.role}")
    if body.is_active is not None and body.is_active != target.is_active:
        sets.append("is_active = :active")
        params["active"] = body.is_active
        audit_bits.append(f"is_active: {target.is_active} -> {body.is_active}")

    if not sets:
        # No-op change (values already match) — nothing to mutate or audit.
        return target

    sets.append("updated_at = NOW()")
    await db.execute(
        text(f"UPDATE users SET {', '.join(sets)} WHERE user_id = :uid"), params
    )
    # One audit row per logical action so the trail is queryable per action type.
    if body.role is not None and body.role != target.role:
        await _audit(
            db,
            actor_user_id=current.user_id,
            target_user_id=user_id,
            action="role_change",
            detail=f"{target.role} -> {body.role}",
        )
    if body.is_active is not None and body.is_active != target.is_active:
        await _audit(
            db,
            actor_user_id=current.user_id,
            target_user_id=user_id,
            action="deactivate" if body.is_active is False else "reactivate",
            detail=None,
        )
    await db.commit()
    log.info(
        "admin.user_patched",
        actor_user_id=current.user_id,
        target_user_id=user_id,
        changes="; ".join(audit_bits),
    )
    return await _load_user(db, user_id)


@router.post("/{user_id}/reset-password", status_code=204)
async def reset_password(
    user_id: str,
    body: PasswordReset,
    current: CurrentUser = Security(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _load_user(db, user_id)  # 404 if absent
    await db.execute(
        text(
            "UPDATE users SET password_hash = :pw, updated_at = NOW() "
            "WHERE user_id = :uid"
        ),
        {"pw": hash_password(body.password), "uid": user_id},
    )
    # Audit the ACTION only — never the password or the hash.
    await _audit(
        db,
        actor_user_id=current.user_id,
        target_user_id=user_id,
        action="password_reset",
        detail=None,
    )
    await db.commit()
    log.info(
        "admin.user_password_reset",
        actor_user_id=current.user_id,
        target_user_id=user_id,
    )
