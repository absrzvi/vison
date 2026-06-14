"""Request/response models for admin user management (E11-S2).

Password policy (D6, party-mode): NIST-style length-only — min 12, NO composition
rules. max_length=72 is load-bearing, not padding: hash_password truncates at 72
bytes (api/auth.py), so without the cap a >72-byte password would authenticate on
only its first 72 bytes — a silent footgun. The cap 422s it at the boundary.

UserOut NEVER carries password_hash (AC7-7): no secret leaves the API.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

# Roles are a closed set; mirrors the users.role check constraint (0009).
_ROLES = ("admin", "operator")

_Password = Field(min_length=12, max_length=72)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = _Password
    role: str = Field(pattern="^(admin|operator)$")


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


class UserOut(BaseModel):
    user_id: str
    username: str
    role: str
    is_active: bool
