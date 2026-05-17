from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import settings
from .exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

_SCHEMA_FILE = Path(__file__).parent.parent.parent / "schema.sql"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_FILE.read_text())
    conn.commit()


def insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
    version = event.get("schema_version", 1)
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersionError(version)
    conn.execute(
        """
        INSERT OR IGNORE INTO events
            (event_id, journey_id, vehicle_id, timestamp, event_type, severity, source, schema_version, payload)
        VALUES
            (:event_id, :journey_id, :vehicle_id, :timestamp, :event_type, :severity, :source, :schema_version, :payload)
        """,
        {**event, "payload": json.dumps(event.get("payload", {}))},
    )
    conn.commit()


def get_events_page(
    conn: sqlite3.Connection,
    *,
    journey_id: str | None = None,
    after_event_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    page_size = limit or settings.cursor_page_size

    if journey_id is not None:
        # Validate journey exists first
        row = conn.execute(
            "SELECT 1 FROM events WHERE journey_id = ? LIMIT 1", (journey_id,)
        ).fetchone()
        if row is None:
            raise JourneyNotFoundError(journey_id)

    cursor_clause = ""
    params: list[Any] = []

    if after_event_id:
        ref = conn.execute(
            "SELECT timestamp FROM events WHERE event_id = ?", (after_event_id,)
        ).fetchone()
        if ref:
            cursor_clause = "AND (timestamp, event_id) > (?, ?)"
            params.extend([ref["timestamp"], after_event_id])

    journey_clause = "AND journey_id = ?" if journey_id else ""
    if journey_id:
        params.append(journey_id)

    rows = conn.execute(
        f"""
        SELECT event_id, journey_id, vehicle_id, timestamp, event_type,
               severity, source, schema_version, payload
        FROM events
        WHERE 1=1
          {cursor_clause}
          {journey_clause}
        ORDER BY timestamp ASC, event_id ASC
        LIMIT ?
        """,  # noqa: S608
        [*params, page_size],
    ).fetchall()

    return [
        {**dict(r), "payload": json.loads(r["payload"])} for r in rows
    ]


def get_sync_cursor(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT last_event_id FROM sync_cursor WHERE id = 1").fetchone()
    return str(row["last_event_id"]) if row else ""


def advance_sync_cursor(conn: sqlite3.Connection, last_event_id: str, updated_at: str) -> None:
    conn.execute(
        "UPDATE sync_cursor SET last_event_id = ?, updated_at = ? WHERE id = 1",
        (last_event_id, updated_at),
    )
    conn.commit()
