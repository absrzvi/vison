from __future__ import annotations

import asyncio

import httpx
import structlog
from oebb_shared.http.retry import DEFAULT_RETRY

from .context_state import ContextStateManager

log = structlog.get_logger()


class ReservationPoller:
    """Polls reservation data (VLAN 6) via HTTP GET.

    Returns per-coach reservation counts; only car_ids in the configured list
    are retained (server may return extra coaches).
    """

    def __init__(
        self,
        reservation_url: str,
        ctx: ContextStateManager,
        car_ids: list[str],
        poll_interval_s: float,
    ) -> None:
        self._reservation_url = reservation_url
        self._ctx = ctx
        self._car_ids: frozenset[str] = frozenset(car_ids)
        self._poll_interval_s = poll_interval_s
        self._http_client = httpx.AsyncClient()

    async def aclose(self) -> None:
        await self._http_client.aclose()

    @DEFAULT_RETRY
    async def _fetch_reservations(self) -> dict[str, int]:
        r = await self._http_client.get(f"{self._reservation_url}/reservations", timeout=5.0)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, dict):
            raise ValueError(f"reservations payload not an object: {type(raw).__name__}")
        return {
            k: int(v)
            for k, v in raw.items()
            if k in self._car_ids and isinstance(v, (int, float))
        }

    async def _poll_once(self) -> None:
        data = await self._fetch_reservations()
        await self._ctx.update_reservations(data)

    async def run(self) -> None:  # pragma: no cover
        while True:
            try:
                await self._poll_once()
            except Exception:
                log.warning("reservation_poll_failed", recoverable=True)
            await asyncio.sleep(self._poll_interval_s)
