# CLAUDE.md — cloud-sync

Onboard MQTT gateway. FastAPI + aiomqtt + SQLite buffer. Bridges `event-store` (REST) → landside Mosquitto broker. Pure transport — never interprets event payloads.

## Stack

- Python 3.11+, strict mypy
- FastAPI + uvicorn (for /health endpoint only)
- `httpx>=0.27` (event-store client)
- `aiomqtt>=2.0,<3.0` (MQTT publisher)
- `tenacity` via `oebb_shared.http.retry.DEFAULT_RETRY`
- `pydantic-settings` (config via `CLOUD_SYNC_*` env vars)
- `structlog` (JSON renderer)
- Local SQLite buffer with WAL — separate file from event-store's DB

## Commands

```bash
cd cloud-sync
pip install -e ".[dev]"
python -m pytest                  # all tests
python -m pytest -m unit          # fast, no I/O
python -m pytest -m integration   # in-process fake broker + respx
python -m ruff check src/ tests/
python -m mypy --strict src/
```

Coverage threshold: 90%. `main.py` excluded.

## Module Layout

```
src/cloud_sync/
  main.py                  — FastAPI lifespan; launches three asyncio tasks
  config.py                — pydantic-settings Settings(env_prefix="CLOUD_SYNC_")
  db.py                    — SQLite queue layer; WAL; INSERT OR IGNORE dedup
  schema.sql               — publish_queue + cursor_state tables
  event_store_client.py    — httpx.AsyncClient + X-API-Key + DEFAULT_RETRY
  mqtt_client.py           — aiomqtt 2.x publisher + token-bucket rate limiter
  pull_loop.py             — pulls from event-store, enqueues locally
  ack_loop.py              — finds contiguous published prefix, POSTs to event-store
  health.py                — GET /health
tests/
  unit/        — db, rate-limit, topic, health, config, security AST
  integration/ — offline accumulation, ordered flush (flagship), sync cursor ack
  contract/    — topic format allowlist
  _fakebroker.py — minimal MQTT 3.1.1 TCP server (~80 LOC)
```

## File Conventions

- `schema.sql` is the source of truth for the queue DB schema; `db.init_db` executes it on startup
- Three INDEPENDENT asyncio loops — pull, publish, ack — share the queue + a `broker_connected: asyncio.Event` flag. The pull loop NEVER blocks on broker state (72h offline AC).
- Per-task SQLite connections (sqlite3 connections are not designed to be shared across awaits cleanly)
- `INSERT OR IGNORE` keyed by `event_id` is the local dedup gate

## What NOT to Touch

- Do not interpret event payloads. Pure transport. The `payload` field of every envelope passes through verbatim.
- Do not open event-store's `events.db` directly. ADR-4 single-writer rule: cloud-sync goes via HTTP.
- Do not add Kafka, RabbitMQ, or any pub/sub library other than aiomqtt.
- Do not lift the rate limit per reconnect — the bucket is per-process so a flapping broker can't trigger a thundering herd.

## Key Patterns

**Three loops, one queue.** `pull_loop` reads from event-store and `INSERT OR IGNORE`s into `publish_queue`. `mqtt_client.run` connects to Mosquitto and drains the pending rows in `(timestamp, event_id)` order. `ack_loop` computes the contiguous published prefix every 30s and `POST`s it to event-store's `/api/v1/sync/cursor`.

**QoS 1 + landside dedup.** Publish at QoS 1; the landside event-store dedupes via `UNIQUE(journey_id, event_type, timestamp)` (ADR-3). QoS 2 would add latency for no benefit.

**Topic format.** `oebb/events/{vehicle_id}/{event_type}` with `vehicle_id` slugified to `[A-Za-z0-9-]` to defend against MQTT wildcard injection (`#`, `+`).

**Empty-string secret coercion.** `CLOUD_SYNC_EVENT_STORE_API_KEY=`, `CLOUD_SYNC_MQTT_USERNAME=`, `CLOUD_SYNC_MQTT_PASSWORD=` (empty strings) all normalise to `None` at config-load — Docker-compose default placeholder no longer creates a "looks configured but broken" deployment.

**Truncation.** After event-store ACKs a cursor advance, it runs `truncate_old_journeys(retain=3)` — retains the last 3 journeys as a debug buffer on the SQLite WAL file.

## Review Failure Scenarios

Every story touching this service must verify these scenarios before sign-off:

- **72h broker offline:** pull loop must continue accumulating into the local SQLite buffer; no data loss, no crash, no blocking of the event-store client
- **Cursor gap:** ack loop must not advance the cursor past a gap in the contiguous published prefix — partial publishes must not be acknowledged
- **Broker reconnect thundering herd:** rate limiter bucket must prevent burst publish after a flapping broker reconnect
- **Credential misconfiguration:** empty-string env vars (`CLOUD_SYNC_EVENT_STORE_API_KEY=`) must normalise to `None` at config load, not silently pass as a valid key

## Credential Boundary

`CLOUD_SYNC_EVENT_STORE_API_KEY` and MQTT credentials must come from env vars only — never hardcoded, never passed through event payloads. The `payload` field of every envelope is transport-opaque; do not inspect or log it.
