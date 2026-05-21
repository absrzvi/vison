# Story 1.5-2: `rtsp-ingest` Dockerfile

Status: review

## Story

As a platform engineer,
I want a `Dockerfile` for the `rtsp-ingest` service that builds correctly from the Hailo Software Suite base image,
so that the rtsp-ingest container can be deployed as part of the onboard Docker Compose stack with all GStreamer/TAPPAS dependencies available at runtime.

## Acceptance Criteria

1. **`rtsp-ingest/Dockerfile` exists** with `ARG HAILO_BASE=hailo-software-suite:4.23` + `FROM ${HAILO_BASE}` as the base image (not `python:3.11-slim-bookworm` — GStreamer/TAPPAS RTSP plugins are pre-installed in this image and cannot be pip-installed).

2. **`oebb-shared` package is installed** using the two-step pattern: copy `shared/src/oebb_shared` + `shared/pyproject.toml` into a staging dir, `pip install --no-cache-dir ./shared_src`, matching all other containers.

3. **`rtsp-ingest` package is installed** from its `pyproject.toml` with `pip install --no-cache-dir -e .`. All dependencies in `pyproject.toml` must resolve without conflict against the Hailo base image's Python 3.11 environment.

4. **`cameras.json` mounted via volume** — not baked in. The Dockerfile sets `ENV RTSP_INGEST_CAMERAS_JSON_PATH=/config/cameras.json`. A `/config` directory must exist in the image. Volume mount is wired in story 1-5-3.

5. **Health endpoint reachable** — container exposes port 8080 (`RTSP_INGEST_CONTEXT_PUSH_PORT=8080`). `EXPOSE 8080` must appear in the Dockerfile.

6. **`CMD` launches the service** — `rtsp_ingest.main:app` is the FastAPI app object. The CMD must be: `["python", "-m", "uvicorn", "rtsp_ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]` — `main.py` module-level code initialises all components at import time.

7. **Python 3.11 assertion** — `RUN` guard confirms the base image Python version hasn't drifted.

8. **No secrets baked in** — all runtime config (event_store_url, vehicle_id, etc.) is provided via env vars at `docker run` / docker-compose time.

9. **`docker build --check` succeeds** (or produces only the expected Hailo registry pull error) — Dockerfile is syntactically valid with no dangling COPY paths relative to monorepo build context root.

10. **`rtsp-ingest/CLAUDE.md` is created** with stack, commands, module layout, key patterns, credential hygiene boundary, and pipeline.py coverage exclusion — mirrors level of detail in `inference/CLAUDE.md`.

## Failure Scenarios

- **Hailo base image unavailable on dev machine:** Build fails at FROM pull step on a standard laptop. Expected — use `--build-arg HAILO_BASE=my-local-stub:latest` to substitute. Do not add a silent fallback FROM.
- **GStreamer RTSP plugin path wrong at runtime:** If `gst-plugins-good` RTSP demuxer is not on `GST_PLUGIN_PATH`, the pipeline will crash. Do not override `GST_PLUGIN_PATH` — the Hailo base image sets it correctly.

## Dev Notes

### Base Image Decision (same as inference — story 1-5-1 ADR)

Architecture explicitly states `rtsp-ingest` + `inference` both use `hailo-software-suite:4.23` as their base. `rtsp-ingest` needs:
- GStreamer RTSP plugins (rtspsrc, rtph264depay, etc.) from TAPPAS base
- TAPPAS integration if frames are handed directly to inference pipeline
- Cannot be `pip install`-ed from PyPI

### Entry Point

`rtsp-ingest/src/rtsp_ingest/main.py`:
- Module-level code initialises `Scheduler`, `Gate`, `Pipeline`, `FastAPI` app
- `app` object is the FastAPI app (directly usable by uvicorn)
- `if __name__ == "__main__": uvicorn.run(...)` uses `127.0.0.1` — must use `0.0.0.0` in Docker

The CMD should use uvicorn directly (unlike inference which has a custom main loop):
```dockerfile
CMD ["python", "-m", "uvicorn", "rtsp_ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Existing Dockerfile Pattern (from story 1-5-1)

```dockerfile
ARG HAILO_BASE=hailo-software-suite:4.23
FROM ${HAILO_BASE}

WORKDIR /app

RUN python --version 2>&1 | grep -q "Python 3.11" || \
    (echo "ERROR: expected Python 3.11, got $(python --version 2>&1)" && exit 1)

COPY shared/src/oebb_shared shared_src/src/oebb_shared
COPY shared/pyproject.toml shared_src/pyproject.toml
RUN pip install --no-cache-dir ./shared_src

COPY rtsp-ingest/pyproject.toml .
COPY rtsp-ingest/src/ src/
RUN pip install --no-cache-dir -e .

RUN mkdir -p /config
VOLUME ["/config"]

ENV RTSP_INGEST_CAMERAS_JSON_PATH=/config/cameras.json

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "rtsp_ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### `rtsp-ingest/src/rtsp_ingest/config.py` — Relevant env vars

`Settings` uses pydantic-settings with `env_file=".env"`. Key Docker-relevant vars:
```
cameras_json_path     = cameras.json     → override to /config/cameras.json
event_store_url       = http://event-store:8000
context_push_port     = 8080
vehicle_id            = OBB-TEST         (runtime override required)
```

No `env_prefix` defined — env var names map directly from field names.

### Permission Tier

| Action | Tier |
|---|---|
| Write `rtsp-ingest/Dockerfile` | 2 — local file edit |
| Write `rtsp-ingest/CLAUDE.md` | 2 — local file edit |
| `docker build --check` to validate syntax | 3 — shell; expected to fail on Hailo pull |

## Tasks

- [x] Write `rtsp-ingest/Dockerfile`
  - [x] `ARG HAILO_BASE=hailo-software-suite:4.23` + `FROM ${HAILO_BASE}`
  - [x] `WORKDIR /app`
  - [x] Python 3.11 assertion `RUN` guard
  - [x] Two-step oebb-shared install (copy → pip install ./shared_src)
  - [x] Copy rtsp-ingest pyproject.toml + src/, pip install -e .
  - [x] `RUN mkdir -p /config`
  - [x] `VOLUME ["/config"]`
  - [x] `ENV RTSP_INGEST_CAMERAS_JSON_PATH=/config/cameras.json`
  - [x] `EXPOSE 8080`
  - [x] `CMD ["python", "-m", "uvicorn", "rtsp_ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]`
  - [x] Add comment about Hailo Developer Zone registry requirement and security notes
- [x] Write `rtsp-ingest/CLAUDE.md`
  - [x] Stack, commands, module layout (8 files), key patterns, credential hygiene, pipeline.py coverage exclusion
- [x] Validate Dockerfile syntax (`docker build --check` from monorepo root)
- [x] Confirm no secrets baked in; all runtime config is env-var driven

## File List

- `rtsp-ingest/Dockerfile` — NEW
- `rtsp-ingest/CLAUDE.md` — NEW
- `_bmad-output/implementation-artifacts/1-5-2-rtsp-ingest-dockerfile.md` — story file

## Change Log

- 2026-05-21: Wrote `rtsp-ingest/Dockerfile` (FROM hailo-software-suite:4.23, two-step shared install, /config dir + VOLUME, EXPOSE 8080, CMD uvicorn rtsp_ingest.main:app)
- 2026-05-21: Wrote `rtsp-ingest/CLAUDE.md` (stack, commands, 8-file module layout, key patterns, security boundary, failure scenarios)
- 2026-05-21: Validated Dockerfile with `docker build --check` — syntax clean; expected pull failure for Hailo registry confirmed

## Dev Agent Record

### Implementation Plan

- Write Dockerfile mirroring inference/Dockerfile pattern — same base image, same two-step shared install, same Python assertion guard
- Key differences from inference: no `/models` dir (no .hef), port 8080 not 8081, CMD uses uvicorn directly (not `python -m rtsp_ingest.main`)
- Write CLAUDE.md covering 8 modules in rtsp_ingest/src/rtsp_ingest/
- Validate with `docker build --check`

### Completion Notes

- Dockerfile mirrors `inference/Dockerfile` exactly in structure; key differences: no `/models` dir, port 8080 not 8081, CMD uses uvicorn directly (rtsp_ingest.main:app is a real FastAPI app object, unlike inference which uses a custom main loop)
- `GST_PLUGIN_PATH` deliberately not set — Hailo base image owns it
- `VOLUME ["/config"]` declared; no `/models` needed (no .hef in rtsp-ingest)
- `docker build --check` confirmed syntax valid; only failure is expected Hailo registry pull
- CLAUDE.md covers all 8 src files, priority scheduling pattern, P3 gate, door-release override, credential hygiene, coverage exclusion
