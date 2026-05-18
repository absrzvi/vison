from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import structlog
import uvicorn
from fastapi import FastAPI

from .config import settings
from .context_state import ContextStateManager
from .health import router as health_router
from .health import set_snmp_ready
from .journey_tracker import JourneyTracker
from .snmp_poller import SnmpPoller

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()

app = FastAPI(title="OEBB vlan-pollers", version="0.1.0")
app.include_router(health_router)

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
                pass
        # Clear flag when departed (speed > 20 after a stop)
        if speed > 20.0 and _ctx.state.station_approach:
            journey_id = _ctx.state.journey_id
            with structlog.contextvars.bound_contextvars(journey_id=journey_id):
                await _ctx.set_station_approach(False)
        await asyncio.sleep(2.0)


_bg_tasks: list[asyncio.Task[None]] = []


@app.on_event("startup")
async def _startup() -> None:
    _bg_tasks.append(asyncio.create_task(_poller.run()))
    _bg_tasks.append(asyncio.create_task(_station_approach_watchdog()))
    log.info("vlan_pollers_started", vehicle_id=settings.vehicle_id)


if __name__ == "__main__":
    uvicorn.run("vlan_pollers.main:app", host="0.0.0.0", port=8006, reload=False)
