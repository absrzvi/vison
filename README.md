# OEBB Smart Rail — AI Insights-as-a-Service PoC

Nomad Digital / ÖBB Hailo-8 onboard intelligence platform. Occupancy, safety, and operational events from a single Hailo-8 M.2 accelerator on R5001C SYS2.

## Repository layout

```
shared/          Python package oebb-shared — event envelope, EventType enum, WS subscription, HTTP retry
event-store/     Edge SQLite service (FastAPI, port 8001) — receive, store, and replay events onboard
cloud-backend/   Cloud PostgreSQL service (FastAPI, port 8002) — sync target for landside dashboards
control-centre/  React dashboard (port 3000) — Control Centre live view
```

## Quickstart

### Prerequisites

- Docker ≥ 24 with Compose V2
- Python 3.11+ (for running tests locally)

### Run all services

```bash
cp cloud-backend/.env.example cloud-backend/.env
docker compose up --build
```

Health checks:

```bash
curl http://localhost:8001/health/live    # event-store
curl http://localhost:8001/health/ready
curl http://localhost:8002/health/live    # cloud-backend
curl http://localhost:8002/health/ready
```

### Local development (hot-reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Run tests locally

Install shared package first (required by both services):

```bash
pip install -e shared/
pip install -e "event-store/[dev]"
pip install -e "cloud-backend/[dev]"
```

Then run per-package:

```bash
cd event-store   && python -m pytest tests/ -v
cd cloud-backend && python -m pytest tests/unit/ -v
```

## GitLab CI

Pipeline runs on every push: **lint → security → test → build**.

See [`.gitlab-ci.yml`](.gitlab-ci.yml) for full stage definitions.

```bash
# Lint locally before pushing
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Architecture notes

- Events are append-only (ADR-1). `event_id` is the idempotency key at both layers.
- `journey_id` is stable across midnight crossings: `{vehicle_id}_{trip_number}_{YYYYMMDD}` (ADR-2).
- SQLite WAL on edge (ADR-4); PostgreSQL JSONB on cloud.
- All API errors follow `{"error":"...","detail":"...","recoverable":bool}` envelope (ADR-10).
- `schema_version=1` on every event; consumers log WARNING and skip unknown versions (ADR-5).
