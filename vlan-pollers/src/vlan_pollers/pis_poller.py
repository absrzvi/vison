from __future__ import annotations

import asyncio

import httpx
import structlog
from oebb_shared.http.retry import DEFAULT_RETRY

from .context_state import ContextStateManager
from .models import PisState

log = structlog.get_logger()

# Module-level client — reused across polls; closed in main.py lifespan
_http_client = httpx.AsyncClient()


class PISPoller:
    """Polls PIS schedule/delay state (VLAN 3) via HTTP GET.

    Note: shared/adapters/pis is a WRITE adapter (display_message). This poller
    reads schedule data from an HTTP endpoint — no PISAdapter Protocol involved.
    """

    def __init__(
        self,
        pis_url: str,
        ctx: ContextStateManager,
        poll_interval_s: float,
    ) -> None:
        self._pis_url = pis_url
        self._ctx = ctx
        self._poll_interval_s = poll_interval_s

    @DEFAULT_RETRY
    async def _fetch_schedule(self) -> dict[str, object]:
        r = await _http_client.get(f"{self._pis_url}/schedule", timeout=5.0)
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    async def _poll_once(self) -> None:
        data = await self._fetch_schedule()
        pis = PisState(
            next_station=str(data.get("next_station", "")),
            next_station_arrival_utc=str(data.get("next_station_arrival_utc", "")),
            scheduled_departure=str(data.get("scheduled_departure", "")),
            actual_departure=str(data.get("actual_departure", "")),
            platform=str(data.get("platform", "")),
            delay_min=int(str(data.get("delay_min", 0))),
        )
        await self._ctx.update_pis(pis)

    async def run(self) -> None:  # pragma: no cover
        while True:
            try:
                await self._poll_once()
            except Exception:
                log.warning("pis_poll_failed", recoverable=True)
            await asyncio.sleep(self._poll_interval_s)
