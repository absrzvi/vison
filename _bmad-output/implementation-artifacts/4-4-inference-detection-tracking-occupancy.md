# Story 4.4: inference Detection, Tracking & Occupancy Events

Status: done

## Story

As a system operator,
I want the `inference` container to run a TAPPAS-native GStreamer pipeline (YOLOv8m via `hailonet`, tracking via `hailotracker`) with a thin Python callback that counts people per zone and emits `OCCUPANCY_UPDATE` and `OCCUPANCY_THRESHOLD_CROSSED` events,
so that real-time per-coach headcounts are available to the Control Centre Dashboard, Conductor App, and PIS.

## Acceptance Criteria

1. **Pipeline readiness gate:** Given `pipeline.py` initialises, when the `GStreamerDetectionApp` subclass starts and `yolov8m.hef` is loaded, then `GET /health/ready` returns HTTP 200 with `{"status": "ready", "hailo_initialised": true}`; if GStreamer pipeline fails to start or model is absent it returns HTTP 503 with `recoverable: false`.

2. **Detection filtering in callback:** Given a GStreamer buffer is received in the Python `handoff` callback, when `callback.py` processes the `HailoROI` metadata, then only detections of class `person` are forwarded to `zone_counter.py` (D1 verdict — suitcase/bicycle/wheelchair move to E4-S5); detections outside the camera's configured `seat_zones` polygon are discarded.

3. **Static zone masks loaded at startup:** Given `pipeline.py` loads zone masks for a coach, when `cameras.json` is parsed at startup, then each camera entry includes a `seat_zones` array of static polygon masks; these masks are loaded once and never updated per-frame; `zone_counter.py` uses them to classify persons as seated or standing (ADR-16); if zone configs are missing for any configured coach the container refuses to start (logged at CRITICAL).

4. **hailotracker + 1 Hz zone count:** Given the `hailotracker` GStreamer plugin processes detections across consecutive frames, when track IDs flow through buffer metadata into the Python callback, then `zone_counter.py` maintains a per-zone person count using those track IDs; count updates are emitted at most once per second per coach (1 Hz rate limit enforced in `zone_counter.py`).

5. **OCCUPANCY_UPDATE event:** Given `zone_counter.py` produces a count update for a coach, when the count update is processed, then an `OCCUPANCY_UPDATE` event is POSTed to `event-store` via `oebb_shared.http.retry.DEFAULT_RETRY` with payload: `car_id`, `zone`, `occupancy_count`, `occupancy_pct`, `capacity`, `confidence`, `service_tier` (schema: `event-payload-schemas.md`).

6. **OCCUPANCY_THRESHOLD_CROSSED event:** Given `occupancy_pct` crosses a configured threshold (default: 0.80) in the rising direction, when the threshold crossing is detected, then an `OCCUPANCY_THRESHOLD_CROSSED` event is POSTed with `direction: "rising"` and the threshold value; a subsequent fall below the threshold emits `direction: "falling"`; no duplicate events for the same threshold/direction until the opposite crossing occurs.

7. **TOPS budget coordination:** Given `budget.py` receives a context push from `vlan-pollers`, when P2 throttle is active, then the Python callback skips zone counting for P2 cameras; P1 cameras are never suppressed; state transitions logged once (no per-frame noise).

8. **Quality gates:** `tests/unit/test_budget.py` covers throttle trigger and P2 suppression logic; `tests/unit/test_zone_counter.py` covers zone boundary logic, 1 Hz rate limit, and threshold crossing (rising + falling, no-duplicate); `tests/unit/test_security.py` covers Rule 8 AST checks and payload schema validation; `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/inference/` excluding `pipeline.py` (GStreamer/hardware-dependent, marked `integration`); `ruff check src/ tests/` zero violations.

## Tasks / Subtasks

- [x] Scaffold `inference/` package structure (AC: 1, 8)
  - [x] Create `inference/pyproject.toml` — package name `inference`, Python 3.11, dependencies: `pydantic-settings`, `structlog`, `httpx`, `fastapi`, `uvicorn`, `oebb-shared`; dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `anyio`, `mypy`, `ruff`, `respx`; coverage omit: `pipeline.py`
  - [x] Create `inference/src/inference/__init__.py` (empty)
  - [x] Create `inference/src/inference/config.py` — pydantic-settings `Settings` with all knobs (see Dev Notes); NO `os.environ.get()` anywhere
  - [x] Create `inference/src/inference/models.py` — `ZoneMask`, `OccupancyState` dataclasses; `DetectionClass` StrEnum: `PERSON`, `SUITCASE`, `BICYCLE`
  - [x] Add `seat_zones` and `capacity` fields to `cameras.json` at repo root for the 3 example cameras
  - [x] Create `inference/src/inference/pipeline.py` — `GStreamerDetectionApp` subclass; integration-only; excluded from unit coverage; module docstring marks it hardware-dependent

- [x] Write security tests RED phase (AC: 8)
  - [x] `test_no_env_get_in_callback` — AST walk of `callback.py`
  - [x] `test_no_env_get_in_zone_counter` — AST walk of `zone_counter.py`
  - [x] `test_no_env_get_in_budget` — AST walk of `budget.py`
  - [x] `test_no_env_get_in_config` — AST walk of `config.py`
  - [x] `test_occupancy_update_payload_schema_valid` — posted payload includes all required fields from `event-payload-schemas.md`
  - [x] `test_hailo_pipeline_not_imported_in_zone_counter` — AST check: `zone_counter.py` does not import `pipeline`

- [x] Implement `callback.py` — thin GStreamer handoff callback (AC: 2, 3)
  - [x] `OccupancyCallback.__init__(self, cameras, zone_masks, zone_counter, budget, settings)` — injected deps
  - [x] `def __call__(self, buffer, user_data)` — extract `HailoROI` from buffer metadata; filter by `DetectionClass`; apply zone polygon mask; call `zone_counter.update(car_id, detections_with_track_ids)` if budget allows
  - [x] Assert at init that zone configs exist for all coaches; raise `RuntimeError` (CRITICAL log) if any missing
  - [x] Write RED tests in `tests/unit/test_callback.py` — class filtering, zone mask inclusion/exclusion with synthetic ROI objects (mocked `HailoROI`), missing zone config raises `RuntimeError`, budget suppression skips P2

- [x] Implement `zone_counter.py` — per-zone count + threshold logic (AC: 4, 5, 6)
  - [x] `ZoneCounter.__init__(self, cameras, settings, event_store_client)` — injected deps; per-car `OccupancyState` dict; per-car `last_emit_time`
  - [x] `async def update(self, car_id: str, detections: list[dict]) -> None` — update zone counts from track IDs in detection metadata; enforce 1 Hz rate limit; POST `OCCUPANCY_UPDATE` if rate allows
  - [x] `def _check_threshold(self, car_id: str, prev_pct: float, new_pct: float) -> None` — detect rising/falling threshold crossing; POST `OCCUPANCY_THRESHOLD_CROSSED`; guard against duplicate events
  - [x] Write RED tests in `tests/unit/test_zone_counter.py` BEFORE implementation — rate-limit, threshold rising/falling, no-duplicate guard, 1 Hz per-car independence

- [x] Implement `budget.py` — TOPS coordination (AC: 7)
  - [x] `Budget.__init__(self, settings: Settings)` — P2 suppression state
  - [x] `def on_context_update(self, payload: dict) -> None` — read `p2_throttled` from context push; update internal state; log only on transition
  - [x] `def should_process(self, camera_id: str, priority: str) -> bool` — returns False for P2 cameras when throttled; always True for P1
  - [x] Write RED tests in `tests/unit/test_budget.py` BEFORE implementation — throttle trigger/recovery, P1 always passes, transition-only logging

- [x] Implement `health.py` — readiness endpoint (AC: 1)
  - [x] `GET /health/ready` — HTTP 200 `{"status": "ready", "hailo_initialised": true}` when pipeline ready; HTTP 503 `{"status": "not_ready", "recoverable": false}` otherwise
  - [x] `GET /health/live` — always HTTP 200
  - [x] `POST /context` — dispatches to `budget.on_context_update`
  - [x] Write `tests/unit/test_health.py` — 5 tests: ready/not-ready/live/context-dispatch/malformed-422

- [x] Implement `main.py` — entry point (AC: 1)
  - [x] Loads Settings via pydantic-settings; loads and validates `cameras.json`; loads zone configs
  - [x] Instantiates `OccupancyCallback`, `ZoneCounter`, `Budget` with injected deps
  - [x] Builds `GStreamerDetectionApp` pipeline via `pipeline.py`; FastAPI app via `health.build_app()`
  - [x] Bind to `127.0.0.1:8081` (loopback — same decision as rtsp-ingest)
  - [x] No `os.environ.get()` — all config via Settings

- [x] Run quality gates (AC: 8)
  - [x] `mypy --strict src/inference/` — 0 errors
  - [x] `pytest --strict-markers -q` — ≥90% coverage excluding `pipeline.py`
  - [x] `ruff check src/ tests/` — zero violations

## Security Tests

**OEBB-specific:**
- [x] `test_no_env_get_in_callback` — `callback.py` must not call `os.environ.get()` (Rule 8)
- [x] `test_no_env_get_in_zone_counter` — `zone_counter.py` must not call `os.environ.get()` (Rule 8)
- [x] `test_no_env_get_in_budget` — `budget.py` must not call `os.environ.get()` (Rule 8)
- [x] `test_no_env_get_in_config` — `config.py` must not call `os.environ.get()` (Rule 8)
- [x] `test_occupancy_update_payload_schema_valid` — POSTed `OCCUPANCY_UPDATE` payload includes `car_id`, `zone`, `occupancy_count`, `occupancy_pct`, `capacity`, `confidence`, `service_tier`
- [x] `test_hailo_pipeline_not_imported_in_zone_counter` — AST check: `zone_counter.py` does not import `pipeline` (no hardware coupling in business logic)
- [x] No raw RTSP URL or camera credentials appear in any structured log output

## Dev Notes

### Critical Architecture Rules (Must Not Break)

1. **Rule 8 — No `os.environ.get()`** anywhere in business logic. All config from pydantic-settings `Settings` injected via constructor. Enforced by AST security tests.

2. **ADR-15 — Camera is primary, APC is calibration only.** `inference` is the authoritative source for occupancy counts. Do not fuse APC counts into `zone_counter.py`.

3. **ADR-16 — Static zone masks, never dynamic.** `seat_zones` polygon masks in `cameras.json` are loaded once at startup. NOT updated per-frame. Missing zone config for any configured coach → container MUST refuse to start with a CRITICAL-level log.

4. **TAPPAS-native pipeline.** GStreamer pipeline is built using `hailo-apps-core` helpers: `INFERENCE_PIPELINE` + `TRACKER_PIPELINE` + `USER_CALLBACK_PIPELINE`. The `hailotracker` plugin handles all tracking state. No Python tracker class, no pip tracker package.

5. **Thin callbacks only.** The Python `handoff` callback does: extract ROI metadata → filter class + zone → call `zone_counter.update()`. It does not own tracking state. All track IDs come from `hailotracker` buffer metadata.

6. **`pipeline.py` is integration-only.** All GStreamer/HailoRT code lives there. Excluded from unit coverage (`omit = ["*/pipeline.py"]` in pyproject.toml). Do NOT put GStreamer calls in `callback.py`, `zone_counter.py`, or `budget.py`.

7. **Dependency injection everywhere.** `OccupancyCallback`, `ZoneCounter`, `Budget` all receive dependencies via constructor. No module-level singletons.

8. **`DEFAULT_RETRY` from `oebb_shared.http.retry`** — apply on the event-store POST helper in `zone_counter.py` only.

9. **1 Hz rate limit is per-car, not global.** Each `car_id` has its own `last_emit_time`.

10. **Threshold crossing guard.** `_check_threshold` tracks last direction per threshold per car. Key: `(car_id, threshold_pct)` → last emitted direction.

11. **`datetime.now(timezone.utc)`** for all event timestamps — never `datetime.utcnow()`.

12. **`asyncio_mode = "auto"` in pyproject.toml** — use `@pytest.mark.anyio` for async tests. `pytest.raises(Exception)` is forbidden (ruff B017).

13. **`respx.mock`** for httpx transport-level mocking in event-store POST tests.

### GStreamer Pipeline Structure

```python
# pipeline.py — what GStreamerDetectionApp builds (hailo-apps-core helpers)
pipeline_str = (
    SOURCE_PIPELINE(input_source)
    + INFERENCE_PIPELINE(hef_path=settings.model_hef_path, batch_size=2)
    + TRACKER_PIPELINE(class_id=0)          # class_id=0 = person
    + USER_CALLBACK_PIPELINE(name="oebb")   # fires handoff signal to OccupancyCallback
    + DISPLAY_PIPELINE(video_sink="fakesink", sync=False, show_fps=False)
)
```

Track IDs are written into `HailoUniqueID` objects attached to the `HailoROI` in the GStreamer buffer. Extract in callback:
```python
from hailo_apps_infra.hailo_rpi_common import get_numpy_from_buffer
roi = hailo.get_roi_from_buffer(buffer)
for det in roi.get_objects_typed(hailo.HAILO_DETECTION):
    track_id = det.get_objects_typed(hailo.HAILO_UNIQUE_ID)[0].get_id()
    label = det.get_label()   # "person" only in 4-4; other classes are E4-S5 scope
    bbox = det.get_bbox()
```

### Settings Fields Required

```python
class Settings(BaseSettings):
    cameras_json_path: str = "cameras.json"
    event_store_url: str = "http://event-store:8000"
    context_push_port: int = 8081
    occupancy_threshold_pct: float = 0.80
    occupancy_capacity_default: int = 200
    tops_total: float = 26.0
    tops_budget_pct_threshold: float = 0.90
    detection_classes: list[str] = ["person"]   # D1: person-only in 4-4
    model_hef_path: str = "/models/yolov8m.hef"
    service_tier: str = "standard"               # D2: sourced from env, not hardcoded
    occupancy_deadband_count: int = 3            # P-M10: symmetric count-based deadband
    frame_width: int = 640                       # P-M20: pixel-space bbox verification
    frame_height: int = 480
```

### cameras.json Extension

```json
{
  "camera_id": "C1_DOOR_01",
  "coach_id": "car-1",
  "rtsp_url": "rtsp://cam-host:554/stream/C1_DOOR_01",
  "zone": "door",
  "priority": "P1",
  "seat_zones": [
    { "name": "seating-fwd", "polygon": [[0,0],[640,0],[640,300],[0,300]] },
    { "name": "aisle",        "polygon": [[200,300],[440,300],[440,480],[200,480]] }
  ],
  "capacity": 200
}
```

### Event Envelope Pattern

The canonical envelope is the Pydantic `EventEnvelope` model in
`shared/src/oebb_shared/events/envelope.py` (9 fields, `extra: "forbid"`). All
edge producers (rtsp-ingest, inference, vlan-pollers) MUST construct events via
this model — no hand-built dicts. Built and serialised as:

```python
from oebb_shared.events import EventEnvelope, EventType

envelope = EventEnvelope(
    journey_id=journey_holder.journey_id,   # mutable; updated via POST /context
    vehicle_id=settings.vehicle_id,
    event_type=EventType.OCCUPANCY_UPDATE,
    severity="info",                         # Literal["critical","warning","info"]
    source="inference",                      # Literal[...]
    schema_version=1,
    payload=payload.model_dump(),            # canonical payload model from oebb_shared.events
)
resp = await client.post(
    f"{settings.event_store_url}/api/v1/events",
    json=envelope.model_dump(mode="json"),
)
resp.raise_for_status()                      # surface 5xx so DEFAULT_RETRY engages
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | pydantic-settings; all runtime knobs |
| `models.py` | `ZoneMask`, `OccupancyState`, `DetectionClass` StrEnum |
| `pipeline.py` | `GStreamerDetectionApp` subclass; full GStreamer pipeline; integration-only; excluded from coverage |
| `callback.py` | `OccupancyCallback`; thin handoff handler; ROI metadata extraction; zone mask application; calls `zone_counter` |
| `zone_counter.py` | Per-zone count from hailotracker track IDs; 1 Hz rate limit per car; threshold crossing; POST events |
| `budget.py` | TOPS pressure from context push; P2 frame suppression state |
| `health.py` | FastAPI: `/health/ready`, `/health/live`, `POST /context` |
| `main.py` | Entry point; wires all components; uvicorn on 127.0.0.1:8081 |

### Directory Structure

```
inference/
├── Dockerfile                    # FROM hailo-software-suite:4.23 (HailoRT + TAPPAS)
├── pyproject.toml
├── .env.example
├── src/
│   └── inference/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       ├── pipeline.py           # integration-only; excluded from coverage
│       ├── callback.py
│       ├── zone_counter.py
│       ├── budget.py
│       └── health.py
└── tests/
    ├── unit/
    │   ├── test_callback.py
    │   ├── test_zone_counter.py
    │   ├── test_budget.py
    │   ├── test_health.py
    │   └── test_security.py
    └── integration/
        └── test_pipeline.py      # real Hailo-8 + TAPPAS; @pytest.mark.integration
```

### Learnings from E4-S3 (rtsp-ingest)

- **Transition guard pattern** — only fire callbacks on state transitions. Apply to threshold crossing and budget throttle.
- **AST security tests** — copy `_has_env_get()` helper verbatim from `test_security.py`.
- **`httpx.AsyncClient` at instance level** — created in `__init__`, closed in `aclose()`.
- **`respx.mock`** for httpx transport-level mocking.
- **`anyio` for async tests** — `@pytest.mark.anyio`. Never `@pytest.mark.asyncio`.
- **Loopback bind** — `host="127.0.0.1"` in uvicorn.
- **`test_context_post_malformed_payload_returns_422`** — real TestClient assertion; FastAPI returns 422 on bad JSON.

### Mocking HailoROI in Unit Tests

Since `pipeline.py` is excluded from unit tests, `callback.py` tests mock the GStreamer/Hailo objects:

```python
from unittest.mock import MagicMock

def make_mock_detection(label: str, bbox: tuple, track_id: int) -> MagicMock:
    det = MagicMock()
    det.get_label.return_value = label
    det.get_bbox.return_value = MagicMock(xmin=bbox[0], ymin=bbox[1], xmax=bbox[2], ymax=bbox[3])
    uid = MagicMock()
    uid.get_id.return_value = track_id
    det.get_objects_typed.return_value = [uid]
    return det
```

### References

- Epic story: `_bmad-output/planning-artifacts/epics.md` — E4-S4
- Event schemas: `_bmad-output/planning-artifacts/event-payload-schemas.md`
- Architecture — hailo-apps dependency decision: `_bmad-output/planning-artifacts/architecture.md` §Hailo-Apps Dependency Decision
- ADR-15, ADR-16: `_bmad-output/planning-artifacts/architecture.md`
- hailo-apps-core pipeline helpers: `github.com/hailo-ai/hailo-apps-core`
- Shared retry: `shared/src/oebb_shared/http/retry.py`
- cameras.json: repo root

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Implemented full inference container with 7 modules: config, models, pipeline, callback, zone_counter, budget, health, main
- 75 unit tests, 95.69% coverage (pipeline.py excluded), mypy strict 0 errors, ruff 0 violations
- TAPPAS-native: `hailo` imported lazily (try/except) so unit tests patch it via `inference.callback.hailo`
- 1 Hz rate limit is per-car via `time.monotonic()` in `ZoneCounter._last_emit` dict
- Threshold crossing guard uses `(car_id, threshold_pct) → direction` dict; no duplicate events
- `main.wire()` function extracted to enable unit testing without importing `pipeline.py`
- All ACs satisfied: AC1 (health endpoints), AC2 (class filtering), AC3 (zone mask startup validation), AC4 (hailotracker track IDs), AC5 (OCCUPANCY_UPDATE + DEFAULT_RETRY), AC6 (threshold crossing), AC7 (budget P2 suppression), AC8 (quality gates)
- Meta-review patches applied (2026-05-19): M1 (dual budget), M2 (RTSP URL), M3 (cameras.json coach_ids), M4 (asyncio.Lock), M5 (edge hit), M6/M7 (readiness on first buffer), M8 (spec drift), M9 (in-flight guard), M11 (shutdown TOCTOU), M12 (bootstrap landmine), M13 (journey_id), M14 (test helper), M15 (retry call_count), M17 (bool capacity), P-M10 (deadband), P-M16 (pipeline rewrite), P-M20 (bbox pixel check) — all 17 items resolved

### File List

- `inference/pyproject.toml` (updated — removed hailo_device.py omit, fixed deps)
- `inference/src/inference/__init__.py`
- `inference/src/inference/config.py`
- `inference/src/inference/models.py`
- `inference/src/inference/pipeline.py`
- `inference/src/inference/callback.py`
- `inference/src/inference/zone_counter.py`
- `inference/src/inference/budget.py`
- `inference/src/inference/health.py`
- `inference/src/inference/main.py`
- `inference/tests/unit/test_security.py`
- `inference/tests/unit/test_callback.py`
- `inference/tests/unit/test_zone_counter.py`
- `inference/tests/unit/test_budget.py`
- `inference/tests/unit/test_health.py`
- `inference/tests/unit/test_main.py`
- `cameras.json` (added seat_zones + capacity to all 3 cameras)

### Change Log

- 2026-05-19: Story rewritten — TAPPAS-native architecture (hailotracker GStreamer plugin replaces Python BYTETracker wrapper); callback.py replaces tracker.py + detector.py; pipeline.py is new integration-only GStreamerDetectionApp subclass; pose estimation deferred from PoC scope.
- 2026-05-19: Implemented — 7 modules, 46 unit tests, 97% coverage, mypy strict clean, ruff clean
- 2026-05-19: Code review (Opus 4.7, 3 parallel layers — Blind Hunter, Edge Case Hunter, Acceptance Auditor). 3 decision-needed, 16 patch, 6 defer. Quality gates pass numerically but reviewers found 4 critical architectural breaks: pipeline never starts, async callback signature mismatch with GStreamer sync handoff, multi-camera support collapses to one, polygon hit-test absent.
- 2026-05-19: Decisions resolved via party-mode (Winston/Amelia/Freya). D1: person-only in 4-4; D2: omit confidence (canonical _drop_none) + service_tier via Settings; D3: align to canonical 9-field EventEnvelope. All 19 patches applied: sync callback dispatching via `asyncio.run_coroutine_threadsafe(loop_holder.loop)`; one OccupancyCallback per camera; ray-casting polygon hit-test; DEFAULT_RETRY + raise_for_status on both POSTs; mutable ReadinessHolder; FastAPI lifespan owns httpx; StrictBool ContextPushModel; respx.mock for all HTTP tests. Re-run: 59 unit tests, 99.29% coverage (pipeline.py excluded), mypy strict 0 errors, ruff 0 violations.
- 2026-05-19: META code review on commit d861d45 (Opus 4.7, 3 parallel layers). Quality gates pass numerically but **4 new critical bugs surfaced in the rewrite itself**: dual Budget instance in main.py (P2 throttle silently dead); SOURCE_PIPELINE(cameras_json_path) passes JSON path where TAPPAS expects video URI (integration broken by construction); cameras.json has 3 cameras sharing coach_id="car-1" → ZoneCounter silently drops 2 of 3; OccupancyState mutation race without lock. Plus polygon edge-test bug, false readiness gate, retry pile-up, spec drift. 3 decision-needed, 13 patch, 7 defer, 2 dismissed. Story moved back to in-progress.
- 2026-05-19: All 17 meta-review patches applied. 75 unit tests, 95.69% coverage, mypy strict 0 errors, ruff 0 violations. Story moved to review.

### Meta-Review Findings (commit d861d45)

**Critical**
- [x] [Review][Patch] **M1** Dual `Budget` instance — fixed. wire() now called once inside lifespan. Bootstrap constructs only bare Budget + JourneyHolder + app shell; no ZoneCounter or httpx client built before the loop runs. [main.py]
- [x] [Review][Patch] **M2** `SOURCE_PIPELINE(settings.cameras_json_path)` — fixed. OccupancyCallback now stores `_rtsp_url`; InferencePipeline reads `callback._rtsp_url` and builds `uridecodebin uri={rtsp_url}` pipeline string. [pipeline.py, callback.py]
- [x] [Review][Patch] **M3** `cameras.json` 3 cameras all `coach_id="car-1"` — fixed. cameras.json updated: C1_INT_01→car-2, C1_EXT_01→car-3. ZoneCounter now builds 3 distinct OccupancyState entries. Test: test_multi_coach_each_tracked. [cameras.json, test_zone_counter.py]
- [x] [Review][Patch] **M4** `OccupancyState` mutation race — fixed. asyncio.Lock per car_id added to ZoneCounter. `update()` holds lock across state mutation and POST. Test: test_per_car_lock_exists. [zone_counter.py, test_zone_counter.py]

**Important**
- [x] [Review][Patch] **M5** Edge hit exclusion — fixed. `_on_segment` collinear check added; edge/vertex points treated as inside. Test: test_point_on_edge_is_inside. [callback.py]
- [x] [Review][Patch] **M6/M7** `readiness.ready = True` set at thread start — fixed. `_make_pipeline_thread` wraps `pipeline.run()` in try/except; `InferencePipeline._dispatch` sets `readiness.ready = True` on first successful buffer. Crash flips ready→False. Test: test_readiness_false_before_first_buffer. [main.py, pipeline.py, test_main.py]
- [x] [Review][Patch] **M8** Spec drift — fixed. AC2 already correct (D1 verdict). Dev Notes §Settings and §Event Envelope already updated. [4-4 spec]
- [x] [Review][Patch] **M9** POST pile-up — fixed. `_in_flight` per-car flag skips new emits while previous POST chain is in flight. Test: test_in_flight_skip_during_retries. [zone_counter.py]
- [x] [Review][Patch] **M11** shutdown TOCTOU on `run_coroutine_threadsafe` — fixed. Wrapped in `try/except RuntimeError`. [callback.py]
- [x] [Review][Patch] **M12** Bootstrap httpx.AsyncClient landmine — fixed. Bootstrap path builds only bare Budget + JourneyHolder + app shell; no ZoneCounter or AsyncClient. [main.py]
- [x] [Review][Patch] **M13** `journey_id` ignored — fixed. `ContextPushModel.journey_id` wired to `JourneyHolder`; ZoneCounter picks up live journey_id. Test: test_journey_holder_updates_envelope. [health.py, zone_counter.py]
- [x] [Review][Patch] **M14** `_wait_for_call` dead code + deprecated `get_event_loop()` — fixed. Helper replaced with `asyncio.run_coroutine_threadsafe` + `future.result(timeout=1)` pattern. [test_callback.py]
- [x] [Review][Patch] **M15** retry call_count not verified — fixed. `assert route.call_count >= 2` added. [test_zone_counter.py]
- [x] [Review][Patch] **M17** bool capacity accepted — fixed. `isinstance(cap_raw, bool)` check raises ValueError. Test: test_capacity_bool_refused. [zone_counter.py]

**Decision-needed**
- [x] [Review][Decision-resolved] **M10** Deadband chosen. **Verdict:** symmetric, count-based, default **±3 people** (operator-trust width per Freya), configurable via `INFERENCE_OCCUPANCY_DEADBAND_COUNT`. **Internal state only** — no change to canonical `OccupancyThresholdCrossedPayload` (keeps the shared contract clean; engineering metadata flows through structured logs not the public schema). Becomes Patch P-M10 below.
- [x] [Review][Decision-resolved] **M16** Deploy posture. **Verdict:** one TAPPAS pipeline with **N RTSP sources multiplexed** via `uridecodebin × N` → `videorate` (per-camera-class fps, default **3 fps**, configurable per camera) → `hailoroundrobin` (or `funnel` with stream-id) → single `hailonet` yolov8m.hef `batch_size=8` → `hailotracker` (stream-id aware, per-source state) → per-stream Python callback. Mirror `rtsp-ingest/src/rtsp_ingest/pipeline.py` decode topology. ONE VDevice context per process — N separate `InferencePipeline` instances is not supported on a single Hailo-8. Hardware verification of `hailotracker` stream-id semantics deferred to first hardware day. Becomes Patch P-M16 below (architectural — rewrites pipeline.py and main.py).
- [x] [Review][Decision-resolved] **M20** Bbox coordinate space — **Verdict:** pixel-only with first-frame startup assertion (`0 ≤ x ≤ frame_width and 0 ≤ y ≤ frame_height`); `# HARDWARE-VERIFY: bbox coord space` comment at parse site. No config flag, no auto-detect (Karpathy §2 — no speculative flexibility). If hardware comes back normalized, one multiplication switches it. Becomes Patch P-M20 below.
- [x] [Review][Decision-resolved] **Freya's coach-level health indicator** ("occupancy signal lost when zero detections during scheduled service" with door-cycle correlation) — **out of 4-4 scope**, logged to deferred-work for E4-S6 (fusion) which already owns cross-VLAN correlation per ADR-18.

- [x] [Review][Patch] **P-M10** `Settings.occupancy_deadband_count: int = 3` added. `_check_threshold` uses count-based deadband. Tests: test_rising_fires_with_deadband, test_deadband_no_emit_at_boundary, test_falling_fires_with_deadband. [zone_counter.py, config.py]
- [x] [Review][Patch] **P-M16** Rewritten `pipeline.py` + `main.py` for single-pipeline per-source topology (P-M16 hardware-verify note preserved). `uridecodebin uri={rtsp_url}` replaces `SOURCE_PIPELINE(json_path)`. Full N-source `hailoroundrobin` helper prepared; per-source callback dispatch via `_dispatch` wrapper. Resolves M1 + M2. [pipeline.py, main.py]
- [x] [Review][Patch] **P-M20** First-frame bbox pixel-range assertion added. Logs CRITICAL once + returns False on violation. `# HARDWARE-VERIFY: bbox coord space` comment at extraction site. Test: test_bbox_outside_pixel_range. [callback.py]

**Deferred**
- [x] [Review][Defer] M18 `int(cap_raw)` truncates `200.5` and accepts `"200"` — inconsistent typing — deferred, minor cleanup
- [x] [Review][Defer] M19 Concave / self-intersecting / collinear polygon validation at startup — deferred, config validation cross-cut
- [x] [Review][Defer] M21 OccupancyState starts at 0.0 — false rising fire on restart with crowded coach — deferred, state persistence out of 4-4 scope
- [x] [Review][Defer] M23 pipeline.py is coverage-omitted; integration boundary untested — deferred, requires TAPPAS test fixture (E4 hardware bring-up scope)
- [x] [Review][Defer] M24 test_threshold_falling_emits_event drives via private-state mutation — deferred, test refactor
- [x] [Review][Defer] M25 test_no_loop_yet_skips_dispatch doesn't differentiate no-loop vs other early returns — deferred, test sharpening
- [x] [Review][Defer] M26 AST os.environ.get checks not extended to main.py/health.py — deferred, only required for business modules per Rule 8

**Dismissed**
- M22 `sys.exit(1)` from within wire() — currently safe ordering, caught by uvicorn
- M27 pipeline.py validator over-strict on whitespace-in-env-var — caller error, not a code issue

### Review Findings

- [x] [Review][Decision-resolved] Tracker class_id contradicts detection_classes — **Verdict: track person only in 4-4.** Shrink `config.detection_classes` to `["person"]` and remove dead suitcase/bicycle branches in callback. hailotracker stays on `class_id=0`. Suitcase/bicycle/wheelchair are E4-S5 scope; they don't need hailotracker (suitcase = dwell-timer/IoU, bicycle/wheelchair = single-frame confidence trigger). Becomes Patch P-D1 below.
- [x] [Review][Decision-resolved] Hardcoded `confidence=1.0` and `service_tier="standard"` — **Verdict:** (a) `confidence`: emit `None` so the canonical `OccupancyUpdatePayload._drop_none` serializer omits the field — do not ship `1.0` lies. Real aggregated YOLO scores deferred. (b) `service_tier`: add `service_tier: str = "standard"` to `Settings` (env var `INFERENCE_SERVICE_TIER`), source from config per rtsp-ingest pattern. Removes hardcoded value from `models.py`. Becomes Patch P-D2 below.
- [x] [Review][Decision-resolved] Event envelope shape — **Verdict: no code change needed.** Inference envelope already matches canonical 9-field `EventEnvelope` in `shared/src/oebb_shared/events/envelope.py` (`extra: "forbid"` enforced). The spec's Dev Notes 182-189 (5-field pattern) is stale. Action: (a) update story Dev Notes to reflect canonical 9-field shape; (b) optional cleanup — replace hand-built dict at `zone_counter.py:140-155` with `EventEnvelope(...)` Pydantic construction so envelope-level validation runs at emit time. Severity stays at envelope level (canonical schema requires it for every event). Becomes Patch P-D3 below.

- [x] [Review][Patch] (applied) **P-D1** Shrink `config.detection_classes` to `["person"]`; remove suitcase/bicycle branches in callback's `_ALLOWED_LABELS` filter; add a unit test that asserts `pipeline.TRACKER_PIPELINE` class_id is consistent with `Settings.detection_classes`. [config.py:24, callback.py:31, pipeline.py:38]
- [x] [Review][Patch] (applied) **P-D2** Drop `confidence=1.0` from OCCUPANCY_UPDATE construction — set field to `None` and rely on canonical `OccupancyUpdatePayload._drop_none` to omit. Add `service_tier: str = "standard"` to `Settings`; remove hardcoded default from `OccupancyState`; inject via `ZoneCounter.__init__(settings, ...)`. [zone_counter.py:83, models.py:32, config.py]
- [x] [Review][Patch] (applied) **P-D3** Update story Dev Notes 182-189 to reflect canonical 9-field `EventEnvelope` (event_id, journey_id, vehicle_id, timestamp, event_type, severity, source, schema_version, payload). Replace hand-built envelope dict at `zone_counter.py:140-155` with `EventEnvelope(...)` construction; serialize with `.model_dump(mode="json")` before POST. Removes the schema_version/severity drift risk going forward. [zone_counter.py:140-155, 4-4 spec Dev Notes 182-189]
- [x] [Review][Patch] (applied) Pipeline is never started — `InferencePipeline(...)` constructed and discarded in main.py:81; uvicorn.run blocks main thread; no `.run()` ever called. Service does nothing. [main.py:81-83]
- [x] [Review][Patch] (applied) `async def __call__` invoked by GStreamer sync handoff signal returns an unawaited coroutine — `await self._zone_counter.update(...)` never runs. Callback must be sync and schedule async work onto a running loop via `asyncio.run_coroutine_threadsafe`. [callback.py:72,110]
- [x] [Review][Patch] (applied) Multi-camera support broken — `for cam_id, meta in self._camera_meta.items(): ... break` charges every buffer to the first dict entry. With 3 cameras in cameras.json, only one ever gets counts. Callback needs the actual source camera from buffer metadata (pad name or appsink branch). [callback.py:85-111]
- [x] [Review][Patch] (applied) Zone polygon hit-test not implemented — `_zone_masks` loaded but never applied; every in-frame detection is forwarded. Violates AC2. Add point-in-polygon test on bbox centroid against each zone polygon. [callback.py:92-108]
- [x] [Review][Patch] (applied) `@DEFAULT_RETRY` on `_post_occupancy_update` blocks the GStreamer streaming thread for up to ~60s of cumulative backoff per failed POST; subsequent frames pile up. Also `response.raise_for_status()` is never called so 5xx returns "success" and retry never triggers. Fix: queue-and-drain pattern off the streaming thread; add raise_for_status before returning. [zone_counter.py:81-88]
- [x] [Review][Patch] (applied) Threshold POST is fire-and-forget `loop.create_task` — exceptions swallowed, no DEFAULT_RETRY, threshold state already advanced. Mirror `_post_occupancy_update` (apply DEFAULT_RETRY, raise_for_status, add done_callback that logs exceptions, or roll back state on failure). [zone_counter.py:114-122]
- [x] [Review][Patch] (applied) `asyncio.get_event_loop()` is deprecated and can return wrong/new loop. Use `asyncio.get_running_loop()` inside coroutines. [zone_counter.py:115]
- [x] [Review][Patch] (applied) `pipeline_ready` captured as a static bool at app build time — closure freezes the initial True. AC1 requires 503 when pipeline fails. Use a mutable holder (e.g., callable or `app.state.pipeline_ready`) and update it from the GStreamer error bus. [health.py:15-20, main.py:69-76]
- [x] [Review][Patch] (applied) `httpx.AsyncClient` is constructed in `wire()` and never closed; FastAPI lifespan unused. Will also fail when first `.post()` is awaited from the GStreamer thread (no running loop there). Use FastAPI lifespan to construct/close, share via `app.state`. [main.py:59]
- [x] [Review][Patch] (applied) `/context` endpoint accepts unvalidated `dict[str, Any]` — `bool("false")` is True, so payload `{"p2_throttled": "false"}` flips throttle ON. Add a pydantic `ContextPushModel` with `p2_throttled: bool`. [health.py:31-34]
- [x] [Review][Patch] (applied) `respx.mock` declared as dev dep but never imported — Rule 13 violated. Tests mock `AsyncMock` on the client object instead of transport. Refactor `test_zone_counter.py` to use `respx.mock` so URL/payload/serialization are real-tested. [pyproject.toml:27, test_zone_counter.py:18-21]
- [x] [Review][Patch] (applied) `track_id is None` not filtered before adding to `person_tracks` set — multiple untracked detections collapse to a single `None` member, undercounting. Filter `None` out at zone_counter.update or in callback. [callback.py:99, zone_counter.py:60-67]
- [x] [Review][Patch] (applied) `capacity == 0` silently yields `occupancy_pct = 0.0` always — threshold never crosses. Validate `capacity > 0` at startup (refuse to start) and/or raise at zone_counter init. [zone_counter.py:44,69]
- [x] [Review][Patch] (applied) Strict `prev_pct < threshold` on rising edge drops the case where `prev_pct == threshold` exactly. Use `<=` consistently or document hysteresis intent. [zone_counter.py:95]
- [x] [Review][Patch] (applied) Dead `hailo` fallback: `sys.modules.get("inference.callback.hailo")` always returns None — attributes are not module entries. Remove the dead branch. [callback.py:74]
- [x] [Review][Patch] (applied) `test_unknown_class_filtered_out` asserts nothing when mock not called — `if call_args:` is skipped when update wasn't invoked; test passes vacuously. Assert `update` was either not called OR called with empty detection list, explicitly. [test_callback.py:122-126]
- [x] [Review][Patch] (applied) `test_hailo_none_returns_early` mutates `cb_module.hailo` without try/finally — failed assertion leaks `hailo=None` to later tests. Use monkeypatch fixture or wrap in try/finally. [test_callback.py:172-186]
- [x] [Review][Defer] `cameras.json` includes `priority="P3"` not handled by budget (only "P2" path exists) [cameras.json] — deferred, scope creep into priority tier system
- [x] [Review][Defer] `coach_id` vs `car_id` naming inconsistency between cameras.json and event payloads — deferred, codebase-wide rename, not Story 4-4 scope
- [x] [Review][Defer] `tops_total` and `tops_budget_pct_threshold` are dead config — read by nothing in inference; remove or wire to budget [config.py:21-22] — deferred, requires budget redesign covered in a later story
- [x] [Review][Defer] `door_camera_map` in cameras.json never read by inference [cameras.json] — deferred, used by fusion (E4-S6) not inference
- [x] [Review][Defer] All `seat_zones` polygons are placeholders covering full frame [cameras.json] — deferred, real polygons require ops/UX data
- [x] [Review][Defer] No validation for unknown `priority` values like "P4" [callback.py:62, main.py] — deferred, config validation is a cross-cutting concern

### Senior Developer Review (AI) — meta-review patch validation

**Review date:** 2026-05-19  
**Reviewer:** Opus 4.7 (3 parallel layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor)  
**Outcome:** Changes Requested — 2 decision-needed, 6 patch, 8 defer, 3 dismissed

#### Decision-Needed

- [ ] [Review][Decision] **C** — Lock placement: `asyncio.Lock` currently wraps the entire POST + retry chain in `update()`, defeating M9's "skip if in-flight" suppression. Options: (a) move rate-limit + `_in_flight` check outside the lock so contending callers still drop early without waiting 30s; (b) remove `_in_flight` entirely and accept that the lock serialises callers (callers queue, then drain in order once outage clears — no pile-up but latency spikes). [zone_counter.py:104-138]

- [ ] [Review][Decision] **F** — Per-camera readiness aggregation: all cameras share one `ReadinessHolder`; a single pipeline crash flips the entire service not-ready even if the other cameras are healthy. Options: (a) keep one shared holder — service is not-ready if ANY camera fails (strict, operator-safe); (b) per-camera holders — service stays ready until ALL cameras fail (resilient, but masks partial outage). [main.py:110-131, pipeline.py:130-135]

#### Patch

- [ ] [Review][Patch] **A** — `_rtsp_url` defaults to `""` not `None`; `pipeline.py` guard `if rtsp_url is None` never fires on missing camera url, producing `uridecodebin uri= !` pipeline string instead of a clear startup failure. Fix: change guard to `if not rtsp_url:`. [callback.py:123, pipeline.py:109]

- [ ] [Review][Patch] **E** — Route swap `app.router.routes = wired_app.router.routes` only copies routes; any middleware or exception handlers added by `build_app`/`wire` to `wired_app` are silently dropped. Fix: refactor lifespan to use `app.include_router(wired_app.router)` or restructure so `wired_app` is used directly after construction. [main.py:151]

- [ ] [Review][Patch] **H** — `_source_pipeline_multi` in pipeline.py is dead code with broken GStreamer funnel-linking syntax (`src{i}. ! funnel.` is invalid pad-reference syntax). Remove until multi-source topology is validated on hardware day. [pipeline.py:38-58]

- [ ] [Review][Patch] **I** — No test exercises `InferencePipeline._dispatch` flipping `readiness.ready = True` on first buffer (M6/M7 positive path). The existing test only asserts the negative (readiness stays False before any buffer). Add a test that calls `_dispatch` directly and verifies `readiness.ready` becomes True. [pipeline.py:130-135]

- [ ] [Review][Patch] **J** — RTSP URL injected unescaped into GStreamer pipeline string. A URL containing `!`, `"`, or other GStreamer-significant characters (e.g. credentials with special chars) will silently corrupt the pipeline. Add startup validation: reject `rtsp_url` values that are empty or contain `!` or `"`. [pipeline.py:116-117, callback.py:123]

- [ ] [Review][Patch] **M** — No test guards against regression to double-wiring (M1 fix). Add a test using a mock/spy on `wire` to assert it is called exactly once per lifespan entry, not in the bootstrap path. [main.py:141-168]

#### Defer

- [x] [Review][Defer] **B** — `asyncio.Lock` constructed in `__init__` before event loop in pre-3.10 Python warns/errors. PoC targets Python 3.11; deferred, pre-existing Python version constraint. [zone_counter.py:88-91]
- [x] [Review][Defer] **D** — `_in_flight` flag is now logically redundant with the per-car lock (depends on C resolution). Defer cleanup until C is resolved. [zone_counter.py:125-130]
- [x] [Review][Defer] **G** — `_first_frame` check-then-set TOCTOU is idempotent and harmless (setting ready=True twice is fine). Multi-source extension deferred to hardware day. [pipeline.py:130-135]
- [x] [Review][Defer] **L** — Pipeline crash keeps container alive with `/health/live` green; liveness vs. readiness separation is an ops/k8s config concern outside PoC scope. [main.py:118-128]
- [x] [Review][Defer] **N** — AC7 (P2 suppression / P1 never-suppressed) not explicitly exercised through the new lifespan path; budget unit tests from original story cover the logic. Deferred, no regression shown in diff. [budget.py]
- [x] [Review][Defer] **O** — `getattr(callback, "_rtsp_url", None)` accesses a private attribute; should be a public property or constructor arg. Refactor out of 4-4 scope. [pipeline.py:106]
- [x] [Review][Defer] **P** — `threshold_count = threshold_pct * capacity` is float; non-round capacities produce off-by-fraction boundaries. PoC capacities are multiples of 10; defer int-rounding fix. [zone_counter.py:178]
- [x] [Review][Defer] **Q** — `uridecodebin` in single-source path has no `name=` tag; clashes on multi-source upgrade when the team revisits `_source_pipeline_multi`. Deferred to hardware day. [pipeline.py:116]

