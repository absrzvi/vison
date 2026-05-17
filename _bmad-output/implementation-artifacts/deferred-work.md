# Deferred Work

## Deferred from: code review of 1-1-e2e-skeleton-mvp (2026-05-17)

- **#18 `@app.on_event("startup")` deprecated** — migrate to `lifespan` context manager in a future story (FastAPI ≥0.93 deprecation)
- **#19 Timestamps stored as `TEXT` not `TIMESTAMPTZ`** — deliberate PoC simplification; impacts time-range queries; revisit in Epic 3 analytics work
- **#20 `_db_ready` global not safe under multi-worker Uvicorn** — PoC is single-worker; revisit before any production deployment
- **#21 `target_metadata = None` in Alembic** — no ORM models in PoC; autogenerate disabled intentionally
- **#22 Integration test hand-rolls DDL instead of running Alembic** — schema drift risk; fix when cloud-backend schema stabilises
- **#23 `dev-insecure-key` hardcoded default in config** — dev-only; must be overridden via `.env` before any production deployment

## Deferred from: code review of 1-3-postgresql-schema-alembic (2026-05-17)

- **#12 No index on `events.timestamp` / `event_type`** — analytics range queries and SSE alert feeds will full-scan; add composite index in Epic 3 analytics work
- **#13 No index on `journeys.vehicle_id`, `trip_number`** — fleet lookup queries degrade linearly; add when fleet-level queries are introduced
- **#14 `asyncio.run` in env.py risks `RuntimeError` if called while event loop running** — safe for current single-loop usage; review if env.py is ever called from an async context
- **#15 Missing `ingested_at` audit timestamp on events table** — no server-side insertion time; revisit before production if clock-skew detection or ingestion ordering is required
- **#16 `events.vehicle_id` denormalised, no FK/index** — design decision; add index when vehicle-level analytics queries are added
