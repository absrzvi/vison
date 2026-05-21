# CLAUDE.md — rtsp-ingest

RTSP camera ingestion container. Connects to 25–30 onboard camera streams, enforces P1/P2/P3 priority frame rates, gates P3 exterior cameras during station windows, and posts `CAMERA_DEGRADED`/`CAMERA_RECOVERED` events to the `event-store` service. A FastAPI sidecar exposes `/health/ready` and `/context` for vlan-pollers to push journey context and door-release signals.

**Base image:** `hailo-software-suite:4.23` (HailoRT + TAPPAS 5.1.0) — NOT `python:3.11-slim-bookworm`. This is mandatory; GStreamer RTSP source plugins (rtspsrc, rtph264depay, avdec_h264) and TAPPAS integration are pre-installed and cannot be pip-installed.

## Stack

- Python 3.11 + GStreamer/TAPPAS (RTSP multisource pipeline)
- FastAPI + uvicorn (health/context sidecar)
- httpx + tenacity for event-store HTTP client
- pydantic-settings for all config (no `env_prefix` — field names map directly to env vars)
- structlog for structured JSON logging

## Commands

```bash
cd rtsp-ingest
pip install -e ".[dev]"
python -m pytest                   # unit tests only (no camera streams needed)
python -m pytest -m integration    # requires real RTSP camera endpoints
python -m pytest --cov=src/rtsp_ingest --cov-report=term-missing
python -m ruff check src/
python -m mypy src/
```

`pipeline.py` is excluded from coverage in `pyproject.toml` (`omit = ["*/pipeline.py"]`) — it wraps the GStreamer event loop and requires physical camera streams. Do not remove this exclusion.

Coverage gate: 90% (enforced in `pyproject.toml`).

## Module Layout

```
src/rtsp_ingest/
  main.py      — entry point; module-level init of all components; FastAPI app object
  config.py    — pydantic-settings Settings; all runtime config; no os.environ.get()
  models.py    — domain dataclasses: CameraConfig, CameraState, Priority (StrEnum)
  health.py    — FastAPI app factory: /health/ready, /health/live, POST /context
  scheduler.py — TOPS budget enforcement; P1/P2/P3 fps assignment; P2 throttle on pressure
  gate.py      — P3 station window gate; door-release P1 override (120-second window)
  pipeline.py  — GStreamer multisource pipeline; RTSP connect/disconnect; EXCLUDED from coverage
  __init__.py  — empty
```

## Key Patterns

### Module-level initialisation

Unlike `inference/main.py` which uses a custom entry point, `rtsp-ingest/main.py` initialises all components at module level so uvicorn can import `rtsp_ingest.main:app` directly:
```python
_cameras   = load_cameras(settings.cameras_json_path)
_scheduler = Scheduler(_cameras, settings)
_gate      = Gate(cameras=_cameras, scheduler=_scheduler, ...)
_pipeline  = Pipeline(cameras=_cameras, ...)
app        = build_app(scheduler=_scheduler, gate=_gate, pipeline=_pipeline)
```
This means `cameras.json` must be present and readable at startup — the container exits 1 if it is missing.

### Priority frame rate scheduling

`scheduler.py` maintains a `dict[str, CameraState]` per camera:
- P1 (door/vestibule): 10 fps always; never throttled
- P2 (interior): 5 fps normally; 2 fps when `tops_used > 90% of 26 TOPS`
- P3 (exterior/platform): 8 fps only when station window is active; off otherwise

`Scheduler.report_tops(tops_used)` triggers P2 throttle/recovery.
`Scheduler.gate_p3(active)` activates/deactivates all P3 cameras.

### P3 station window gate

`gate.py` receives context pushes from vlan-pollers via `POST /context`:
- `speed_kmh < 20 AND next_station` → `scheduler.gate_p3(True)` within 500ms
- `speed_kmh > 20` → `scheduler.gate_p3(False)`

Door-release override (`event: "door_release"`): calls `scheduler.override_to_p1(camera_ids, 120.0)` — camera reverts to configured priority after 120 seconds. This override is internal to rtsp-ingest only (ADR-18 Trigger 1) — not published to event-store.

### RTSP disconnect/reconnect

`pipeline.py` monitors GStreamer bus messages. On `CAMERA_DEGRADED`:
- Posts event to event-store (camera_id, coach_id, reason)
- Attempts reconnect with exponential backoff (tenacity)
- On reconnect posts `CAMERA_RECOVERED`

### Health readiness

`/health/ready` returns 200 only when `scheduler.active_p1_count() >= 1`. Before any P1 stream connects, returns 503 with `{"status": "starting"}`.

## File Conventions

- All config via `pydantic-settings` Settings — no `os.environ.get()` anywhere
- New camera event types: add to `shared/events/types.py` first (ADR-5), then emit in `pipeline.py`
- `cameras.json` format: `{"cameras": [...], "door_camera_map": {"door_id": ["camera_id", ...]}}`
- `pipeline.py` integration tests: mark with `@pytest.mark.integration`

## Required Runtime Configuration

These must be supplied at container startup (not in the Dockerfile):

All env vars use the `RTSP_INGEST_` prefix (from `env_prefix` in `Settings`).

| Env var | Default | Notes |
|---|---|---|
| `RTSP_INGEST_CAMERAS_JSON_PATH` | `cameras.json` | Set to `/config/cameras.json` in Dockerfile; bind-mount actual file |
| `RTSP_INGEST_VEHICLE_ID` | `OBB-TEST` | Override for real train ID |
| `RTSP_INGEST_EVENT_STORE_URL` | `http://event-store:8000` | Correct for onboard compose stack |
| `RTSP_INGEST_CONTEXT_PUSH_PORT` | `8080` | Port uvicorn binds; matches `EXPOSE 8080` |
| `RTSP_INGEST_TOPS_BUDGET_PCT_THRESHOLD` | `0.90` | Fraction of TOPS at which P2 throttle kicks in |
| `RTSP_INGEST_TOPS_TOTAL` | `26.0` | Total Hailo-8 TOPS budget |
| `RTSP_INGEST_P1_FPS` | `10.0` | P1 (door/vestibule) frame rate |
| `RTSP_INGEST_P2_FPS` | `5.0` | P2 (interior) frame rate at normal load |
| `RTSP_INGEST_P2_THROTTLED_FPS` | `2.0` | P2 frame rate under TOPS pressure |
| `RTSP_INGEST_P3_FPS` | `8.0` | P3 (exterior) frame rate during station window |
| `RTSP_INGEST_STATION_SPEED_THRESHOLD_KMH` | `20.0` | Speed below which P3 station gate activates |
| `RTSP_INGEST_DOOR_RELEASE_OVERRIDE_S` | `120.0` | Seconds a door-release P1 override lasts |

## Security Boundary

**PoC limitations (document before fleet rollout):**

1. **Container runs as root.** Hailo/camera device permissions on R5001C SYS2 must be validated on first hardware bring-up day before adding a non-root `USER`.

2. **`POST /context` relies on VLAN isolation.** The `/context` endpoint has no token auth — protected by VLAN 5/7/8 network isolation only. At fleet rollout, add `X-API-Key` check.

**Always enforced:**
- VLAN poller credentials must never appear in rtsp-ingest code paths
- Do not inline API keys or passwords in source files
- Audit this boundary on every story touching this service

## Review Failure Scenarios

- **cameras.json missing:** `load_cameras()` raises; module-level init fails; container exits 1. Bind-mount the file before starting.
- **P1 stream never connects:** `/health/ready` returns 503. Docker Compose `depends_on: condition: service_healthy` will hold back inference until P1 is live.
- **GStreamer RTSP plugin missing:** Pipeline fails with `no element "rtspsrc"`. Do not override `GST_PLUGIN_PATH` — the base image owns it.
