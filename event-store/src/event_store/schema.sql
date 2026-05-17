-- ADR-4: event-store is sole SQLite write authority (single-writer)
-- ADR-1: append-only; no UPDATE or DELETE on events table
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS journeys (
    journey_id   TEXT PRIMARY KEY,
    vehicle_id   TEXT NOT NULL,
    trip_number  TEXT NOT NULL,
    route_name   TEXT,
    origin       TEXT,
    destination  TEXT,
    start_time   TEXT,  -- ISO-8601 UTC
    end_time     TEXT   -- ISO-8601 UTC, nullable
);

CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    journey_id      TEXT NOT NULL,
    vehicle_id      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,   -- ISO-8601 UTC (source_timestamp)
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    source          TEXT NOT NULL,
    schema_version  INTEGER NOT NULL DEFAULT 1,
    payload         TEXT NOT NULL,   -- JSON blob
    ingested_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (journey_id, event_type, timestamp)  -- idempotency: (journey_id, event_type, source_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_events_journey_id ON events (journey_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp  ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_severity   ON events (severity);

-- Cursor-based pagination: (timestamp, event_id) composite
CREATE INDEX IF NOT EXISTS idx_events_cursor ON events (timestamp, event_id);

CREATE TABLE IF NOT EXISTS sync_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    last_synced_event_id TEXT,
    last_sync_at    TEXT
);

-- Ensure singleton row exists
INSERT OR IGNORE INTO sync_state (id) VALUES (1);
