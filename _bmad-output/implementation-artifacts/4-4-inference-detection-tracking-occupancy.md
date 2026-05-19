# Story 4.4: inference Detection, Tracking & Occupancy Events

Status: review

## Story

As a system operator,
I want the `inference` container to run a TAPPAS-native GStreamer pipeline (YOLOv8m via `hailonet`, tracking via `hailotracker`) with a thin Python callback that counts people per zone and emits `OCCUPANCY_UPDATE` and `OCCUPANCY_THRESHOLD_CROSSED` events,
so that real-time per-coach headcounts are available to the Control Centre Dashboard, Conductor App, and PIS.

## Acceptance Criteria

1. **Pipeline readiness gate:** Given `pipeline.py` initialises, when the `GStreamerDetectionApp` subclass starts and `yolov8m.hef` is loaded, then `GET /health/ready` returns HTTP 200 with `{"status": "ready", "hailo_initialised": true}`; if GStreamer pipeline fails to start or model is absent it returns HTTP 503 with `recoverable: false`.

2. **Detection filtering in callback:** Given a GStreamer buffer is received in the Python `handoff` callback, when `callback.py` processes the `HailoROI` metadata, then only detections of class `person`, `suitcase`, `bicycle` are forwarded to `zone_counter.py`; detections outside the camera's configured `seat_zones` polygon are discarded.

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
    label = det.get_label()   # "person", "suitcase", "bicycle"
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
    detection_classes: list[str] = ["person", "suitcase", "bicycle"]
    model_hef_path: str = "/models/yolov8m.hef"
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

```python
envelope = {
    "event_id": str(uuid.uuid4()),
    "event_type": event_type,
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source": "inference",
    "payload": payload,
}
await client.post(f"{settings.event_store_url}/api/v1/events", json=envelope)
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
- 46 unit tests, 97.14% coverage (pipeline.py excluded), mypy strict 0 errors, ruff 0 violations
- TAPPAS-native: `hailo` imported lazily (try/except) so unit tests patch it via `inference.callback.hailo`
- 1 Hz rate limit is per-car via `time.monotonic()` in `ZoneCounter._last_emit` dict
- Threshold crossing guard uses `(car_id, threshold_pct) → direction` dict; no duplicate events
- `main.wire()` function extracted to enable unit testing without importing `pipeline.py`
- All ACs satisfied: AC1 (health endpoints), AC2 (class filtering), AC3 (zone mask startup validation), AC4 (hailotracker track IDs), AC5 (OCCUPANCY_UPDATE + DEFAULT_RETRY), AC6 (threshold crossing), AC7 (budget P2 suppression), AC8 (quality gates)

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
