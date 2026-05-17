from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import structlog

log = structlog.get_logger()


def advance_cursor(conn: sqlite3.Connection, last_event_id: str) -> None:
    """Atomically advance sync cursor. WAL commit guarantees SIGKILL durability."""
    updated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "UPDATE sync_state SET last_synced_event_id = ?, last_sync_at = ? WHERE id = 1",
        (last_event_id, updated_at),
    )
    conn.commit()
    log.info("sync_cursor_advanced", last_event_id=last_event_id)


def truncate_old_journeys(conn: sqlite3.Connection, retain: int = 3) -> int:
    """Delete events for journeys older than the last `retain` journeys.

    Journeys are ranked by most recent event timestamp. The newest `retain`
    journeys are kept as a debug buffer; all others are purged.
    Returns the number of rows deleted.
    """
    cursor = conn.execute(
        """
        DELETE FROM events
        WHERE journey_id NOT IN (
            SELECT journey_id FROM events
            GROUP BY journey_id
            ORDER BY MAX(timestamp) DESC
            LIMIT :retain
        )
        """,
        {"retain": retain},
    )
    conn.commit()
    deleted = cursor.rowcount
    log.info("truncation_executed", deleted=deleted, retained_journeys=retain)
    return deleted
