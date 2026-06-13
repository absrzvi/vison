"""Alert-class kill-switch fan-out filter — story 10-1 AC13.

Filters new ALERT_RAISED events of a disabled class out of every fan-out path
to Control Centre (SSE live publish + SSE replay). In-flight escalations stay
visible: only events with t_raised > disabled_at are filtered.

The disabled-class map is cached in-process for 60s; admin endpoint writes call
invalidate() so a kill-switch takes effect on the next fan-out.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()


class AlertClassFilter:
    def __init__(self, ttl_s: float = 60.0) -> None:
        self._ttl = ttl_s
        self._loaded_at: float | None = None
        # alert_code → disabled_at
        self._disabled: dict[str, datetime] = {}
        # R3 clou-3/4: serialise the check-await-set. _generation bumps on every
        # invalidate() so a load whose query overlapped an admin write does NOT
        # cache its now-stale result (which would mask the kill-switch for a TTL).
        self._lock = asyncio.Lock()
        self._generation = 0

    def invalidate(self) -> None:
        self._loaded_at = None
        self._generation += 1

    async def _load(self, db: AsyncSession) -> None:
        now = time.monotonic()
        if self._loaded_at is not None and now - self._loaded_at < self._ttl:
            return
        async with self._lock:
            now = time.monotonic()
            if self._loaded_at is not None and now - self._loaded_at < self._ttl:
                return
            gen_at_start = self._generation
            rows = await db.execute(
                text("""
                    SELECT alert_code, disabled_at
                    FROM alert_class_state
                    WHERE state = 'disabled'
                """)
            )
            disabled = {r.alert_code: r.disabled_at for r in rows}
            if self._generation != gen_at_start:
                # An invalidate() landed during the query — this snapshot may
                # predate the admin write. Apply it but leave the cache stale so
                # the next is_filtered re-loads rather than trusting a racy map.
                self._disabled = disabled
                self._loaded_at = None
                return
            self._disabled = disabled
            self._loaded_at = now

    async def is_filtered(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        payload: dict[str, Any],
        t_raised: datetime,
    ) -> bool:
        """True when this event must be dropped from Control Centre fan-out.

        Only ALERT_RAISED is killable — ALERT_RESOLVED and other allow-listed
        types always pass so in-flight escalations can still resolve.
        """
        if event_type != "ALERT_RAISED":
            return False
        await self._load(db)
        alert_code = str(payload.get("alert_code", ""))
        disabled_at = self._disabled.get(alert_code)
        if disabled_at is None:
            return False
        if disabled_at.tzinfo is None:
            disabled_at = disabled_at.replace(tzinfo=UTC)
        if t_raised.tzinfo is None:
            t_raised = t_raised.replace(tzinfo=UTC)
        if t_raised > disabled_at:
            log.info(
                "fanout.alert_class_filtered",
                alert_code=alert_code,
                t_raised=str(t_raised),
                disabled_at=str(disabled_at),
            )
            return True
        return False


# Process-wide instance shared by ingest (live publish) and SSE replay.
alert_class_filter = AlertClassFilter()
