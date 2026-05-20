"""Pull loop — reads from event-store, enqueues locally.

Runs INDEPENDENTLY of the broker connection state. This is the heart of the
72h offline tolerance: even when the MQTT broker is unreachable, this loop
keeps pulling rows from event-store into the local SQLite buffer.

On HTTP failure: log + back off + retry. Cursor advances locally per pulled
batch (via ``cursor_state_set_pulled``) BEFORE publish — so a restart
resumes pulling from the LAST observed event_id, not the last acked one.
``INSERT OR IGNORE`` handles any duplicates from event-store transparently.

Per-envelope resilience (code-review 2026-05-20):
  * Malformed envelopes (missing required keys) no longer kill the loop.
    The bad envelope is logged + skipped; cursor still advances past it via
    the last well-formed envelope in the batch.
"""
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from typing import Any

import httpx
import structlog

from . import db as db_mod
from .config import Settings
from .event_store_client import EventStoreClient

log = structlog.get_logger()

_REQUIRED_ENVELOPE_KEYS: tuple[str, ...] = (
    "event_id",
    "vehicle_id",
    "event_type",
    "timestamp",
)


def _last_well_formed_event_id(envelopes: list[dict[str, Any]]) -> str | None:
    """Return the event_id of the LAST envelope that has all required keys.

    Used to advance the cursor even when the page contains a mix of valid
    and malformed envelopes — we don't want a single bad row at the tail
    to block forever.
    """
    for env in reversed(envelopes):
        if all(k in env for k in _REQUIRED_ENVELOPE_KEYS):
            return str(env["event_id"])
    return None


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
            # Enqueue each envelope defensively — a malformed one cannot
            # kill the loop.
            for envelope in page.data:
                missing = [k for k in _REQUIRED_ENVELOPE_KEYS if k not in envelope]
                if missing:
                    log.warning(
                        "cloud_sync.malformed_envelope_skipped",
                        missing_keys=missing,
                        event_id=envelope.get("event_id"),
                    )
                    continue
                try:
                    db_mod.enqueue_event(conn, envelope)
                except (KeyError, sqlite3.Error) as exc:
                    log.warning(
                        "cloud_sync.enqueue_failed",
                        event_id=envelope.get("event_id"),
                        error=str(exc),
                    )
                    continue
            # Advance cursor to the LAST WELL-FORMED envelope in the batch.
            # A trailing bad envelope cannot pin the cursor.
            last_id = _last_well_formed_event_id(page.data)
            if last_id is not None:
                db_mod.cursor_state_set_pulled(conn, last_id)
                log.info(
                    "cloud_sync.pull_batch",
                    count=len(page.data),
                    last_event_id=last_id,
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
