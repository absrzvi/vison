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

Coverage threshold: 90% (raised in story 4-7).

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

**Idempotent ingest** (story 4-7): `POST /api/v1/events` is idempotent on the natural key `(journey_id, event_type, timestamp)`. A first insert returns **201** with `{"data": {"event_id": "...", "stored": true}}`; a duplicate returns **200** with `{"data": {"event_id": "...", "stored": false}}` — NOT 409. The change from 409 → 200 means producers (inference, fusion) with `@DEFAULT_RETRY` don't backoff-retry on legitimate dupes. Dedup is enforced by the SQLite `UNIQUE (journey_id, event_type, timestamp)` constraint via `INSERT OR IGNORE`.

**Cursor pagination**: `GET /api/v1/events?after=<event_id>&limit=N` returns events with `(timestamp, event_id) > (ref.timestamp, ref.event_id)` in ascending order. `next_cursor` is the `event_id` of the last item on a full page. The cloud-backend polls this endpoint and advances its cursor. Do not change the `EventPage` response shape (`{data, count, journey_id, next_cursor}`) without updating the cloud-backend sync client.

**Filters** (story 4-7): `GET /api/v1/events` also accepts `event_type` (repeatable) and `min_severity` (one of `info|warning|critical`, ordered).

**Authentication** (story 4-7): All `/api/v1/*` routes require `X-API-Key`. Health endpoints and `/ws` are open. Configure via `EVENT_STORE_API_KEY` env var. When unset, auth is bypassed and a startup WARN is logged (dev convenience).

**WebSocket fan-out** (story 4-7): `/ws` accepts a `SubscriptionRequest` JSON as the first frame; replays the last `reconnect_replay_depth` events matching the filter; then streams live events as they are written via POST. The broadcaster uses a per-subscriber `asyncio.Queue(maxsize=256)` — slow consumers have events dropped (logged + counter) rather than blocking the writer path.

**Sync cursor endpoint** (story 4-CS1): `POST /api/v1/sync/cursor` advances `sync_state.last_synced_event_id` and triggers `truncate_old_journeys(retain=3)`. Used ONLY by the cloud-sync container. Body `{"last_event_id": "<uuid4>"}`. Auth-gated by `X-API-Key`. Idempotent: re-submitting the same id returns 200 with `truncated_journeys=0`. Unknown event_id → 400 `INVALID_CURSOR` (same ADR-10 envelope shape as the `?after=<unknown>` path).

## Review Failure Scenarios

Every story touching this service must verify these scenarios before sign-off:

- **Cursor gap:** a sequence gap in event IDs (e.g. events 1–5, then 8) — cursor must not advance past the gap; events 6–7 must not be silently dropped
- **Concurrent duplicate ingest:** two simultaneous `POST /events` with the same natural key — both return without error; exactly one `stored: true`
- **Stale Hailo results on reconnect:** if the inference pipeline reconnects and replays, idempotent ingest must absorb replayed events without side effects
- **WS slow consumer:** a subscriber that doesn't drain its queue — events must be dropped with a log entry, not block the writer path

## Untrusted Input Boundary

All event payloads arriving via `POST /events` originate from the Hailo inference pipeline and VLAN pollers — treat them as untrusted. Validate against the Pydantic schema strictly (no extra fields, no raw pass-through to SQLite string interpolation). Do not log raw payload content at INFO level — log event_id and type only.
