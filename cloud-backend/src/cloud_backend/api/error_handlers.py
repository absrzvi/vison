from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse

log = structlog.get_logger()


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", path=request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "detail": "An unexpected error occurred.", "recoverable": True},
    )
