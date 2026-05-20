"""Ack loop — advances event-store's sync cursor + truncates locally.

Runs every ``ack_interval_s`` seconds. Computes the contiguous published
prefix of the queue (the longest run of rows with ``published_at`` set,
starting from the chronologically-oldest row). The event_id at the end of
that prefix is safe to ACK upstream — every event up to and including it
has reached the broker.

On successful ACK:
  * Update ``cursor_state.last_acked_event_id``
  * Delete confirmed-published rows from ``publish_queue`` (queue is for
    retry only — once event-store has the ack we don't need them locally)

Event-store internally runs ``truncate_old_journeys(retain=3)`` after each
successful ACK — that's the ADR-4 sync-then-truncate pattern.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
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
    """Long-running ack task."""
    conn = conn_factory()
    try:
        while not stop_event.is_set():
            await _tick(client, conn, settings)
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=settings.ack_interval_s
                )
            except TimeoutError:
                continue
    finally:
        conn.close()


async def _tick(
    client: EventStoreClient,
    conn: sqlite3.Connection,
    settings: Settings,
) -> None:
    """Run one ACK round. Public-by-name for tests."""
    new_cursor = db_mod.contiguous_published_prefix(conn)
    if new_cursor is None:
        return
    _, last_acked = db_mod.cursor_state_get(conn)
    if last_acked == new_cursor:
        return
    log.info("cloud_sync.flush_started", new_cursor=new_cursor)
    t0 = time.perf_counter()
    try:
        body = await client.ack_cursor(new_cursor)
    except httpx.HTTPError as exc:
        log.warning("cloud_sync.ack_failed", error=str(exc))
        return
    acked = body.get("data", {}).get("acked")
    truncated = body.get("data", {}).get("truncated_journeys", 0)
    if acked is None:
        # Cursor drift; ack_cursor already logged.
        return
    db_mod.cursor_state_set_acked(conn, acked)
    deleted = db_mod.delete_acked(conn, acked)
    duration_ms = (time.perf_counter() - t0) * 1000.0
    log.info(
        "cloud_sync.flush_complete",
        acked=acked,
        truncated_journeys=truncated,
        deleted_local_rows=deleted,
        duration_ms=round(duration_ms, 2),
    )


# Public alias for testing the inner step directly.
tick = _tick
