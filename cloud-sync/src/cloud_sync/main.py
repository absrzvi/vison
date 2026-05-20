"""cloud-sync entry point.

Launches three independent asyncio tasks under FastAPI's lifespan:
  1. ``pull_loop.run`` — reads from event-store, enqueues locally
  2. ``MqttPublisher.run`` — drains the queue, publishes to Mosquitto
  3. ``ack_loop.run`` — periodically advances event-store's sync cursor

On shutdown the ``stop_event`` is set and all tasks are awaited with a
short timeout.

No os.environ.get() — all config via pydantic-settings (Rule 8).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
import uvicorn
from fastapi import FastAPI

from . import ack_loop, pull_loop
from . import db as db_mod
from .config import Settings
from .event_store_client import EventStoreClient
from .health import router as health_router
from .mqtt_client import MqttPublisher

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger()


def _build_app(settings: Settings) -> FastAPI:
    """Construct the FastAPI app + lifespan."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # 1. Initialise the SQLite buffer (idempotent).
        boot_conn = db_mod.get_connection(settings.queue_db_path)
        try:
            db_mod.init_db(boot_conn)
        finally:
            boot_conn.close()

        # 2. Shared resources: stop signal, http client, MQTT publisher.
        stop_event = asyncio.Event()
        http_client = httpx.AsyncClient(timeout=10.0)
        event_store = EventStoreClient(http_client, settings)
        mqtt = MqttPublisher(settings)

        # Per-task connection factory.
        def _conn_factory() -> db_mod.sqlite3.Connection:  # type: ignore[name-defined]
            return db_mod.get_connection(settings.queue_db_path)

        # 3. Expose to /health.
        app.state.queue_db_path = settings.queue_db_path
        app.state.mqtt = mqtt

        # 4. Launch the three loops. Each task gets a done-callback that
        # surfaces any exception in structured logs (code-review patch
        # 2026-05-20). Without this a sibling task crash would leave the
        # container in a zombie state — healthy on /health but with one of
        # the three loops dead until restart.
        def _task_done_callback(task: asyncio.Task[None]) -> None:
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                log.warning(
                    "cloud_sync.background_task_crashed",
                    task_name=task.get_name(),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        tasks = [
            asyncio.create_task(
                pull_loop.run(stop_event, event_store, _conn_factory, settings),
                name="cloud_sync.pull_loop",
            ),
            asyncio.create_task(
                mqtt.run(stop_event, _conn_factory),
                name="cloud_sync.mqtt_publish_loop",
            ),
            asyncio.create_task(
                ack_loop.run(stop_event, event_store, _conn_factory, settings),
                name="cloud_sync.ack_loop",
            ),
        ]
        for t in tasks:
            t.add_done_callback(_task_done_callback)
        log.info("cloud_sync.started", port=settings.port)
        try:
            yield
        finally:
            stop_event.set()
            for t in tasks:
                t.cancel()
            # Bounded shutdown — don't hang behind a stuck publish.
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=10.0,
                )
            except TimeoutError:
                log.warning("cloud_sync.shutdown_gather_timeout")
            await http_client.aclose()
            log.info("cloud_sync.stopped")

    app = FastAPI(title="cloud-sync", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    return app


def main() -> None:  # pragma: no cover
    settings = Settings()
    app = _build_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":  # pragma: no cover
    main()
