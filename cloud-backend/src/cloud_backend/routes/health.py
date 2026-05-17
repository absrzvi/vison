from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import check_connection

router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    connected = await check_connection()
    if not connected:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "PostgreSQL not reachable"},
        )
    return JSONResponse(content={"status": "ok", "db_connected": True})
