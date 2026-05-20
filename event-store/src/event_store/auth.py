"""X-API-Key authentication dependency — AC8.

Sourced from ``Settings.api_key`` (env ``EVENT_STORE_API_KEY``). When the key
is unset (``None``), the dependency bypasses verification — a single startup
WARN documents this in `main.py`. Production deployments MUST set the env var.

Comparison uses ``hmac.compare_digest`` to defend against timing-attack
fingerprinting of the configured key.
"""
from __future__ import annotations

import hmac
from typing import Annotated

import structlog
from fastapi import Header, HTTPException

from .config import settings

log = structlog.get_logger()


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    configured = settings.api_key
    if configured is None:
        # Dev-mode bypass. Startup WARN already emitted in main.py lifespan.
        return
    expected = configured.get_secret_value().encode()
    provided = (x_api_key or "").encode()
    if not x_api_key or not hmac.compare_digest(provided, expected):
        log.warning("auth.invalid_api_key", provided_present=bool(x_api_key))
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHENTICATED",
                "detail": "missing or invalid X-API-Key",
                "recoverable": False,
            },
        )
