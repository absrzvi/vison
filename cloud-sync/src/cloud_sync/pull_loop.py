"""Pull loop — reads from event-store, enqueues locally.

Runs INDEPENDENTLY of the broker connection state. This is the heart of the
72h offline tolerance: even when the MQTT broker is unreachable, this loop
keeps pulling rows from event-store into the local SQLite buffer.

On HTTP failure: log + back off + retry. Cursor advances locally per pulled
batch (via ``cursor_state_set_pulled``) BEFORE publish — so a restart
resumes pulling from the LAST observed event_id, not the last acked one.
``INSERT OR IGNORE`` handles any duplicates from event-store transparently.
"""
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable

import httpx
import structlog

from . import db as db_mod
from .config import Settings
from .event_store_client import EventStoreClient

log = structlog.get_logger()


async def run(
    stop_event: asyncio.Event,
    client: EventStoreClient,
    conn_factory: Callable[[], sqlite3.Connection],
    settings: Settings,
) -> None:
    """Long-running pull task. Stops when ``stop_event`` is set."""
    conn = conn_factory()
    try:
        while not stop_event.is_set():
            cursor, _ = db_mod.cursor_state_get(conn)
            try:
                page = await client.pull(
                    after_event_id=cursor, limit=settings.pull_batch_size
                )
            except httpx.HTTPError as exc:
                log.warning("cloud_sync.pull_failed", error=str(exc))
                await _sleep_or_stop(stop_event, 5.0)
                continue
            if not page.data:
                await _sleep_or_stop(stop_event, settings.pull_poll_interval_s)
                continue
            for envelope in page.data:
                db_mod.enqueue_event(conn, envelope)
            db_mod.cursor_state_set_pulled(conn, page.data[-1]["event_id"])
            log.info(
                "cloud_sync.pull_batch",
                count=len(page.data),
                last_event_id=page.data[-1]["event_id"],
            )
            # If the page wasn't full, sleep briefly before polling again.
            if page.next_cursor is None:
                await _sleep_or_stop(stop_event, settings.pull_poll_interval_s)
    finally:
        conn.close()


async def _sleep_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
    """Sleep, but wake immediately if ``stop_event`` fires."""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        return
