from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

_snmp_connected: bool = False


def set_snmp_ready(value: bool) -> None:
    global _snmp_connected
    _snmp_connected = value


@router.get("/health/ready")
def health_ready() -> JSONResponse:
    if not _snmp_connected:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "snmp_connected": False, "recoverable": True},
        )
    return JSONResponse(content={"status": "ready", "snmp_connected": True})
