from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..database import check_connection

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    db_connected: bool


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    connected = check_connection()
    return HealthResponse(status="ok" if connected else "degraded", db_connected=connected)
