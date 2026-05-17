from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from ..config import get_settings

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_header_scheme)) -> str:
    if not api_key or api_key != get_settings().api_key:
        raise HTTPException(
            status_code=401,
            detail={"error": "UNAUTHORIZED", "detail": "API key required", "recoverable": False},
        )
    return api_key
