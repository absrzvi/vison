# Story 1.5-3: Onboard Docker Compose

Status: done

## Story

As a platform engineer,
I want a `docker-compose.onboard.yml` that brings up the complete standalone onboard stack (event-store, rtsp-ingest, inference),
so that the full onboard pipeline can be started with a single command on the R5001C SYS2 edge device.

## Acceptance Criteria

1. **`docker-compose.onboard.yml` exists** at the monorepo root and defines exactly three services: `event-store`, `rtsp-ingest`, `inference`.

2. **`event-store` service** builds from `event-store/Dockerfile` (context `.`), binds `/data` volume for SQLite persistence, sets `EVENT_STORE_API_KEY` via env var, exposes port 8001, and has a `healthcheck` using `/health/ready`.

3. **`rtsp-ingest` service** builds from `rtsp-ingest/Dockerfile` (context `.`, `HAILO_BASE` build-arg documented), bind-mounts `cameras.json` to `/config/cameras.json`, sets all required `RTSP_INGEST_*` env vars, depends on `event-store` (condition: `service_healthy`), exposes port 8080, and has a `healthcheck` using `/health/ready`.

4. **`inference` service** builds from `inference/Dockerfile` (context `.`, `HAILO_BASE` build-arg documented), bind-mounts the `.hef` model to `/models/yolov8m.hef` and `cameras.json` to `/config/cameras.json`, passes `--device=/dev/hailo0` and `--group-add video` for Hailo-8 hardware, sets all required `INFERENCE_*` env vars, depends on both `event-store` (condition: `service_healthy`) AND `rtsp-ingest` (condition: `service_healthy`), exposes port 8081, and has a `healthcheck` using `/health/ready`.

5. **`event-store` is the dependency root** — `rtsp-ingest` depends on `event-store`; `inference` depends on `event-store` AND `rtsp-ingest`. This ensures event-store is always up before either pipeline service starts.

6. **Named volume** `onboard_event_store_data` declared for the event-store SQLite file — not an anonymous volume.

7. **No secrets hardcoded** — `EVENT_STORE_API_KEY`, `RTSP_INGEST_VEHICLE_ID`, `INFERENCE_VEHICLE_ID` are set to dev-safe placeholder values with comments marking them as override-required for production.

8. **Build-arg `HAILO_BASE`** is documented in a comment for both `rtsp-ingest` and `inference` build sections — operators know how to substitute a stub image on non-Hailo dev machines.

9. **File is valid YAML** and `docker compose -f docker-compose.onboard.yml config` exits 0 (or with only the expected Hailo-device warning).

## Failure Scenarios

- **event-store not ready before rtsp-ingest starts:** `depends_on: condition: service_healthy` gates startup; without it rtsp-ingest may try to POST events before event-store is accepting connections.
- **Hailo device `/dev/hailo0` absent:** `inference` will fail to acquire the device and `ReadinessHolder` will stay false; `/health/ready` returns 503. The compose file must pass the device through but inference must not crash the whole stack.

## Dev Notes

### Services in scope

From architecture decision (container map memory):
- **Onboard (SYS2):** event-store, rtsp-ingest, inference (+ vlan-pollers, fusion — out of scope for this story)
- **Landside:** cloud-backend, postgres (already in `docker-compose.yml`)

This file covers the three containerised-so-far onboard services only. vlan-pollers and fusion are not yet containerised.

### Port assignments

| Service | Internal port | Host port |
|---|---|---|
| event-store | 8001 | 8001 |
| rtsp-ingest | 8080 | 8080 |
| inference | 8081 | 8081 |

### Key env vars

**event-store:**
- `EVENT_STORE_API_KEY=onboard-dev-key` (placeholder; required at runtime)
- `DB_PATH=/data/events.db`

**rtsp-ingest** (prefix `RTSP_INGEST_`):
- `RTSP_INGEST_CAMERAS_JSON_PATH=/config/cameras.json`
- `RTSP_INGEST_EVENT_STORE_URL=http://event-store:8001`
- `RTSP_INGEST_VEHICLE_ID=OBB-TEST`

**inference** (prefix `INFERENCE_`):
- `INFERENCE_CAMERAS_JSON_PATH=/config/cameras.json`
- `INFERENCE_MODEL_HEF_PATH=/models/yolov8m.hef`
- `INFERENCE_EVENT_STORE_URL=http://event-store:8001`
- `INFERENCE_VEHICLE_ID=OBB-TEST`
- `INFERENCE_EVENT_STORE_API_KEY=onboard-dev-key`

### Healthcheck pattern

Follow the pattern from `docker-compose.yml` — use `python -c "import urllib.request; urllib.request.urlopen(...)"` (no curl dependency).

### Device passthrough

```yaml
devices:
  - /dev/hailo0:/dev/hailo0
group_add:
  - video
```

### Permission Tier

| Action | Tier |
|---|---|
| Write `docker-compose.onboard.yml` | 2 — local file edit |
| `docker compose -f docker-compose.onboard.yml config` | 3 — shell |

Tier 3 (compose config validation) requires explicit sign-off. Story complete once file is syntactically valid YAML; full stack bring-up requires Hailo hardware (out of scope).

## Tasks

- [x] Write `docker-compose.onboard.yml`
  - [x] `event-store` service with build, volumes, env, healthcheck, ports
  - [x] `rtsp-ingest` service with build (HAILO_BASE arg), bind-mounts, env, depends_on event-store, healthcheck, ports
  - [x] `inference` service with build (HAILO_BASE arg), bind-mounts, device passthrough, env, depends_on both, healthcheck, ports
  - [x] Named volume `onboard_event_store_data`
  - [x] Comments marking override-required env vars
- [x] Validate YAML syntax (`docker compose -f docker-compose.onboard.yml config`)

## File List

- `docker-compose.onboard.yml` — NEW
- `_bmad-output/implementation-artifacts/1-5-3-onboard-docker-compose.md` — story file

## Change Log

- 2026-05-21: Wrote `docker-compose.onboard.yml` (3 services: event-store, rtsp-ingest, inference; named volume; device passthrough; healthcheck gates; HAILO_BASE build-arg documented)
- 2026-05-21: Validated with `docker compose -f docker-compose.onboard.yml config` — exits 0

## Dev Agent Record

### Implementation Plan

- Write docker-compose.onboard.yml following the pattern from docker-compose.yml (healthcheck, volumes, depends_on)
- Three services only: event-store, rtsp-ingest, inference
- Hailo device passthrough on inference; both Hailo services use HAILO_BASE build-arg
- Validate YAML with `docker compose config`

### Review Findings (code-review 2026-05-21, Opus 4.7)

**Decision-needed (1)**
- [x] [Review][Decision] D1 — resolved: changed `inference depends_on rtsp-ingest` from `service_healthy` → `service_started`; added production note to change back when real RTSP streams are available

**Patches (7)**
- [x] [Review][Patch] P1 — added `event_store_api_key: str = ""` to rtsp-ingest `config.py`; `RTSP_INGEST_EVENT_STORE_API_KEY` now honoured [rtsp-ingest/src/rtsp_ingest/config.py]
- [x] [Review][Patch] P2 — added `event_store_api_key: str = ""` to inference `config.py`; `INFERENCE_EVENT_STORE_API_KEY` now honoured [inference/src/inference/config.py]
- [x] [Review][Patch] P3 — compose env keys renamed to `EVENT_STORE_DB_PATH`/`EVENT_STORE_CURSOR_PAGE_SIZE` matching event-store env_prefix [docker-compose.onboard.yml]
- [x] [Review][Patch] P4 — `event_store_url` default changed to `http://event-store:8001` in both config files; test `_make_settings` fixed to use field names not prefixed env var names (149 inference tests pass) [rtsp-ingest/config.py, inference/config.py, inference/tests/unit/test_tripwire.py]
- [x] [Review][Patch] P5 — added `restart: unless-stopped` to all three services [docker-compose.onboard.yml]
- [x] [Review][Patch] P6 — added `start_period: 60s` to rtsp-ingest healthcheck; `start_period: 90s` to inference healthcheck [docker-compose.onboard.yml]
- [x] [Review][Patch] P7 — added "PRODUCTION OVERRIDE REQUIRED" comments to vehicle ID vars; added HAILO_BASE comment to inference build section [docker-compose.onboard.yml]

**Deferred (6)**
- [x] [Review][Defer] P8 — `INFERENCE_FUSION_URL: http://fusion:8090` points to non-existent service in this stack — deferred, fusion not yet containerised; inference fusion calls are optional/guarded; out of scope for 1-5-3
- [x] [Review][Defer] P9 — `group_add: video` may not grant Hailo-8 access (driver may use `hailo` group) — deferred, requires hardware verification on SYS2; same class as inference D1
- [x] [Review][Defer] P10 — bind mount `./cameras.json` auto-creates directory if absent — deferred, Docker behaviour; cannot prevent at compose level without entrypoint guard; documented in CLAUDE.md
- [x] [Review][Defer] P11 — no container security hardening (`cap_drop`, `read_only`, `security_opt`) — deferred, pre-existing PoC posture documented in Dockerfiles
- [x] [Review][Defer] P12 — port 8080 published on all host interfaces — deferred, PoC; VLAN isolation is auth boundary
- [x] [Review][Defer] P13 — no pinned `HAILO_BASE` digest — deferred, pre-existing (same as 1-5-1 P6, 1-5-2 P7)

### Completion Notes

- Three services only: event-store (python:3.11-slim base), rtsp-ingest (HAILO_BASE), inference (HAILO_BASE)
- Dependency chain: event-store healthy → rtsp-ingest starts → rtsp-ingest healthy → inference starts
- inference healthcheck uses 15s interval / 6 retries (more generous — Hailo device init takes longer)
- Hailo device: `devices: /dev/hailo0` + `group_add: video`; without it hailonet element init fails silently
- cameras.json bind-mounted read-only to both rtsp-ingest and inference at `/config/cameras.json`
- HEF model bind-mounted at `/opt/hailo/models/yolov8m.hef` (production SYS2 path; annotated as override)
- Named volume `onboard_event_store_data` (not anonymous) so SQLite survives container restarts
- `docker compose config` exits 0 — YAML fully valid
