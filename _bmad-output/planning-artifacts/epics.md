---
stepsCompleted: [1, 2, 3, 4]
adrUpdates: [ADR-15, ADR-16, ADR-17, ADR-18]
storiesAdded: [E4-S8, E4-S9, E4-S10, E6-S1, E6-S2, E6-S3, E7-S1, E7-S2, E8-S1, E8-S2, E9-S1, E9-S2, E9-S3, E5-S1, E5-S2, E5-S3, E5-S4, E1.5-1, E1.5-2, E1.5-3, E1.5-4, E3-S8, E1-S6']
lastUpdated: 2026-06-05
changelog:
  - "2026-06-05: Detector model drift fix (readiness drift check) — E4-S6 §1352 AC now names `yolox_s_leaky.hef` (YOLOX, Apache-2.0) instead of retired AGPL `yolov8m.hef`. Aligns epics with architecture.md ADR-16 §465 amendment + Hailo capacity budget. No scope change."
  - "2026-05-30 (later): ADR-20 ratified — SSE replaces WebSocket for landside push. Re-scoped E1-S6 (now onboard-only), added new E1-S6' (cloud-backend SSE fan-out), updated E2-S1 (Real SSE Client), E5-S1 (Luggage Live Feed via SSE). Removed FR25 from Epic 2 FRs covered."
  - "2026-05-30: Backfilled Epic 5 (Luggage) + Epic 1.5 (Onboard Infra) bodies from implementation-artifacts. Moved E2-S9 → E3-S8 (System Health). Updated FR Coverage Map for FR23/25/32/34/35 Phase-2 descope. Deduped Epic 3/4 headers."
  - "2026-05-21: Added Epic 6/7/8/9 hardening stories + ADR-15..18."
inputDocuments:
  - _bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/design-artifacts/DD-001-cc-dashboard.md
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md
  - _bmad-output/planning-artifacts/event-payload-schemas.md
  - _bmad-output/planning-artifacts/implementation-readiness-report-2026-05-30.md
  - project-context.md
---

# OEBB Smart Rail — Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for OEBB Smart Rail, decomposing the requirements from the user stories, UX Design, and Architecture into implementable stories for the PoC.

---

## Requirements Inventory

### Functional Requirements

FR1: Live per-coach headcount displayed in real time to Conductor App, PIS, Control Centre Dashboard, and Driver Display.
FR2: Luggage item count per coach surfaced to Conductor App and Control Centre.
FR3: Colour-coded train diagram (coach-level congestion map) shown to conductor and passengers.
FR4: Alert raised to conductor when a bag has been left unattended beyond a configurable duration threshold.
FR5: Alert raised to conductor and driver when a passenger or bag is blocking a door.
FR6: Active Stadler/TCMS alarms ingested via SNMP and shown in plain language to conductor, technician, and driver (critical only for driver).
FR7: High-priority correlated door alert raised when camera and door fault sensor both agree a door problem exists.
FR8: Conductor and passengers are alerted when accessibility-dependent passenger (wheelchair/pushchair) is detected, with coach and door number.
FR9: Speed-correlated door fault escalation — door fault alerts at speed carry higher severity.
FR10: AI alerts suppressed during depot maintenance mode.
FR11: Alert when accessibility door is released and a wheelchair user is nearby.
FR12: Alert to conductor and platform staff when wheelchair ramp is deployed.
FR13: AI-generated fault pattern detection — recurring alarm patterns flagged to technician and maintenance manager.
FR14: Predictive fault alerting — subsystem predicted to fail within a time window surfaced to technician and maintenance manager.
FR15: Natural language diagnostics agent — technician can ask "safe to continue?" and receive a cited answer.
FR16: Automated cleaning work orders generated when coach occupancy intensity exceeds threshold.
FR17: Energy anomalies flagged against occupancy data for fleet maintenance manager.
FR18: Bistro demand intelligence — demand level (HIGH/MEDIUM/LOW), footfall sparkline, queue count, coach load direction, stock alert.
FR19: Boarding volume prediction shown to bistro staff, platform staff, and driver.
FR20: Control Centre dashboard — live fleet view with occupancy, active incidents, and fault alerts across all trains.
FR21: Unified prioritised incident feed for control centre operator, sorted by severity.
FR22: Real-time dwell time shown per stop to control centre operator and capacity planner.
FR23: Predictive overcrowding warning — forecast capacity breach at an upcoming stop.
FR24: Slip/fall detection alert to control centre operator.
FR25: Prohibited zone detection alert to control centre operator.
FR26: Degraded operation alert to control centre operator, technician, and maintenance manager.
FR27: All incidents tagged with trip ID and route for post-incident review.
FR28: Fleet maintenance manager sees predicted failure windows per train.
FR29: Odometer-based maintenance scheduling — flag trains approaching mileage inspection thresholds.
FR30: Parking-triggered depot logic — maintenance window summary generated on train entering parking mode.
FR31: Energy mode awareness — flag trains in battery/energy-saving mode duration.
FR32: No-show seat detection data by route, day type, and class for capacity planner.
FR33: Anonymised ridership analytics — monthly boardings, peak loads, coach class occupancy.
FR34: Occupancy-normalised energy KPIs per journey for ESG reporting.
FR35: Advertising audience metadata — aggregate audience profiles per route.
FR36: Platform display screens show incoming train coach load in real time.
FR37: PIS exterior/interior screens synced with PIS platform change/delay announcements.

### Non-Functional Requirements

NFR1: System uptime ≥99.5% — Docker restart policies; graceful degradation on SYS1 loss.
NFR2: Occupancy accuracy ≥95% — APC fusion for ground-truth calibration.
NFR3: False-positive alert rate <5% — formal suppression state machine.
NFR4: Alert latency within station dwell window (30–90s) — local inference, no cloud round-trip for alerts.
NFR5: Raw video must never leave the train — edge-only inference; anonymised events to cloud only.
NFR6: GDPR compliance — anonymised aggregate only to cloud; events tagged for deletion scope.
NFR7: Rail environment compliance — hardware rated -40°C to +85°C (Hailo-8 M.2 confirmed).
NFR8: Connectivity resilience — all 4 onboard interfaces fully functional when SYS1 is down; Control Centre Dashboard degrades gracefully.
NFR9: All events carry trip_id, vehicle_id, ISO-8601 UTC timestamp to support post-hoc metric analysis.
NFR10: All API responses use snake_case JSON; React frontend converts to camelCase at the API client layer only.
NFR11: All REST routes prefixed /api/v1/ from day one.
NFR12: Coverage gate ≥80% enforced via pytest-cov --cov-fail-under=80.
NFR13: CI/CD on GitLab CI/CD (.gitlab-ci.yml); stages: ruff, mypy --strict, bandit, detect-secrets, pytest.
NFR14: Structured JSON logging (timestamp, container_name, level, event_type, trip_id, message) to local file with logrotate.
NFR15: API key must never appear in source control — managed via .env (PoC) or Docker secrets (fleet).

### Additional Requirements (Architecture)

- Event envelope schema (ADR-1): uuid, journey_id, vehicle_id, timestamp, event_type, severity, source, payload — all events must use this envelope.
- journey_id key scheme (ADR-2): {vehicle_id}_{trip_number}_{journey_start_date_YYYYMMDD} — stable across midnight crossings.
- PostgreSQL schema (ADR-3): `journeys` table + `events` table with JSONB payload; idempotency unique constraint on (journey_id, event_type, source_timestamp).
- SQLite sync cursor pattern (ADR-4): event-store is sole SQLite write authority; sync-then-truncate with sync_state table; keep last 3 journeys as debug buffer.
- EventType taxonomy (ADR-5): shared `events/types.py` StrEnum; append-only — new types require ADR review.
- Auth (ADR-6/7): VLAN isolation for onboard PoC; API key for cloud in PoC; OAuth2/OIDC upgrade path at fleet rollout.
- WebSocket subscription model (ADR-9): client-driven subscriptions with event_type filter, min_severity, coach_id filter, reconnect_replay_depth=50.
- Error envelope (ADR-10): {error, detail, recoverable} on all REST and WebSocket error conditions.
- Docker Compose orchestration for PoC (ADR-11); GitLab CI/CD confirmed (ADR-12).
- Shared code monorepo: `shared/events/`, `shared/adapters/apc/`, `shared/ws/subscription.py`, `shared/http/retry.py`.
- Container startup race: all outbound HTTP clients must implement exponential backoff with health-check loop (P1).
- All containers: `python:3.11-slim-bookworm`, FastAPI+Uvicorn (event-store only), asyncio throughout, httpx for HTTP, pyproject.toml + ruff + pytest.
- APCAdapter Protocol (ADR from architecture) + MockAPCAdapter — swap real adapter when APC format confirmed.
- Implementation sequence: events/types.py → envelope → PostgreSQL DDL → sync cursor → APCAdapter stub → WebSocket spec → FastAPI routes → Control Centre Dashboard → rtsp-ingest → vlan-pollers → inference → fusion → GitLab CI → Conductor App.
- Dev priority: Control Centre Dashboard is the first interface to build (drives WebSocket API contract, early demo surface).

### UX Design Requirements

UX-DR1: Control Centre Dashboard — App shell with top nav bar, critical alert hook (pulsing red pill when Critical escalation unacknowledged >60s), and tab bar (Live · Analytics · System Health).
UX-DR2: Live Monitoring — KPI strip (Active Trains, Open Escalations, Active Incidents, Capacity Alerts, Luggage Alerts) with tap-to-filter behaviour wired to unified feed.
UX-DR3: Fleet List — sorted by severity (red → amber → green); normal trains collapsed by default behind toggle; per-train card shows severity dot, route, dwell status pill, coach occupancy bars, avg%.
UX-DR4: Unified Feed — severity-sorted stream; filter pills (Type · Status · Severity) combinable; unacknowledged count badge; clear filters control.
UX-DR5: Escalation Detail — right-side panel (createPortal); shows full event context; Acknowledge / Resolve / Flag for capacity review actions.
UX-DR6: Train Detail Panel — right panel within Live Monitoring; per-coach occupancy breakdown; AI inference status per coach; recent events list.
UX-DR7: System Health view — subsystem health grid; camera uptime bars; SNMP poll latency; degradation timeline.
UX-DR8: Analytics Panel — four tabs: Exception Workflow, Occupancy Heatmap, Dwell Time, AI Detection Quality; all tabs respond to shared date range selector (7d / 14d / 30d).
UX-DR9: Analytics / Exception Workflow — escalation table with status badges, route/train column, timestamps, resolution time; trend sparklines.
UX-DR10: Analytics / Occupancy Heatmap — route × hour grid with 6-band colour scale (threshold labels: <40%, 40%, 60%, 75%, 90%, ≥90%); horizontal scroll with right-edge fade indicator; labelled legend swatches.
UX-DR11: Analytics / Dwell Time — per-station scheduled vs actual dwell bars with excess indicator; scatter plot of dwell vs occupancy with trend line and Y-axis label; breach count per station.
UX-DR12: Analytics / AI Detection Quality — KPI strip (events, false-positive rate, avg confidence, fleet AI uptime); stacked bar chart of detection events by type per day (unattended / overcrowded / oversized); false positives shown separately below bars; per-train AI inference uptime bars colour-coded by threshold.
UX-DR13: Design token system: all colours via CSS custom properties (--obb-sev-*, --obb-surface-*, --obb-text-on-dark-*, --obb-blue-accent, --obb-border-dark, --font-mono).
UX-DR14: Responsive layout: dashboard designed for 1440px+ desktop; no mobile breakpoints in PoC scope.
UX-DR15: Prototype to production delta (9 items from DD-001): replace MockWebSocketClient with real WS; wire KPI tile filter taps; implement fleet sort by passenger count descending; wire Escalation Detail acknowledge/resolve to API; implement Train Detail API integration; wire capacity review queue endpoint; implement date-range-aware API calls for analytics; replace mock analytics data with real REST endpoints; add per-operator configurable alert threshold.

### FR Coverage Map

> _Updated 2026-05-30: FR23, FR25, FR32, FR34, FR35 descoped to Phase 2 per readiness review. See PRD §5.5 (Deferred / Out of PoC Scope; was §5.4 before the 2026-06-05 Operator Adoption & Trust insertion) for rationale._

| Requirement | Epic(s) |
|---|---|
| FR1–FR3 (occupancy, congestion) | Epic 4 (Onboard Edge Pipeline), Epic 2 (CC Dashboard surfaces) |
| FR4–FR5 (unattended bag, door obstruction) | Epic 4 (inference + fusion), Epic 2 (CC unified feed), Epic 5 (Luggage UI) |
| FR6–FR7 (TCMS alarms, correlated door) | Epic 4 (vlan-pollers + fusion) |
| FR8, FR11–FR12 (accessibility) | Epic 4 (inference + fusion + ramp signal) |
| FR9–FR10 (speed-correlated, maintenance suppression) | Epic 4 (fusion suppression state machine) |
| FR13–FR17 (diagnostics AI, cleaning, energy) | Deferred Phase 2 (Diagnostics AI scope) |
| FR18–FR19 (bistro demand, boarding prediction) | Descoped PoC (Bistro / Platform Staff are Phase 2) |
| FR20–FR21, FR26 (CC live ops) | Epic 2 (Live Operations) |
| FR22 (real-time dwell), FR26 (degraded), FR27 (trip-tag), FR33 (ridership analytics) | Epic 3 (Analytics + System Health), Epic 1 (envelope/trip_id) |
| FR23 (predictive overcrowding) | Deferred Phase 2 |
| FR24 (slip/fall) | Epic 4 (inference safety) |
| FR25 (prohibited zone) | Deferred Phase 2 |
| FR28–FR31 (maintenance manager) | Deferred Phase 2 (Maintenance Dashboard is Phase 2) |
| FR32 (no-show), FR34 (energy KPI), FR35 (advertising audience) | Deferred Phase 2 |
| FR36–FR37 (platform displays, PIS) | Deferred Phase 2 (Platform Staff + PIS apps are Phase 2) |
| FR38–FR42 (operator adoption & trust: confidence metadata, inference heartbeat, kill-switch, behavioural telemetry, alert-quality rates) | Epic 10 (E10-S1 confidence/heartbeat/kill-switch, E10-S2 telemetry, E10-S5 quality rates). Added to PRD §5.4 v1.3 (2026-06-05). |

## Epic List

| # | Epic | Priority | PoC scope |
|---|---|---|---|
| 1 | Foundation & Shared Infrastructure | P0 | ✅ Done |
| 2 | Control Centre Dashboard — Live Operations | P0 | ✅ Done |
| 3 | Control Centre Dashboard — Analytics & System Health | P0 | ✅ Done |
| 4 | Onboard Edge Pipeline | P0 | ✅ Done |
| 5 | Luggage Monitoring — Live Data | P0 | ✅ Done |
| 1.5 | Onboard Containerised Infrastructure (bridge) | P0 | ✅ Done |
| 6 | Fusion Hardening — Journey Lifecycle & Handler Robustness | P1 | ✅ In scope — hardening sprint 1 |
| 7 | Retry & Idempotency Hardening | P1 | ✅ In scope — hardening sprint 1 |
| 8 | Analytics UI Hardening | P2 | ✅ In scope — hardening sprint 1 |
| 9 | Container & Infrastructure Hardening | P2 | ✅ In scope — hardening sprint 1 |
| 10 | Operator Adoption & Trust (AI PM gap-closure) | P1 | 🆕 Proposed — pre-pilot |
| 11 | Control Centre Admin & Identity | P1 | 📋 Planned 2026-06-14 — 5 stories broken down (self-contained JWT, OIDC-swappable); not yet ready-for-dev |

---

## Approved Epic List — Phase 1 PoC

> **Phase scope (confirmed 2026-05-16):**
> Phase 1 = Epics 1–4. Passenger Portal deferred to Phase 1.1 (needs design delivery). PIS Screens, Conductor App, Driver Display, Maintenance Dashboard, Bistro App deferred to Phase 2.
>
> **Event payload schemas:** See `event-payload-schemas.md` — all 17 event types fully specified. Link this file in every story that produces or consumes events.

### Epic 1: Foundation & Shared Infrastructure
Developers can deploy a working system skeleton — event envelope, shared types, DB schema, WebSocket subscription spec, CI/CD pipeline, and landside ingestion infrastructure — so all subsequent epics build on a consistent, tested foundation.

**Story 1 must be:** E2E skeleton MVP — FastAPI running, WebSocket handler stubbed, DB migrations green, GitLab CI passing. Nothing else parallelises until this ships.

**FRs covered:** All NFRs (NFR1–NFR15), ADR-1 through ADR-14 (architecture prerequisites)
**Key deliverables:** `shared/events/types.py`, event envelope, PostgreSQL DDL (`journeys` + `events`), SQLite single-writer, `APCAdapter` Protocol + `MockAPCAdapter`, WebSocket `SubscriptionRequest`, FastAPI+Uvicorn skeleton, `.gitlab-ci.yml`
**Payload schemas:** `event-payload-schemas.md` — all 17 types must be implemented as Pydantic models in `shared/events/`

#### Story 1.L1 — Landside MQTT Ingestion Infrastructure
**As a** backend engineer,
**I want** a Mosquitto broker and TimescaleDB writer running landside in Docker,
**so that** events published by onboard trains are persisted to the timeseries database and made available to the WebSocket gateway and REST API.

**Acceptance criteria:**
- Eclipse Mosquitto broker runs as a Docker service, reachable on port 1883 (internal) and 8883 (TLS, fleet — plain TCP for PoC)
- An `mqtt-ingestor` service subscribes to the `oebb/events/#` topic hierarchy and writes every received event to the `events` TimescaleDB table using the standard event envelope schema (ADR-1)
- Duplicate events are rejected via the idempotency constraint on `(journey_id, event_type, source_timestamp)` (ADR-3)
- `mqtt-ingestor` exposes a `/health` endpoint returning `{"status": "ok", "broker_connected": true, "db_connected": true}`
- A `docker-compose.yml` at repo root brings up: Mosquitto, TimescaleDB, `mqtt-ingestor`, FastAPI event-store, and the WebSocket gateway as a single `docker compose up` command
- GitLab CI runs an integration test that publishes a mock event envelope to Mosquitto and asserts it appears in TimescaleDB within 2 seconds
- Topic structure: `oebb/events/{vehicle_id}/{event_type}` — wildcard subscription `oebb/events/#` captures all trains

**Dependencies:** Story E1-S1 (event envelope + DB schema must exist first)
**Containers added:** `mosquitto`, `mqtt-ingestor`

---

#### Story E1-S1 — System Skeleton MVP

**As a** developer,
**I want** a minimal but fully wired system skeleton — FastAPI running, WebSocket handler stubbed, PostgreSQL migrations green, and `docker compose up` bringing everything up cleanly,
**so that** all subsequent stories have a consistent, tested foundation to build on and nothing blocks parallel development.

**Acceptance criteria:**

**Given** the repository is freshly cloned  
**When** `docker compose up` is run  
**Then** the following services start without error: `event-store` (FastAPI + Uvicorn on port 8000), `postgres` (PostgreSQL 15), and `mosquitto` (MQTT broker); all pass their health checks within 30 seconds

**Given** the `event-store` container is running  
**When** `GET /api/v1/health` is called  
**Then** `{"status": "ok", "db_connected": true}` is returned with HTTP 200

**Given** the `event-store` container is running  
**When** a WebSocket client connects to `ws://event-store:8000/ws`  
**Then** the connection is accepted and a stub welcome message `{"type": "connected"}` is sent; the handler stays open and does not error

**Given** the repo contains `pyproject.toml` at the root  
**When** `ruff check .` is run  
**Then** it exits 0 with no violations (config: `select = ["E", "F", "I", "UP"]`, `line-length = 100`)

**Given** the repo contains `pyproject.toml`  
**When** `mypy --strict shared/ event_store/` is run  
**Then** it exits 0 with no type errors

**Given** `pytest` is run against the skeleton  
**When** coverage is measured  
**Then** `pytest-cov --cov-fail-under=80` passes (skeleton has ≥80% coverage of the lines that exist)

**And** every container's `Dockerfile` uses `python:3.11-slim-bookworm` as base image  
**And** the repo structure includes `shared/`, `event_store/`, `docker-compose.yml`, and `pyproject.toml` at root  
**And** all outbound HTTP clients use `httpx>=0.27` (async) — no `requests` import anywhere in source

**Dependencies:** None — this is the root story  
**Deliverables:** `docker-compose.yml`, `event_store/main.py`, `event_store/ws/handler.py` (stub), `shared/` package skeleton, `pyproject.toml`

---

#### Story E1-S2 — Event Envelope & Pydantic Models

**As a** developer,
**I want** a canonical `EventEnvelope` Pydantic model and all 17 event payload models living in `shared/events/`,
**so that** every container produces and consumes events with a single, validated, type-safe schema and no ad-hoc dict manipulation.

**Acceptance criteria:**

**Given** the `shared/events/types.py` module  
**When** it is imported  
**Then** `EventType` is a `StrEnum` containing exactly these 17 values: `OCCUPANCY_UPDATE`, `OCCUPANCY_THRESHOLD_CROSSED`, `ALERT_RAISED`, `ALERT_RESOLVED`, `VESTIBULE_CONGESTION`, `LUGGAGE_RACK_SATURATION`, `UNATTENDED_BAG`, `DOOR_OBSTRUCTION`, `ACCESSIBILITY_DETECTED`, `RAMP_DEPLOYED`, `ALARM_ACTIVE`, `ALARM_CLEARED`, `JOURNEY_STARTED`, `JOURNEY_ENDED`, `CAMERA_DEGRADED`, `CAMERA_RECOVERED`, `SYNC_COMPLETED`

**Given** the `shared/events/envelope.py` module  
**When** a valid dict is passed to `EventEnvelope(**data)`  
**Then** the model validates and `event_id` is a UUID v4 string, `journey_id` matches the pattern `{vehicle_id}_{trip_number}_{YYYYMMDD}`, `timestamp` is ISO-8601 UTC with Z suffix, `event_type` is an `EventType` member, `severity` is one of `critical | warning | info`, `source` is one of `inference | fusion | vlan-pollers`

**Given** an `EventEnvelope` with an unrecognised `event_type`  
**When** Pydantic validates it  
**Then** a `ValidationError` is raised (no silent coercion)

**Given** `shared/events/payloads.py`  
**When** it is imported  
**Then** it exports one Pydantic model per `EventType`, with field names and types exactly matching `event-payload-schemas.md`; all 17 models are present

**Given** the payload model for `OCCUPANCY_UPDATE`  
**When** `confidence` is omitted from the input dict  
**Then** the field is absent from the serialised output (not set to `0` or `null`) — matches the cross-cutting constraint in `event-payload-schemas.md`

**And** `mypy --strict shared/events/` passes with zero errors  
**And** `pytest tests/unit/test_event_envelope.py` achieves ≥80% coverage of `shared/events/`  
**And** `EventEnvelope.model_json_schema()` can be called without error (enables future OpenAPI integration)

**Dependencies:** E1-S1 (repo skeleton, `shared/` package exists)  
**Deliverables:** `shared/events/types.py`, `shared/events/envelope.py`, `shared/events/payloads.py`, `tests/unit/test_event_envelope.py`

---

#### Story E1-S3 — PostgreSQL Schema & Alembic Migrations

**As a** developer,
**I want** the `journeys` and `events` PostgreSQL tables created via Alembic migrations with the correct idempotency constraint,
**so that** the landside database is ready to receive events from `mqtt-ingestor` and serve analytics queries from the Control Centre Dashboard without duplicate ingestion risk.

**Acceptance criteria:**

**Given** the migration is run against a fresh PostgreSQL 15 database  
**When** `alembic upgrade head` is executed  
**Then** it exits 0 and the `journeys` table exists with columns: `journey_id` (PK, text), `vehicle_id` (text, not null), `trip_number` (text, not null), `route_name` (text, nullable), `origin` (text, nullable), `destination` (text, nullable), `start_time` (timestamptz, not null), `end_time` (timestamptz, nullable)

**And** the `events` table exists with columns: `event_id` (PK, uuid), `journey_id` (FK → `journeys.journey_id`, not null), `event_type` (text, not null), `severity` (text, not null), `source` (text, not null), `timestamp` (timestamptz, not null), `payload` (jsonb, not null), `source_timestamp` (timestamptz, not null)

**And** a unique constraint exists on `(journey_id, event_type, source_timestamp)` — inserting a duplicate raises a DB-level constraint violation, not a silent upsert

**And** a column comment on `journey_id` in both tables reads: "journey_start_date is anchored at trip_number first-seen by vlan-pollers; stable across midnight crossings"

**Given** a second `alembic upgrade head` run against the already-migrated database  
**When** it is executed  
**Then** it exits 0 with no changes applied (idempotent migration run)

**Given** an event is inserted with a duplicate `(journey_id, event_type, source_timestamp)`  
**When** the insert is attempted  
**Then** a `UniqueViolation` (psycopg error code 23505) is raised — no row inserted, no silent skip

**And** `testcontainers-python` is used for all integration tests; no DB mocking permitted (NFR requirement)  
**And** `pytest tests/integration/test_migrations.py` passes against a real PostgreSQL container

**Dependencies:** E1-S1 (docker-compose with postgres service), E1-S2 (EventType taxonomy for `event_type` column values)  
**Deliverables:** `alembic/versions/0001_initial_schema.py`, `alembic.ini`, `tests/integration/test_migrations.py`

---

#### Story E1-S4 — SQLite Event Store & Sync Cursor

**As a** developer,
**I want** the `event-store` container to persist events to a journey-scoped SQLite database with a WAL-safe sync cursor,
**so that** events are durably buffered onboard and can be reliably synced to the cloud without data loss across tunnel traversals or container restarts.

**Acceptance criteria:**

**Given** the `event-store` container receives a POST to `/api/v1/events` with a valid `EventEnvelope` JSON body  
**When** the request is processed  
**Then** the event is written to SQLite in WAL mode; the response is HTTP 201 with `{"event_id": "<uuid>", "stored": true}`

**Given** the `event-store` container is running  
**When** `POST /api/v1/events` is called with a duplicate `(journey_id, event_type, source_timestamp)`  
**Then** HTTP 409 is returned with error envelope `{"error": "DUPLICATE_EVENT", "detail": "...", "recoverable": false}`; no duplicate row is written

**Given** the `sync_state` table exists in SQLite with column `last_synced_event_id`  
**When** the sync cursor advances to `event_id = X` and the container is killed (SIGKILL) before truncation runs  
**Then** on restart, all events with `event_id > last_synced_event_id` are still present in SQLite and can be re-synced (no data loss)

**Given** events from the last 3 journeys are in SQLite  
**When** truncation runs  
**Then** only events from journeys older than the last 3 are removed; the most recent 3 journeys are retained as debug buffer

**Given** all fixtures use `tmp_path`-scoped SQLite files  
**When** WAL mode is enabled  
**Then** no test uses `:memory:` as the DB path (enforced by a linting assertion in `conftest.py`)

**And** `pytest tests/integration/test_sync_cursor.py` passes the SIGKILL scenario described in ADR-4: simulate cloud ack for events 1–50, kill before truncate, restart, assert events 1–50 still present, assert dedup on re-sync  
**And** structured JSON logs are emitted for: event written, event rejected (duplicate), sync cursor advance, truncation executed

**Dependencies:** E1-S1 (container skeleton), E1-S2 (EventEnvelope Pydantic model)  
**Deliverables:** `event_store/db/sqlite.py`, `event_store/db/sync_cursor.py`, `event_store/api/events.py` (POST endpoint), `tests/integration/test_sync_cursor.py`

---

#### Story E1-S5 — APC Adapter Interface & Mock

**As a** developer,
**I want** a typed `APCAdapter` Protocol and a `MockAPCAdapter` implementation with deterministic synthetic data,
**so that** all fusion container development and tests can proceed without real APC hardware, and swapping in the real adapter when the format is confirmed is a single-file change.

**Acceptance criteria:**

**Given** `shared/adapters/apc/adapter.py`  
**When** it is imported  
**Then** it exports `APCAdapter` as a `typing.Protocol` with exactly these async methods: `get_occupancy(car_id: str) -> OccupancyReading` and `get_door_state(car_id: str) -> DoorState`

**And** `OccupancyReading` is a dataclass with fields: `car_id: str`, `count: int`, `timestamp: str` (ISO-8601 UTC)  
**And** `DoorState` is a dataclass with fields: `car_id: str`, `door_id: str`, `is_open: bool`, `timestamp: str`

**Given** `shared/adapters/apc/mock.py` exports `MockAPCAdapter`  
**When** `mock.get_occupancy("car-1")` is called  
**Then** it returns an `OccupancyReading` with deterministic, configurable synthetic values; the same `car_id` always returns the same count unless the mock is reconfigured

**Given** a test that injects `MockAPCAdapter` where `APCAdapter` is type-hinted  
**When** `mypy --strict` is run  
**Then** no type errors are raised (Protocol conformance verified statically)

**Given** `MockAPCAdapter` is used in place of the real adapter  
**When** all fusion-dependent unit tests run  
**Then** zero tests are blocked on APC hardware availability

**And** the module is importable from `from shared.adapters.apc import APCAdapter, MockAPCAdapter`  
**And** `pytest tests/unit/test_apc_adapter.py` achieves ≥80% coverage of `shared/adapters/apc/`

**Dependencies:** E1-S1 (shared package structure)  
**Deliverables:** `shared/adapters/apc/adapter.py`, `shared/adapters/apc/mock.py`, `tests/unit/test_apc_adapter.py`

---

#### Story E1-S6 — WebSocket Subscription Spec & Filter Logic

> **⚠ Scope refined 2026-05-30 by ADR-20.** This story stays as the **onboard event-store** WS contract (intra-CCU consumers: Conductor App + Driver Display in Phase 2). The **landside** cloud-backend → Control Centre push is now SSE — see new story **E1-S6'** below for the SSE fan-out and integration tests. ACs in this story are unchanged for the onboard event-store; do not implement them on the cloud-backend.

**As a** developer,
**I want** the WebSocket endpoint to accept a `SubscriptionRequest` on connect and filter delivered events server-side by event type, severity, and coach ID — with reconnect replay of the last N matching events,
**so that** the Control Centre Dashboard only receives the events it needs and silently missed events (during disconnection) are replayed on reconnect.

**Acceptance criteria:**

**Given** a WebSocket client connects to `ws://event-store:8000/ws` and sends a `SubscriptionRequest` JSON message  
**When** the message is received  
**Then** the server parses it into a `SubscriptionRequest` dataclass with fields: `event_types: list[str]`, `min_severity: str` (`info | warning | critical`), `coach_ids: list[str] | None`, `reconnect_replay_depth: int = 50`; invalid messages return `{"error": "INVALID_SUBSCRIPTION", "detail": "...", "recoverable": false}` and close the connection

**Given** a subscription with `min_severity = "warning"` and a new `info`-severity event is published  
**When** the server processes the event  
**Then** the event is NOT delivered to that subscriber

**Given** a subscription with `event_types = ["OCCUPANCY_UPDATE"]` and a `DOOR_OBSTRUCTION` event arrives  
**When** the server processes the event  
**Then** the event is NOT delivered to that subscriber

**Given** a subscription with `coach_ids = ["car-3"]` and an event for `car-1` arrives  
**When** the server processes the event  
**Then** the event is NOT delivered to that subscriber

**Given** a client reconnects after a 10-second disconnection with `reconnect_replay_depth = 50`  
**When** the subscription handshake completes  
**Then** the server delivers the last 50 events matching the subscription filter that were stored during the disconnection, in chronological order, before resuming live delivery

**Given** a client that was never disconnected  
**When** a new event arrives  
**Then** the event is delivered once and only once — no duplicate delivery

**And** `pytest tests/unit/test_ws_subscription_filter.py` covers all four filter cases above  
**And** `mypy --strict event_store/ws/` passes with zero errors

**Dependencies:** E1-S1 (WebSocket stub), E1-S2 (EventType, severity), E1-S4 (event store for replay)  
**Deliverables:** `shared/ws/subscription.py` (`SubscriptionRequest` dataclass), `event_store/ws/handler.py` (full implementation replacing stub), `tests/unit/test_ws_subscription_filter.py`

---

#### Story E1-S6' — Cloud-Backend SSE Alert Fan-Out

> _New story added 2026-05-30 per ADR-20 to formalise the landside push transport that was implemented ad-hoc in `cloud-backend/routes/alerts_sse.py`. Replaces the landside half of the original E1-S6 scope._

**As a** developer,
**I want** the cloud-backend to expose a Server-Sent Events stream on `GET /api/v1/alerts/stream` that pushes a fixed allow-list of alert event types to authenticated subscribers,
**so that** the Control Centre Dashboard receives real-time alerts over a simple HTTP-friendly transport without needing a bidirectional WebSocket channel landside.

**Acceptance criteria:**

**Given** a client connects to `GET /api/v1/alerts/stream` with a valid `X-API-Key` header  
**When** the connection is established  
**Then** an `EventSource`-compatible stream is returned with `Content-Type: text/event-stream`; each delivered event has fields `event: <event_type>`, `id: <event_id>`, `data: <json-payload>`; the connection stays open until the client closes it

**Given** `ingest.publish_alert(event)` is called on the cloud-backend  
**When** the event type is in `ALERT_EVENT_TYPES = {ALARM_ACTIVE, ALERT_RAISED, ALERT_RESOLVED, LUGGAGE_RACK_SATURATION, UNATTENDED_BAG}`  
**Then** the event is fanned out to all connected subscribers within 500ms of `publish_alert` returning

**Given** a published event whose type is NOT in `ALERT_EVENT_TYPES` (e.g. `OCCUPANCY_UPDATE`)  
**When** `publish_alert` is called  
**Then** the event is persisted to PostgreSQL (existing ingest path) but is NOT pushed over the SSE stream

**Given** an unauthenticated GET to `/api/v1/alerts/stream`  
**When** the request is processed  
**Then** HTTP 401 is returned with the ADR-10 error envelope `{"error": "UNAUTHORIZED", "detail": "API key required", "recoverable": false}`; no stream is opened

**Given** multiple concurrent subscribers (≥3)  
**When** a single `publish_alert` fires  
**Then** all subscribers receive the event; per-subscriber queues are isolated (one slow consumer must not block the others)

**Given** a uvicorn worker is restarted while a client is connected  
**When** the connection drops  
**Then** the client (via `EventSource` auto-reconnect) reconnects with its `Last-Event-ID`; any events the client missed during the gap are reconciled by the client calling REST endpoints (`GET /api/v1/trains/{id}/alerts?status=active`, `GET /api/v1/analytics/system-health`) — there is no server-side wire replay (ADR-20)

**And** `tests/integration/test_alerts_sse.py` covers: valid subscription delivers event within 500ms; unauthenticated request returns 401; non-allow-listed event type is not pushed; 3 concurrent subscribers all receive a single publish; reconnect after worker restart does not produce a duplicate (the same `id` is only seen once if `Last-Event-ID` is honoured by the client)  
**And** `mypy --strict cloud_backend/routes/alerts_sse.py` passes  
**And** no `X-API-Key` value appears in any test fixture file or log line

**Dependencies:** E1-S3 (PostgreSQL events table), E1-S7 (API auth + error envelope), existing `cloud-backend/routes/ingest.py` (already calls `publish_alert`)  
**Deliverables:** `cloud-backend/src/cloud_backend/routes/alerts_sse.py` (ratify current implementation against ACs above + extend `ALERT_EVENT_TYPES` to include luggage types per ADR-20 §Migration impact #3), `tests/integration/test_alerts_sse.py`

---

#### Story E1-S7 — REST API Skeleton & Error Envelope

**As a** developer,
**I want** all FastAPI REST routes prefixed `/api/v1/`, secured with API key authentication, and returning the standard ADR-10 error envelope on all error conditions,
**so that** every API consumer has a consistent, versioned, authenticated interface and error handling is uniform across the system.

**Acceptance criteria:**

**Given** the `event-store` FastAPI app is running  
**When** any request is made without an `X-API-Key` header  
**Then** HTTP 401 is returned with `{"error": "UNAUTHORIZED", "detail": "API key required", "recoverable": false}`

**Given** a valid `X-API-Key` is provided (value loaded from `.env`, never hardcoded)  
**When** `GET /api/v1/health` is called  
**Then** HTTP 200 is returned with `{"status": "ok", "db_connected": true}`

**Given** a request to any endpoint encounters an unhandled exception  
**When** FastAPI processes it  
**Then** HTTP 500 is returned with `{"error": "INTERNAL_ERROR", "detail": "<safe message>", "recoverable": true}`; the raw exception traceback is logged but never returned to the client

**Given** a request is made to `/api/v2/anything` or any unversioned path  
**When** FastAPI processes it  
**Then** HTTP 404 is returned — no unversioned routes exist

**Given** the `shared/http/retry.py` module  
**When** an outbound `httpx` call fails with a transient error (5xx, timeout)  
**Then** exponential backoff with jitter is applied for up to 3 retries; after 3 failures, an error is raised and logged with structured JSON

**And** `OEBB_API_KEY` is read exclusively from environment variable; a `grep -r "OEBB_API_KEY" --include="*.py"` finds only the env-read line, never a hardcoded value  
**And** `detect-secrets` baseline file is committed to repo; pre-commit hook blocks commits containing strings matching `password|secret|key|token|credential`  
**And** `mypy --strict event_store/` and `mypy --strict shared/http/` pass with zero errors

**Dependencies:** E1-S1 (FastAPI skeleton), E1-S4 (events POST endpoint exists)  
**Deliverables:** `event_store/api/auth.py`, `event_store/api/error_handlers.py`, `shared/http/retry.py`, `.env.example`, `.secrets.baseline`

---

### Epic 2: Control Centre Dashboard — Live Operations
Control Centre operators (Claudia) can monitor the full fleet in real time — live train cards with occupancy and severity, unified escalation feed, acknowledge/resolve actions, and escalation detail panel.

**FRs covered:** FR20, FR21, FR24, FR26, FR27 (FR25 descoped 2026-05-30 per PRD v1.1)
**UX-DRs covered:** UX-DR1–UX-DR6, UX-DR13–UX-DR15
**Prototype reference:** `control-centre/` — DD-001 accepted 2026-05-16
**Component files:** `src/components/shell/`, `src/components/live/`, `src/components/train-detail/`, `src/context/FleetContext.jsx`, `src/hooks/useFleetData.js`, `src/sse/RealSseClient.js` (replaces `src/mock/MockWebSocketClient.js` reference per ADR-20)

---

#### Story E2-S1 — Real Push Client (SSE)

> **⚠ Scope refined 2026-05-30 by ADR-20.** Title and AC content updated: landside transport is **SSE**, not WebSocket. The client now uses `EventSource` against `/api/v1/alerts/stream` (no `SubscriptionRequest` round-trip; server filters at `ALERT_EVENT_TYPES`). `MockWebSocketClient` retained as dev fallback under the same name to minimise churn; document the misnomer in code comments. State reconciliation on reconnect uses REST, not wire replay.

**As a** Control Centre operator,
**I want** the dashboard to connect to the live cloud-backend SSE stream (`/api/v1/alerts/stream`) instead of the mock client,
**so that** fleet state, escalations, and train health data reflect real-time events from onboard trains rather than simulated data.

**Acceptance criteria:**

**Given** the dashboard loads in a browser  
**When** `FleetContext` initialises  
**Then** it opens an `EventSource` against `VITE_SSE_URL` (default: `/api/v1/alerts/stream`) — the `X-API-Key` is delivered via the SSE `withCredentials` pattern (CORS-allowed header on the same origin, or via a short-lived signed URL parameter when cross-origin); no subscription handshake message is sent (server-side allow-list per ADR-20)

**Given** the SSE stream is open  
**When** a server event arrives with `event: <event_type>` and `data: <ADR-1 envelope JSON>`  
**Then** `FleetContext` maps it to the frontend train shape documented in DD-001 §4; all consumers (FleetList, UnifiedFeed, TrainDetail, SystemHealth) update without a page reload

**Given** the SSE connection drops  
**When** the browser's built-in `EventSource` reconnect fires  
**Then** the reconnect attempt uses the last-seen `Last-Event-ID` header; a "Reconnecting…" amber banner is shown in the top nav; existing fleet state is preserved (not wiped) during reconnection

**Given** the SSE stream reconnects after a drop  
**When** the stream resumes  
**Then** the client calls `GET /api/v1/trains/{id}/alerts?status=active` for any train it had active in state, plus `GET /api/v1/analytics/system-health`, to reconcile any events missed during the gap; the "Reconnecting…" banner clears; deduplication on `event_id` prevents duplicates in the unified feed

**Given** `VITE_SSE_URL` is not set  
**When** the app starts  
**Then** the browser console logs a single `[FleetContext] VITE_SSE_URL not set — falling back to MockWebSocketClient` warning and the mock client is used; no uncaught exception (legacy class name retained; misnomer documented in source comment)

**And** `MockWebSocketClient` is preserved and remains the default when `VITE_SSE_URL` is absent — the real client is an additive replacement, not a deletion (class is renamed to `RealSseClient.js`; the old `RealWebSocketClient.js` is deleted with a stub re-export that logs a one-time deprecation warning)  
**And** no API keys or secrets appear in frontend source code or built assets

**Dependencies:** E1-S6' (cloud-backend SSE fan-out), E1-S7 (API auth)  
**Files changed:** `src/context/FleetContext.jsx`, `src/hooks/useFleetData.js`, new `src/sse/RealSseClient.js`, remove `src/ws/RealWebSocketClient.js`

---

#### Story E2-S2 — KPI Strip Filter Tap Wiring

**As a** Control Centre operator,
**I want** tapping a KPI tile (Open Escalations, Active Incidents, Capacity Alerts, Luggage Alerts) to automatically activate the matching filter in the unified feed,
**so that** I can drill from a count to the relevant items in one tap without manually setting filters.

**Acceptance criteria:**

**Given** the Live Monitoring view is open with the unified feed visible  
**When** the operator taps the "Open Escalations" KPI tile (`pid-kpi-tile-escalations`)  
**Then** the unified feed filter bar (`pid-feed-filter-bar`) activates the "Unacked" status filter; the feed scrolls to the top; the "Clear filters" control becomes visible

**Given** the operator taps the "Capacity Alerts" KPI tile (`pid-kpi-tile-capacity`)  
**When** the tap is processed  
**Then** the feed activates the "occupancy" type filter; events of other types are hidden

**Given** the operator taps the "Luggage Alerts" KPI tile (`pid-kpi-tile-luggage`)  
**When** the tap is processed  
**Then** the feed navigates to `/dashboard/luggage` (the Luggage Monitoring view) with no additional filter state

**Given** a KPI tile filter is active  
**When** the operator taps "Clear filters" in the feed  
**Then** all filter pills reset to "All"; the KPI tiles return to display-only state; no tile appears selected

**Given** the "Active Trains" KPI tile (`pid-kpi-tile-trains`)  
**When** it is tapped  
**Then** nothing happens — this tile is display-only and has no filter behaviour; it has no `cursor: pointer` or hover state

**And** KPI tile filter state is managed in shared context so navigating away and back preserves the active filter  
**And** each tappable KPI tile has `role="button"` and `tabIndex={0}` with Enter/Space keyboard support

**Dependencies:** E2-S1 (real fleet data populating KPI counts)  
**Files changed:** `src/components/live/LiveMonitoring.jsx`, `src/components/live/UnifiedFeed.jsx`, `src/context/FleetContext.jsx`

---

#### Story E2-S3 — Fleet List Passenger Count Sort

**As a** Control Centre operator,
**I want** the fleet list to sort trains by total passengers aboard (descending) as the default sort,
**so that** the busiest trains are always at the top and I can spot capacity pressure at a glance.

**Acceptance criteria:**

**Given** the fleet list renders with live data  
**When** no sort has been manually selected  
**Then** trains are ordered by `total passengers aboard` (sum of `headCount` across all coaches) descending — the train with the most passengers appears first within each severity band

**Given** two trains have equal passenger counts  
**When** the list renders  
**Then** they are sub-sorted by severity (red → amber → green) as a tiebreaker

**Given** the sort toggle control (`fleet-sort-toggle`) is present  
**When** the operator selects "Severity" sort  
**Then** trains reorder to severity-first (red → amber → green); within the same severity, passenger count descending is the tiebreaker

**Given** the operator switches from "Severity" back to "Passengers" sort  
**When** the selection is made  
**Then** the list reverts to passenger count descending; the toggle reflects the active sort

**Given** a train's passenger count updates via a new WebSocket event  
**When** `FleetContext` processes the event  
**Then** the fleet list re-sorts automatically without a manual refresh; the train card animates to its new position if its rank changes (CSS transition, not instant jump)

**And** normal trains (green severity) remain collapsed behind the "Show N normal trains" toggle regardless of sort order  
**And** the sort preference is stored in `localStorage` and restored on page reload

**Dependencies:** E2-S1 (real passenger counts from WebSocket)  
**Files changed:** `src/components/live/FleetList.jsx`, `src/context/FleetContext.jsx`

---

#### Story E2-S4 — Unified Feed "New Items" Chip

**As a** Control Centre operator,
**I want** a "↑ N new items" chip to appear at the top of the unified feed when new escalations arrive while I'm scrolled down,
**so that** my reading position is not interrupted by auto-scroll and I can choose when to jump to new items.

**Acceptance criteria:**

**Given** the unified feed is scrolled below the top  
**When** one or more new escalation events arrive via WebSocket  
**Then** a chip reading "↑ N new item" / "↑ N new items" appears fixed at the top of the feed container; the feed does NOT auto-scroll to the top

**Given** the chip is visible  
**When** the operator taps or clicks the chip  
**Then** the feed scrolls to the top smoothly; the chip disappears; the new item count resets to zero

**Given** the feed is already scrolled to the top  
**When** new items arrive  
**Then** the feed scrolls to show the new item at the top automatically; the chip does NOT appear (scroll is not interrupted because operator is already at top)

**Given** the chip shows "↑ 3 new items"  
**When** 2 more items arrive before the operator taps the chip  
**Then** the count updates to "↑ 5 new items" — it accumulates, it does not reset

**Given** any active filter is applied to the feed  
**When** a new item arrives that does not match the active filter  
**Then** it does NOT increment the chip count (only filtered-in items count)

**And** the chip uses `pid-feed-new-chip` as its element ID  
**And** the chip is keyboard accessible: `role="button"`, `tabIndex={0}`, Enter/Space triggers the scroll

**Dependencies:** E2-S1 (live events flowing into feed)  
**Files changed:** `src/components/live/UnifiedFeed.jsx`

---

#### Story E2-S5 — Escalation Detail Acknowledge / Resolve API Wiring

**As a** Control Centre operator,
**I want** the Acknowledge and Resolve actions in the Escalation Detail panel to POST to the backend API,
**so that** my actions are persisted, visible to other operators, and logged against the escalation record.

**Acceptance criteria:**

**Given** an escalation with status `unacknowledged` is open in EscalationDetail  
**When** the operator clicks "Acknowledge"  
**Then** a `POST /api/v1/escalations/{id}/acknowledge` request is sent with the `X-API-Key` header; on HTTP 200 the escalation status updates to `acknowledged` in `FleetContext`; the Acknowledge button is replaced by the Resolve form

**Given** an escalation with status `acknowledged` is open  
**When** the operator enters outcome text (≤200 chars) + selects at least one action tag and clicks "Resolve"  
**Then** a `POST /api/v1/escalations/{id}/resolve` request is sent with body `{"outcome": "<text>", "action_tags": ["<tag>", ...], "operator_id": "<from session>"}` and `X-API-Key` header; on HTTP 200 the escalation status updates to `resolved` in `FleetContext`

**Given** the API returns HTTP 4xx or 5xx  
**When** the request fails  
**Then** the action button re-enables; a toast error message appears: "Action failed — please try again"; the escalation status does NOT change in the UI

**Given** two operators have the same escalation open simultaneously  
**When** Operator A acknowledges it  
**Then** Operator B's open panel updates the status pill to `acknowledged` within 5 seconds via the next WebSocket tick; no stale UI state persists

**Given** the Resolve form requires outcome text  
**When** the operator attempts to submit with an empty outcome field  
**Then** the submit button remains disabled and a `"Outcome required"` inline validation message appears below the textarea

**And** the backend REST endpoints `POST /api/v1/escalations/{id}/acknowledge` and `POST /api/v1/escalations/{id}/resolve` must exist (backend story dependency noted)  
**And** all API calls use the shared `httpx` retry utility (ADR-10 error envelope on failure)

**Dependencies:** E2-S1 (FleetContext with real data), E1-S7 (API auth + error envelope)  
**Files changed:** `src/components/live/EscalationDetail.jsx`, new `src/api/escalations.js`  
**Backend required:** `POST /api/v1/escalations/{id}/acknowledge`, `POST /api/v1/escalations/{id}/resolve`

---

#### Story E2-S6 — Train Detail Event-Store Alert Integration

**As a** Control Centre operator,
**I want** the Train Detail panel's Active Alerts list to show first-class alert events from the event-store rather than being derived inline from coach occupancy flags,
**so that** alerts are accurate, carry full context (type, timestamp, confidence, camera), and don't disappear when occupancy data refreshes.

**Acceptance criteria:**

**Given** a train detail panel opens for train ID `{id}`  
**When** the panel mounts  
**Then** a `GET /api/v1/trains/{id}/alerts?status=active` request is sent; the response populates the `td-alerts-list` with alert events in the canonical shape: `{ alert_id, type, coach_id, title, confidence, camera_id, raised_at, status }`

**Given** the API returns an empty array  
**When** the alerts list renders  
**Then** an empty state message "No active alerts for this train" is shown; the `td-alerts-list` does not render a list

**Given** an alert is resolved via the WebSocket stream while the panel is open  
**When** the `ALERT_RESOLVED` event arrives in `FleetContext`  
**Then** the resolved alert is removed from the `td-alerts-list` within one render cycle — no stale resolved alerts remain visible

**Given** a new `ALERT_RAISED` event arrives for the open train  
**When** `FleetContext` processes it  
**Then** the new alert is prepended to the `td-alerts-list` without requiring a panel close/reopen

**Given** the `GET /api/v1/trains/{id}/alerts` call fails  
**When** the error is returned  
**Then** the error envelope (ADR-10) is logged; the alerts section shows "Alert data unavailable" with a retry button; the rest of the Train Detail panel remains functional

**And** the inline derivation of alerts from `coach.hasAlert` is removed from `TrainDetail.jsx` — no fallback to the prototype shortcut  
**And** coach cell tap still filters the alerts list to the selected coach (existing behaviour preserved)

**Dependencies:** E2-S1 (FleetContext + WebSocket), E1-S7 (API auth)  
**Files changed:** `src/components/train-detail/TrainDetail.jsx`  
**Backend required:** `GET /api/v1/trains/{id}/alerts?status=active`

---

#### Story E2-S7 — Loading Skeletons

**As a** Control Centre operator,
**I want** skeleton placeholder states to appear while data-driven sections are loading,
**so that** the UI feels responsive and I know the app is working rather than wondering if it has hung.

**Acceptance criteria:**

**Given** the dashboard loads and the WebSocket connection has not yet delivered its first message  
**When** any of these sections render: KPI strip, fleet list, unified feed, train detail panel  
**Then** each section shows an animated skeleton (pulsing grey blocks matching the approximate layout) rather than an empty container or spinner

**Given** the KPI strip is in skeleton state  
**When** it renders  
**Then** 5 skeleton tiles appear matching the width and height of the real tiles; each pulses with the `--obb-surface-3` → `--obb-surface-4` animation

**Given** the fleet list is in skeleton state  
**When** it renders  
**Then** 3 skeleton train cards appear; each shows a skeleton severity dot, route line, and occupancy bar area

**Given** the unified feed is in skeleton state  
**When** it renders  
**Then** 4 skeleton feed items appear; each shows a skeleton severity dot, title line, and meta line

**Given** the first WebSocket message arrives  
**When** `FleetContext` processes it  
**Then** all skeleton states are replaced by real content in a single render; no skeleton remains visible alongside real data

**Given** the WebSocket delivers data for some trains but not all  
**When** partial data renders  
**Then** real cards show for trains with data; no skeleton persists for trains already received; the "N new items" chip does not fire during initial load

**And** skeleton animation uses CSS `@keyframes` on a shared `.skeleton-pulse` utility class — no JS-driven animation  
**And** skeleton components are co-located with their parent component file (e.g. `FleetListSkeleton` in `FleetList.jsx`)

**Dependencies:** E2-S1 (WebSocket connection state available in FleetContext)  
**Files changed:** `src/components/live/FleetList.jsx`, `src/components/live/UnifiedFeed.jsx`, `src/components/live/LiveMonitoring.jsx`, `src/components/train-detail/TrainDetail.jsx`, `src/styles/skeletons.css`

---

#### Story E2-S8 — Per-Operator Configurable Alert Threshold

**As a** Control Centre operator,
**I want** to configure the threshold at which the critical alert hook (pulsing red pill) activates,
**so that** I can tune alert sensitivity to match my operational context rather than using a hardcoded 60-second default.

**Data model:**

Preferences are stored per operator in a `operator_preferences` PostgreSQL table:

```sql
CREATE TABLE operator_preferences (
  operator_id          TEXT PRIMARY KEY,   -- derived server-side from X-API-Key
  threshold_sec        INTEGER NOT NULL DEFAULT 60
    CHECK (threshold_sec IN (30, 60, 90, 120)),
  staleness_threshold_sec INTEGER NOT NULL DEFAULT 120
    CHECK (staleness_threshold_sec IN (60, 120, 180, 300)),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**API shape:**

```
GET  /api/v1/operators/me/preferences
     → 200 { operator_id, threshold_sec, staleness_threshold_sec }
     → 404 { error: "NOT_FOUND", ... } when no row exists (use defaults: threshold_sec=60, staleness_threshold_sec=120)

PATCH /api/v1/operators/me/preferences
     body: { threshold_sec?: 30|60|90|120, staleness_threshold_sec?: 60|120|180|300 }
     → 200 { operator_id, threshold_sec, staleness_threshold_sec, updated_at }
     → 422 { error: "INVALID_PREFERENCE", detail: "...", recoverable: true }
```

`operator_id` is derived server-side from the `X-API-Key` header — never sent in the request body.

**Acceptance criteria:**

**Given** the operator opens their preferences (settings icon in top nav)  
**When** the preferences panel renders  
**Then** `GET /api/v1/operators/me/preferences` is called; two controls are shown: "Critical alert threshold" (30s / 60s / 90s / 120s, default 60s) and "Connection staleness warning" (60s / 120s / 180s / 300s, default 120s); returned values are highlighted; 404 uses defaults

**Given** the operator selects a new threshold and confirms  
**When** the selection is confirmed  
**Then** `PATCH /api/v1/operators/me/preferences` is called with `{ threshold_sec: N }`; on HTTP 200 the alert hook immediately uses the new value; the preference is also persisted to `localStorage` key `oebb.cc.alertThresholdSeconds` as a cache for offline / fast-load

**Given** the operator reloads the page  
**When** `FleetContext` initialises  
**Then** `localStorage` is read first (instant); a background `GET /api/v1/operators/me/preferences` call reconciles the server value; if they differ, the server value wins and `localStorage` is updated

**Given** the `PATCH` call fails (4xx/5xx)  
**When** the error is returned  
**Then** the threshold control reverts to the previous value; a toast error appears: "Preference not saved — please retry"; `localStorage` is not updated

**Given** an unacknowledged critical escalation exists  
**When** elapsed time since arrival exceeds the operator's configured threshold  
**Then** `pid-app-shell-alert-hook` pulses red and navigates to `/dashboard/live` when clicked

**Given** the escalation is acknowledged  
**When** `FleetContext` processes acknowledgement  
**Then** the alert hook disappears regardless of threshold

**And** the threshold control is keyboard accessible: arrow keys cycle options, Enter confirms  
**And** `DEFAULT_ALERT_THRESHOLD_SECONDS = 60` is the named constant — no magic numbers anywhere

**Dependencies:** E2-S1 (FleetContext + escalation state), E2-S5 (acknowledge action), E1-S7 (API auth + error envelope), E1-S3 (PostgreSQL schema — migration adds `operator_preferences` table)  
**Files changed:** `src/components/shell/AppShell.jsx`, new `src/components/shell/OperatorPreferences.jsx`, `src/context/FleetContext.jsx`, new `src/api/preferences.js`  
**Backend required:** `GET /api/v1/operators/me/preferences`, `PATCH /api/v1/operators/me/preferences`, Alembic migration for `operator_preferences` table

---

> _E2-S9 (System Health Data Feed Integration) was moved to Epic 3 as **E3-S8** on 2026-05-30 to remove a forward dependency on E3-S1._

---

### Epic 3: Control Centre Dashboard — Analytics & System Health

Control Centre operators and capacity planners can analyse historical exceptions, occupancy heatmaps, dwell times, and AI detection quality; fleet maintenance managers can review live system health.

**FRs covered:** FR22 (historical dwell), FR26 (degraded operation), FR33 (anonymised ridership analytics)
**UX-DRs covered:** UX-DR7–UX-DR12
**Component files:** `src/components/analytics/`, `src/components/health/SystemHealth.jsx`
**New REST endpoints required:** `/api/v1/analytics/exceptions`, `/api/v1/analytics/occupancy-heatmap`, `/api/v1/analytics/dwell-time`, `/api/v1/analytics/detection-quality`, `/api/v1/analytics/system-health` — all date-range-aware (system-health endpoint is current-state only)

---

#### Story E3-S1 — Analytics REST Endpoints (Backend)

> **⚠ Oversized — split before dev pickup (readiness review 2026-05-30).** This story defines 5 distinct endpoints with separate response shapes, error handling, and integration tests. Decompose at dev start into:
> - **E3-S1a** — `GET /api/v1/analytics/exceptions` (capacity exceptions; consumed by E3-S2)
> - **E3-S1b** — `GET /api/v1/analytics/occupancy-heatmap` (consumed by E3-S3)
> - **E3-S1c** — `GET /api/v1/analytics/dwell-time` (consumed by E3-S4)
> - **E3-S1d** — `GET /api/v1/analytics/detection-quality` (consumed by E3-S5)
> - **E3-S1e** — `GET /api/v1/analytics/system-health` (consumed by E3-S8; current-state only, no `?range=` param)
>
> Rationale: a single failure or rollback on one endpoint must not block the other four. Each endpoint can ship and pass CI independently; the parent story stays as the umbrella spec until the last sub-story merges.

**As a** developer,
**I want** five date-range-aware analytics REST endpoints implemented in the cloud backend,
**so that** all four analytics sub-tabs and the system health view can query real historical data from PostgreSQL instead of returning mock values.

**Acceptance criteria:**

**Given** the cloud backend is running with migrated PostgreSQL schema (E1-S3)  
**When** `GET /api/v1/analytics/exceptions?range=7d` is called with a valid `X-API-Key`  
**Then** HTTP 200 is returned with a JSON array of exception records; each record contains: `exception_id`, `route`, `train_id`, `departure`, `date`, `status` (`unreviewed | in_review | dismissed`), `severity`, `coach_peaks` (array of `{ coach_id, peak_pct }`), `trend` (array of 7 daily peak values), `conrad_flag` (object or null); records are grouped by route in the response

**Given** `GET /api/v1/analytics/occupancy-heatmap?range=14d`  
**When** called  
**Then** HTTP 200 returns `{ routes: [...], hours: ["05:00"..."23:00"], cells: [[pct|null, ...], ...] }` — `null` for hours with no data in the range; cells are pre-aggregated averages, not raw events

**Given** `GET /api/v1/analytics/dwell-time?range=30d`  
**When** called  
**Then** HTTP 200 returns an array of station records: `{ station, scheduled_sec, actual_sec, breach_count, occupancy_pct }` sorted by `actual_sec` descending; `breach_count` is the cumulative count of dwell breaches in the requested range, queried directly from the events table — not scaled from a 7d base

**Given** `GET /api/v1/analytics/detection-quality?range=7d`  
**When** called  
**Then** HTTP 200 returns `{ kpi: { total_events, fp_rate, avg_confidence, fleet_uptime_pct }, daily_bars: [...], per_train_uptime: [...] }`; `fp_rate` is `null` when both `total_events` and `total_fp` are zero (not `0.0`)

**Given** `GET /api/v1/analytics/system-health`  
**When** called (no range param — returns current state)  
**Then** HTTP 200 returns an array of train health records matching the shape documented in DD-001 §4 `appDetail` / `deviceDetail` / `connectivity` fields; `last_healthy` timestamps are ISO-8601 UTC strings (not client-formatted)

**Given** an invalid range value such as `?range=90d` is passed  
**When** the request is processed  
**Then** HTTP 422 is returned with `{"error": "INVALID_RANGE", "detail": "range must be one of: 7d, 14d, 30d", "recoverable": true}`

**And** all five endpoints require `X-API-Key` authentication (ADR-7)  
**And** `testcontainers-python` integration tests seed the PostgreSQL DB with fixture events and assert each endpoint returns the correct aggregated values  
**And** `mypy --strict` passes on all new backend modules

**Dependencies:** E1-S3 (PostgreSQL schema), E1-S7 (API auth + error envelope), E1-L1 (events in DB from MQTT ingestor)  
**Deliverables:** `cloud_backend/api/analytics.py`, `cloud_backend/api/system_health.py`, `tests/integration/test_analytics_endpoints.py`

---

#### Story E3-S2 — Capacity Exceptions — Real Data & Date Picker

**As a** Control Centre operator,
**I want** the Capacity Exceptions tab to show real historical exception records from the backend and let me select any date range up to 90 days back,
**so that** I can investigate capacity patterns beyond the 30-day mock window and take action on real incidents.

**Acceptance criteria:**

**Given** the Analytics panel opens on the Capacity Exceptions tab  
**When** the component mounts  
**Then** `GET /api/v1/analytics/exceptions?range=7d` is called (default range); a loading skeleton is shown while the request is in flight; results replace the skeleton on success

**Given** the response contains exception records  
**When** the list renders  
**Then** exceptions are grouped by route (route group header + count badge); within each group, records are sorted red-first; the coach occupancy chart uses server-provided `coach_peaks` array — no client-side derivation from a timeline

**Given** the operator changes the date range control  
**When** a new range is selected  
**Then** the request is re-fired with the new `?range=` parameter; the list and detail panel update; the previously selected exception is deselected

**Given** the date range selector  
**When** it renders  
**Then** it is a full calendar date picker (not the 3-option toggle); the operator can select any start and end date up to 90 days back from today; the selected range is passed to the API as `?from=YYYY-MM-DD&to=YYYY-MM-DD` (the backend accepts both `range=` shorthand and explicit `from/to`)

**Given** the operator clicks "Add to capacity review queue" on an unreviewed exception  
**When** the review modal is completed (note + priority selected) and confirmed  
**Then** `POST /api/v1/analytics/exceptions/{id}/review` is called with `{ note, priority }`; on success the exception status updates to `in_review` and the action strip shows "Queued · Priority: {X}" with the `queued_at` timestamp

**Given** the operator clicks "No action required" (dismiss)  
**When** confirmed  
**Then** `POST /api/v1/analytics/exceptions/{id}/dismiss` is called; on success the exception moves to the dismissed section; "Reopen" ghost button calls `POST /api/v1/analytics/exceptions/{id}/reopen`

**Given** the operator clicks the "Export CSV" button in the Analytics tab bar  
**When** the request completes  
**Then** `GET /api/v1/capacity-review-queue/export?format=csv` is called; the browser downloads a file named `capacity-review-{YYYY-MM-DD}.csv` containing all queued and in-review exceptions with columns: `exception_id`, `route`, `train_id`, `departure_date`, `priority`, `note`, `queued_by`, `queued_at`, `status`; dismissed exceptions are excluded

**Given** the capacity review queue is empty  
**When** the operator clicks "Export CSV"  
**Then** the download still proceeds; the CSV contains the header row only; no error toast

**And** `GET /api/v1/analytics/exceptions` API error shows: "Exception data unavailable — retry" with a retry button; no crash  
**And** the "View Conrad's full flag →" link is wired to navigate to the Conductor App capacity flag deep-link URL (stored in `VITE_CONDUCTOR_APP_URL` env var); if env var is absent the link is hidden  
**And** the capacity review queue is stored in an internal `capacity_review_queue` PostgreSQL table — no integration with external ÖBB fleet planning systems in PoC scope

**Dependencies:** E3-S1 (backend endpoint), E2-S1 (FleetContext for WS connection state)  
**Files changed:** `src/components/analytics/ExceptionWorkflow.jsx`, new `src/api/analytics.js`  
**Backend required:** `POST /api/v1/analytics/exceptions/{id}/review`, `/dismiss`, `/reopen`, `GET /api/v1/capacity-review-queue/export`

**Data model (new table):**
```sql
CREATE TABLE capacity_review_queue (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exception_id TEXT NOT NULL,
  route        TEXT NOT NULL,
  train_id     TEXT NOT NULL,
  departure_date DATE NOT NULL,
  priority     TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
  note         TEXT,
  queued_by    TEXT NOT NULL,   -- operator_id from X-API-Key
  queued_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status       TEXT NOT NULL DEFAULT 'in_review'
               CHECK (status IN ('in_review', 'dismissed'))
);
```

---

#### Story E3-S3 — Occupancy Heatmap — Real Data

**As a** Control Centre operator,
**I want** the Occupancy Heatmap to show real per-range aggregated occupancy data from the backend,
**so that** the route × hour grid reflects actual historical patterns rather than a scaled mock array.

**Acceptance criteria:**

**Given** the operator navigates to the Occupancy Heatmap tab  
**When** the component mounts  
**Then** `GET /api/v1/analytics/occupancy-heatmap?range=7d` is called (inheriting the shared date range state); a loading skeleton matching the grid dimensions is shown during the request

**Given** the API response contains `cells` with some `null` values  
**When** the heatmap renders  
**Then** `null` cells display "—" with dim styling (`occ-heatmap__cell--null`); they are not clamped to `0` or rendered as `0%`

**Given** the operator changes the shared date range (7d / 14d / 30d)  
**When** the new range is selected  
**Then** `GET /api/v1/analytics/occupancy-heatmap?range={new_range}` is called; the grid re-renders with the new data; hover tooltips update to reflect the new range label

**Given** the API returns a route the heatmap has not seen before  
**When** the grid renders  
**Then** the new route appears as a new row without any code change — rows are data-driven, not hardcoded

**Given** the API call fails  
**When** the error is returned  
**Then** the heatmap area shows "Occupancy data unavailable" with a retry button; the tab bar and date range selector remain functional

**And** all existing heatmap interactions remain functional with real data: hover tooltip, keyboard navigation (`tabIndex`, `aria-label`, `:focus-visible`), hover scale animation, right-edge scroll fade  
**And** the peak hour table below the heatmap uses the same API response — no separate request

**Dependencies:** E3-S1 (backend endpoint)  
**Files changed:** `src/components/analytics/OccupancyHeatmap.jsx`, `src/api/analytics.js`

---

#### Story E3-S4 — Dwell Time — Real Data

**As a** Control Centre operator,
**I want** the Dwell Time tab to show real breach counts and dwell durations queried from the event store per selected range,
**so that** I can make accurate station performance assessments based on actual data rather than multiplied mock values.

**Acceptance criteria:**

**Given** the operator navigates to the Dwell Time tab  
**When** the component mounts  
**Then** `GET /api/v1/analytics/dwell-time?range=7d` is called; a loading skeleton is shown; on success, the bar chart and scatter plot render with real station data

**Given** the API response includes `breach_count` per station  
**When** the breach count section renders  
**Then** it shows the direct server value — no `×1/×2/×4` multiplier is applied client-side; the period label matches the selected range ("this week" / "last 14 days" / "last 30 days")

**Given** the operator changes the date range  
**When** the new range is selected  
**Then** `GET /api/v1/analytics/dwell-time?range={new_range}` is fired; the bar chart, scatter plot, breach counts, and correlation insight all update from the new response

**Given** the API returns an empty station array  
**When** the component renders  
**Then** the empty state "No dwell data available for this period." is shown for both the bar chart and scatter plot sections

**Given** the scatter plot renders  
**When** it displays  
**Then** regression line and R² correlation label are computed client-side from the server-provided `{ actual_sec, occupancy_pct }` pairs — the server does not pre-compute R²; the existing `fmtSec` formatting function is preserved unchanged

**And** the API error state shows "Dwell data unavailable — retry" with retry button  
**And** all existing chart interactions are preserved: scheduled tick hover tooltip, scatter dot colours by station, axis tick placement

**Dependencies:** E3-S1 (backend endpoint)  
**Files changed:** `src/components/analytics/DwellTime.jsx`, `src/api/analytics.js`

---

#### Story E3-S5 — AI Detection Quality — Real Data

**As a** Control Centre operator,
**I want** the AI Detection Quality tab to show real per-week detection counts and per-train uptime computed from the inference event log,
**so that** I can assess actual AI performance rather than viewing deterministic baked constants.

**Acceptance criteria:**

**Given** the operator navigates to the AI Detection Quality tab  
**When** the component mounts  
**Then** `GET /api/v1/analytics/detection-quality?range=7d` is called; a loading skeleton is shown for the KPI strip, bar chart, and uptime list; results replace skeletons on success

**Given** the API returns `fp_rate: null` (both `total_events` and `total_fp` are zero)  
**When** the KPI strip renders  
**Then** the FP rate tile shows "—" and "(no data)" label — not "0%" or "0.0%"; this matches the existing prototype null-state logic

**Given** the `daily_bars` array in the API response  
**When** the detection chart renders for `range=7d`  
**Then** bars are labelled Mon–Sun from the actual dates in the response; for `range=14d` or `range=30d` bars are weekly aggregates labelled W1, W2, etc.; `maxBar` is floored at 1 to prevent divide-by-zero

**Given** the `per_train_uptime` array in the response  
**When** the uptime list renders  
**Then** trains are sorted ascending by uptime (lowest first); the uptime bar maps 70–100% to full bar width; the 85% warning threshold line is shown; colours: green ≥85% · amber 70–84% · red <70%

**Given** the operator changes the date range  
**When** the new range is selected  
**Then** `GET /api/v1/analytics/detection-quality?range={new_range}` is fired; KPI strip, chart, and uptime list all update; no `Math.random()` or baked constants remain in the component

**And** the API error state shows "Detection quality data unavailable — retry" with retry button  
**And** bar hover tooltip content is derived from the API response breakdown rows — not from local mock constants  
**And** `useMemo([dateRange])` memoisation is preserved for chart and uptime computations

**Dependencies:** E3-S1 (backend endpoint)  
**Files changed:** `src/components/analytics/AIDetection.jsx`, `src/api/analytics.js`

---

#### Story E3-S6 — System Health WebSocket Staleness & Live Timestamps

**As a** Fleet Maintenance Manager,
**I want** the System Health view to show a staleness banner when the WebSocket data is more than 2 minutes old, and to display server-sourced `lastHealthy` timestamps with accurate live elapsed,
**so that** I can immediately know if health data is stale and trust that fault timing reflects what the server recorded.

**Acceptance criteria:**

**Given** the System Health view is open and receiving WebSocket updates  
**When** the last WebSocket message was received more than 120 seconds ago  
**Then** an amber "⚠ Data may be stale — reconnecting…" banner appears at the top of the System Health view; it does not obscure the summary strip

**Given** the staleness banner is visible  
**When** a new WebSocket message arrives  
**Then** the banner disappears within one render cycle; the "Last Update" summary tile resets its elapsed counter to "0s ago"

**Given** a train row in the fleet health grid has a fault  
**When** the inline detail panel opens  
**Then** `lastHealthy` displayed in the panel footer ("Last fully healthy: HH:MM today · Xm ago") is the ISO-8601 UTC value from the server response — not a hardcoded mock scenario time; the elapsed calculation uses `Date.now()` against this server timestamp

**Given** the `last_healthy` field in the server response is `null` (no fault this session)  
**When** the panel footer renders  
**Then** "Last fully healthy" section is not shown; no empty placeholder or "—" appears in the footer

**Given** `connectivity` is absent from the server response for a train  
**When** the Train Link row renders in the detail panel  
**Then** it shows "No data" — existing prototype behaviour preserved

**And** the staleness threshold of 120 seconds is a named constant `WS_STALENESS_THRESHOLD_MS = 120_000` in `FleetContext.jsx` — not a magic number  
**And** the "Last Update" summary tile's live-ticking elapsed counter (`setInterval`, 1s) continues to use `Date.now()` against the last-received WS message timestamp — no change to that logic

**Dependencies:** E2-S1 (real WebSocket client with connection state in FleetContext)  
**Files changed:** `src/components/health/SystemHealth.jsx`, `src/context/FleetContext.jsx`

---

#### Story E3-S7 — System Health Maintenance Ticket API

**As a** Fleet Maintenance Manager,
**I want** maintenance tickets raised from the System Health panel to get server-generated reference numbers,
**so that** ticket IDs are stable, unique, and traceable in the maintenance system rather than being random client-side strings.

**Acceptance criteria:**

**Given** the System Health inline detail panel is open for a train with issues  
**When** the operator clicks "Raise Maintenance Ticket" and confirms  
**Then** `POST /api/v1/maintenance/tickets` is called with body `{ train_id, issue_summary, raised_by: "<operator_id>" }` and `X-API-Key` header; the request is sent before the confirmation UI updates

**Given** the API returns HTTP 201 with `{ ticket_id: "REF#XXXXX", created_at: "<ISO-8601>" }`  
**When** the response is received  
**Then** the panel footer updates to the "raised" state showing the server-returned `ticket_id` in monospace; the toast shows "Ticket raised — {ticket_id} · {train_id}" and auto-dismisses after 4s

**Given** the API returns HTTP 4xx or 5xx  
**When** the error is received  
**Then** the confirmation UI reverts to the default "Raise Maintenance Ticket" button state; a toast error "Ticket creation failed — please try again" appears; no fake ticket ID is shown

**Given** the operator presses Escape during the two-step confirmation  
**When** Escape is detected  
**Then** the pending confirmation state is cancelled; no API call is made; existing prototype behaviour preserved

**Given** the `MAINTENANCE_APP_ENABLED` flag  
**When** it is `false` (current default)  
**Then** the Maintenance App CTA (`sh-panel-cta`) remains hidden; the flag value is read from `VITE_MAINTENANCE_APP_ENABLED` env var; no hardcoded `false` in component logic

**And** `Math.random()` is removed entirely from `SystemHealth.jsx` — no client-side ticket ID generation remains  
**And** the backend endpoint `POST /api/v1/maintenance/tickets` must exist (noted as backend dependency)

**Dependencies:** E1-S7 (API auth), E2-S1 (operator session context for `raised_by`)  
**Files changed:** `src/components/health/SystemHealth.jsx`, `src/api/maintenance.js`  
**Backend required:** `POST /api/v1/maintenance/tickets`

---

#### Story E3-S8 — System Health Data Feed Integration

> _Moved from Epic 2 (was E2-S9) on 2026-05-30 to resolve a forward dependency on E3-S1._

**As a** Control Centre operator,
**I want** the System Health view to show live CCTV, application, and connectivity status from the backend rather than mock data,
**so that** I can detect real train health degradations and act on accurate container and device status.

**Acceptance criteria:**

**Given** the operator navigates to `/dashboard/health`  
**When** `SystemHealth` mounts  
**Then** `GET /api/v1/analytics/system-health` is called; a loading skeleton (3 skeleton rows matching the grid layout) is shown while the request is in flight; on success the fleet health grid renders with real data

**Given** the API response contains a train with `appStatus: "red"` and `appDetail` array  
**When** the operator clicks that train's row  
**Then** the inline detail panel renders the per-container drill-down from the server's `appDetail`; no client-side generation of container names or statuses

**Given** the API response contains `last_healthy` as an ISO-8601 UTC string  
**When** the "Since" column renders  
**Then** elapsed time is computed from `Date.now()` minus the parsed server timestamp — not from a hardcoded mock time; the value live-ticks every second via `setInterval`

**Given** the WebSocket delivers a `CAMERA_DEGRADED` or `CAMERA_RECOVERED` event for a train while System Health is open  
**When** `FleetContext` processes the event  
**Then** the affected train's `cctvStatus` badge updates without a full page refresh or re-fetch of the REST endpoint

**Given** the `GET /api/v1/analytics/system-health` call fails  
**When** the error is returned  
**Then** the grid shows "System health data unavailable" with a retry button; the summary strip shows "—" for all counts; no crash

**And** `lastHealthy` timestamps in the prototype (hardcoded `'09:43'`, `'10:51'`) are removed; the component uses server-sourced ISO-8601 strings exclusively  
**And** `Math.random()` ticket ref generation in `SystemHealth.jsx` remains unchanged — server-generated ticket IDs are a Phase 2 concern (flag `MAINTENANCE_APP_ENABLED = false` unchanged)  
**And** staleness detection (amber "reconnecting…" banner) triggers when no WS message has been received for longer than the operator's `staleness_threshold_sec` preference (default 120s); the threshold is read from `FleetContext` which sources it from `operator_preferences` with `localStorage` cache

**Dependencies:** E3-S1 (backend `/api/v1/analytics/system-health` endpoint), E2-S1 (FleetContext with CAMERA_DEGRADED/RECOVERED event handling), E2-S7 (shared skeleton animation class)  
**Files changed:** `src/components/health/SystemHealth.jsx`  
**Backend required:** `GET /api/v1/analytics/system-health` (covered by E3-S1)

---

### Epic 4: Onboard Edge Pipeline

The system detects occupancy, congestion, luggage, door obstructions, accessibility events, and TCMS alarms onboard — producing structured events that are buffered locally and published to the landside MQTT broker.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR24, FR26, FR27
**Containers:** `rtsp-ingest`, `vlan-pollers`, `inference`, `fusion`, `event-store`, `cloud-sync`
**Hardware:** Hailo-8 M.2 (25–30 cameras/train confirmed); HailoRT + TAPPAS 5.1.0
**Base images:** `rtsp-ingest` + `inference` use Hailo Software Suite Docker image (HailoRT 4.23); all others use `python:3.11-slim-bookworm`
**Can run in parallel with Epics 2–3** against `MockAPCAdapter` and mock TCMS data until hardware is available
**Payload schemas:** All 17 event types in `event-payload-schemas.md` must be produced by this epic's containers
**Architecture rules:** All 14 enforcement rules from architecture §Enforcement Summary apply to every story in this epic

#### Story E4-S1 — `vlan-pollers` SNMP & Context State

**As a** system operator,
**I want** the `vlan-pollers` container to poll Stadler SNMP (VLAN 7) for alarms and trip state, track the current journey ID, and push context state changes to downstream containers,
**so that** all other containers have authoritative journey context and TCMS alarm data without accessing SNMP directly.

**Acceptance criteria:**

**Given** `vlan-pollers` starts with a valid SNMP community string and VLAN 7 IP  
**When** the container reaches readiness  
**Then** `GET /health/ready` returns HTTP 200 with `{"status": "ready", "snmp_connected": true}`; if SNMP is unreachable within 30s it returns HTTP 503 with `{"status": "starting", "snmp_connected": false, "recoverable": true}`

**Given** a Stadler SNMP TRAP arrives on VLAN 7 containing `im0triTripNumber`  
**When** `snmp_poller.py` processes the trap  
**Then** `journey_tracker.py` records `journey_start_date` as the UTC date at first-seen of that `trip_number`; subsequent events for the same `trip_number` use the recorded date — the journey ID does NOT change if wall-clock rolls past midnight

**Given** `tests/unit/test_journey_id.py`  
**When** a trip starts at 23:45 and an event arrives at 00:05 with the same `trip_number`  
**Then** the generated `journey_id` is identical for both events — the midnight-crossing stability test from ADR-2 passes

**Given** `im0AlarmEntry` OIDs are received in a SNMP GetBulk response  
**When** `snmp_decoder.py` parses them  
**Then** each alarm is decoded into an `AlarmEntry` dataclass with fields: `alarm_id`, `description`, `severity` (mapped from SNMP severity integer), `active: bool`; unknown OIDs are logged at WARNING with `recoverable=True` and skipped — no crash

**Given** the `ContextState` changes (new trip number, alarm raised/cleared, speed update)  
**When** `context_state.py` detects a delta  
**Then** the updated state is pushed via HTTP POST to `fusion` and `inference` at their `/context` endpoints using `httpx` async with the `DEFAULT_RETRY` tenacity primitive; pushes are suppressed if the state did not change (delta-only)

**Given** a `ALARM_ACTIVE` or `ALARM_CLEARED` event must be emitted  
**When** an alarm state changes  
**Then** the event is POSTed to `event-store` at `POST /api/v1/events` using the canonical `EventEnvelope` with `event_type = EventType.ALARM_ACTIVE` or `EventType.ALARM_CLEARED`; payload matches `event-payload-schemas.md`

**Given** a door release signal is received from VLAN 2 or VLAN 7 (ZFR door controller or TCMS)  
**When** `snmp_poller.py` or `zfr_poller.py` detects the door release event  
**Then** `context_state.py` sets `ContextState.door_release = true` for the affected car and immediately pushes this state to `rtsp-ingest` via HTTP POST to `rtsp-ingest/context`; the push carries `{ event: "door_release", car_id, door_id }` so `rtsp-ingest` can issue a `STREAM_PRIORITY` command to the relevant camera IDs (ADR-18 Trigger 1)

**Given** `ContextState.pis` contains a `next_station_arrival_utc` timestamp  
**When** the current UTC time is within 120 seconds of `next_station_arrival_utc`  
**Then** `context_state.py` sets `ContextState.station_approach = true` and pushes this flag to `fusion` within 2 seconds; `fusion` uses this flag to add `"priority": "escalated"` to any `ALERT_RAISED` payload emitted while the flag is active (ADR-18 Trigger 3); when the train departs (speed > 20 km/h after station stop) the flag is cleared

**And** all logs use `structlog` with `journey_id` bound to context at task entry  
**And** `datetime.now(timezone.utc)` is used for all timestamps — no `datetime.now()`  
**And** `mypy --strict src/` passes; `ruff` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/vlan_pollers/`  
**And** `docker-compose.dev.yml` provides a synthetic SNMP endpoint so tests run without real hardware

**Dependencies:** E1-S1 (docker-compose skeleton), E1-S2 (EventType enum + envelope), E1-S4 (event-store POST /events endpoint)  
**Deliverables:** `vlan-pollers/src/vlan_pollers/snmp_poller.py`, `journey_tracker.py`, `context_state.py`, `snmp_decoder.py`, `health.py`; `tests/unit/test_journey_id.py`, `test_snmp_decoder.py`, `test_context_state.py`

---

#### Story E4-S2 — `vlan-pollers` APC, PIS & Reservation Pollers

**As a** system operator,
**I want** `vlan-pollers` to poll APC door counts (VLAN 8), PIS schedule/delay state (VLAN 3), and reservation data (VLAN 6) and expose a unified `ContextState` to downstream containers,
**so that** fusion and inference have live schedule, occupancy ground-truth, and reservation context without polling these VLANs directly.

**Acceptance criteria:**

**Given** `apc_poller.py` is configured  
**When** the container starts  
**Then** it uses `MockAPCAdapter` from `shared/adapters/apc/mock.py` by default (APC format unconfirmed); the adapter is injected via constructor — no direct instantiation inside `apc_poller.py`; swapping to a real adapter requires only changing the injected instance in `main.py`

**Given** `MockAPCAdapter.get_occupancy("car-3")` is called  
**When** the result is returned  
**Then** it is an `OccupancyReading` dataclass with deterministic values; the reading is included in the next `ContextState` delta push to `fusion`

**Given** `pis_poller.py` polls VLAN 3  
**When** a platform change or delay message is received  
**Then** `ContextState.pis` is updated with `{ next_station, scheduled_departure, actual_departure, platform, delay_min }`; a delta push is triggered to `fusion` and `inference` within 2 seconds of the PIS update

**Given** `reservation_poller.py` polls VLAN 6  
**When** reservation data is received  
**Then** `ContextState.reservations` is updated with per-coach reservation counts; the data is available to `fusion` on the next context state read

**Given** any VLAN poller fails to reach its target (connection refused, timeout)  
**When** the failure occurs  
**Then** the error is logged at WARNING with `recoverable=True` and the last known state is retained; the container does NOT exit; the specific poller retries with `DEFAULT_RETRY` exponential backoff

**Given** `docker-compose.dev.yml`  
**When** it is used for local development  
**Then** synthetic APC, PIS, and reservation endpoints are provided so all pollers function without real VLAN hardware

**And** `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/vlan_pollers/` (combined with E4-S1 tests)  
**And** no poller uses `os.environ.get()` — all config comes from `pydantic-settings` `config.py`

**Dependencies:** E4-S1 (`vlan-pollers` container skeleton, `ContextState` data structure, `main.py` wiring), E1-S5 (APCAdapter Protocol + MockAPCAdapter)  
**Deliverables:** `vlan-pollers/src/vlan_pollers/apc_poller.py`, `pis_poller.py`, `reservation_poller.py`; `tests/unit/test_apc_poller.py`, `test_pis_poller.py`

---

#### Story E4-S3 — `rtsp-ingest` Camera Pipeline

**As a** system operator,
**I want** the `rtsp-ingest` container to connect to 25–30 RTSP camera streams, enforce P1/P2/P3 priority frame rates, and activate P3 exterior cameras only during station windows,
**so that** the Hailo-8 TOPS budget is managed correctly and downstream inference always receives frames at the right priority.

**Acceptance criteria:**

**Given** `cameras.json` at repo root defines 25–30 cameras with fields `{ rtsp_url, camera_id, coach_id, zone, priority }`  
**When** `rtsp-ingest` starts  
**Then** it loads `cameras.json`, initialises a `hailo-apps` `multisource` GStreamer pipeline for all entries, and connects to each stream; `GET /health/ready` returns HTTP 200 only when at least one P1 stream is active

**Given** the pipeline is running  
**When** frames are being processed  
**Then** P1 cameras (door/vestibule) deliver at 10 fps always; P2 cameras (interior) deliver at 5 fps always; P3 cameras (exterior/platform) deliver at 8 fps only during the station window — at all other times P3 cameras are gated off

**Given** `scheduler.py` monitors the TOPS budget  
**When** the budget exceeds the configured threshold (default: 90% of 26 TOPS)  
**Then** P2 cameras are throttled to 2 fps; a structured log is emitted at WARNING: `budget_pressure`, `tops_used_pct`, `throttled_tier="P2"`, `recoverable=True`; P1 cameras are never throttled

**Given** `gate.py` receives a context state update from `vlan-pollers` with `next_station` and `speed_kmh < 20`  
**When** the station window condition is met (speed below threshold AND door release signal received)  
**Then** P3 cameras are activated within 500ms; when `speed_kmh > 20` again P3 cameras are deactivated

**Given** a P1 camera stream drops (RTSP disconnect)  
**When** the disconnect is detected by the GStreamer pipeline  
**Then** a `CAMERA_DEGRADED` event is POSTed to `event-store` with `camera_id`, `coach_id`, `reason`; reconnect is attempted with `DEFAULT_RETRY` exponential backoff; on reconnect a `CAMERA_RECOVERED` event is posted

**Given** `rtsp-ingest` exposes `POST /context` and receives a `door_release` push from `vlan-pollers`  
**When** the push payload includes `{ event: "door_release", car_id, door_id }`  
**Then** `gate.py` looks up the `camera_ids` associated with that `door_id` in `cameras.json`, raises their priority to P1 for 120 seconds, and emits a `STREAM_PRIORITY` internal command; this command is NOT written to `event-store` and NOT published via MQTT — it is internal to `rtsp-ingest` only (ADR-18 Trigger 1); after the 120-second window the cameras revert to their configured priority

**And** `tests/unit/test_scheduler.py` covers P2 throttle trigger and recovery conditions with synthetic TOPS readings  
**And** `tests/unit/test_gate.py` covers P3 activation/deactivation with synthetic speed + door state inputs; also covers door-release P1 override with a 120-second timeout  
**And** `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/rtsp_ingest/` excluding `pipeline.py` (hardware-dependent; marked `integration`)

**Dependencies:** E1-S1 (docker-compose), E1-S2 (EventType enum), E4-S1 (`vlan-pollers` context state available for gate signals)  
**Deliverables:** `rtsp-ingest/src/rtsp_ingest/pipeline.py`, `scheduler.py`, `gate.py`, `health.py`; `cameras.json` schema + example; `tests/unit/test_scheduler.py`, `test_gate.py`

---

#### Story E4-S4 — `inference` Detection, Tracking & Occupancy Events

**As a** system operator,
**I want** the `inference` container to run YOLOv8m on Hailo-8 frames via a TAPPAS-native GStreamer pipeline, track persons using the `hailotracker` plugin, count people per zone via a thin Python callback, and emit `OCCUPANCY_UPDATE` and `OCCUPANCY_THRESHOLD_CROSSED` events,
**so that** real-time per-coach headcounts are available to the Control Centre Dashboard, Conductor App, and PIS.

**Acceptance criteria:**

**Given** `hailo_device.py` initialises  
**When** the Hailo-8 device is present and `yolox_s_leaky.hef` (YOLOX, Apache-2.0) is loaded  
**Then** `GET /health/ready` returns HTTP 200 with `{"status": "ready", "hailo_initialised": true}`; if the device is absent or the model fails to load it returns HTTP 503 with `recoverable: false`

**Given** a frame from `rtsp-ingest` is received  
**When** `detector.py` processes it via the hailo-apps detection callback  
**Then** detections are filtered to classes: `person`, `suitcase`, `bicycle`; zone masking is applied in the Python callback so only detections within the camera's configured zone are passed to `zone_counter.py`

**Given** `detector.py` loads zone masks for a coach  
**When** `cameras.json` is parsed at startup  
**Then** each camera entry includes a `seat_zones` array of static polygon masks defining seated vs. standing areas; these masks are fixed for the coach geometry and are NOT updated per frame — `zone_counter.py` uses them to classify persons as seated or standing (ADR-16); no dynamic zone calibration occurs during runtime

**Given** the `hailotracker` GStreamer plugin processes detections across consecutive frames  
**When** track IDs are assigned by the native Kalman+IoU tracker and flow through buffer metadata into the Python callback  
**Then** `zone_counter.py` maintains a per-zone person count using those tracking IDs; count updates are emitted at most once per second per coach (1 Hz rate limit enforced in `zone_counter.py`)

**Given** `zone_counter.py` produces a count update for a coach  
**When** the count update is processed  
**Then** an `OCCUPANCY_UPDATE` event is POSTed to `event-store` with payload matching `event-payload-schemas.md`: `car_id`, `zone`, `occupancy_count`, `occupancy_pct`, `capacity`, `confidence`, `service_tier`

**Given** `occupancy_pct` crosses a configured threshold (default: 0.80) in the rising direction  
**When** the threshold crossing is detected  
**Then** an `OCCUPANCY_THRESHOLD_CROSSED` event is POSTed with `direction: "rising"` and the threshold value; a subsequent fall below the threshold emits `direction: "falling"`; no duplicate events are emitted for the same threshold/direction until the opposite crossing occurs

**Given** `budget.py` detects TOPS pressure from the scheduler  
**When** P2 throttle is active  
**Then** `inference` reduces P2 frame processing rate accordingly; the reduction is coordinated via the shared context state, not by re-routing frames

**And** `tests/unit/test_budget.py` covers throttle trigger and P2 suppression logic  
**And** `tests/unit/test_zone_counter.py` covers zone boundary logic with synthetic tracking IDs  
**And** `mypy --strict src/` passes; hardware-dependent tests (`test_hailo_device.py`) are marked `integration` and excluded from default `pytest` run  
**And** `datetime.now(timezone.utc)` used for all event timestamps; `structlog` with `camera_id` and `journey_id` bound at frame handler entry

**Dependencies:** E1-S2 (EventEnvelope + payload models), E1-S4 (event-store POST endpoint), E4-S1 (`vlan-pollers` context for journey_id), E4-S3 (`rtsp-ingest` frames)  
**Deliverables:** `inference/src/inference/pipeline.py`, `callback.py`, `zone_counter.py`, `budget.py`, `health.py`, `config.py`, `models.py`; `tests/unit/test_budget.py`, `test_zone_counter.py`, `test_security.py` (no `tracker.py` — tracking is native `hailotracker` GStreamer plugin)

---

#### Story E4-S5 — `inference` Safety & Accessibility Detection

**As a** system operator,
**I want** the `inference` container to detect door obstructions, wheelchair/pushchair presence, ramp deployment, and slip/fall events using the Hailo-8 models,
**so that** safety-critical alerts reach conductors and the Control Centre within the station dwell window.

**Acceptance criteria:**

**Given** `detector.py` detects a `person` or `suitcase` bounding box overlapping a configured door zone  
**When** the overlap persists for ≥2 consecutive frames  
**Then** a `DOOR_OBSTRUCTION` candidate is emitted to `fusion` for cross-reference with ZFR door state; `inference` does NOT post the alert directly — fusion is authoritative for door obstruction alerts (FR7)

**Given** `detector.py` detects a `bicycle` class detection (COCO proxy for wheelchair/pushchair) in a vestibule or door zone  
**When** the detection confidence is ≥ the configured threshold (default: 0.80 — resolved OQ3)  
**Then** an `ACCESSIBILITY_DETECTED` event is POSTed to `event-store` with payload: `car_id`, `zone`, `detection_type` (`wheelchair | pushchair`), `door_id` (nearest door), `confidence`; payload matches `event-payload-schemas.md`

**Given** `vlan-pollers` context state includes a `ramp_deployed: true` signal from TCMS  
**When** `inference` receives the context update  
**Then** a `RAMP_DEPLOYED` event is POSTed to `event-store` with `car_id`, `door_id`, `deployed_at` timestamp

**Given** a person's tracked bounding box height/aspect ratio across consecutive frames indicates a fall (height collapse > configured threshold AND centroid velocity > threshold)  
**When** the condition is detected in `zone_counter.py` using hailotracker output  
**Then** an `ALERT_RAISED` event with `alert_type: "slip_fall"` is emitted to `fusion` for enrichment and suppression check before posting to `event-store` (pose keypoints deferred to post-PoC; hailotracker bounding box heuristic used for PoC)

**Given** a `VESTIBULE_CONGESTION` threshold is exceeded (person count in vestibule zone above configured limit)  
**When** the condition is detected by `zone_counter.py`  
**Then** a `VESTIBULE_CONGESTION` event is POSTed to `event-store` with `car_id`, `zone: "vestibule"`, `count`, `threshold`; payload matches `event-payload-schemas.md`

**And** `tests/unit/test_slip_fall.py` covers bounding box height/velocity heuristic thresholds with synthetic tracking sequences — no Hailo-8 required  
**And** door obstruction candidates are passed to `fusion` via HTTP POST, not written directly to `event-store` — fusion applies suppression before emitting  
**And** all confidence values are omitted (not set to 0) when the inference model is unavailable for a camera, per the cross-cutting constraint in `event-payload-schemas.md`

**Dependencies:** E4-S4 (`pipeline.py`, `callback.py`, `zone_counter.py` all exist), E4-S1 (context state for ramp signal), E4-S6 (fusion receives door obstruction candidates — note: E4-S5 and E4-S6 are developed together; the interface contract is defined here)  
**Deliverables:** updates to `callback.py` (door zone + accessibility logic); `tests/unit/test_slip_fall.py`, `test_accessibility.py`

---

#### Story E4-S6 — `fusion` Alert Correlation & Suppression State Machine

> **✅ RESOLVED 2026-06-05 — shipped as a single story (status: `done`).** The advisory split below was *not* taken; E4-S6 was implemented whole and its code-review follow-ups were folded into the hardening epics (6/7). Sub-story decomposition retained for historical reference only — do not action.
>
> _(Original 2026-05-30 readiness note:)_ **⚠ Oversized — split before dev pickup.** This story bundles 6 modules (suppression state machine, door obstruction correlation, occupancy fusion per ADR-15, speed escalation, depot lifecycle, enrichment). Decompose at dev start into:
> - **E4-S6a** — Suppression state machine (`suppression.py`): NORMAL ↔ MAINTENANCE ↔ DEPOT transitions with multi-condition handling
> - **E4-S6b** — Door obstruction correlation (`door_obstruction.py`): ZFR cross-reference + speed-correlated severity escalation (FR7, FR9)
> - **E4-S6c** — Occupancy fusion (`occupancy.py`): authoritative camera count per ADR-15; `weight_apc` removal; APC reserved for post-hoc accuracy reporting (NFR2 v1.1)
> - **E4-S6d** — Enrichment + depot lifecycle (`enrichment.py`, `JOURNEY_ENDED` on `im0vstShutdownAll`)
>
> Rationale: each module owns a distinct failure mode and test surface. Suppression bugs must not regress occupancy fusion correctness, and vice versa.

**As a** system operator,
**I want** the `fusion` container to correlate camera detections with TCMS/ZFR state, apply the suppression state machine, enrich events with journey metadata, and post finalised alerts to `event-store`,
**so that** false-positive alert rate stays below 5% and alerts are suppressed correctly during maintenance mode, depot parking, and GPS-invalid conditions.

**Acceptance criteria:**

**Given** `suppression.py` implements the suppression state machine  
**When** a `MAINTENANCE_MODE` signal is received from `vlan-pollers` context state  
**Then** all AI-generated alert candidates are suppressed (not posted to `event-store`); the suppression state is logged at INFO: `suppression_active`, `reason="maintenance_mode"`, `journey_id`; alerts resume immediately when maintenance mode clears

**Given** a door obstruction candidate arrives from `inference`  
**When** `door_obstruction.py` cross-references it with the ZFR VLAN 2 door command state  
**Then** if the door is commanded CLOSED and camera confirms obstruction, an `ALERT_RAISED` event with `alert_type: "door_obstruction"` is posted to `event-store`; if ZFR and camera disagree, the candidate is discarded and logged at DEBUG

**Given** a door fault exists AND `vlan-pollers` context reports `speed_kmh > 0`  
**When** `door_obstruction.py` evaluates the alert  
**Then** the alert severity is escalated to `critical` (speed-correlated door fault escalation, FR9); at speed = 0 the same alert is `warning`

**Given** the train enters depot mode (`im0vstShutdownAll` SNMP signal received)  
**When** `suppression.py` processes the signal  
**Then** the state machine transitions to `DEPOT` suppression state; all inference alerts are suppressed; `JOURNEY_ENDED` event is POSTed to `event-store`; on exit from depot the state machine transitions back to `NORMAL`

**Given** `occupancy.py` receives both a camera count and an APC count for the same coach  
**When** fusion runs  
**Then** the camera-derived count is the authoritative occupancy figure and is used directly in `OCCUPANCY_UPDATE` events (ADR-15); the `weight_camera` and `weight_apc` config parameters are removed; APC is not blended into the live count

**Given** `enrichment.py` processes any alert candidate  
**When** it prepares the final `EventEnvelope`  
**Then** it attaches: `journey_id` (from context state), `vehicle_id`, `timestamp` (`datetime.now(timezone.utc)`), `schema_version: 1`; severity is mapped from the alert type using the unified severity model (`critical | warning | info`)

**And** `tests/unit/test_suppression.py` covers: maintenance→normal transition, GPS invalid state, depot shutdown, and the case where two suppression conditions are active simultaneously  
**And** `tests/unit/test_occupancy.py` covers 3-band (staff) and 4-band (portal) threshold logic with synthetic readings  
**And** `tests/integration/test_fusion_pipeline.py` runs synthetic frames through the full fusion pipeline end-to-end and asserts events appear in `event-store` SQLite  
**And** `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/fusion/`

**Dependencies:** E1-S2 (EventEnvelope + enrichment), E1-S4 (event-store POST endpoint), E1-S5 (APCAdapter), E4-S1 (ContextState + SNMP suppression signals), E4-S5 (door obstruction + accessibility candidates)  
**Deliverables:** `fusion/src/fusion/suppression.py`, `door_obstruction.py`, `occupancy.py`, `congestion.py`, `accessibility.py`, `unattended_bag.py`, `enrichment.py`, `health.py`; full test suite

---

#### Story E4-S7 — `event-store` Onboard REST API & WebSocket Fan-Out

> **⚠ Oversized — split before dev pickup (readiness review 2026-05-30).** REST endpoints, WebSocket fan-out, and reconnect replay are three distinct concerns with separate concurrency models. Decompose at dev start into:
> - **E4-S7a** — REST API surface: `POST /api/v1/events` (idempotent), `GET /api/v1/events` (cursor pagination + filters), `GET /api/v1/journeys/{id}`; concurrent write p99 latency test
> - **E4-S7b** — WebSocket fan-out: subscriber filter matching at write-time, ≤100ms delivery SLO, no duplicate delivery to a connected client
> - **E4-S7c** — Reconnect replay (`websocket/replay.py`): last-N matching events on reconnect, schema_version skew handling
>
> Rationale: REST and WS handlers can be developed and reviewed in parallel by different developers; replay is a higher-risk path that benefits from isolated review.

**As a** developer,
**I want** the `event-store` container to expose a complete REST API (POST events, GET events with cursor pagination, GET journeys) and fan out new events to all subscribed WebSocket clients in real time,
**so that** onboard interfaces (Conductor App, Driver Display, PIS) can consume live events and historical event queries over a single, tested API surface.

**Acceptance criteria:**

**Given** `POST /api/v1/events` receives a valid `EventEnvelope` JSON body  
**When** the event is processed  
**Then** it is written to SQLite in WAL mode (E1-S4 logic reused); HTTP 201 returned with `{"data": {"event_id": "<uuid>", "stored": true}}`; the event is immediately fanned out to all WebSocket subscribers whose `SubscriptionRequest` filter matches the event

**Given** `POST /api/v1/events` receives a duplicate `(journey_id, event_type, source_timestamp)`  
**When** the insert is attempted  
**Then** HTTP 200 is returned (idempotent — not 409); a single row exists in SQLite; the event is NOT fanned out again to WebSocket subscribers (deduplication at write time)

**Given** `GET /api/v1/events?journey_id={id}&event_type=ALERT_RAISED&min_severity=warning`  
**When** called with valid filters and `X-API-Key`  
**Then** HTTP 200 returns `{"data": [...], "count": N, "journey_id": "{id}", "next_cursor": "<uuid> | null"}`; results are cursor-paginated (default page size: 100); `next_cursor` is the `event_id` of the last item on the page

**Given** `GET /api/v1/journeys/{journey_id}`  
**When** called  
**Then** HTTP 200 returns the journey metadata record from SQLite; HTTP 404 with ADR-10 error envelope if not found

**Given** a WebSocket client connects and sends a valid `SubscriptionRequest`  
**When** a new event is written via `POST /api/v1/events`  
**Then** the event is delivered to all matching subscribers within 100ms of the write completing; delivery order matches insertion order within a single journey

**Given** `websocket/replay.py` is invoked on reconnect  
**When** a client reconnects with `reconnect_replay_depth=50`  
**Then** exactly the last 50 events matching the subscription filter are replayed in chronological order before live delivery resumes; no event is delivered twice if the client was not disconnected

**And** `tests/integration/test_event_store_concurrent_writes.py` runs 4 concurrent writers posting events and asserts p99 write latency < 50ms using `tmp_path`-scoped SQLite WAL files  
**And** `tests/contract/test_event_schema_version.py` publishes `EventEnvelope(schema_version=999)` and asserts event-store logs WARNING and does not crash  
**And** `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/event_store/`

**Dependencies:** E1-S1 (container skeleton), E1-S2 (EventEnvelope validation), E1-S4 (SQLite WAL + sync cursor — extended here with full REST API), E1-S6 (WebSocket subscription + replay logic — integrated here into full event-store)  
**Deliverables:** `event_store/routes/events.py`, `routes/journeys.py`, `websocket/handler.py` (full), `websocket/replay.py`; `tests/integration/test_event_store_concurrent_writes.py`, `tests/contract/test_event_schema_version.py`

---

#### Story 4.CS1 — Cloud-Sync Container (Onboard MQTT Gateway)
**As a** system operator,
**I want** a `cloud-sync` container on the train that buffers events locally and publishes them to the landside Mosquitto broker,
**so that** no event data is lost during cellular dead zones or tunnel traversals, and the upstream pipeline containers are never blocked waiting for a network connection.

**Acceptance criteria:**
- `cloud-sync` subscribes to the onboard `event-store` (reads from the SQLite sync cursor defined in ADR-4) and publishes each event to the landside Mosquitto broker on topic `oebb/events/{vehicle_id}/{event_type}`
- All events are buffered in the local SQLite queue before publish; the queue is flushed in order on reconnect (no event dropped, no event published twice — idempotency guaranteed by the landside constraint in ADR-3)
- When the MQTT connection is unavailable, `cloud-sync` continues reading from `event-store` and accumulates up to 72 hours of events in the SQLite buffer without stalling any upstream container
- On reconnect, backlogged events are published in chronological order at a configurable rate-limit (default: 500 events/second) to avoid flooding the broker
- `cloud-sync` exposes a `/health` endpoint returning `{"status": "ok", "broker_connected": bool, "queue_depth": int, "last_publish_utc": "ISO-8601"}`
- Structured JSON log entries emitted on: connect, disconnect, reconnect, flush start, flush complete, publish error
- Container uses the shared sync-then-truncate pattern (ADR-4): marks events as synced in `sync_state` table; retains last 3 journeys in SQLite as debug buffer before truncating
- GitLab CI: unit tests cover offline queue accumulation and ordered flush; integration test publishes 100 events with a simulated broker drop mid-sequence and asserts all 100 arrive landside in order

**Architecture note:** `cloud-sync` is intentionally stateless with respect to business logic — it is a pure transport layer. It never interprets event payloads; it reads the envelope and publishes it verbatim. All fusion and enrichment has already happened upstream in `fusion` and `event-store`.

**Dependencies:** Story E1-S1 (event envelope), Story E4 event-store stories (SQLite sync cursor), Story 1.L1 (Mosquitto broker must exist landside)
**Container added:** `cloud-sync`

---

#### Story E4-S8 — Gangway Tripwire Ingest (Inter-Wagon Movement)

**As a** system operator,
**I want** the `inference` container to detect persons crossing gangway boundaries between coaches using virtual tripwires at gangway camera feeds, emitting `WAGON_EXIT` and `WAGON_ENTRY` events,
**so that** `fusion` can maintain a closed-ledger per-coach count and detect inter-wagon movement that would otherwise cause occupancy drift.

**Acceptance criteria:**

**Given** `cameras.json` includes a gangway camera entry with `zone: "gangway-fwd"` or `zone: "gangway-aft"` and a `tripwire` field specifying a polygon line across the camera frame  
**When** `rtsp-ingest` starts  
**Then** each gangway camera is loaded with its tripwire configuration: `{ coach_from, coach_to, direction_axis, tripwire_polygon }`; the configuration is validated at startup — a missing `tripwire` field on a gangway-zone camera raises a startup error

**Given** `hailotracker` is tracking a `track_id` in a gangway camera frame  
**When** the tracked person's bounding box centroid crosses the tripwire polygon from the `coach_from` side to the `coach_to` side  
**Then** a `WAGON_EXIT` event is POSTed to `event-store` with payload: `{ track_id, coach_from, coach_to, camera_id, direction, confidence }`; `direction` is `"forward"` or `"backward"` relative to train direction of travel; payload matches `event-payload-schemas.md`

**Given** a `WAGON_EXIT` event has been emitted for a `track_id`  
**When** the same `track_id` is subsequently detected crossing the entry tripwire on the adjacent coach's gangway camera  
**Then** a `WAGON_ENTRY` event is POSTed to `event-store` with the same `track_id`, `coach_from`, `coach_to`, and `direction`; the pair is linked by `track_id`

**Given** a tripwire crossing is detected with `confidence < 0.70`  
**When** the event would be emitted  
**Then** the event is NOT posted; a structured log is emitted at DEBUG with `reason: "low_confidence"`, `track_id`, `confidence`; the track continues to be monitored

**Given** a `track_id` exits via `WAGON_EXIT` but no matching `WAGON_ENTRY` arrives within 10 seconds  
**When** the timeout expires  
**Then** a structured log is emitted at WARNING with `reason: "orphaned_exit"`, `track_id`, `coach_from`, `coach_to`; `fusion` is notified via its `/context` endpoint so it can flag the ledger as unreconciled

**And** `tests/unit/test_tripwire.py` covers centroid crossing detection with synthetic bounding box sequences — tripwire crossed, not crossed, and partial crossing (low confidence) — no Hailo-8 required  
**And** gangway cameras are always P1 priority in `cameras.json` — they are never throttled by the TOPS budget scheduler  
**And** `mypy --strict src/` passes for all new `inference` module additions

**Dependencies:** E4-S4 (`pipeline.py`, `callback.py`, `zone_counter.py`), E4-S3 (`rtsp-ingest` gangway camera stream), E1-S2 (EventType enum — `WAGON_EXIT`, `WAGON_ENTRY` must be present), E1-S4 (event-store POST endpoint)  
**Deliverables:** `inference/src/inference/tripwire.py`; updates to `detector.py` (gangway zone routing); `cameras.json` gangway camera entries; `tests/unit/test_tripwire.py`

---

#### Story E4-S9 — Closed-Ledger Reconciliation Engine

**As a** system operator,
**I want** the `fusion` container to maintain a closed-ledger per-coach passenger count that is reconciled using `WAGON_EXIT`/`WAGON_ENTRY` pairs and validated against station boarding events,
**so that** per-coach occupancy remains accurate across inter-wagon movement and any unreconciled drift is surfaced before station arrival.

**Acceptance criteria:**

**Given** `fusion` starts and the journey is active  
**When** the `coach_ledger` table is initialised in the `fusion` SQLite database  
**Then** each row has fields: `coach_id`, `ledger_count`, `last_reconciled_utc`, `unreconciled_exits`; the table is initialised from the last known `OCCUPANCY_UPDATE` counts per coach at journey start

**Given** a `WAGON_EXIT` event is received by `fusion`  
**When** the event is processed  
**Then** `ledger_count` for `coach_from` is decremented by 1 and `unreconciled_exits` is incremented; processing is deferred until the paired `WAGON_ENTRY` arrives or the 10-second orphan timeout fires

**Given** a `WAGON_ENTRY` event is received with a `track_id` matching a prior `WAGON_EXIT`  
**When** the pair is reconciled  
**Then** `ledger_count` for `coach_to` is incremented by 1; `unreconciled_exits` for `coach_from` is decremented; reconciliation timestamp is updated; no event is emitted for a clean reconciliation

**Given** the `ContextState.station_approach` flag is set (train within 2 minutes of a station stop)  
**When** the closed-ledger invariant check runs  
**Then** `fusion` sums `ledger_count` across all coaches; if the sum has changed from the last station stop (net passengers gained or lost between stops is non-zero), a `LEDGER_DRIFT_ALERT` event is POSTed to `event-store` with payload: `{ expected_total, actual_total, delta, coach_breakdown, reconciliation_applied }`; if `|delta| ≤ reconciliation_threshold` (default: 3), counts are auto-corrected and `reconciliation_applied: true`; if delta exceeds threshold, `reconciliation_applied: false` and human review is required

**Given** `reconciliation_applied: false` is emitted in a `LEDGER_DRIFT_ALERT`  
**When** the alert is stored  
**Then** the per-coach `occupancy_count` in subsequent `OCCUPANCY_UPDATE` events is NOT adjusted — the raw camera count remains authoritative (ADR-15); the drift is flagged for post-journey analysis only

**And** `tests/unit/test_ledger.py` covers: clean WAGON_EXIT+ENTRY pair, orphaned exit timeout, pre-station invariant check with delta within threshold, and delta exceeding threshold  
**And** the `coach_ledger` SQLite table uses WAL mode (consistent with ADR-4) with the same `DEFAULT_RETRY` write pattern as other `fusion` state tables  
**And** `mypy --strict src/` passes for all new `fusion` module additions

**Dependencies:** E4-S8 (WAGON_EXIT/WAGON_ENTRY events), E4-S6 (fusion container skeleton, ContextState), E1-S2 (EventType enum — `LEDGER_DRIFT_ALERT`, `WAGON_EXIT`, `WAGON_ENTRY` present), E1-S4 (event-store POST endpoint)  
**Deliverables:** `fusion/src/fusion/ledger.py`; `coach_ledger` SQLite schema migration; `tests/unit/test_ledger.py`

---

#### Story E4-S10 — Coach Comfort Index

**As a** control centre operator,
**I want** `fusion` to compute and publish a `COACH_COMFORT_INDEX` event for each coach on station approach and on significant occupancy change,
**so that** the Control Centre Dashboard and capacity planning analytics have a single comfort signal that combines standing headcount and reservation fill.

**Acceptance criteria:**

**Given** `fusion` receives an `OCCUPANCY_UPDATE` event  
**When** the new `occupancy_pct` differs from the last emitted comfort index by more than 0.10 (10 percentage points)  
**Then** `fusion` computes a `COACH_COMFORT_INDEX` for that coach and POSTs it to `event-store`; the event is NOT emitted for every `OCCUPANCY_UPDATE` — only when the 10% delta threshold is crossed or a station approach is detected

**Given** the `ContextState.station_approach` flag is set  
**When** the flag transitions from `false` to `true`  
**Then** `fusion` emits a `COACH_COMFORT_INDEX` event for every active coach within 2 seconds, regardless of whether the 10% occupancy delta has been crossed

**Given** `fusion` has the current `OCCUPANCY_UPDATE` (`occupancy_count`, `capacity`) and `ContextState.reservations` (per-coach `reserved_seats`)  
**When** a `COACH_COMFORT_INDEX` event is computed  
**Then** the payload matches `event-payload-schemas.md`: `{ car_id, reserved_seats, occupied_seats, standing_count, comfort_score, service_tier }`; `occupied_seats = min(occupancy_count, reserved_seats)`; `standing_count = max(0, occupancy_count - reserved_seats)`; `comfort_score = 1.0 - (standing_count / capacity)` clamped to [0.0, 1.0]; `service_tier` is taken from the coach entry in `ContextState`

**Given** `ContextState.reservations` is unavailable (reservation poller has not yet returned data)  
**When** a comfort index computation is triggered  
**Then** the event is NOT emitted — it is deferred until reservation data is available; a structured log is emitted at DEBUG with `reason: "reservations_unavailable"`, `car_id`

**Given** `COACH_COMFORT_INDEX` is written to `event-store`  
**When** the event is stored  
**Then** it is published via MQTT to `oebb/events/{vehicle_id}/COACH_COMFORT_INDEX` by `cloud-sync` following the standard sync path; the Control Centre Dashboard analytics tab consumes it via the landside `mqtt-ingestor` → TimescaleDB pipeline

**And** `tests/unit/test_comfort_index.py` covers: standing count calculation, comfort score clamping at 0.0 and 1.0, deferred emission when reservations are unavailable, station-approach trigger  
**And** `mypy --strict src/` passes for all new `fusion` module additions

**Dependencies:** E4-S6 (fusion container, ContextState), E4-S2 (reservation data in ContextState), E4-S4 (OCCUPANCY_UPDATE source), E1-S2 (EventType enum — `COACH_COMFORT_INDEX` present), E1-S4 (event-store POST endpoint)  
**Deliverables:** `fusion/src/fusion/comfort_index.py`; updates to `fusion/src/fusion/main.py` (trigger wiring); `tests/unit/test_comfort_index.py`

---

### Epic 5: Luggage Monitoring — Live Data

Control Centre operators can monitor unattended bag and luggage-rack-saturation events in real time through a dedicated Luggage Monitoring tab fed by live `UNATTENDED_BAG` and `LUGGAGE_RACK_SATURATION` events on the WebSocket, with a staleness banner, an age-gated KPI tile, and per-coach attribution in the train detail grid — replacing the prototype's 7 hardcoded mock events.

**FRs covered:** FR2 (luggage count) + FR4 (unattended bag alert) at the Control Centre surface
**UX-DRs covered:** UX-DR15 (Luggage Monitoring view)
**Prototype reference:** `control-centre/src/components/live/LuggageMonitoring.jsx` (existing; mock data path being replaced)
**Component files:** `src/components/live/LuggageMonitoring.jsx`, `src/components/live/UnifiedFeed.jsx`, `src/components/live/KpiStrip.jsx`, `src/context/FleetContext.jsx`, `src/ws/RealWebSocketClient.js`, `src/mock/luggage.js`, `src/mock/websocket.js`
**Status:** ✅ Done — 4 stories shipped; canonical specs in `_bmad-output/implementation-artifacts/5-*.md`

---

#### Story E5-S1 — Luggage Monitoring Live Feed

> **⚠ Transport updated 2026-05-30 by ADR-20.** Title was "Luggage Monitoring Live WebSocket Feed". Luggage events now flow over the SSE stream from E1-S6'. ACs below are unchanged in intent — they refer to the SSE client and `ALERT_EVENT_TYPES` allow-list instead of WebSocket + `SubscriptionRequest`.

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab and the Luggage Alerts KPI tile to reflect live luggage events arriving over the SSE stream rather than the 7 hardcoded mock events,
**so that** I can see real-time unattended bag alerts and rack saturation events as they are detected onboard, and respond before the situation escalates.

**Canonical spec:** `_bmad-output/implementation-artifacts/5-1-luggage-ws-live-feed.md` (7 ACs — filename retained for git history; intent updated to SSE)

**Key acceptance criteria (summary, ADR-20-aligned):**
- `LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` are added to the cloud-backend `ALERT_EVENT_TYPES` allow-list in `alerts_sse.py` so they are pushed over the SSE stream (no client-side `SUBSCRIPTION_REQUEST` needed)
- `RealSseClient` routes both event types into a `LUGGAGE_EVENT` frontend message with the documented shape `{ id, trainId, coachId, state, title, detail, confidence, timestamp, stillFrame }`
- `FleetContext` replaces the static `LUGGAGE_EVENTS`/`LUGGAGE_ESCALATIONS` constants with a live `luggageEvents` state; updates are merged into `escalations` via `luggageEventsToEscalations()`
- `MockWebSocketClient` (kept under legacy name as dev fallback) emits at least 2 `LUGGAGE_EVENT` messages (one `unattended`, one `overcrowded`) so the tab remains testable offline
- Duplicate `event_id`s on SSE reconnect (via `Last-Event-ID`) are silently dropped via `_trackSeenId`
- Empty state ("No luggage events received yet.") is preserved when `luggageEvents` is empty — no crash, no mock fallback

**Dependencies:** E2-S1 (RealSseClient), E1-S6' (cloud-backend SSE fan-out + `ALERT_EVENT_TYPES` extended to luggage types)
**Files changed:** `src/sse/RealSseClient.js`, `src/mock/websocket.js`, `src/context/FleetContext.jsx`, `src/components/live/LuggageMonitoring.jsx`, `cloud-backend/src/cloud_backend/routes/alerts_sse.py` (extend allow-list)

---

#### Story E5-S2 — Luggage Monitoring Live UI

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab to display a loading state while waiting for the first WS events, show live event cards with correctly formatted timestamps and elapsed time, surface per-coach status in the train detail grid from live `coachId` values, and allow me to filter events by type without the filter resetting on new arrivals,
**so that** I can monitor live luggage alerts without confusion from broken timestamps, incorrect coach attribution, or disorienting filter resets.

**Canonical spec:** `_bmad-output/implementation-artifacts/5-2-luggage-monitoring-live-ui.md`

**Key acceptance criteria (summary):**
- Loading skeleton while `luggageEvents` is empty AND WS has not yet delivered its first message; replaced by content on first message (or by the empty state after a connected-no-events period)
- `formatTimestamp` and `elapsedMin` accept the unified ISO-8601 input — no HH:MM legacy branch
- Per-coach attribution in the train detail grid is derived from `event.coachId` from the live payload, not hardcoded mappings
- Type filter (overcrowded / unattended) state persists across new event arrivals — filter does not reset
- All existing event card visual treatment (severity ramp, confidence chips, pulsing border) preserved

**Dependencies:** E5-S1 (live luggage events flowing into context)
**Files changed:** `src/components/live/LuggageMonitoring.jsx`

---

#### Story E5-S3 — Luggage KPI Live Monitoring (Staleness + Age-Gated KPI)

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab to warn me when luggage data is stale, the KPI strip to flag unattended bags only once they exceed a configurable age threshold, and a preference control to tune that threshold,
**so that** I can trust the KPI numbers reflect real operational urgency and avoid alert fatigue from short-duration false alarms.

**Canonical spec:** `_bmad-output/implementation-artifacts/5-3-luggage-kpi-live-monitoring.md`

**Key acceptance criteria (summary):**
- An amber "⚠ Luggage data may be stale — reconnecting…" banner appears when no `LUGGAGE_EVENT` has arrived for the operator's `staleness_threshold_sec` preference (default 120s); reuses the staleness mechanism from E3-S6
- The "Unattended bags" KPI tile counts only events where `elapsedSec > age_gate_sec` (default 180s); below the gate they appear in the feed but are excluded from the KPI count
- A new `luggage_age_gate_sec` field is added to `operator_preferences` (CHECK constraint: 60, 120, 180, 300); GET/PATCH on `/api/v1/operators/me/preferences` returns and accepts it
- Preferences panel (`OperatorPreferences.jsx`) adds the age-gate control; keyboard accessible (arrow keys, Enter to confirm)
- Existing per-operator `threshold_sec` and `staleness_threshold_sec` behaviour preserved

**Status:** ready-for-dev
**Dependencies:** E5-S1, E5-S2, E2-S8 (operator_preferences table + GET/PATCH endpoints), E3-S6 (staleness mechanism)
**Files changed:** `src/components/live/LuggageMonitoring.jsx`, `src/components/live/KpiStrip.jsx`, `src/components/shell/OperatorPreferences.jsx`, `src/context/FleetContext.jsx`; cloud-backend `operator_preferences` Alembic migration + preferences endpoint update

---

#### Story E5-S4 — Luggage ISO Timestamp Migration

**As a** developer maintaining the Control Centre luggage mock data,
**I want** all static `LUGGAGE_EVENTS` timestamps migrated to ISO-8601 UTC strings and the legacy HH:MM code paths removed,
**so that** `elapsedMin` and `formatTimestamp` have a single, testable code path that is consistent with live WebSocket events.

**Canonical spec:** `_bmad-output/implementation-artifacts/5-4-luggage-iso-timestamps.md`

**Key acceptance criteria (summary):**
- All static mock timestamps in `src/mock/luggage.js` are ISO-8601 UTC strings with `Z` suffix — no `'HH:MM'` literals remain
- `formatTimestamp(input)` accepts ISO-8601 only; the legacy HH:MM branch is deleted
- `elapsedMin(start, end)` accepts ISO-8601 only; legacy branch deleted
- Existing unit tests updated; new test covers ISO-8601 parse + elapsed computation against a fixed `Date.now()` mock
- No visual regression — rendered timestamps remain in the same format as before

**Dependencies:** None (refactor)
**Files changed:** `src/mock/luggage.js`, `src/components/live/LuggageMonitoring.jsx` (formatter callsites), test files

---

### Epic 1.5: Onboard Containerised Infrastructure

The complete onboard pipeline (event-store, rtsp-ingest, inference) builds and runs on the R5001C SYS2 edge device via a single `docker-compose.onboard.yml`, with Hailo Software Suite base image used where TAPPAS/HailoRT/GStreamer are required and a CI-safe smoke test verifying the containerisation layer without Hailo hardware.

**Bridge purpose:** Epic 1 delivered landside infrastructure (FastAPI, PostgreSQL, MQTT). Epic 1.5 delivers the *onboard* containerisation that Epic 4 stories run inside. Without it, Epic 4 stories have no execution surface on SYS2.
**FRs covered:** NFR1 (uptime — restart policies + healthchecks), NFR13 (CI gates)
**Containers:** `event-store`, `rtsp-ingest`, `inference`
**Base images:** `hailo-software-suite:4.23` for `rtsp-ingest` and `inference`; `python:3.11-slim-bookworm` for `event-store`
**Status:** ✅ Done — 4 stories shipped; canonical specs in `_bmad-output/implementation-artifacts/1-5-*.md`

---

#### Story E1.5-1 — `inference` Dockerfile

**As a** platform engineer,
**I want** a `Dockerfile` for the `inference` service that builds correctly from the Hailo Software Suite base image,
**so that** the inference container can be deployed as part of the onboard Docker Compose stack with all GStreamer/TAPPAS/HailoRT dependencies available at runtime.

**Canonical spec:** `_bmad-output/implementation-artifacts/1-5-1-inference-dockerfile.md`

**Key acceptance criteria (summary):**
- `inference/Dockerfile` uses `FROM hailo-software-suite:4.23` (HailoRT + TAPPAS pre-installed; not pip-installable)
- `oebb-shared` installed via the two-step staging pattern (copy `shared/src/oebb_shared` + `shared/pyproject.toml` → `pip install --no-cache-dir ./shared_src`)
- Non-editable install of the inference package
- `HEALTHCHECK` directive present (per Epic 9 hardening — added in retro)
- Comment block documents `# Hailo base image — pin to sha256 digest on first SYS2 hardware bring-up.`
- `docker build` succeeds in CI on a runner without the Hailo image present (uses `ARG HAILO_BASE` with a stub for dry-run validation)

**Dependencies:** E1-S2 (oebb-shared package exists)
**Deliverables:** `inference/Dockerfile`

---

#### Story E1.5-2 — `rtsp-ingest` Dockerfile

**As a** platform engineer,
**I want** a `Dockerfile` for the `rtsp-ingest` service that builds correctly from the Hailo Software Suite base image,
**so that** the rtsp-ingest container can be deployed as part of the onboard Docker Compose stack with all GStreamer/TAPPAS dependencies available at runtime.

**Canonical spec:** `_bmad-output/implementation-artifacts/1-5-2-rtsp-ingest-dockerfile.md`

**Key acceptance criteria (summary):**
- `rtsp-ingest/Dockerfile` uses `ARG HAILO_BASE=hailo-software-suite:4.23` + `FROM ${HAILO_BASE}`
- `oebb-shared` installed via the two-step staging pattern matching all other containers
- Non-editable install of the rtsp-ingest package
- `HEALTHCHECK` directive present
- Hailo digest-pin comment block matches the inference Dockerfile pattern
- Builds cleanly in CI

**Dependencies:** E1-S2
**Deliverables:** `rtsp-ingest/Dockerfile`

---

#### Story E1.5-3 — Onboard Docker Compose

**As a** platform engineer,
**I want** a `docker-compose.onboard.yml` that brings up the complete standalone onboard stack (event-store, rtsp-ingest, inference),
**so that** the full onboard pipeline can be started with a single command on the R5001C SYS2 edge device.

**Canonical spec:** `_bmad-output/implementation-artifacts/1-5-3-onboard-docker-compose.md`

**Key acceptance criteria (summary):**
- `docker-compose.onboard.yml` at monorepo root defines exactly three services: `event-store`, `rtsp-ingest`, `inference`
- `event-store` builds from `event-store/Dockerfile` (context `.`), mounts `/data` volume for SQLite WAL, takes `EVENT_STORE_API_KEY` via env, exposes port 8001, healthchecks via `/health/ready`
- `rtsp-ingest` and `inference` build from their Hailo-based Dockerfiles; restart policy `unless-stopped`
- Onboard-only — no landside services (no Mosquitto, no PostgreSQL, no cloud-backend) in this compose file (those are in `docker-compose.yml` at root)
- `cloud-sync` (Story E4-CS1) is added later as the bridge; this compose file is the standalone onboard floor
- Documented network model: SYS2-local bridge network; no external port mappings on rtsp-ingest/inference

**Dependencies:** E1.5-1, E1.5-2
**Deliverables:** `docker-compose.onboard.yml`

---

#### Story E1.5-4 — Onboard Smoke Test

**As a** platform engineer,
**I want** a CI-safe smoke test script that verifies the onboard `event-store` container builds and starts healthy with no external dependencies,
**so that** every push can confirm the containerisation layer works without requiring Hailo hardware.

**Canonical spec:** `_bmad-output/implementation-artifacts/1-5-4-onboard-smoke-test.md`

**Key acceptance criteria (summary):**
- `scripts/smoke-test-onboard.sh` exists at monorepo root, executable
- Brings up only `event-store` via `docker compose -f docker-compose.onboard.yml up -d event-store` (rtsp-ingest and inference are skipped — they need Hailo hardware or real RTSP streams)
- Polls `/health/ready` until HTTP 200 or 60s timeout
- POSTs a synthetic `EventEnvelope` and asserts HTTP 201
- Reads it back via `GET /api/v1/events?journey_id=...` and asserts presence
- Tears down cleanly; exits 0 on success, non-zero on any failure
- GitLab CI invokes this script on every push to `master`

**Dependencies:** E1.5-3, E1-S4 (event-store API)
**Deliverables:** `scripts/smoke-test-onboard.sh`, `.gitlab-ci.yml` update

---

## Hardening Epics — Post-PoC Sprint 1

> These epics address correctness and reliability gaps identified in code reviews across Epics 1–5. They carry no new functional requirements. Priority order: E6 (highest risk — correctness) → E7 (cross-container correctness) → E8 (UI reliability) → E9 (ops/infra).

---

### Epic 6: Fusion Hardening — Journey Lifecycle & Handler Robustness

Fusion containers reset all per-journey state correctly on journey change and all async handlers are resilient to timeout and validation errors, so long-running PoC sessions do not accumulate incorrect state or drop events silently.

**Source:** Deferred items from E4-S9, E4-S10, E4-S6 code reviews  
**Containers:** `fusion/`  
**FRs covered:** NFR1 (uptime), NFR3 (false-positive rate)

---

#### Story E6-S1 — Fusion Journey-Lifecycle Reset Hook

**As a** system operator,
**I want** all fusion per-journey state reset cleanly when a new journey begins,
**so that** drift counts, ledger entries, suppression flags, and coach indexes from a previous journey do not bleed into the next journey's computations.

**Acceptance criteria:**

**Given** `fusion` is running and `ContextState.journey_id` transitions from `journey_A` to `journey_B`  
**When** the transition is detected  
**Then** the following state is reset to its initialised default within one event-loop tick: `CoachLedger.unreconciled_exits` (→ 0), `CoachLedger._last_drift_bucket` (→ None), `CoachLedger._seen_wagon` (→ empty set), `CoachLedger._seen_occupancy` (→ empty dict), `ComfortIndex._observed_coaches` (→ empty dict), `ComfortIndex._last_emitted_pct` (→ empty dict), `SuppressionGate._depot_journey_ended_emitted_for` (→ empty set)

**Given** the journey-lifecycle reset fires  
**When** a `LEDGER_DRIFT_OBSERVATION` event was in-flight at the moment of reset  
**Then** the in-flight event is completed with the pre-reset journey_id; no event is emitted with a mismatched journey_id

**Given** the reset hook runs  
**When** `ContextState.reservations` is absent for the new journey  
**Then** `ComfortIndex` defers emission as per E4-S10 behaviour — the reset does not cause a spurious emission

**Given** a test that simulates two consecutive journeys with differing occupancy patterns  
**When** the second journey begins  
**Then** `unreconciled_exits` starts at 0 (not carrying over from journey 1); `_last_drift_bucket` is None; ledger count starts at 0; a `LEDGER_DRIFT_OBSERVATION` from journey 1 does not appear in journey 2's event stream

**And** `tests/unit/test_journey_lifecycle.py` covers all four state fields above with a two-journey transition scenario  
**And** `mypy --strict fusion/src/` passes with zero errors after the change

**Dependencies:** E4-S9 (CoachLedger), E4-S10 (ComfortIndex), E4-S6 (SuppressionGate)  
**Deliverables:** `fusion/src/fusion/journey_lifecycle.py` (reset hook); wiring in `fusion/src/fusion/main.py`; `tests/unit/test_journey_lifecycle.py`

---

#### Story E6-S2 — Fusion Handler Async Exception Hardening

**As a** system operator,
**I want** all fusion `/candidates/*` route handlers to catch `asyncio.TimeoutError` and `pydantic.ValidationError` without returning HTTP 500,
**so that** a single malformed or timed-out upstream event does not crash the handler and interrupt the pipeline.

**Acceptance criteria:**

**Given** a `/candidates/occupancy_update` POST where the downstream `event-store` call times out (simulated via `httpx.TimeoutException`)  
**When** the handler processes the request  
**Then** HTTP 200 is returned to the caller (fusion is best-effort); a structured JSON log is emitted at WARNING with `reason: "emit_timeout"`, `event_type`, `car_id`, `elapsed_ms`; no HTTP 500 is returned

**Given** a `/candidates/occupancy_update` POST where the request body fails Pydantic validation  
**When** the handler processes the request  
**Then** HTTP 422 is returned with the standard ADR-10 error envelope `{"error": "VALIDATION_ERROR", "detail": "<pydantic message>", "recoverable": true}`; no unhandled exception propagates to the ASGI layer

**Given** `gate.should_emit()` is called for the ledger check and again for the comfort index check within the same handler invocation  
**When** the gate is stateless (current behaviour)  
**Then** both calls return independently — no double-advance of any internal counter; a TODO comment is added: `# TODO: refactor to single gate.should_emit() call when gate becomes stateful`

**Given** the same exception handling pattern is applied to all `/candidates/*` handlers (`door_obstruction`, `accessibility_detected`, `wagon_crossing`, `occupancy_update`)  
**When** `grep -r "asyncio.TimeoutError\|ValidationError" fusion/src/fusion/` is run  
**Then** every handler file contains at least one catch block for each exception type

**And** `tests/unit/test_handler_exceptions.py` covers: timeout → 200 + warning log, ValidationError → 422 + error envelope, for at least two handler routes  
**And** `mypy --strict fusion/src/` passes with zero errors

**Dependencies:** E4-S6 (handler skeleton), E6-S1 (journey lifecycle — must land first to avoid test interference)  
**Deliverables:** Updates to `fusion/src/fusion/health.py` and all `/candidates/*` handler modules; `tests/unit/test_handler_exceptions.py`

---

#### Story E6-S3 — Inference Test Hygiene (AsyncMock Warnings)

**As a** developer,
**I want** the 5 `RuntimeWarning: coroutine never awaited` warnings eliminated from the inference test suite,
**so that** the test output is clean and warning-free, making genuine future warnings visible.

**Acceptance criteria:**

**Given** `pytest tests/unit/test_door_obstruction.py tests/unit/test_vestibule_congestion.py -W error::RuntimeWarning` is run  
**When** all tests execute  
**Then** the command exits 0 with no `RuntimeWarning` raised — all previously-warned coroutines are now properly awaited or bound as `MagicMock`

**Given** the fix replaces `AsyncMock` bindings on `resp.raise_for_status` with `MagicMock`  
**When** the production call path executes `resp.raise_for_status()` synchronously  
**Then** the mock reflects the actual call signature — no `await` is present in production code at that callsite

**And** total inference test count does not decrease (no tests removed to fix the warning)  
**And** `pytest inference/tests/ --tb=short` exits 0 with all tests passing

**Dependencies:** E4-S5 (inference safety tests exist)  
**Deliverables:** Updates to `inference/tests/unit/test_door_obstruction.py`, `inference/tests/unit/test_vestibule_congestion.py`

---

### Epic 7: Retry & Idempotency Hardening

The shared HTTP retry policy correctly classifies 4xx responses as non-retriable, and the gangway tripwire uses emit-then-commit ordering to prevent silent event loss on retry failure, so the pipeline does not burn retry budgets on permanent errors or produce inconsistent crossing state.

**Source:** Deferred items from E4-S8 (W1, W3), E4-S6, E4-CS1 code reviews  
**Containers:** `shared/`, `inference/` (tripwire), `cloud-sync/`  
**FRs covered:** NFR1 (uptime), NFR8 (connectivity resilience)

---

#### Story E7-S1 — Shared Retry Policy: Exclude 4xx

**As a** developer,
**I want** `shared/http/retry.py`'s `DEFAULT_RETRY` decorator to not retry on 4xx responses,
**so that** a 422 Unprocessable Entity (e.g. malformed event payload) does not burn 50 seconds of retry budget before surfacing the error.

**Acceptance criteria:**

**Given** an outbound `httpx` call returns HTTP 422  
**When** `DEFAULT_RETRY` is applied  
**Then** no retry is attempted; the 422 response is raised immediately as `httpx.HTTPStatusError`; a structured log is emitted at ERROR with `status_code: 422`, `url`, `reason: "non_retriable_4xx"`

**Given** an outbound `httpx` call returns HTTP 503  
**When** `DEFAULT_RETRY` is applied  
**Then** exponential backoff with jitter is applied for up to 3 retries (existing behaviour preserved)

**Given** an outbound `httpx` call returns HTTP 429 (rate limited)  
**When** `DEFAULT_RETRY` is applied  
**Then** it is treated as retriable (same as 5xx) — rate-limit back-off is the correct response

**Given** an outbound `httpx` call returns HTTP 400  
**When** `DEFAULT_RETRY` is applied  
**Then** no retry is attempted — 400 is a permanent client error

**And** a contract test `tests/unit/test_retry_policy.py` covers: 422 → no retry, 503 → 3 retries, 429 → retry, 400 → no retry  
**And** `mypy --strict shared/` passes with zero errors  
**And** the change is verified to not break any existing integration test that relies on retry behaviour (run full test suite)

**Dependencies:** E1-S7 (shared retry module exists)  
**Deliverables:** `shared/src/oebb_shared/http/retry.py` (policy update); `tests/unit/test_retry_policy.py`

---

#### Story E7-S2 — Gangway Tripwire: Emit-Then-Commit Ordering

**As a** system operator,
**I want** the gangway tripwire to record `_last_side` only after a successful HTTP emit,
**so that** a crossing is not silently lost when the emit fails after retries — the side state stays consistent with what was actually published.

**Acceptance criteria:**

**Given** `_emit_wagon_exit` is called and the HTTP POST to `event-store` succeeds  
**When** the emit returns  
**Then** `_last_side` is updated to reflect the new side immediately after the successful response — not before the call

**Given** `_emit_wagon_exit` is called and the HTTP POST fails after all retries  
**When** all retries are exhausted  
**Then** `_last_side` retains its pre-emit value; the next crossing detection for the same person will re-trigger the emit; a structured WARNING log is emitted with `reason: "emit_failed_side_not_committed"`, `track_id`, `car_id`

**Given** `_build_envelope` captures `journey_id` at emit time  
**When** a journey rollover occurs between the crossing detection and the emit call  
**Then** the envelope uses the journey_id that was current when `_build_envelope` was called — not a stale closure value; add a `# NOTE: journey_id snapshotted at detection time` comment to document intent

**And** `tests/unit/test_tripwire_ordering.py` covers: successful emit → side committed, failed emit → side not committed, journey rollover → correct journey_id in envelope  
**And** `mypy --strict inference/src/` passes with zero errors

**Dependencies:** E4-S8 (tripwire implementation), E7-S1 (retry policy must be correct before testing failure paths)  
**Deliverables:** `inference/src/inference/tripwire.py` (ordering fix); `tests/unit/test_tripwire_ordering.py`

---

### Epic 8: Analytics UI Hardening

All four analytics tabs and the system health view handle rapid date-range changes without stale fetches, retry controls are debounced, and the `FleetContext` provider does not cause unnecessary re-renders on every WebSocket tick.

**Source:** Deferred items from E3-S3, E3-S4, E3-S5, E3-S7, E2-S2, E5-S1 code reviews  
**Component files:** `src/components/analytics/`, `src/context/FleetContext.jsx`  
**FRs covered:** UX-DR8–UX-DR12 (analytics interactions), NFR1 (uptime)

---

#### Story E8-S1 — AbortController Pass — Analytics Fetch Cancellation

**As a** Control Centre operator,
**I want** analytics data fetches to be cancelled when I change the date range before a previous request completes,
**so that** stale responses from a previous range never overwrite the current view.

**Acceptance criteria:**

**Given** the operator changes the date range while a fetch is in flight (e.g. changes from 7d to 14d before the 7d response arrives)  
**When** the new range triggers a new fetch  
**Then** the previous `fetch` call is aborted via `AbortController.abort()`; the stale response is discarded; only the 14d response populates the component

**Given** the component unmounts while a fetch is in flight  
**When** React tears down the effect  
**Then** the in-flight fetch is aborted; no `setState` is called after unmount; no `Warning: Can't perform a React state update on an unmounted component` appears in console

**Given** the pattern is applied consistently  
**When** `grep -n "AbortController" src/api/analytics.js` is run  
**Then** every exported fetch function in `analytics.js` accepts an optional `signal` parameter and passes it to `fetch()`; callers (`ExceptionWorkflow`, `OccupancyHeatmap`, `DwellTime`, `AIDetection`) each create an `AbortController` in their `useEffect` and pass `controller.signal` to the fetch

**Given** the retry button is clicked rapidly multiple times  
**When** clicks fire within 300ms of each other  
**Then** only one fetch is initiated (debounced via a 300ms leading-edge debounce or in-flight guard); no duplicate requests appear in the network tab

**And** `analytics.test.js` is updated to cover: abort on range change, abort on unmount, no state update after abort  
**And** no existing analytics acceptance criteria are broken

**Dependencies:** E3-S1–S5 (analytics components exist)  
**Files changed:** `src/api/analytics.js`; `src/components/analytics/ExceptionWorkflow.jsx`, `OccupancyHeatmap.jsx`, `DwellTime.jsx`, `AIDetection.jsx`

---

#### Story E8-S2 — FleetContext Provider Memoisation

**As a** Control Centre operator,
**I want** the `FleetContext` provider value to be memoised so it does not change reference on every WebSocket tick,
**so that** components that consume only static parts of context (e.g. `setDateRange`) are not re-rendered on every incoming event.

**Acceptance criteria:**

**Given** the `FleetContext.Provider` renders with a `value` object  
**When** a WebSocket `TRAIN_UPDATE` event is received that does not change any value consumed by `SystemHealth`  
**Then** `SystemHealth` does not re-render (verified via `React.memo` + render count spy in test)

**Given** the `value` object passed to `FleetContext.Provider`  
**When** it is constructed  
**Then** it is wrapped in `useMemo` with a dependency array containing every state variable and callback included in the value; the dependency array is exhaustive (no missing deps per `eslint-plugin-react-hooks`)

**Given** the memoisation is in place  
**When** `fleet` state updates due to a WS event  
**Then** components that consume only `setDateRange` or `alertThreshold` from context do not re-render — only components consuming `fleet` re-render

**And** no existing behaviour is changed — all consumers receive the same value shape  
**And** `eslint --rule react-hooks/exhaustive-deps` passes on `FleetContext.jsx` with zero warnings

**Dependencies:** E2-S1 (FleetContext real WS client)  
**Files changed:** `src/context/FleetContext.jsx`

---

### Epic 9: Container & Infrastructure Hardening

All production container images use non-editable installs, include `HEALTHCHECK` directives, carry a documented Hailo base image digest placeholder, and the cloud-backend database schema has indexes to support analytics query performance.

**Source:** Deferred items from E1-S1, E1-S3, E1-S4, E4-CS1, E1-5-1, E1-5-2, E1-5-3 code reviews  
**Containers:** all Dockerfiles, `cloud-backend/` migrations  
**FRs covered:** NFR1 (uptime), NFR13 (CI/CD)

---

#### Story E9-S1 — PostgreSQL Analytics Indexes

**As a** developer,
**I want** composite indexes on the `events` table covering `(timestamp, event_type)` and `(vehicle_id, timestamp)`, and an index on `journeys.vehicle_id`,
**so that** analytics range queries and fleet-level lookups do not full-scan the events table as data grows.

**Acceptance criteria:**

**Given** the Alembic migration `0002_add_analytics_indexes.py` is run against a PostgreSQL 15 database with the existing `events` and `journeys` tables  
**When** `alembic upgrade head` is executed  
**Then** it exits 0; a `btree` index named `ix_events_timestamp_event_type` exists on `(timestamp, event_type)`; a `btree` index named `ix_events_vehicle_timestamp` exists on `(vehicle_id, timestamp)`; a `btree` index named `ix_journeys_vehicle_id` exists on `journeys.vehicle_id`

**Given** the migration is run a second time (idempotency check)  
**When** `alembic upgrade head` is executed  
**Then** it exits 0 with no changes (indexes already exist — `CREATE INDEX IF NOT EXISTS` semantics)

**Given** a test that seeds 10,000 events across 5 vehicle IDs and queries `GET /api/v1/analytics/occupancy-heatmap?range=30d`  
**When** `EXPLAIN ANALYZE` is run on the underlying query  
**Then** the query plan shows `Index Scan` on `ix_events_timestamp_event_type` — not `Seq Scan`

**And** `tests/integration/test_analytics_indexes.py` uses `testcontainers-python` and verifies the index exists via `pg_indexes` system table  
**And** `alembic downgrade -1` reverts the indexes cleanly

**Dependencies:** E1-S3 (initial migration), E3-S1 (analytics endpoints that benefit from indexes)  
**Deliverables:** `cloud_backend/migrations/versions/0002_add_analytics_indexes.py`; `tests/integration/test_analytics_indexes.py`

---

#### Story E9-S2 — Dockerfile Hardening Pass (All Containers)

**As a** DevOps engineer,
**I want** all production Dockerfiles to use non-editable pip installs, declare `HEALTHCHECK` directives, and document the Hailo base image digest pin location,
**so that** production images are reproducible, container orchestrators can probe readiness, and hardware bring-up does not require Dockerfile edits.

**Acceptance criteria:**

**Given** `cloud_backend/Dockerfile`, `event_store/Dockerfile`, `cloud_sync/Dockerfile`, `inference/Dockerfile`, `rtsp_ingest/Dockerfile`  
**When** each is inspected  
**Then** every `RUN pip install` line uses `pip install .` (non-editable) — no `-e` flag in any production Dockerfile; the change is verified by `grep -r "pip install -e" */Dockerfile` returning no matches

**Given** each Dockerfile  
**When** it is built and the resulting image is inspected  
**Then** a `HEALTHCHECK` instruction is present; for Python/FastAPI containers the check is: `HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1`; `PORT` defaults match each container's existing `EXPOSE` value

**Given** `inference/Dockerfile` and `rtsp_ingest/Dockerfile` which use `hailo-software-suite:4.23`  
**When** the Dockerfile is read  
**Then** a comment block reads: `# Hailo base image — pin to sha256 digest on first SYS2 hardware bring-up.` followed by `# See: https://hailo.ai/developer-zone/ for digest lookup.`; the tag `4.23` is retained as-is (digest cannot be pinned without registry access)

**Given** `@app.on_event("startup")` in `cloud_backend/main.py`  
**When** the file is inspected  
**Then** it has been migrated to a `@asynccontextmanager lifespan` function (FastAPI ≥0.93 pattern); `@app.on_event("startup")` does not appear anywhere in `cloud_backend/`

**And** `docker build --check` passes for all five Dockerfiles (dry-run build validation)  
**And** existing CI test suite passes without changes to any test file

**Dependencies:** E1-S1 (Dockerfiles exist), E1-5-1/E1-5-2 (inference + rtsp-ingest Dockerfiles exist)  
**Deliverables:** Updates to `cloud_backend/Dockerfile`, `event_store/Dockerfile`, `cloud_sync/Dockerfile`, `inference/Dockerfile`, `rtsp_ingest/Dockerfile`, `cloud_backend/main.py`

---

#### Story E9-S3 — Cloud-Sync Performance: Batch Commits & Background Truncation

**As a** system operator,
**I want** `cloud-sync` to batch SQLite commits across multiple events and run `truncate_old_journeys` in a background task rather than blocking the route handler,
**so that** sustained event throughput does not cause excessive fsync load on SYS2 and the uvicorn worker is not blocked on multi-thousand-row deletes.

**Acceptance criteria:**

**Given** `cloud-sync` receives 100 events within a 200ms window  
**When** `mark_published` is called for each  
**Then** commits are batched: a single `COMMIT` is issued at most once per 50ms (configurable via `CLOUD_SYNC_COMMIT_INTERVAL_MS` env var, default 50); individual row writes are still immediate (WAL append); only the fsync is deferred

**Given** a `POST /api/v1/events` request triggers the truncation check  
**When** truncation is needed (journey count > 3)  
**Then** `truncate_old_journeys` is dispatched via `asyncio.create_task` (background); the HTTP response is returned before truncation completes; a structured log is emitted at DEBUG when truncation starts and completes

**Given** `CLOUD_SYNC_COMMIT_INTERVAL_MS=0` is set (disable batching)  
**When** `mark_published` is called  
**Then** each call commits immediately — existing behaviour preserved; this is the test-safe mode

**And** `tests/integration/test_cloud_sync_perf.py` verifies: 100 rapid `mark_published` calls produce ≤10 commits (with default 50ms batch interval); truncation completes without blocking the HTTP response  
**And** `mypy --strict cloud_sync/src/` passes with zero errors

**Dependencies:** E4-CS1 (cloud-sync container), E1-S4 (SQLite patterns)  
**Deliverables:** Updates to `cloud_sync/src/cloud_sync/db.py`; `tests/integration/test_cloud_sync_perf.py`

---

### Epic 10: Operator Adoption & Trust (AI PM Gap-Closure)

**Source:** [owning-the-gap-ai-pm-analysis.md](owning-the-gap-ai-pm-analysis.md) — closes the gap between "the system works" and "the operator changes how they run trains because of it." Required before any signed ÖBB pilot.

**Why now:** Stories E10-S1 and E10-S2 must land before Control Centre PostgreSQL contracts harden further — retrofitting `confidence_score` into `AlertRaisedPayload` and behavioural telemetry into the `events` schema is far more expensive post-pilot than now.

**Out of scope:** Model accuracy improvements (Epic 4 territory), Conductor App UI work (Phase 2).

**Stories (priority order — implement in this sequence):**

#### Story E10-S1 — Alert Confidence Metadata, Kill-Switch & AI Pipeline Health

> **⚠ Still oversized after the 2026-05-30 scope refinement — split before dev pickup (readiness review 2026-05-30).** Even with playbook content, FP rate definition, and admin UI removed, this story still bundles shared-schema changes, a new event type, a cloud-backend kill-switch table + endpoint, and three CC UI surfaces. Decompose at dev start into:
> - **E10-S1a** — Shared schema + inference heartbeat: `AlertRaisedPayload` confidence fields, `model_versions` in detection payloads, `INFERENCE_HEARTBEAT` event type, `model_provenance.py` in inference, `train_inference_heartbeat` table + upsert on ingest
> - **E10-S1b** — Cloud-backend kill-switch: `alert_class_state` table, `X-Admin-Key`-protected `POST /api/v1/admin/alert-classes/{alert_code}/{disable|enable}`, REST + SSE fan-out enforcement, hardcoded `confidence_thresholds.py` + read-only GET
> - **E10-S1c** — Control Centre UI surfaces: per-alert confidence chip on alert rows, server-triggered degraded banner via `ai_quality_degraded` flag on `/health`, AI pipeline row on System Health (Green/Amber/Red from heartbeat liveness)
>
> Rationale: a/b are backend-only and can ship without touching the UI; c depends on a/b but is independently testable. Splitting also lets the shared schema migration land first so Epic 4 producers can adopt the new fields without waiting for the kill-switch backend.

> **Scope refined 2026-05-30 via grill-me + party-mode.** Exec-failure playbook content moved to E10-S3. False-positive rate definition deferred to new E10-S5. Admin UI deferred to new Epic 11. Story is now **code-only** with three discrete UI surfaces (no standalone "AI Quality" tile).

**As an** AI PM closing the gap between "the system works" and "the operator changes how they run trains because of it,"
**I want** every `ALERT_RAISED` event to carry per-alert confidence and model-provenance metadata, every inference container to emit a 60-second heartbeat, three surfaces in Control Centre that consume them (per-alert confidence chip, fleet-degraded banner, AI pipeline row on System Health), and a cloud-backend kill-switch that suppresses new alerts of a disabled class at the API/SSE fan-out layer,
**so that** procurement conversations have a credible answer to "what happens when the AI is wrong," operators have a per-alert trust signal, and Nomad on-call has an emergency rollback path during PoC.

**See `_bmad-output/implementation-artifacts/10-1-alert-confidence-and-ai-pipeline-health.md` for the full 24-AC story file.** Summary of locked decisions from the design session:

- **Schema (shared):** `AlertRaisedPayload` gains required `confidence_score: float | None`, `confidence_basis: Literal["model","sensor","fused"]`, `model_versions: dict[str, str]`. Validator enforces basis/score/models combinations. Detection payloads gain `model_versions`.
- **Model provenance (inference):** New `model_provenance.py` produces 4-key dict using Hailo `HEF.get_network_group_names()` (lie-proof), HEF SHA256, git SHA (build arg), labels SHA. Stamped on every candidate payload.
- **New event `INFERENCE_HEARTBEAT`:** Emitted by inference every 60s independent of detections. Cloud-backend upserts `train_inference_heartbeat` table on ingest. Distinguishes "healthy and quiet" from "Hailo crashed."
- **Fusion plumbing:** `Enrichment.emit_alert` gains required keyword-only `confidence_basis`. Per-handler call-site updates pass upstream confidence + handler-side fused additions (e.g. `door_sensor_firmware`).
- **Kill-switch (cloud-backend):** New `alert_class_state` table. `X-Admin-Key`-protected `POST /api/v1/admin/alert-classes/{alert_code}/{disable|enable}`. Fan-out enforcement filters new alerts of disabled classes from REST + SSE; in-flight escalations stay visible. No UI in E10-S1 — operated via curl per E10-S3 playbook. UI deferred to Epic 11.
- **Confidence thresholds:** Per-class hardcoded `cloud-backend/src/cloud_backend/config/confidence_thresholds.py` with `# CALIBRATE` placeholder values. Read-only `GET /api/v1/config/confidence-thresholds`. Mutability deferred to Epic 11.
- **Control Centre — three surfaces replace the original "AI Quality" tile:**
  1. **Per-alert confidence chip** on alert rows. States: `High confidence` / `Medium confidence` / `Verify`. No numeric score on chip (drawer only). Chip absent when `basis !== "model"`.
  2. **"Degraded" banner** at top of alerts list, server-triggered via `ai_quality_degraded` flag on `GET /api/v1/health` (rule: rolling 1h mean confidence < 0.60, 30s cache). Copy: "AI alert quality is degraded. Nomad has been notified. Continue to verify alerts against CCTV as normal."
  3. **"AI pipeline" row on System Health** — three states (Green/Amber/Red) driven by heartbeat liveness. Cold state: "AI pipeline: starting. No inferences yet."
- **Out of scope (explicit):** standalone AI Quality tile, new top-level nav item, rollup table, background aggregation job, FP rate metric (→ E10-S5), admin UI (→ Epic 11), real auth (→ Epic 11), playbook content (→ E10-S3), auto-expiry on disabled classes, critical-alert kill-switch bypass.

**Dependencies:** E4-S5 (inference safety/accessibility), E4-S6 (fusion alert correlation), E2-S5 (escalation acknowledge/resolve), E2-S9 / E3-S6 (system health page), Hailo `pyhailort` package (already present per E1-5-1).

**Permission tier:** Tier 3 (shared event schema + two Alembic migrations + inference Dockerfile `GIT_SHA` arg) + Tier 2 (remainder).

---

#### Story E10-S2 — Operator Behavioural Telemetry

**As an** AI PM measuring whether alerts change operator behaviour,
**I want** every escalation lifecycle event (raised → acknowledged → resolved → silently-dismissed) logged with operator-attributable telemetry and queryable via a new audit endpoint,
**so that** after 8 weeks of pilot operation I can identify which alert classes have the highest ack-to-action rate, which are being silently dismissed, and which thresholds need retuning.

**Acceptance criteria:**

**Given** an escalation transitions state (`raised`, `acknowledged`, `resolved`)  
**When** the transition is persisted  
**Then** a row is inserted into `escalation_audit` with columns: `escalation_id`, `operator_id`, `alert_class`, `t_fired`, `t_ack`, `t_resolve`, `outcome_tags[]`, `dwell_focus_ms`, `model_version`, `confidence_score`

**Given** a Claudia user navigates away from an unacknowledged escalation detail panel (route change or tab close)  
**When** the panel is closed without an Acknowledge action and the escalation is still in `raised` state  
**Then** an `escalation_silently_dismissed` event is emitted with `escalation_id`, `operator_id`, `t_viewed`, `t_dismissed`, `dwell_focus_ms`; this surfaces in the System Health AI Quality tile as a "silent dismissal rate (1h)" indicator

**Given** the new endpoint `GET /api/v1/escalations-audit`  
**When** called with `?from=<iso>&to=<iso>&alert_class=<class>`  
**Then** it returns per-alert-class funnels: `{alert_class, count_raised, count_acknowledged, count_resolved, count_silently_dismissed, median_t_ack_seconds, p95_t_ack_seconds, outcome_tag_distribution}`

**Given** the weekly Alert Effectiveness Report job runs every Monday 06:00 UTC  
**When** it executes  
**Then** it generates `reports/alert-effectiveness-{YYYY-WW}.md` containing: top-5 high-volume / low-action alert classes (retune candidates), median ack latency by class, threshold-change events from the previous week and their impact on ack rate, silent-dismissal rate trend

**And** an Alembic migration creates `escalation_audit` with appropriate indices (`alert_class`, `operator_id`, `t_fired`)  
**And** the migration is safe under concurrent reads (NFR-compliant; matches Epic 1 migration pattern)  
**And** `cloud-backend` unit tests cover the funnel-aggregation query at ≥80% coverage  
**And** no PII beyond `operator_id` (already in scope per existing ack/resolve schema) is logged — GDPR-compliant per NFR6

**Dependencies:** E10-S1 (confidence_score in AlertRaisedPayload), E2-S5 (acknowledge/resolve flow), E3-S1 (analytics REST patterns)  
**Deliverables:** `cloud-backend/migrations/versions/00XX_escalation_audit.py`, `cloud-backend/src/api/v1/escalations_audit.py`, `cloud-backend/src/services/alert_effectiveness_report.py`, `control-centre/src/lib/telemetry/dismissal.js`, tests

**Permission tier:** Tier 3 (Alembic migration on shared cloud-backend DB — default permission mode required)

---

#### Story E10-S3 — Critical-Alert Operational SOP & Drill Cadence

> **Actor model corrected 2026-06-13** (see memory `project-actor-model-conrad`). "Conrad" is the **virtual on-train conductor = the onboard AI platform** that *raises* alerts — not a human in the response loop. Acknowledgement authority is **train-type-conditional**: on **conductorless** trains (regional/Nahverkehr) only the landside Fleet Manager / remote staff can acknowledge; on **Fernverkehr** (long-distance) trains an onboard human conductor can also acknowledge. The original two-actor "Conrad assess → escalate → Claudia" sequence and the ÖBB police/station security-handoff contract are **out of PoC scope** and removed from this story.

**As an** AI PM preparing for ÖBB pilot kickoff,
**I want** a documented SOP for critical alerts that branches on train type (conductorless vs Fernverkehr) and acknowledgement channel, a decision matrix binding (alert_code × confidence × speed × location) to a routing/priority decision, and a drill cadence wired to the pilot kickoff checklist,
**so that** when a critical alert fires there is a written and rehearsed sequence — not a UI screen and a hope.

**Acceptance criteria:**

**Given** a critical alert fires (fire, fall, door-at-speed, unattended item with `confidence_score >= 0.85`), raised by the on-train platform (Conrad)  
**When** the operational team responds  
**Then** they follow the SOP in `_bmad-output/operational-procedures/critical-alert-sop.md` covering: **conductorless-train branch** (landside Fleet Manager / remote staff acknowledge + resolve — the default and primary PoC case), **Fernverkehr branch** (onboard conductor may acknowledge from the Conductor App, else it falls through to landside after the amber window), **landside-unreachable branch** (secondary Control Centre operator paged), and **dead-zone branch** (event queued onboard, escalation surfaces on reconnect). No onboard-human step is assumed on conductorless trains.

**Given** the critical-alert decision matrix in `_bmad-output/operational-procedures/alert-routing-matrix.md`  
**When** an alert is emitted  
**Then** the matrix defines, per `alert_code`, the priority/handling decision as a function of `confidence_score` bucket, train speed bucket, location (in-station vs in-transit), **and train type (conductorless vs Fernverkehr)**; each row has a signoff date and ÖBB ops owner

**And** a drill cadence is added to the pilot kickoff checklist: monthly tabletop drills (the landside team — and, for Fernverkehr, an onboard conductor — walk the SOP for a randomly selected critical alert class), quarterly live drills (a planted test event on a non-revenue service)  
**And** both documents are linked from `_bmad-output/planning-artifacts/owning-the-gap-ai-pm-analysis.md` Gap 1

**Out of PoC scope (explicit):** ÖBB police/station security-handoff contract and the "ÖBB security notified" outcome tag (single-landside-actor model has no police/station hop); any SOP branch that treats Conrad as a human who "assesses" or can be "unreachable" (Conrad is the platform — platform liveness is the 10-1 heartbeat/AI-pipeline-health concern, not an SOP routing branch).

**Dependencies:** E10-S1 (confidence_score must exist to define the decision matrix); train-type metadata available per vehicle (conductorless vs Fernverkehr) — confirm source with ÖBB (fleet config) before the matrix's train-type column can be populated  
**Deliverables:** `_bmad-output/operational-procedures/critical-alert-sop.md`, `_bmad-output/operational-procedures/alert-routing-matrix.md`, `_bmad-output/operational-procedures/drill-cadence.md`, updates to pilot kickoff checklist

**Permission tier:** Tier 2 (documentation only — but each artefact requires named ÖBB signoff before pilot, which is a Tier 3 process boundary)

---

#### Story E10-S4 — Dwell-Time-Aware Alert Framing & Delay-Minutes-Avoided KPI

**As an** AI PM aligning the product to Conrad's on-time-departure KPI,
**I want** every pre-departure alert to carry a `seconds_to_departure` field sourced from ZFR/PIS, a dwell-time suffix in alert copy, an on-time-saved totaliser in the Conrad app pre-departure summary, and a new fleet KPI tracking delay-minutes-avoided,
**so that** the product speaks Conrad's language and the business case is measurable in the metric ÖBB actually rewards.

**Acceptance criteria:**

**Given** an alert is emitted while a train is in `DWELL` state at a station  
**When** the envelope is built  
**Then** the payload contains `seconds_to_departure: int | null` derived from the ZFR/PIS scheduled departure feed; null only if the feed is unavailable (logged as a `DWELL_FEED_DEGRADED` event)

**Given** the Conductor App pre-departure alert banner  
**When** an alert renders with `seconds_to_departure` populated  
**Then** the title includes the suffix `· {N}s to departure` (e.g. `"Door obstruction · Coach 6 · 90s to departure"`); colour shifts from amber to red when `seconds_to_departure < 30`

**Given** the Conductor App pre-departure summary screen  
**When** the train completes a station dwell  
**Then** a "minutes saved this shift" totaliser updates, computed as Σ over acknowledged-before-departure alerts of `seconds_to_departure × ack_action_factor` (factor derived from the outcome-tag → resolution-time mapping); the totaliser resets at journey start

**Given** the Control Centre fleet KPI strip  
**When** the daily KPI window updates  
**Then** a new tile "Delay-minutes avoided (24h)" shows the fleet-wide sum, computed from `escalation_audit` rows where outcome_tag indicates an in-time resolution

**And** the new KPI is added to the business goals doc [01-Business-Goals](../design-artifacts/B-Trigger-Map/01-Business-Goals.md) as a measurable success criterion  
**And** unit tests cover the `seconds_to_departure` computation including the null-on-feed-loss path  
**And** the Conductor App is explicitly out-of-scope for the PoC Control Centre (descoped to Phase 2) — this story ships only the event-payload field, the Control Centre KPI tile, and a Conductor App spec stub; the Conductor App UI work is gated on Conductor App epic activation

**Dependencies:** E10-S2 (escalation_audit for KPI computation), E4-S2 (VLAN pollers — PIS feed), Conductor App epic (UI portions deferred)  
**Deliverables:** `shared/events/payloads.py` (alert payload + DwellFeedDegradedPayload), `vlan-pollers/` PIS departure-time extraction, `cloud-backend/src/api/v1/kpi/delay_minutes_avoided.py`, `control-centre/src/components/kpi/DelayMinutesAvoidedTile.jsx`, Conductor App spec stub at `_bmad-output/design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md`

**Permission tier:** Tier 2 (local edits) + Tier 3 (event schema field — default permission mode for the payload migration)

---

#### Story E10-S5 — Alert Quality Measurement (Resolution Quality Tile)

> **Source:** Deferred from E10-S1 design session (2026-05-30). E10-S1's AI Quality drawer intentionally ships without a false-positive rate because the metric is unfalsifiable as currently defined. This story closes that gap by replacing the single "FP rate" claim with three observable rates, an explicit operator-tagged false-positive signal, and a redefinition of NFR3.

**As an** AI PM measuring whether alerts are operationally useful,
**I want** the Claudia resolve flow to capture an explicit `false_positive` outcome tag, the AI Quality drawer to show three orthogonal resolution-quality rates per alert class (no-action rate, auto-resolved-before-ack rate, explicit-false-positive rate), and NFR3 to be redefined against measurable quantities,
**so that** procurement claims about model accuracy are grounded in operator-observable behaviour rather than vibes, and post-pilot retune candidates are identifiable from the data.

**Acceptance criteria:**

**Given** Story 2-5's resolve flow outcome-tag enum  
**When** the enum is updated  
**Then** a new tag `false_positive` is added; Claudia can select it when resolving any escalation; selecting it is mutually exclusive with action tags (i.e. an escalation can be `false_positive` OR have ≥1 action tag, never both)

**Given** the AI Quality drawer in System Health (E10-S1 surface)  
**When** the drawer is opened  
**Then** it shows three rates per alert class (rolling 7-day, not 1-hour — calibration requires a longer window):
- `no_action_rate` = `resolved_with_zero_action_tags / resolved_total`
- `auto_resolved_before_ack_rate` = `auto_resolved_before_ack / raised_total`  
- `explicit_fp_rate` = `resolved_with_tag("false_positive") / resolved_total`

Each rate displayed with its count denominator (e.g. `4.2% (3 of 71)`) so small-sample noise is visible. No aggregated single "FP rate" number; all three shown side-by-side.

**Given** the PRD's NFR3 (`<5% FP rate`)  
**When** the PRD is updated  
**Then** NFR3 is redefined as: `explicit_fp_rate < 5% per alert class over a rolling 7-day window`, with the other two rates demoted to targets (not gates)

**And** the alert effectiveness report (E10-S2 weekly job) is updated to flag any alert class breaching the new NFR3 threshold  
**And** the resolve UI gets a small explanation: "Mark `false_positive` if the model was wrong (no bag, no obstruction, no fall). Mark an action tag if the model was right and you took action." — Freya to spec exact placement  
**And** training material is updated to cover the new tag (E10-S3 SOP appendix)

**Dependencies:** E10-S1 (confidence metadata + AI Quality drawer must exist), E10-S2 (`escalation_audit` table provides the data), E2-S5 (resolve flow + outcome tags).

**Deliverables:** `shared/src/oebb_shared/events/payloads.py` (outcome-tag enum update), `cloud-backend/src/cloud_backend/api/ai_quality_rates.py` (new endpoint), `control-centre/src/components/health/AIQualityRates.jsx` (new component in drawer), `cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py` (update for NFR3 breach flag), `_bmad-output/planning-artifacts/prd.md` (NFR3 redefinition), training material updates in E10-S3 SOP.

**Permission tier:** Tier 2 (local edits) + Tier 3 (event schema enum extension — default permission mode).

---

### Epic 11: Control Centre Admin & Identity

> **Source:** Surfaced 2026-05-30 during E10-S1 grill-me. Prerequisite for any role-gated feature in Control Centre. E10-S1 ships kill-switch endpoints behind a shared `CC_ADMIN_KEY` — Epic 11 replaces that with real auth + an admin UI.

**Goal:** Introduce authentication, user management, profile management, and a Control Centre admin/configuration surface. Unlocks the UI half of E10-S1's kill-switch and the mutability deferral on E10-S1's confidence thresholds.

> **Planning pass: 2026-06-14 (Saga).** Placeholder → full breakdown. Auth-seam compatibility verified against live code first (epic-10-retro prerequisite). See **"Shipped-seam facts"** below — the breakdown is grounded in what is actually shipped, not the aspirational `cloud-backend/CLAUDE.md` description.

#### Auth approach decision (PoC)

**Self-contained JWT** — cloud-backend issues and verifies its own tokens against a local `users` table (passlib/bcrypt password hashing). **No external IdP for the PoC.** Keycloak / ÖBB-OIDC SSO is the **Phase-2 upgrade path** and is explicitly out of scope here.

Rationale (recorded in **ADR-23**, authored by E11-S1): standing up an IdP for ~3 operators + 1 admin is speculative infra the PoC doesn't need, and a *self*-hosted Keycloak would likely be replaced by *ÖBB's own* IdP at fleet rollout — building it now risks building the SSO integration twice. The cost of deferral is contained **iff** token *verification* is decoupled from token *issuance*: E11-S1 isolates verification behind a single `get_current_user` dependency that reads a validated claim set, indifferent to issuer. Moving to Keycloak/ÖBB-OIDC later becomes "point the verifier at the IdP's JWKS, delete local issuance, swap the login screen for a redirect" — the 13 protected routers never change. That seam contract is an E11-S1 acceptance criterion, not an aspiration.

#### Shipped-seam facts (verified 2026-06-14 against live code)

- **Current auth = two flat API-key schemes, NOT JWT.** `cloud-backend/src/cloud_backend/api/auth.py::require_api_key` checks one shared `X-API-Key` against `Settings.api_key`. `cloud-backend/src/cloud_backend/routes/admin_alert_classes.py::require_admin_key` checks `X-Admin-Key` against `Settings.cc_admin_key` (fail-closed via `secrets.compare_digest`).
- **No user identity exists today.** `operator_id` is a free-text body field the client sends (`control-centre/src/api/escalations.js`); the server never verifies it. **`operator_preferences` rows are keyed by the *API-key string itself*** (`preferences.py`: `WHERE operator_id = :oid` where `:oid` = the API key) — so E11-S3 carries a data-migration concern, not a clean extract.
- **`get_current_user` does NOT exist.** The `cloud-backend/CLAUDE.md` description of JWT/`get_current_user`/role-in-route is aspirational — E11-S1 makes it real and corrects the doc.
- **No auth libs installed** (no `pyjwt`/`python-jose`/`passlib`). E11-S1 adds the dependency.
- **Frontend has no login concept.** `VITE_API_KEY` is baked into the bundle and sent on every call. No token store, no login screen, no 401→re-auth flow. E11-S1 frontend is a genuinely new surface.
- **Protected-route inventory (the JWT swap must keep every one covered):** 14 routers behind `require_api_key` — `fleet`, `alerts`/SSE, `escalations`, `escalations-audit`, `analytics`, `capacity_review`, `config`, `ai-quality`, `ai-pipeline`/`health`, `kpi`, `maintenance`, `events`(ingest), `operators/me`(preferences), plus the standalone `/api/v1/health` route. 1 router behind `require_admin_key` — `admin/alert-classes` (the E11-S4 swap point).
- **Migrations run 0001→0008.** Epic 11's `users` table is **0009**.

#### Story breakdown

| Story | Title | Tier | Depends on | Review tier (A2) |
|---|---|---|---|---|
| E11-S1 | JWT auth foundation + login flow | 3 | — | **FULL** (auth) |
| E11-S2 | User management (CRUD + roles + password reset) | 3 | E11-S1 | **FULL** (auth + migration) |
| E11-S3 | Profile management + preferences re-key migration | 3 | E11-S1, E11-S2 | **FULL** (migration) |
| E11-S4 | Admin UI for kill-switch (X-Admin-Key → JWT swap) | 3 | E11-S1, E11-S2 | **FULL** (auth swap) |
| E11-S5 | Configuration surface (mutable thresholds, user-scoped) | 2/3 | E11-S1, E11-S3 | LIGHT→FULL if migration |

**Sequence:** S1 → S2 → (S3 ∥ S4) → S5. S3 and S4 are independent once S1+S2 land.

---

##### E11-S1 — JWT auth foundation + login flow

**As** the cloud-backend, **I want** to issue and verify my own JWTs against a local credential store, with role-claim-based authorization behind a single `get_current_user` dependency, **so that** every protected route knows *who* is calling and with *what role*, and an external IdP can later be swapped in without touching those routes.

**Scope:**
- Add `pyjwt` + `passlib[bcrypt]` to `cloud-backend/pyproject.toml`. New `Settings` fields: `jwt_secret` (HS256 PoC; env, fail-closed empty default), `jwt_issuer`, `jwt_algorithm` (default HS256), `jwt_access_ttl_minutes`. **Config-driven so an RS256/JWKS issuer drops in later without code change.**
- `users` table (**Alembic 0009**): `user_id` (uuid pk), `username` (unique), `password_hash`, `role` (`admin`|`operator` check constraint), `is_active`, `created_at`, `updated_at`.
- `api/auth.py`: add `create_access_token(user)`, `get_current_user` (verifies signature/exp/issuer, loads claim set → `CurrentUser{user_id, username, role}`), and `require_role(*roles)` dependency factory. **`get_current_user` is the single verification seam — it does NOT know how the token was issued.**
- `routes/auth.py`: `POST /api/v1/auth/login` (username+password → access token; bcrypt verify; 401 on bad creds, same ADR-10 error envelope), `GET /api/v1/auth/me` (returns `CurrentUser`).
- **Keep `require_api_key` alive in parallel** (do NOT rip out the 14 routers yet) — E11-S1 ships the JWT machinery + login; the route-by-route cutover is staged so no protected surface is left unauthenticated mid-epic. Cutover of the 14 `require_api_key` routers to `get_current_user` happens at the end of S1 in one reviewed pass, with a contract test asserting all 14 reject a missing/invalid token 401.
- Frontend: login screen (`/login` route), token store (in-memory + sessionStorage), `Authorization: Bearer` on all API calls (replace `VITE_API_KEY` header usage), 401→redirect-to-login interceptor, logout.
- **ADR-23** (self-contained JWT for PoC; OIDC/Keycloak Phase-2 swap-in; the verification-seam contract) — shipped in the same commit per the ADR-FRESHNESS create-story rule.
- Correct `cloud-backend/CLAUDE.md` auth section to describe the now-real `get_current_user`.

**Acceptance criteria:**
1. `POST /api/v1/auth/login` with valid creds returns a signed JWT carrying `sub`, `role`, `iss`, `exp`; invalid creds return 401 with `{"error":"UNAUTHORIZED",...}` (ADR-10 shape) and no token.
2. A protected route called with a valid Bearer token resolves `get_current_user` to the correct `{user_id, username, role}`; called with a missing, expired, tampered-signature, or wrong-issuer token returns 401 — **never 500** (mirrors the JWT-edge-case scenario in `cloud-backend/CLAUDE.md`).
3. `require_role("admin")` returns 403 for a valid `operator` token; 200 for a valid `admin` token.
4. **Seam contract:** token verification is isolated in `get_current_user`; issuer, algorithm, and signing key are config-driven; a documented test/assertion demonstrates that introducing a second (external) issuer would not require editing any of the 13 protected routers. (This is the OIDC-swap guarantee — its violation is an AC fail.)
5. All 14 previously-`require_api_key` routers + the standalone `/api/v1/health` route reject a request with no/invalid token (401), proven by a single parametrized integration test enumerating every protected prefix.
6. Frontend: unauthenticated user hitting any route is redirected to `/login`; successful login stores the token and lands on the dashboard; a 401 from any API call clears the token and redirects to `/login`; logout clears the token.
7. `jwt_secret` empty/unset fails closed (no token verifies; login cannot mint a usable token) — same fail-closed posture as `cc_admin_key`.
8. ADR-23 exists and is referenced; `cloud-backend/CLAUDE.md` auth section matches shipped reality.

**Security Tests (RED-first):** expired token → 401; tampered signature → 401; `alg:none` / algorithm-confusion attempt → 401; wrong-issuer token → 401; operator token on admin route → 403; missing role claim → 401/403 not 500; login brute-force returns uniform 401 (no user-enumeration timing/message difference).

**Integration test (A1 + A3):** real Postgres (testcontainers) seeded with a real bcrypt-hashed user **via the actual user-creation path / login flow — not a raw INSERT of a hand-computed hash**; drive `login → Bearer → protected route → 401-on-tamper` end-to-end. Must run and pass before review (A1 hard gate).

**Permission tier:** **Tier 3** — new dependency, DB migration, auth. Default permission mode.

**Deliverables:** `cloud-backend/pyproject.toml`, `cloud-backend/src/cloud_backend/config/__init__.py`, `cloud-backend/migrations/versions/0009_users.py`, `cloud-backend/src/cloud_backend/api/auth.py`, `cloud-backend/src/cloud_backend/routes/auth.py`, `cloud-backend/src/cloud_backend/main.py` (mount + staged cutover), `cloud-backend/CLAUDE.md`, `control-centre/src/components/auth/Login.jsx` + token store + fetch interceptor, `_bmad-output/architecture-artifacts/ADR-23-self-contained-jwt.md`.

---

##### E11-S2 — User management (CRUD + roles + password reset)

**As** an admin, **I want** to create, list, deactivate, and role-assign operator/admin accounts and reset passwords, **so that** ÖBB ops can manage who has Control Centre access without editing the database by hand.

**Scope:**
- `routes/users.py` behind `require_role("admin")`: `GET /api/v1/admin/users`, `POST /api/v1/admin/users` (create with role + initial password), `PATCH /api/v1/admin/users/{id}` (role, is_active), `POST /api/v1/admin/users/{id}/reset-password`. All audited the same way `admin_alert_classes` audits (structured log + landside-origin event envelope).
- Password policy at the boundary (min length; reject empty). bcrypt cost factor in config.
- Frontend: admin "Users" settings screen (list, create-user modal, role toggle, deactivate, reset-password) — gated on `role === 'admin'`; hidden/blocked for operators.

**Acceptance criteria:**
1. Admin creates an operator; the new user can immediately `login` and receives an `operator`-role token.
2. Operator token on any `/api/v1/admin/users` endpoint → 403; admin token → 200.
3. Deactivating a user (`is_active=false`) causes their subsequent `login` to fail 401 **and** any existing token of theirs to fail `get_current_user` (active-check on verify, not just at login).
4. Password reset invalidates the old password (old creds 401, new creds 200).
5. Every user-management mutation writes an audit event (actor = admin `user_id`, target, action) — queryable like the kill-switch audit.
6. Cannot delete/deactivate the last active admin (lock-out guard) → 409.
7. Frontend Users screen renders loading/error/populated; create + role-toggle + deactivate + reset round-trip and reflect in the list.

**Security Tests (RED-first):** operator escalating self to admin via PATCH → 403; user-enumeration on create (duplicate username) returns a uniform error; reset-password requires admin role not just authentication; deactivated-user token rejected mid-session.

**Integration test (A1 + A3):** seed the acting admin **via the real user-creation flow**, then drive create→login-as-new-user→deactivate→login-fails end-to-end on real Postgres. Run + pass before review.

**Permission tier:** **Tier 3** — auth + migration-adjacent. Default permission mode.

**Deliverables:** `cloud-backend/src/cloud_backend/routes/users.py`, `cloud-backend/src/cloud_backend/api/users.py` (Pydantic models), `control-centre/src/components/admin/Users.jsx` + `src/api/users.js`.

---

##### E11-S3 — Profile management + preferences re-key migration

**As** a logged-in operator, **I want** my preferences (alert threshold, staleness threshold) stored against *my* identity and editable from a profile screen, **so that** my settings follow me regardless of which shared key the deployment uses.

**Scope:**
- **Data migration concern (load-bearing):** `operator_preferences.operator_id` currently holds the **shared API-key string**, not a user identity. **Alembic 0010** must re-key existing rows. Decision required at create-story: existing rows are keyed to a now-defunct secret — the safe PoC choice is to **drop/seed** preferences against real `user_id`s (there is no real per-user data to preserve — every "operator" was the same shared key), rather than attempt a fabricated mapping. Document this in the story as a Decision; do not silently migrate.
- Re-point `preferences.py` from `:oid = api_key` to `:oid = current_user.user_id` via `get_current_user`. The `/api/v1/operators/me/preferences` GET/PATCH endpoints already exist — this is a key-source swap, not a new endpoint.
- Frontend: Profile screen surfacing the existing preference controls (extracted from wherever `OperatorPreferences` currently lives) under the authenticated user.

**Acceptance criteria:**
1. Two different logged-in users have independent preferences; user A's PATCH never affects user B's row.
2. `operator_preferences` is keyed by `user_id` (FK to `users`); the old API-key-string keying is gone (verified by schema + a test that the column references a real user).
3. Alembic 0010 applies cleanly and idempotently on a DB containing pre-migration rows; the re-key Decision (drop/seed vs map) is documented and the migration does exactly what's documented — no data invented.
4. Profile screen renders loading/error/populated; PATCH round-trips and persists across logout/login.
5. A logged-out user cannot read or write preferences (401).

**Security Tests (RED-first):** user A cannot read/write user B's preferences by manipulating the request (no `operator_id` accepted from the client body — identity comes only from the token); SQL-safety on the user-id key path.

**Integration test (A1 + A3):** real Postgres; create two users via the real flow, drive independent PATCH/GET, assert isolation; run the 0009→0010 migration chain and assert idempotency. Run + pass before review.

**Permission tier:** **Tier 3** — DB migration on existing data. Default permission mode.

**Deliverables:** `cloud-backend/migrations/versions/0010_preferences_rekey_user_id.py`, `cloud-backend/src/cloud_backend/routes/preferences.py`, `control-centre/src/components/profile/Profile.jsx`.

---

##### E11-S4 — Admin UI for kill-switch (X-Admin-Key → JWT swap)

**As** an admin, **I want** to disable/enable an alert class from a settings screen, **so that** the E10-S1 kill-switch is operated through the UI with role-based auth instead of a shared admin key and curl.

**Scope:**
- Swap `admin_alert_classes` router's dependency from `Security(require_admin_key)` to `Security(require_role("admin"))` — the **single clean swap point** confirmed against live code. Remove `X-Admin-Key`/`CC_ADMIN_KEY` usage for this router (keep the audit-event plumbing intact — `actor_name` now comes from `current_user`, not a body field).
- Frontend: admin "Alert Classes" settings screen — list (from existing `GET /api/v1/admin/alert-classes`), per-class disable/enable toggle calling the existing POST endpoints; gated on `role === 'admin'`.

**Acceptance criteria:**
1. Admin toggles an alert class from the UI; the change takes effect at the fan-out filter (a new alert of a disabled class is suppressed from REST + SSE; in-flight escalations stay visible) — i.e. the E10-S1 behavior is preserved end-to-end through the new auth path.
2. Operator token on the kill-switch endpoints → 403; the UI toggle is not shown to operators.
3. Audit event still written on every toggle, now with `actor = current_user.user_id` (no more body-supplied `actor_name`); the audit trail is unbroken across the auth swap.
4. `X-Admin-Key`/`CC_ADMIN_KEY` is no longer accepted on this router (old curl path 401s).
5. Frontend screen renders loading/error/populated; toggle round-trips and reflects current state.

**Security Tests (RED-first):** operator cannot disable an alert class (403); request with old `X-Admin-Key` but no Bearer token → 401; admin role required, authentication alone insufficient.

**Integration test (A1):** real Postgres; admin-token toggle → assert fan-out filter state changed and audit row written; operator-token toggle → 403. Run + pass before review.

**Permission tier:** **Tier 3** — auth swap on a live kill-switch. Default permission mode.

**Deliverables:** `cloud-backend/src/cloud_backend/routes/admin_alert_classes.py` (dependency swap + actor source), `control-centre/src/components/admin/AlertClasses.jsx` + `src/api/alertClasses.js`, `cloud-backend/src/cloud_backend/config/__init__.py` (deprecate `cc_admin_key`).

---

##### E11-S5 — Configuration surface (mutable thresholds, user-scoped)

**As** an admin, **I want** the per-class confidence thresholds (currently hardcoded, read-only) to be editable, and per-operator alert thresholds to be genuinely user-scoped, **so that** calibration values can change without a redeploy and operator settings are owned by real users.

**Scope:**
- Confidence thresholds: today `cloud-backend/src/cloud_backend/config/confidence_thresholds.py` is hardcoded with a read-only `GET /api/v1/config/confidence-thresholds` (E10-S1). Make them mutable — persisted (small `config_kv` or `confidence_thresholds` table, **Alembic 0011 if a table is added**) with an admin-only `PATCH`. The kill-switch fan-out / confidence-gating reads the persisted values.
- Per-operator alert threshold (E2-S8 / Story 2-8): **already shipped** in `preferences.py`, but was keyed by API-key-as-operator-id; E11-S3 already re-keys it to real users. E11-S5's remaining job is the **admin-facing** config surface, not re-building the operator preference.
- Frontend: admin "Configuration" settings screen for the confidence thresholds (operator-facing alert threshold stays on the Profile screen from S3).

**Acceptance criteria:**
1. Admin edits a per-class confidence threshold via UI; the new value is persisted and used by the live confidence gate / degraded-banner logic (verified end-to-end, not just stored).
2. Operator token on the threshold-PATCH endpoint → 403; read may stay operator-visible (matches current read-only GET exposure).
3. If a table is added: Alembic 0011 applies cleanly + idempotently; seeded with the current hardcoded `# CALIBRATE` defaults so behavior is unchanged until edited.
4. Invalid threshold values (out of 0.0–1.0, or below the degraded floor) rejected 422 with ADR-10 envelope.
5. Config screen renders loading/error/populated; edit round-trips and persists.

**Security Tests (RED-first):** operator cannot mutate thresholds (403); out-of-range/NaN values rejected at the boundary; a malformed value cannot disable the confidence gate (fail-safe to the hardcoded default, not to "no gating").

**Integration test (A1 + A3):** real Postgres; admin PATCH a threshold → assert the persisted value is read by the gate on the next evaluation (drive an alert through, not just re-GET the config). Run + pass before review.

**Permission tier:** **Tier 2** (mutable config) escalating to **Tier 3** if a migration is added. Default permission mode.

**Deliverables:** `cloud-backend/src/cloud_backend/routes/config.py` (add PATCH), `cloud-backend/src/cloud_backend/config/confidence_thresholds.py` (read from store), optional `cloud-backend/migrations/versions/0011_confidence_thresholds.py`, `control-centre/src/components/admin/Configuration.jsx`.

---

**Out of scope:** SSO integration with ÖBB's IDP / Keycloak (Phase 2 — the verification seam built by E11-S1/ADR-23 is designed to accept it as a contained swap once the ÖBB tenant is identified). Refresh-token rotation / sliding sessions (PoC uses a single short-TTL access token + re-login). Multi-tenant / org-scoping. Email-based password-reset flows (admin-initiated reset only).

**Cross-cutting (retro action items wired in):**
- **A1 (hard integration gate)** — already in `_bmad/custom/bmad-dev-story.toml`; every story above names an integration test that must *run and pass* on real Postgres before flipping to `review`. Auth is the canonical test/prod-divergence risk (epic-10-retro §Key Insights) — the gate matters most here.
- **A2 (risk-tier review)** — already in `_bmad/custom/bmad-code-review.toml`; auth + migration ⇒ every story except possibly E11-S5 is **FULL adversarial wire-replay** review tier. Each story states its tier in the table above.
- **A3 (create-story divergence rule)** — applied per-story at create-story time: integration tests seed via the **real user-creation/login path**, never raw INSERTs of hand-computed hashes or client-supplied identities.

**Status:** `backlog` — breakdown complete (2026-06-14), **not yet `ready-for-dev`**. Next: `create-story E11-S1` in a fresh context (verify the staged-cutover approach against `main.py` router mounting before coding). E10 work does NOT block Epic 11; the shared-key seam was designed forward-compatible and that has now been verified.

---
