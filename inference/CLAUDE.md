# CLAUDE.md — inference

Hailo-8 detection and tracking container. Runs a GStreamer/TAPPAS pipeline (YOLOX-S, `yolox_s_leaky.hef`, Apache-2.0, on Hailo-8 M.2) that emits structured events to the `event-store` service. AGPL `yolov8m` is retired (ADR-16 §465); pose estimation is deferred and out of bench/trip scope. A FastAPI sidecar exposes `/health/ready` and `/context` for vlan-pollers to push journey context.

**Base image:** `hailo-software-suite:4.23` (HailoRT + TAPPAS 5.1.0) — NOT `python:3.11-slim-bookworm`. This is mandatory; TAPPAS GStreamer plugins cannot be pip-installed.

## Stack

- Python 3.11 + GStreamer/TAPPAS (hailonet, hailofilter, hailotracker)
- HailoRT 4.23 Python bindings (pre-installed in base image)
- FastAPI + uvicorn (health/context sidecar only — not the inference path)
- httpx + tenacity for event-store HTTP client
- pydantic-settings for all config (`INFERENCE_` prefix)
- structlog for structured JSON logging

## Commands

```bash
cd inference
pip install -e ".[dev]"
python -m pytest                   # unit tests only (no Hailo device needed)
python -m pytest -m integration    # requires real Hailo-8 hardware
python -m pytest --cov=src/inference --cov-report=term-missing
python -m ruff check src/
python -m mypy src/
```

`pipeline.py` is excluded from coverage in `pyproject.toml` (`omit = ["*/pipeline.py"]`) — it wraps the GStreamer event loop and requires a physical Hailo device. Do not remove this exclusion.

Coverage gate: 90% (enforced in `pyproject.toml`).

## Module Layout

```
src/inference/
  main.py        — entry point; wires all components, starts GStreamer thread, runs uvicorn
  config.py      — pydantic-settings Settings (env_prefix="INFERENCE_"); all runtime config
  health.py      — FastAPI app factory: /health/ready, /health/live, POST /context
  models.py      — domain dataclasses: ZoneMask, ReadinessHolder, JourneyHolder, LoopHolder
  budget.py      — TOPS budget coordinator; P2 camera suppression under thermal pressure
  callback.py    — OccupancyCallback; GStreamer buffer callback → zone_counter + event POST
  pipeline.py    — InferencePipeline; GStreamerDetectionApp subclass (TAPPAS); EXCLUDED from coverage
  safety.py      — SafetyHandler; accessibility/ramp events, slip-fall detection
  tripwire.py    — TripwireHandler; gangway directional tripwire → gangway traversal events
  zone_counter.py — per-zone people counting from hailotracker track IDs; POST events to event-store
  heartbeat.py   — periodic liveness/heartbeat emission
  model_provenance.py — model file hash/provenance reporting (HEF identity)
```

## Key Patterns

### Two runtimes, one process

`main.py` runs two concurrent runtimes:
1. **GStreamer pipeline** — runs on ONE daemon thread (`threading.Thread`) hosting a single multiplexed pipeline (N sources → hailoroundrobin → one hailonet → one VDevice; P-M16). GStreamer owns its own main loop; do not call GStreamer APIs from the asyncio loop.
2. **uvicorn/asyncio** — runs on the main thread. FastAPI handlers execute here.

Cross-runtime dispatch uses `asyncio.run_coroutine_threadsafe(coro, loop_holder.loop)` — the loop reference is captured in `LoopHolder` during the lifespan startup and passed into callbacks that need to schedule async work from the GStreamer thread.

### Context push (`POST /context`)

`vlan-pollers` sends `POST /context` with `journey_id` and throttle flags when a new trip starts. `health.py` updates `JourneyHolder.journey_id` (shared with zone_counter / safety_handler). All events emitted after this carry the new journey_id.

### Readiness aggregation

`ReadinessHolder` is one per camera. `health.py` aggregates:
- all ready → `status: ready`, 200
- some ready → `status: degraded`, 200
- none ready → `status: not_ready`, 503

`pipeline.py` sets `ready = True` on first successful buffer; the thread wrapper flips `ready = False` on exit/crash.

### Event client

`httpx.AsyncClient` (timeout 5s) is created in the uvicorn lifespan context and passed into zone_counter, safety_handler, and callbacks. Do not create httpx clients outside lifespan — they must be closed cleanly on shutdown.

## File Conventions

- All config via `pydantic-settings` Settings class — no `os.environ.get()` anywhere
- `main()` is excluded from coverage with `# pragma: no cover` — it is the integration entry point
- New camera event types: add to `shared/events/types.py` first (ADR-5), then add emission in zone_counter / safety_handler / tripwire as appropriate
- `cameras.json` format: `{"cameras": [{camera_id, coach_id, zone, seat_zones, tripwire?, ...}]}`

## What NOT to Touch

- Do not override `GST_PLUGIN_PATH` in the Dockerfile — the Hailo base image sets it correctly
- Do not create httpx clients outside of the FastAPI lifespan — leaked clients cause shutdown hangs
- Do not add credentials to any inference code path — see security boundary below

## Required Runtime Configuration

These must be supplied at container startup (not in the Dockerfile):

| Env var | Required | Default | Notes |
|---|---|---|---|
| `INFERENCE_EVENT_STORE_API_KEY` | **required** | _(none)_ | X-API-Key for event-store `/api/v1/*`; all event POSTs return 401 without it |
| `INFERENCE_VEHICLE_ID` | required | `OBB-TEST` | Override for real train ID |
| `INFERENCE_JOURNEY_ID` | set via /context | `OBB-TEST_unknown_19700101` | Updated by vlan-pollers POST /context on each trip |

Required host device (wire in docker-compose.onboard.yml, story 1-5-3):
- `--device=/dev/hailo0 --group-add video` — Hailo-8 M.2 PCIe device; without it `hailonet` element init fails silently and `ReadinessHolder` stays false

## Security Boundary

**PoC limitations (document before fleet rollout):**

1. **Container runs as root.** Hailo device permissions on R5001C SYS2 must be validated on first hardware bring-up day before adding a non-root `USER` with `video`/`render` group membership. Do not assume the Hailo SDK's device node permissions match a non-root uid without testing.

2. **`POST /context` relies on VLAN isolation.** The `/context` endpoint (journey_id push from vlan-pollers) has no token auth — it is protected by VLAN 5/7/8 network isolation only. At fleet rollout, add `X-API-Key` check matching the event-store pattern, or OAuth2/OIDC per ADR-6/7.

**Always enforced:**
- VLAN poller credentials and Hailo device credentials must never pass through inference code paths
- `X-API-Key` header for event-store calls — set via `INFERENCE_EVENT_STORE_API_KEY` env var at startup
- Do not inline API keys, token strings, or passwords in source files
- Audit this boundary on every story that touches this service

## Review Failure Scenarios

- **GStreamer `hailonet` element missing:** Pipeline crashes with `no element "hailonet"` if TAPPAS plugin path is wrong. `ReadinessHolder.ready` must flip to `False` — verify the pipeline thread's `finally` block.
- **Model file absent at startup:** `/models/yolox_s_leaky.hef` missing → `InferencePipeline` init fails. Thread wrapper must catch and flip `ready = False`; container must not crash the whole Docker stack.
- **cameras.json missing or malformed:** `main()` calls `sys.exit(1)` — intentional; no cameras means no useful work.
- **Slow event-store:** httpx 5s timeout with tenacity retry. Do not block the GStreamer callback waiting for HTTP; use `run_coroutine_threadsafe` to schedule async POSTs without blocking.
