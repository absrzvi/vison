# CLAUDE.md — event-store

FastAPI service (Python 3.11+). Receives inference events from the on-train Hailo-8 ingest pipeline and persists them to SQLite. Also maintains a sync cursor for the cloud-backend to pull events it hasn't seen. Depends on `oebb-shared` for event schemas.

## Stack

- FastAPI + uvicorn
- SQLite via Python's built-in `sqlite3` (no SQLAlchemy — intentionally lightweight for edge deployment)
- Pydantic v2 + pydantic-settings
- structlog
- No external DB dependency — SQLite file path configured via env var

## Commands

```bash
cd event-store
pip install -e ".[dev]"
python -m pytest                  # all tests
python -m pytest -m unit          # fast, no disk I/O
python -m pytest -m integration   # writes to a temp SQLite file
python -m ruff check src/
python -m mypy src/
uvicorn event_store.main:app --reload  # dev server on :8001
```

Coverage threshold: 80%.

## Module Layout

```
src/event_store/
  routes/     — POST /events (ingest), GET /events (sync pull), GET /health
  models.py   — Pydantic request/response models
  database.py — SQLite connection + schema init (reads schema.sql on startup)
  exceptions.py — domain exceptions mapped to HTTP status codes
  config.py   — pydantic-settings Settings
  sync/       — sync cursor logic (last-seen event ID per consumer)
  websocket/  — optional WS push to local on-train consumers
  main.py     — app factory
schema.sql    — authoritative schema; database.py executes this on startup
```

## File Conventions

- `schema.sql` is the source of truth for the DB schema — always update it and `database.py` together
- Do not use Alembic — schema migrations are handled by re-running `schema.sql` with `CREATE TABLE IF NOT EXISTS`
- Integration tests write to a temp file fixture, never a shared DB

## What NOT to Touch

- Do not add SQLAlchemy — the explicit sqlite3 connection is intentional for minimal edge footprint
- Do not add PostgreSQL or any networked DB dependency
- `migrations/` if present — not used; schema is managed via `schema.sql`

## Key Patterns

Idempotent ingest: `POST /events` accepts a `event_id` (UUID from the train). Duplicate `event_id` returns 409 without re-inserting. This is the primary deduplication mechanism across reconnects.

Sync cursor: `GET /events?since_id=<n>` returns all events with `rowid > since_id`. The cloud-backend polls this endpoint and advances its cursor. Do not change the response shape without updating the cloud-backend sync client.
