-- cloud-sync local SQLite buffer schema. Owned by cloud-sync only.
-- ADR-4: WAL mode for durability under SIGKILL.
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=OFF;

CREATE TABLE IF NOT EXISTS publish_queue (
    event_id      TEXT PRIMARY KEY,
    vehicle_id    TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    envelope_json TEXT NOT NULL,
    enqueued_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    published_at  TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_pending
    ON publish_queue (timestamp, event_id)
    WHERE published_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_queue_published
    ON publish_queue (timestamp, event_id)
    WHERE published_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS cursor_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_pulled_event_id TEXT,
    last_acked_event_id  TEXT,
    updated_at TEXT
);

INSERT OR IGNORE INTO cursor_state (id) VALUES (1);
