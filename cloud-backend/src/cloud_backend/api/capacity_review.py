from __future__ import annotations

from pydantic import BaseModel, field_validator


class ReviewRequest(BaseModel):
    note: str | None = None
    priority: str

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: str) -> str:
        allowed = {"Low", "Medium", "High", "low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"priority must be one of Low/Medium/High, got: {v!r}")
        return v.lower()


class ReviewResponse(BaseModel):
    status: str
    queued_at: str


class StatusResponse(BaseModel):
    status: str
