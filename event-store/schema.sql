-- ADR-4: event-store is sole SQLite write authority (single-writer)
-- ADR-1: append-only; no UPDATE or DELETE on events table
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    journey_id      TEXT NOT NULL,
    vehicle_id      TEXT NOT NULL,
    timestamp       TEXT NOT NULL,   -- ISO-8601 UTC
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    source          TEXT NOT NULL,
    schema_version  INTEGER NOT NULL DEFAULT 1,
    payload         TEXT NOT NULL    -- JSON blob
);

CREATE INDEX IF NOT EXISTS idx_events_journey_id   ON events (journey_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp    ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_event_type   ON events (event_type);

-- Cursor-based pagination support: (timestamp, event_id) composite
CREATE INDEX IF NOT EXISTS idx_events_cursor ON events (timestamp, event_id);

CREATE TABLE IF NOT EXISTS sync_cursor (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    last_event_id   TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL
);

-- Ensure singleton row exists
INSERT OR IGNORE INTO sync_cursor (id, last_event_id, updated_at)
VALUES (1, '', '1970-01-01T00:00:00Z');
