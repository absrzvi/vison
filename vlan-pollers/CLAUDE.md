# CLAUDE.md — vlan-pollers

Onboard VLAN data-poller service (Python 3.11 + FastAPI). Polls the onboard data-source VLANs — Stadler SNMP (speed/train control), APC door counts, PIS/FIS schedules, and reservations — derives journey + context state, and pushes `/context` to the onboard consumers (`inference`, `rtsp-ingest`, `fusion`). Depends on `oebb-shared` for adapters and event schemas. Pure read-side: it reads sensors and pushes context; it does not ingest events itself.

## Stack

- Python 3.11+, strict mypy
- FastAPI + uvicorn (health endpoint + lifespan task host)
- `pysnmp>=6.1` (Stadler SNMP polling)
- `httpx>=0.27` + `tenacity>=8.2` (context push to consumers; `oebb_shared` retry)
- `pydantic-settings` for config (no `env_prefix` — field names map directly to env vars)
- `structlog` (JSON renderer)

## Commands

```bash
cd vlan-pollers
pip install -e ".[dev]"
python -m pytest                  # all tests
python -m pytest -m unit          # pure logic, no I/O
python -m pytest -m integration   # real adapters / respx
python -m ruff check src/ tests/
python -m mypy --strict src/
```

Coverage threshold: 90% (`fail_under = 90`; `main.py` omitted).

## Module Layout

```
src/vlan_pollers/
  main.py             — FastAPI lifespan; launches the poller asyncio tasks
  config.py           — pydantic-settings Settings; poll intervals, source URLs, car_ids
  models.py           — domain dataclasses / Pydantic models
  health.py           — GET /health; SNMP-ready flag
  snmp_poller.py      — Stadler SNMP poll loop (speed → station-approach detection)
  snmp_decoder.py     — SNMP OID/value decoding
  apc_poller.py       — APC door-count poll loop
  pis_poller.py       — PIS/FIS schedule poll loop
  reservation_poller.py — reservation poll loop
  journey_tracker.py  — JourneyTracker; derives journey_id transitions
  context_state.py    — ContextStateManager; builds + pushes /context to consumers
```

## File Conventions

- All config via `pydantic-settings` Settings — no `os.environ.get()` anywhere
- One poller module per data source; shared correlation lives in `context_state.py` / `journey_tracker.py`
- Each poller runs as an independent asyncio task launched in the lifespan — a single source failing must not stop the others

## Key Patterns

**Context push, not event ingest.** vlan-pollers POSTs `/context` (journey_id, speed/station-approach, door-release, throttle flags) to `inference`, `rtsp-ingest`, and `fusion`. It does NOT POST to event-store — it is the upstream context source, not an event producer.

**Journey lifecycle.** `JourneyTracker` derives `journey_id` transitions; on change, the new journey_id flows out on the next `/context` push so downstream state machines (e.g. fusion comfort index) reset on the right boundary. See `[fusion]` journey-lifecycle notes for the consumer side.

**Station-approach detection.** `snmp_poller` reads speed; `context_state` derives the station-approach edge (within `station_approach_window_s`) that `rtsp-ingest` uses to gate P3 cameras. Edge semantics must match what the consumer expects (peek/consume on the fusion side).

## Untrusted Input Boundary

SNMP, APC, and PIS/FIS responses are external/untrusted (root `CLAUDE.md` § Prompt Injection at External Data Boundaries). Validate and decode strictly in the poller/decoder before building context — reject unexpected fields, log anomalies. Do not pass raw poller output into a consumer push without schema validation.

## Credential Boundary

SNMP community strings and any source credentials come from env vars only — never hardcoded, never passed through context payloads or logged. Audit this boundary on every story touching this service (root `CLAUDE.md` § Credential Hygiene).
