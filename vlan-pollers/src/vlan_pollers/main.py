from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .context_state import ContextStateManager
from .context_state import _http_client as _ctx_client
from .health import router as health_router
from .health import set_snmp_ready
from .journey_tracker import JourneyTracker
from .snmp_poller import SnmpPoller
from .snmp_poller import _http_client as _poller_client

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

_tracker = JourneyTracker()
_ctx = ContextStateManager(
    fusion_url=settings.fusion_url,
    inference_url=settings.inference_url,
    rtsp_ingest_url=settings.rtsp_ingest_url,
)
_poller = SnmpPoller(
    vehicle_id=settings.vehicle_id,
    snmp_host=settings.snmp_host,
    snmp_port=settings.snmp_port,
    snmp_community=settings.snmp_community,
    snmp_speed_oid=settings.snmp_speed_oid,
    poll_interval_s=settings.snmp_poll_interval_s,
    tracker=_tracker,
    ctx=_ctx,
    event_store_url=settings.event_store_url,
    set_snmp_ready_fn=set_snmp_ready,
)


async def _station_approach_watchdog() -> None:
    """Periodically checks PIS next_station_arrival_utc and sets station_approach flag."""
    while True:
        arrival_str = _ctx.state.pis.next_station_arrival_utc
        speed = _ctx.state.speed_kmh

        if arrival_str:
            try:
                arrival_dt = datetime.fromisoformat(arrival_str.replace("Z", "+00:00"))
                now = datetime.now(UTC)
                secs_until = (arrival_dt - now).total_seconds()
                approaching = 0 <= secs_until <= settings.station_approach_window_s
                journey_id = _ctx.state.journey_id
                with structlog.contextvars.bound_contextvars(journey_id=journey_id):
                    await _ctx.set_station_approach(approaching)
            except ValueError:
                log.warning("pis_arrival_parse_failed", value=arrival_str, recoverable=True)
        else:
            # No PIS data — clear stale approach flag
            if _ctx.state.station_approach:
                journey_id = _ctx.state.journey_id
                with structlog.contextvars.bound_contextvars(journey_id=journey_id):
                    await _ctx.set_station_approach(False)

        # Clear flag when speed rises well above approach threshold (departed from stop).
        # Use elif so this can't override the approach=True set above in the same tick.
        if speed > 20.0 and _ctx.state.station_approach:
            journey_id = _ctx.state.journey_id
            with structlog.contextvars.bound_contextvars(journey_id=journey_id):
                await _ctx.set_station_approach(False)

        await asyncio.sleep(2.0)


_bg_tasks: list[asyncio.Task[None]] = []


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    _bg_tasks.append(asyncio.create_task(_poller.run()))
    _bg_tasks.append(asyncio.create_task(_station_approach_watchdog()))
    log.info("vlan_pollers_started", vehicle_id=settings.vehicle_id)
    try:
        yield
    finally:
        for task in _bg_tasks:
            task.cancel()
        await asyncio.gather(*_bg_tasks, return_exceptions=True)
        await _ctx_client.aclose()
        await _poller_client.aclose()
        log.info("vlan_pollers_stopped")


app = FastAPI(title="OEBB vlan-pollers", version="0.1.0", lifespan=_lifespan)
app.include_router(health_router)


if __name__ == "__main__":
    uvicorn.run("vlan_pollers.main:app", host="0.0.0.0", port=8006, reload=False)
