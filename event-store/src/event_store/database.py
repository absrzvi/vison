from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import structlog

from .config import settings
from .exceptions import JourneyNotFoundError, UnsupportedSchemaVersionError

log = structlog.get_logger()

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


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


def insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> bool:
    """Insert event. Returns True if inserted, False if duplicate (idempotent)."""
    version = event.get("schema_version", 1)
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        log.warning("schema_version_unsupported", schema_version=version, recoverable=True)
        raise UnsupportedSchemaVersionError(version)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO events
            (event_id, journey_id, vehicle_id, timestamp, event_type,
             severity, source, schema_version, payload)
        VALUES
            (:event_id, :journey_id, :vehicle_id, :timestamp, :event_type,
             :severity, :source, :schema_version, :payload)
        """,
        {**event, "payload": json.dumps(event.get("payload", {}))},
    )
    conn.commit()
    inserted = cursor.rowcount > 0
    if inserted:
        log.info("event_stored", event_id=event.get("event_id"), journey_id=event.get("journey_id"))
    else:
        log.info("event_duplicate", event_id=event.get("event_id"))
    return inserted


def get_journey(conn: sqlite3.Connection, journey_id: str) -> dict[str, Any]:
    """Return journey metadata or raise JourneyNotFoundError."""
    row = conn.execute(
        "SELECT journey_id, vehicle_id, trip_number, route_name, "
        "origin, destination, start_time, end_time "
        "FROM journeys WHERE journey_id = ?",
        (journey_id,),
    ).fetchone()
    if row is None:
        raise JourneyNotFoundError(journey_id)
    return dict(row)


def get_events_page(
    conn: sqlite3.Connection,
    *,
    journey_id: str | None = None,
    after_event_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    page_size = limit or settings.cursor_page_size

    if journey_id is not None:
        row = conn.execute(
            "SELECT 1 FROM journeys WHERE journey_id = ? LIMIT 1", (journey_id,)
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
        """,
        [*params, page_size],
    ).fetchall()

    return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]


def get_sync_cursor(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT last_synced_event_id FROM sync_state WHERE id = 1"
    ).fetchone()
    if row is None or row["last_synced_event_id"] is None:
        return ""
    return str(row["last_synced_event_id"])


def advance_sync_cursor(conn: sqlite3.Connection, last_event_id: str, updated_at: str) -> None:
    conn.execute(
        "UPDATE sync_state SET last_synced_event_id = ?, last_sync_at = ? WHERE id = 1",
        (last_event_id, updated_at),
    )
    conn.commit()
    log.info("sync_cursor_advanced", last_event_id=last_event_id)
