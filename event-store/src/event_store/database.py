from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import structlog

from .config import settings
from .exceptions import (
    InvalidCursorError,
    JourneyNotFoundError,
    UnsupportedSchemaVersionError,
)

log = structlog.get_logger()

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

# Severity ordering — info < warning < critical. Used to bind the
# min_severity filter as an integer score in SQL.
_SEVERITY_SCORE: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


def _severity_score(value: str) -> int:
    """Return the integer score for a known severity. Raises ValueError for
    unknown strings — caller must validate at boundary."""
    if value not in _SEVERITY_SCORE:
        raise ValueError(f"unknown severity: {value!r}")
    return _SEVERITY_SCORE[value]


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


def _build_filter_clauses(
    *,
    event_types: list[str] | None,
    min_severity: str | None,
    journey_id: str | None,
    after_event_id: str | None,
    conn: sqlite3.Connection,
) -> tuple[list[str], list[Any]]:
    """Build dynamic WHERE clauses + parameters for filtered event reads.

    Code-review patches (2026-05-20):
      * Unknown ``after_event_id`` now raises ``InvalidCursorError`` so the
        route layer can return 400 with the ADR-10 envelope. Previously a
        bogus cursor silently returned page 1 from the start, which is a
        pagination footgun.
      * Unknown ``min_severity`` raises ``ValueError`` rather than silently
        becoming "match all" via the legacy -1 sentinel.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if after_event_id:
        ref = conn.execute(
            "SELECT timestamp FROM events WHERE event_id = ?", (after_event_id,)
        ).fetchone()
        if ref is None:
            raise InvalidCursorError(after_event_id)
        clauses.append("(timestamp, event_id) > (?, ?)")
        params.extend([ref["timestamp"], after_event_id])

    if journey_id:
        clauses.append("journey_id = ?")
        params.append(journey_id)

    if event_types:
        placeholders = ",".join(["?"] * len(event_types))
        clauses.append(f"event_type IN ({placeholders})")
        params.extend(event_types)

    if min_severity:
        threshold = _severity_score(min_severity)
        clauses.append(
            "(CASE severity "
            "WHEN 'critical' THEN 2 "
            "WHEN 'warning' THEN 1 "
            "WHEN 'info' THEN 0 "
            "ELSE -1 END) >= ?"
        )
        params.append(threshold)

    return clauses, params


def get_events_page(
    conn: sqlite3.Connection,
    *,
    journey_id: str | None = None,
    after_event_id: str | None = None,
    limit: int | None = None,
    event_types: list[str] | None = None,
    min_severity: str | None = None,
) -> list[dict[str, Any]]:
    """Cursor-paginated, filterable event read.

    AC4: filters by event_type (list, IN clause) and min_severity (ordered).
    """
    page_size = limit or settings.cursor_page_size

    if journey_id is not None:
        row = conn.execute(
            "SELECT 1 FROM journeys WHERE journey_id = ? LIMIT 1", (journey_id,)
        ).fetchone()
        if row is None:
            raise JourneyNotFoundError(journey_id)

    clauses, params = _build_filter_clauses(
        event_types=event_types,
        min_severity=min_severity,
        journey_id=journey_id,
        after_event_id=after_event_id,
        conn=conn,
    )
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = conn.execute(
        f"""
        SELECT event_id, journey_id, vehicle_id, timestamp, event_type,
               severity, source, schema_version, payload
        FROM events
        {where_sql}
        ORDER BY timestamp ASC, event_id ASC
        LIMIT ?
        """,
        [*params, page_size],
    ).fetchall()

    return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]


def get_filtered_events_for_replay(
    conn: sqlite3.Connection,
    *,
    event_types: list[str] | None,
    min_severity: str | None,
    coach_ids: list[str] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Return the LAST ``limit`` events matching the subscription filter,
    in chronological order (timestamp ASC, event_id ASC) — AC7.

    SQL strategy: ORDER BY DESC + LIMIT to grab the tail, then reverse in
    Python. O(n log n) on the index, not on the whole table.

    Coach filter semantics (code-review patch 2026-05-20): the live broadcast
    path treats events whose payload lacks ``car_id`` as "match any coach
    filter" (see ``broadcaster._coach_id_from_payload`` + ``SubscriptionRequest
    .matches_coach``). The replay query must MIRROR that semantic — events
    with NULL ``json_extract(payload, '$.car_id')`` are included regardless of
    the coach_ids filter, so reconnect doesn't drop e.g. JOURNEY_ENDED events
    that have empty payloads.

    JSON1 dependency (code-review patch): ``json_extract`` is a HARD dependency.
    SQLite 3.38+ ships JSON1 by default; the Dockerfile uses python:3.11-slim
    which includes a compatible build. If JSON1 is unavailable the query
    raises ``OperationalError`` — caller logs + returns no results so the
    handler can continue rather than crash. Documented behaviour, not
    silently lying as the previous docstring did.
    """
    if coach_ids is not None and len(coach_ids) == 0:
        # Caller validated this at the boundary; defence in depth.
        raise ValueError("coach_ids must be None or a non-empty list")

    clauses, params = _build_filter_clauses(
        event_types=event_types,
        min_severity=min_severity,
        journey_id=None,
        after_event_id=None,
        conn=conn,
    )
    if coach_ids:
        placeholders = ",".join(["?"] * len(coach_ids))
        # Mirror live semantics: events without car_id match all coach filters.
        clauses.append(
            f"(json_extract(payload, '$.car_id') IN ({placeholders}) "
            "OR json_extract(payload, '$.car_id') IS NULL)"
        )
        params.extend(coach_ids)
    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    try:
        rows = conn.execute(
            f"""
            SELECT event_id, journey_id, vehicle_id, timestamp, event_type,
                   severity, source, schema_version, payload
            FROM events
            {where_sql}
            ORDER BY timestamp DESC, event_id DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # JSON1 unavailable or query miscompile. Don't crash the handler;
        # the live path will start streaming as soon as live events arrive.
        log.warning(
            "replay.sql_failed",
            error=str(exc),
            sql_hint="json_extract may be unavailable (rebuild SQLite with JSON1)",
        )
        return []

    # Reverse so callers receive chronological order.
    return [
        {**dict(r), "payload": json.loads(r["payload"])} for r in reversed(rows)
    ]


def get_sync_cursor(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT last_synced_event_id FROM sync_state WHERE id = 1"
    ).fetchone()
    if row is None or row["last_synced_event_id"] is None:
        return ""
    return str(row["last_synced_event_id"])


def advance_sync_cursor(conn: sqlite3.Connection, last_event_id: str, updated_at: str) -> None:
    """Deprecated shim — use event_store.sync.cursor.advance_cursor instead."""
    from .sync.cursor import advance_cursor  # avoid circular at module level
    advance_cursor(conn, last_event_id)
