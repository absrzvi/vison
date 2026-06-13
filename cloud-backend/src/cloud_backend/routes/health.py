from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Security
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import require_api_key
from ..config.confidence_thresholds import DEGRADED_BANNER_FLOOR
from ..database import check_connection, get_db

router = APIRouter()


class _DegradedCache:
    """E10-S1 AC17: 30s in-process cache for the ai_quality_degraded flag."""

    def __init__(self, ttl_s: float = 30.0) -> None:
        self._ttl = ttl_s
        self._computed_at: float | None = None
        self._value = False
        # R3 clou-3/4: guard the check-await-set so two concurrent requests
        # can't interleave around the await and lost-update the cached value.
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        self._computed_at = None
        self._value = False

    async def get(self, db: AsyncSession) -> bool:
        now = time.monotonic()
        if self._computed_at is not None and now - self._computed_at < self._ttl:
            return self._value
        async with self._lock:
            # Double-check inside the lock: a coroutine that queued behind the
            # query-holder returns the freshly-cached value instead of re-querying.
            now = time.monotonic()
            if self._computed_at is not None and now - self._computed_at < self._ttl:
                return self._value
            result = await db.execute(
                text("""
                    SELECT AVG((payload->>'confidence_score')::float)
                    FROM events
                    WHERE event_type = 'ALERT_RAISED'
                      AND timestamp > NOW() - INTERVAL '1 hour'
                      AND (payload->>'confidence_basis') = 'model'
                """)
            )
            mean = result.scalar()
            self._value = mean is not None and float(mean) < DEGRADED_BANNER_FLOOR
            self._computed_at = now
            return self._value


degraded_cache = _DegradedCache()


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


@router.get("/api/v1/health", dependencies=[Security(require_api_key)])
async def api_health(db: AsyncSession = Depends(get_db)) -> dict[str, str | bool]:
    """CC-facing health summary. E10-S1 AC17: server-computed degraded flag
    (fleet-wide rolling-1h mean of model-basis confidence vs the banner floor).

    R3 clou-2: X-API-Key required, matching every other /api/v1/* endpoint. The
    infra probes /health/live and /health/ready stay open for k8s / load-balancer.
    """
    return {
        "status": "ok",
        "ai_quality_degraded": await degraded_cache.get(db),
    }
