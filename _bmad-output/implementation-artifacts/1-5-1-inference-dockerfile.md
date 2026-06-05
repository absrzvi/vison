# Story 1.5-1: `inference` Dockerfile

Status: done

## Story

As a platform engineer,
I want a `Dockerfile` for the `inference` service that builds correctly from the Hailo Software Suite base image,
so that the inference container can be deployed as part of the onboard Docker Compose stack with all GStreamer/TAPPAS/HailoRT dependencies available at runtime.

## Acceptance Criteria

1. **`inference/Dockerfile` exists** with `FROM hailo-software-suite:4.23` as the base image (not `python:3.11-slim-bookworm` — HailoRT + TAPPAS are pre-installed in this image and cannot be installed via pip).

2. **`oebb-shared` package is installed** using the same two-step pattern as all other containers: copy `shared/src/oebb_shared` + `shared/pyproject.toml` into a staging dir, `pip install --no-cache-dir ./shared_src`, then copy and install the inference package.

3. **`inference` package is installed** in editable mode (`pip install --no-cache-dir -e .`) from its `pyproject.toml`. All dependencies listed in `pyproject.toml` must resolve without conflict against the Hailo base image's pre-installed Python 3.11 environment.

4. **Model file mounted via volume** — the `.hef` file is NOT baked into the image. The Dockerfile sets `ENV INFERENCE_MODEL_HEF_PATH=/models/yolov8m.hef` as a documented default. A `/models` directory must exist in the image (created via `RUN mkdir -p /models`). The volume mount is wired in docker-compose.onboard.yml (story 1-5-3), not here.

5. **`cameras.json` mounted via volume** — not baked in. The Dockerfile sets `ENV INFERENCE_CAMERAS_JSON_PATH=/config/cameras.json`. A `/config` directory must exist in the image.

6. **Health endpoint reachable** — container exposes port 8081 (`INFERENCE_CONTEXT_PUSH_PORT=8081`). `EXPOSE 8081` must appear in the Dockerfile. The `/health/ready` path returns 200 when cameras are initialised.

7. **`CMD` launches uvicorn on the health FastAPI app** — `inference.health:build_app` is the FastAPI app factory, but `inference.main` is the true entry point (it starts GStreamer on a thread and then calls uvicorn). The CMD must be: `["python", "-m", "inference.main"]` — do NOT use `uvicorn inference.main:app ...` directly (the app object is built dynamically inside `main.py`).

8. **No secrets baked in** — all runtime config (event_store_url, fusion_url, vehicle_id, journey_id, etc.) is provided via env vars at `docker run` / docker-compose time. The Dockerfile sets only the paths that have meaningful defaults (`/models/yolov8m.hef`, `/config/cameras.json`).

9. **`docker build` succeeds** (or produces only the expected "layer not available" warning for the Hailo base image on a non-Hailo dev machine) — the Dockerfile must be syntactically valid with no dangling COPY paths relative to the monorepo build context root.

10. **`inference/CLAUDE.md` is created** (does not exist yet) with stack, commands, module layout, key patterns, and file conventions — mirrors the level of detail in `event-store/CLAUDE.md` and `cloud-backend/CLAUDE.md`.

## Failure Scenarios

- **Hailo base image unavailable on dev machine:** The build will fail with a pull error on a standard x86 laptop that has no access to the Hailo Developer Zone registry. This is expected. The Dockerfile must include a comment noting this and optionally an `ARG HAILO_BASE=hailo-software-suite:4.23` so a local stub image can be substituted for CI layer-cache testing. Do not add a fallback FROM — it would produce a broken image silently.
- **GStreamer plugin path wrong at runtime:** If TAPPAS plugins are not on `GST_PLUGIN_PATH`, the pipeline will crash with `no element "hailonet"`. The Hailo base image sets this correctly; do not override `GST_PLUGIN_PATH` in the Dockerfile unless you know the exact path in `hailo-software-suite:4.23`.

## Dev Notes

### Base Image Decision (Architecture ADR)

Architecture explicitly states (line ~1102):

> `rtsp-ingest` + `inference`: base from **Hailo Software Suite Docker image** (HailoRT 4.23 + TAPPAS 5.1.0, available from Hailo Developer Zone) rather than `python:3.11-slim-bookworm`
> All other containers remain on `python:3.11-slim-bookworm`

This is non-negotiable. `inference` needs:
- `hailort` Python bindings (for `.hef` model loading)
- `hailonet`, `hailofilter`, `hailotracker` GStreamer plugins (TAPPAS)
- GStreamer 1.x core libs
- None of these can be `pip install`-ed from PyPI.

### Existing Dockerfile Pattern (copy exactly for shared install)

All other containers use this two-step shared package install:
```dockerfile
COPY shared/src/oebb_shared shared_src/src/oebb_shared
COPY shared/pyproject.toml shared_src/pyproject.toml
RUN pip install --no-cache-dir ./shared_src

COPY inference/pyproject.toml .
COPY inference/src/ src/

RUN pip install --no-cache-dir -e .
```
Build context is the **monorepo root** (same as `event-store` and `cloud-backend` — see `docker-compose.yml` `context: .`).

### `inference/src/inference/config.py` — All env vars

The `Settings` class uses `env_prefix="INFERENCE_"`. Defaults that matter for Docker:
```
INFERENCE_CAMERAS_JSON_PATH    = cameras.json          → override to /config/cameras.json
INFERENCE_EVENT_STORE_URL      = http://event-store:8000  (correct for onboard stack)
INFERENCE_CONTEXT_PUSH_PORT    = 8081
INFERENCE_MODEL_HEF_PATH       = /models/yolov8m.hef
INFERENCE_FUSION_URL           = http://fusion:8090
INFERENCE_VEHICLE_ID           = OBB-TEST              (runtime override required)
INFERENCE_JOURNEY_ID           = OBB-TEST_unknown_19700101  (runtime override)
```

### Entry Point

`inference/src/inference/main.py`:
- Starts GStreamer pipeline on a background thread
- Calls `build_app(...)` to create the FastAPI health/context-push app
- Runs uvicorn on port `settings.context_push_port` (default 8081)

**Do not use** `CMD ["uvicorn", "inference.health:build_app", ...]` — `build_app` is a factory function that requires runtime arguments. The correct CMD is:
```dockerfile
CMD ["python", "-m", "inference.main"]
```

### `inference/CLAUDE.md` Content Requirements

Must cover:
- **Stack:** Python 3.11, FastAPI, GStreamer/TAPPAS (hailonet/hailofilter/hailotracker), HailoRT 4.23, httpx, structlog, pydantic-settings
- **Commands:** `pip install -e ".[dev]"`, `python -m pytest`, `ruff check src/`, `mypy src/`, how to skip `pipeline.py` in coverage (already in `pyproject.toml`)
- **Module layout** (all 8 files in `src/inference/`): budget.py, callback.py, config.py, health.py, main.py, models.py, pipeline.py, safety.py, tripwire.py, zone_counter.py — with a one-line role per file
- **Key patterns:** GStreamer thread + uvicorn asyncio loop (two separate runtimes); `context_push_port` for vlan-pollers to push journey_id; `LoopHolder` / `run_coroutine_threadsafe` for cross-thread async dispatch
- **Credential hygiene boundary:** VLAN poller and Hailo credentials must not appear in inference code paths (CLAUDE.md security rule)
- **pipeline.py is excluded from coverage** — it requires a real Hailo device; mark integration tests with `@pytest.mark.integration`

### Permission Tier

| Action | Tier |
|---|---|
| Write `inference/Dockerfile` | 2 — local file edit |
| Write `inference/CLAUDE.md` | 2 — local file edit |
| `docker build` to validate syntax | 3 — shell; expected to fail on Hailo pull |

Tier 3 (docker build) requires explicit sign-off before running. The story is complete once the Dockerfile is syntactically valid and structurally correct; a full successful build requires the Hailo Developer Zone registry (out of scope for this story).

## Tasks

- [x] Write `inference/Dockerfile`
  - [x] `ARG HAILO_BASE=hailo-software-suite:4.23` + `FROM ${HAILO_BASE}`
  - [x] `WORKDIR /app`
  - [x] Two-step oebb-shared install (copy → pip install ./shared_src)
  - [x] Copy inference pyproject.toml + src/, pip install -e .
  - [x] `RUN mkdir -p /models /config`
  - [x] `ENV INFERENCE_MODEL_HEF_PATH=/models/yolov8m.hef INFERENCE_CAMERAS_JSON_PATH=/config/cameras.json`
  - [x] `EXPOSE 8081`
  - [x] `CMD ["python", "-m", "inference.main"]`
  - [x] Add comment about Hailo Developer Zone registry requirement
- [x] Write `inference/CLAUDE.md` (does not exist yet — required by story standards)
  - [x] Stack, commands, module layout, key patterns, credential hygiene boundary, pipeline.py coverage exclusion
- [x] Validate Dockerfile syntax (e.g. `docker build --no-cache --dry-run .` or `hadolint`) — do not push/pull the Hailo image
- [x] Confirm no secrets are baked in; all runtime config is env-var driven

## File List

- `inference/Dockerfile` — NEW (patched: VOLUME declaration, Python assertion, security notes, device docs)
- `inference/CLAUDE.md` — NEW (patched: required runtime config section, security boundary expanded)
- `inference/src/inference/main.py` — MODIFIED (P1: uvicorn host 127.0.0.1 → 0.0.0.0)
- `_bmad-output/implementation-artifacts/1-5-1-inference-dockerfile.md` — story file updated
- `_bmad-output/implementation-artifacts/deferred-work.md` — deferred items appended

## Change Log

- 2026-05-21: Wrote `inference/Dockerfile` (FROM hailo-software-suite:4.23, two-step shared install, /models /config dirs, EXPOSE 8081, CMD python -m inference.main)
- 2026-05-21: Wrote `inference/CLAUDE.md` (stack, commands, 10-file module layout, key patterns, security boundary, failure scenarios)
- 2026-05-21: Validated Dockerfile with `docker build --check` — syntax clean; expected pull failure for Hailo registry confirmed

## Dev Agent Record

### Completion Notes

- Dockerfile uses `ARG HAILO_BASE` so CI can substitute a stub image without changing the file
- `GST_PLUGIN_PATH` deliberately not set — Hailo base image owns it
- `CMD ["python", "-m", "inference.main"]` — not uvicorn directly; `main()` starts GStreamer thread then uvicorn
- `docker build --check` confirmed full parse success; only failure is expected Hailo registry pull (no DockerHub access)
- CLAUDE.md covers all 10 src files, two-runtime architecture, credential hygiene, coverage exclusion

### Review Findings (code-review 2026-05-21, Opus 4.7)

**Decision-needed (2)**
- [x] [Review][Decision] D1 — Runs as root: no `USER` directive — resolved: defer to hardware day; documented in Dockerfile comment + CLAUDE.md security boundary
- [x] [Review][Decision] D2 — `POST /context` unauthenticated — resolved: VLAN isolation is the PoC auth boundary; documented in Dockerfile comment + CLAUDE.md

**Patches (5)**
- [x] [Review][Patch] P1 — `uvicorn` binds `127.0.0.1` → fixed to `0.0.0.0` [inference/src/inference/main.py:240]
- [x] [Review][Patch] P3 — `INFERENCE_EVENT_STORE_API_KEY` documented as required runtime env var [inference/CLAUDE.md, inference/Dockerfile]
- [x] [Review][Patch] P4 — Hailo device passthrough (`--device=/dev/hailo0`) documented [inference/CLAUDE.md, inference/Dockerfile]
- [x] [Review][Patch] P5 — Added `VOLUME ["/models", "/config"]` declaration [inference/Dockerfile]
- [x] [Review][Patch] P7 — Python 3.11 assertion added as `RUN` guard [inference/Dockerfile]

**Deferred (7)**
- [x] [Review][Defer] P2 — No `inference` service in `docker-compose.yml` — deferred, scope is story 1-5-3 (docker-compose.onboard.yml)
- [x] [Review][Defer] P6 — Mutable base image tag `hailo-software-suite:4.23` — deferred, cannot verify digest without Hailo registry
- [x] [Review][Defer] P8 — No `HEALTHCHECK` in Dockerfile — deferred, pre-existing pattern (event-store/cloud-backend also lack it)
- [x] [Review][Defer] P9 — `degraded` readiness returns 200 — deferred, pre-existing in health.py, not changed here
- [x] [Review][Defer] P10 — Editable install in production image — deferred, matches existing event-store/cloud-backend pattern
- [x] [Review][Defer] P13 — `EXPOSE 8081` fragile if context_push_port env-overridden — deferred, documented in CLAUDE.md, low risk
- [x] [Review][Defer] P14/P15 — Daemon-thread shutdown race / no STOPSIGNAL — deferred, pre-existing design in main.py

## Story-Specific OEBB Failure Scenarios

1. **GStreamer `hailonet` element missing at runtime:** If the Hailo base image tag changes or the TAPPAS plugin path shifts between minor releases, the GStreamer pipeline will fail at startup with `no element "hailonet"`. The health endpoint returns `not_ready` (503) rather than crashing — verify this is what actually happens by checking `inference/health.py` logic.

2. **Model file not mounted:** If `/models/yolov8m.hef` is absent at startup, `inference.pipeline` will fail to load the model. The health endpoint should reflect `not_ready`; the container must not crash the entire Docker stack — check that the pipeline thread catches this and sets the `ReadinessHolder.ready = False`.
