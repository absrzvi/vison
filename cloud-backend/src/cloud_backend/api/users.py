"""Request/response models for admin user management (E11-S2).

Password policy (D6, party-mode): NIST-style length-only — min 12, NO composition
rules. max_length=72 is load-bearing, not padding: hash_password truncates at 72
bytes (api/auth.py), so without the cap a >72-byte password would authenticate on
only its first 72 bytes — a silent footgun. The cap 422s it at the boundary.

UserOut NEVER carries password_hash (AC7-7): no secret leaves the API.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

# Roles are a closed set; mirrors the users.role check constraint (0009).
_ROLES = ("admin", "operator")

# min_length=12 (NIST length-only, D6). max_length is enforced in BYTES by the
# validator below, NOT here: a Field max_length counts CHARACTERS, but bcrypt only
# mixes the first 72 BYTES (hash_password truncates there), so a 72-char multibyte
# password (e.g. 72x "ä" = 144 bytes) would silently authenticate on its first 72
# bytes — the exact truncation footgun the cap exists to close. We cap the byte
# length instead. (No char max_length here so the byte check owns the upper bound.)
_Password = Field(min_length=12)
_MAX_PASSWORD_BYTES = 72


def _validate_password_bytes(v: str) -> str:
    if len(v.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError(
            f"password must be at most {_MAX_PASSWORD_BYTES} bytes "
            "(bcrypt mixes only the first 72 bytes; longer passwords would be "
            "silently truncated)"
        )
    return v


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = _Password
    role: str = Field(pattern="^(admin|operator)$")

    _check_password_bytes = field_validator("password")(_validate_password_bytes)


class UserPatch(BaseModel):
    """Partial update — role and/or is_active. At least one must be present."""

    role: str | None = Field(default=None, pattern="^(admin|operator)$")
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> UserPatch:
        if self.role is None and self.is_active is None:
            raise ValueError("at least one of 'role' or 'is_active' is required")
        return self


class PasswordReset(BaseModel):
    password: str = _Password

    _check_password_bytes = field_validator("password")(_validate_password_bytes)


class UserOut(BaseModel):
    user_id: str
    username: str
    role: str
    is_active: bool
