from __future__ import annotations

import asyncio

import structlog
from oebb_shared.adapters.apc.adapter import APCAdapter, OccupancyReading
from oebb_shared.http.retry import DEFAULT_RETRY

from .context_state import ContextStateManager

log = structlog.get_logger()


class APCPoller:
    """Polls APC (VLAN 8) occupancy data via injected APCAdapter.

    The adapter is constructor-injected — MockAPCAdapter is never instantiated here.
    """

    def __init__(
        self,
        adapter: APCAdapter,
        ctx: ContextStateManager,
        car_ids: list[str],
        poll_interval_s: float,
    ) -> None:
        self._adapter = adapter
        self._ctx = ctx
        self._car_ids: tuple[str, ...] = tuple(car_ids)
        self._poll_interval_s = poll_interval_s

    @DEFAULT_RETRY
    async def _fetch_occupancy(self, car_id: str) -> OccupancyReading:
        return await self._adapter.get_occupancy(car_id)

    async def _poll_once(self) -> None:
        readings: dict[str, OccupancyReading] = {}
        for car_id in self._car_ids:
            reading = await self._fetch_occupancy(car_id)
            readings[car_id] = reading
        await self._ctx.update_occupancy(readings)

    async def run(self) -> None:  # pragma: no cover
        while True:
            try:
                await self._poll_once()
            except Exception:
                log.warning("apc_poll_failed", recoverable=True)
            await asyncio.sleep(self._poll_interval_s)
