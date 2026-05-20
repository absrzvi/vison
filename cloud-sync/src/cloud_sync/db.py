"""SQLite queue layer for cloud-sync.

Owned exclusively by cloud-sync. NEVER touches event-store's DB file.
WAL mode (ADR-4). Per-task connections — do NOT share a connection across
``await`` boundaries.

``INSERT OR IGNORE`` keyed by ``event_id`` is the local dedup gate — restart
safety is achieved by re-pulling from ``last_pulled_event_id`` (NOT
``last_acked_event_id``), and duplicates from event-store are quietly skipped.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger()

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def _now_iso_z() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with WAL + Row factory.

    Each loop calls this on its own; never share connections across tasks.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Execute the embedded schema.sql idempotently."""
    conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()


def enqueue_event(conn: sqlite3.Connection, envelope: dict[str, Any]) -> bool:
    """INSERT OR IGNORE — returns True if a new row was inserted.

    The full envelope JSON is stored verbatim; we never mutate it. Only
    ``event_id``, ``vehicle_id``, ``event_type``, ``timestamp`` are extracted
    for indexing.
    """
    payload_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO publish_queue
            (event_id, vehicle_id, event_type, timestamp, envelope_json)
        VALUES (:event_id, :vehicle_id, :event_type, :timestamp, :envelope_json)
        """,
        {
            "event_id": envelope["event_id"],
            "vehicle_id": envelope["vehicle_id"],
            "event_type": envelope["event_type"],
            "timestamp": envelope["timestamp"],
            "envelope_json": payload_json,
        },
    )
    conn.commit()
    return cursor.rowcount > 0


def iter_pending(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    """Return up to ``limit`` not-yet-published rows in chronological order."""
    rows = conn.execute(
        """
        SELECT event_id, vehicle_id, event_type, timestamp, envelope_json
        FROM publish_queue
        WHERE published_at IS NULL
        ORDER BY timestamp ASC, event_id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_published(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute(
        "UPDATE publish_queue SET published_at = ? WHERE event_id = ?",
        (_now_iso_z(), event_id),
    )
    conn.commit()


def mark_failed(conn: sqlite3.Connection, event_id: str, error: str) -> None:
    conn.execute(
        """
        UPDATE publish_queue
        SET attempts = attempts + 1,
            last_error = ?
        WHERE event_id = ?
        """,
        (error, event_id),
    )
    conn.commit()


def queue_depth(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM publish_queue WHERE published_at IS NULL"
    ).fetchone()
    return int(row["n"]) if row else 0


def last_publish_utc(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MAX(published_at) AS ts FROM publish_queue"
    ).fetchone()
    if row is None or row["ts"] is None:
        return None
    return str(row["ts"])


def cursor_state_get(
    conn: sqlite3.Connection,
) -> tuple[str | None, str | None]:
    """Return (last_pulled_event_id, last_acked_event_id) or (None, None)."""
    row = conn.execute(
        "SELECT last_pulled_event_id, last_acked_event_id FROM cursor_state WHERE id = 1"
    ).fetchone()
    if row is None:
        return (None, None)
    return (row["last_pulled_event_id"], row["last_acked_event_id"])


def cursor_state_set_pulled(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute(
        """
        UPDATE cursor_state
        SET last_pulled_event_id = ?, updated_at = ?
        WHERE id = 1
        """,
        (event_id, _now_iso_z()),
    )
    conn.commit()


def cursor_state_set_acked(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute(
        """
        UPDATE cursor_state
        SET last_acked_event_id = ?, updated_at = ?
        WHERE id = 1
        """,
        (event_id, _now_iso_z()),
    )
    conn.commit()


def contiguous_published_prefix(conn: sqlite3.Connection) -> str | None:
    """Return the event_id of the LAST row in the contiguous published prefix.

    Walks rows in (timestamp, event_id) ascending order until the first
    ``published_at IS NULL`` gap. The id of the row just before the gap is
    safe to ACK upstream — every event up to and including it has reached
    the broker.

    Returns ``None`` when the first pending row already lacks ``published_at``
    (no progress to ACK yet).

    Strategy (code-review 2026-05-20): use two targeted queries instead of
    scanning the whole queue. (1) Find the (timestamp, event_id) of the
    first pending row — that's the "gap". (2) Find the last published row
    strictly before the gap. O(log N) on the indexed columns, no full scan.
    Drops memory pressure from O(N) to O(1) during 72h offline windows.
    """
    gap = conn.execute(
        """
        SELECT timestamp, event_id
        FROM publish_queue
        WHERE published_at IS NULL
        ORDER BY timestamp ASC, event_id ASC
        LIMIT 1
        """
    ).fetchone()
    if gap is None:
        # No gap — everything is published.
        last_row = conn.execute(
            """
            SELECT event_id
            FROM publish_queue
            WHERE published_at IS NOT NULL
            ORDER BY timestamp DESC, event_id DESC
            LIMIT 1
            """
        ).fetchone()
        return str(last_row["event_id"]) if last_row else None
    # Find the last published row strictly before the gap.
    before_gap = conn.execute(
        """
        SELECT event_id
        FROM publish_queue
        WHERE published_at IS NOT NULL
          AND (timestamp, event_id) < (?, ?)
        ORDER BY timestamp DESC, event_id DESC
        LIMIT 1
        """,
        (gap["timestamp"], gap["event_id"]),
    ).fetchone()
    return str(before_gap["event_id"]) if before_gap else None


def delete_acked(conn: sqlite3.Connection, up_to_event_id: str) -> int:
    """Delete published rows whose (timestamp, event_id) is ≤ that of the cursor.

    Returns the number of rows deleted. Idempotent: re-running with the same
    cursor deletes 0 rows. Called only after event-store has ACKed the cursor.
    """
    ref = conn.execute(
        "SELECT timestamp FROM publish_queue WHERE event_id = ?",
        (up_to_event_id,),
    ).fetchone()
    if ref is None:
        log.warning("cloud_sync.delete_acked.unknown_cursor", event_id=up_to_event_id)
        return 0
    cursor = conn.execute(
        """
        DELETE FROM publish_queue
        WHERE published_at IS NOT NULL
          AND (timestamp, event_id) <= (?, ?)
        """,
        (ref["timestamp"], up_to_event_id),
    )
    conn.commit()
    return cursor.rowcount
