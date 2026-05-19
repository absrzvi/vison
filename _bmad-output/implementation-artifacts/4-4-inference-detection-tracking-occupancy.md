# Story 4.4: inference Detection, Tracking & Occupancy Events

Status: ready-for-dev

## Story

As a system operator,
I want the `inference` container to run YOLOv8m on Hailo-8 frames, track persons across frames with BYTETracker, count people per zone, and emit `OCCUPANCY_UPDATE` and `OCCUPANCY_THRESHOLD_CROSSED` events,
so that real-time per-coach headcounts are available to the Control Centre Dashboard, Conductor App, and PIS.

## Acceptance Criteria

1. **Hailo device init + health gate:** Given `hailo_device.py` initialises, when the Hailo-8 device is present and `yolov8m.hef` is loaded, then `GET /health/ready` returns HTTP 200 with `{"status": "ready", "hailo_initialised": true}`; if the device is absent or the model fails to load it returns HTTP 503 with `recoverable: false`.

2. **Detection filtering + zone masking:** Given a frame from `rtsp-ingest` is received, when `detector.py` processes it via the hailo-apps detection callback, then detections are filtered to classes: `person`, `suitcase`, `bicycle`; zone masking is applied so only detections within the camera's configured zone are passed to `tracker.py`.

3. **Static zone masks loaded at startup:** Given `detector.py` loads zone masks for a coach, when `cameras.json` is parsed at startup, then each camera entry includes a `seat_zones` array of static polygon masks defining seated vs. standing areas; these masks are fixed for the coach geometry and NOT updated per frame — `zone_counter.py` uses them to classify persons as seated or standing (ADR-16); no dynamic zone calibration occurs at runtime; if zone configs are missing for any configured coach the container refuses to start (logged at CRITICAL).

4. **BYTETracker + 1 Hz zone count:** Given `tracker.py` receives detections across consecutive frames, when BYTETracker associates detections to track IDs, then `zone_counter.py` maintains a per-zone person count using tracking IDs; count updates are emitted at most once per second per coach (1 Hz rate limit enforced in `zone_counter.py`).

5. **OCCUPANCY_UPDATE event:** Given `zone_counter.py` produces a count update for a coach, when the count update is processed, then an `OCCUPANCY_UPDATE` event is POSTed to `event-store` via `oebb_shared.http.retry.DEFAULT_RETRY` with payload: `car_id`, `zone`, `occupancy_count`, `occupancy_pct`, `capacity`, `confidence`, `service_tier` (schema: `event-payload-schemas.md`).

6. **OCCUPANCY_THRESHOLD_CROSSED event:** Given `occupancy_pct` crosses a configured threshold (default: 0.80) in the rising direction, when the threshold crossing is detected, then an `OCCUPANCY_THRESHOLD_CROSSED` event is POSTed with `direction: "rising"` and the threshold value; a subsequent fall below the threshold emits `direction: "falling"`; no duplicate events for the same threshold/direction until the opposite crossing occurs.

7. **TOPS budget coordination:** Given `budget.py` detects TOPS pressure from the scheduler, when P2 throttle is active (coordinated via shared context state from `rtsp-ingest`), then `inference` reduces P2 frame processing rate accordingly; the reduction is coordinated via context state, not by re-routing frames.

8. **Quality gates:** `tests/unit/test_budget.py` covers throttle trigger and P2 suppression logic; `tests/unit/test_zone_counter.py` covers zone boundary logic, 1 Hz rate limit, and threshold crossing (rising + falling, no-duplicate); `tests/unit/test_detector.py` covers class filtering and zone mask application with synthetic bounding boxes; `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/inference/` excluding `hailo_device.py` and `pipeline.py` (hardware-dependent, marked `integration`); `ruff check src/ tests/` zero violations.

## Tasks / Subtasks

- [ ] Scaffold `inference/` package structure (AC: 1, 8)
  - [ ] Create `inference/pyproject.toml` — package name `inference`, Python 3.11, dependencies: `pydantic-settings`, `structlog`, `httpx`, `fastapi`, `uvicorn`, `oebb-shared`; dev deps: `pytest`, `pytest-asyncio`, `pytest-cov`, `anyio`, `mypy`, `ruff`, `respx`
  - [ ] Create `inference/src/inference/__init__.py` (empty)
  - [ ] Create `inference/src/inference/config.py` — pydantic-settings `Settings` with all knobs (see Dev Notes); NO `os.environ.get()` anywhere
  - [ ] Create `inference/src/inference/models.py` — `ZoneMask`, `Detection`, `TrackedPerson`, `OccupancyState` dataclasses; `DetectionClass` StrEnum: `PERSON`, `SUITCASE`, `BICYCLE`
  - [ ] Add `seat_zones` field to `cameras.json` at repo root for the 3 example cameras
  - [ ] Create `inference/src/inference/hailo_device.py` — hardware stub; module docstring marks integration-only; excluded from coverage

- [ ] Implement `detector.py` — zone masking + class filtering (AC: 2, 3)
  - [ ] `Detector.__init__(self, cameras: list[CameraConfig], zone_masks: dict[str, list[ZoneMask]], settings: Settings)` — injected deps; assert at init that zone configs exist for all coaches; raise `RuntimeError` (CRITICAL log) if any coach missing
  - [ ] `def filter_detections(self, camera_id: str, raw_detections: list[dict]) -> list[Detection]` — filter to PERSON/SUITCASE/BICYCLE; apply zone polygon mask; return only in-zone detections
  - [ ] Write RED tests in `tests/unit/test_detector.py` BEFORE implementation — class filtering, zone mask inclusion/exclusion with synthetic bbox coordinates, missing zone config raises RuntimeError

- [ ] Implement `tracker.py` — BYTETracker wrapper (AC: 4)
  - [ ] `Tracker.__init__(self, settings: Settings)` — initialise BYTETracker with configured fps/thresholds
  - [ ] `def update(self, detections: list[Detection], frame_id: int) -> list[TrackedPerson]` — BYTETracker update; return tracked persons with stable `track_id`
  - [ ] Mark any GStreamer/HailoRT-dependent lines as `# pragma: no cover`
  - [ ] Write unit tests with synthetic detection sequences (no hardware required)

- [ ] Implement `zone_counter.py` — per-zone count + threshold logic (AC: 4, 5, 6)
  - [ ] `ZoneCounter.__init__(self, cameras, settings, event_store_client)` — injected deps; per-car `OccupancyState` dict; per-car `last_emit_time`
  - [ ] `async def update(self, car_id: str, tracked_persons: list[TrackedPerson]) -> None` — update zone counts; enforce 1 Hz rate limit; POST `OCCUPANCY_UPDATE` if rate allows
  - [ ] `def _check_threshold(self, car_id: str, prev_pct: float, new_pct: float) -> None` — detect rising/falling threshold crossing; POST `OCCUPANCY_THRESHOLD_CROSSED`; guard against duplicate events
  - [ ] Write RED tests in `tests/unit/test_zone_counter.py` BEFORE implementation — all named tests (see Security Tests section), plus rate-limit, threshold no-duplicate guards

- [ ] Implement `budget.py` — TOPS coordination (AC: 7)
  - [ ] `Budget.__init__(self, settings: Settings)` — P2 suppression state
  - [ ] `def on_context_update(self, payload: dict) -> None` — read `p2_throttled` from context push; update internal state
  - [ ] `def should_process(self, camera_id: str, priority: str) -> bool` — returns False for P2 cameras when throttled; always True for P1
  - [ ] Write RED tests in `tests/unit/test_budget.py` BEFORE implementation — throttle trigger/recovery, P1 always passes

- [ ] Implement `health.py` — readiness endpoint (AC: 1)
  - [ ] `GET /health/ready` — HTTP 200 `{"status": "ready", "hailo_initialised": true}` when device ready; HTTP 503 `{"status": "not_ready", "recoverable": false}` otherwise
  - [ ] `GET /health/live` — always HTTP 200
  - [ ] `POST /context` — dispatches to `budget.on_context_update`
  - [ ] Write `tests/unit/test_health.py` — 5 tests: ready/not-ready/live/context-dispatch/malformed-422

- [ ] Write security tests (AC: 8)
  - [ ] `test_no_env_get_in_detector` — AST walk (Rule 8)
  - [ ] `test_no_env_get_in_zone_counter` — AST walk (Rule 8)
  - [ ] `test_no_env_get_in_budget` — AST walk (Rule 8)
  - [ ] `test_no_env_get_in_config` — AST walk (Rule 8)
  - [ ] `test_occupancy_update_payload_schema_valid` — posted payload matches `event-payload-schemas.md` required fields

- [ ] Implement `main.py` — entry point (AC: 1)
  - [ ] Loads Settings via pydantic-settings; loads cameras.json; loads zone configs
  - [ ] Instantiates HailoDevice (stub for PoC), Detector, Tracker, ZoneCounter, Budget with injected deps
  - [ ] FastAPI app via `health.build_app()`; lifespan wires startup/shutdown
  - [ ] Bind to `127.0.0.1` (loopback — same decision as rtsp-ingest)
  - [ ] No `os.environ.get()` — all config via Settings

- [ ] Run quality gates (AC: 8)
  - [ ] `mypy --strict src/inference/` — 0 errors
  - [ ] `pytest --strict-markers -q` — ≥90% coverage excluding `hailo_device.py` and `pipeline.py`
  - [ ] `ruff check src/ tests/` — zero violations

## Security Tests

**OEBB-specific:**
- [ ] `test_no_env_get_in_detector` — `detector.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_no_env_get_in_zone_counter` — `zone_counter.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_no_env_get_in_budget` — `budget.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_no_env_get_in_config` — `config.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_occupancy_update_payload_schema_valid` — POSTed `OCCUPANCY_UPDATE` payload includes `car_id`, `zone`, `occupancy_count`, `occupancy_pct`, `capacity`, `confidence`, `service_tier`
- [ ] `test_hailo_device_not_imported_in_zone_counter` — AST check: `zone_counter.py` does not import `hailo_device` (no hardware coupling in business logic)
- [ ] No raw RTSP URL or camera credentials appear in any structured log output

## Dev Notes

### Critical Architecture Rules (Must Not Break)

1. **Rule 8 — No `os.environ.get()`** anywhere in business logic. All config from pydantic-settings `Settings` injected via constructor. Enforced by AST security tests (same pattern as E4-S1/S2/S3).

2. **ADR-15 — Camera is primary, APC is calibration only.** `inference` is the authoritative source for occupancy counts. APC data (from `vlan-pollers`) is a calibration reference only — it does NOT influence the live `OccupancyState`. When APC delta vs camera count exceeds threshold, `fusion` emits `CALIBRATION_DRIFT` (not `inference`). Do not fuse APC counts into `zone_counter.py`.

3. **ADR-16 — Static zone masks, never dynamic.** `seat_zones` polygon masks in `cameras.json` are loaded once at startup. They are NOT updated per-frame. `zone_counter.py` uses them to classify persons as seated vs standing. Missing zone config for any configured coach → container MUST refuse to start with a CRITICAL-level log. Do not silently default to empty masks.

4. **Hailo-8 device is a singleton.** `hailo_device.py` owns the device exclusively. No other module may obtain a HailoRT device handle. `inference` is the only container that accesses the Hailo-8 hardware.

5. **`hailo_device.py` is integration-only.** All GStreamer/HailoRT code lives there. Exclude from unit coverage via `pyproject.toml` omit. Do NOT put hardware calls in `detector.py`, `tracker.py`, or `zone_counter.py` — those must be fully unit-testable with synthetic inputs.

6. **Dependency injection everywhere.** `Detector`, `Tracker`, `ZoneCounter`, `Budget` all receive dependencies via constructor. No module-level singletons. Same pattern as `vlan-pollers` E4-S2 and `rtsp-ingest` E4-S3.

7. **`DEFAULT_RETRY` from `oebb_shared.http.retry`** — import and apply on the event-store POST helper in `zone_counter.py` only (not on the frame processing loop).

8. **1 Hz rate limit is per-car, not global.** Each `car_id` has its own `last_emit_time`. A coach with rapid zone changes should not suppress other coaches from emitting.

9. **Threshold crossing guard.** `_check_threshold` must track last direction per threshold per car. Emitting `rising` twice without an intervening `falling` is a bug. Use a `dict[str, str]` keyed by `(car_id, threshold_pct)` → last emitted direction.

10. **`datetime.now(timezone.utc)` for all event timestamps** — never `datetime.utcnow()` (deprecated). Event envelopes follow the same schema as E4-S3 pipeline.py.

11. **`asyncio_mode = "auto"` in pyproject.toml** — no `@pytest.mark.asyncio` needed. Use `@pytest.mark.anyio` for async tests. `pytest.raises(Exception)` is forbidden (ruff B017) — always use specific exception types.

12. **`respx.mock`** for httpx transport-level mocking in event-store POST tests. Same pattern as E4-S3 `test_pipeline_events.py`.

### Settings Fields Required

```python
class Settings(BaseSettings):
    cameras_json_path: str = "cameras.json"
    zone_config_dir: str = "config/zones"         # path to {coach_type}.json zone files
    event_store_url: str = "http://event-store:8000"
    context_push_port: int = 8081                 # avoid collision with rtsp-ingest:8080
    occupancy_threshold_pct: float = 0.80         # rising/falling threshold
    occupancy_capacity_default: int = 200         # per-car default when not in cameras.json
    tops_total: float = 26.0
    tops_budget_pct_threshold: float = 0.90
    detection_classes: list[str] = ["person", "suitcase", "bicycle"]
    tracker_fps: float = 25.0
    tracker_track_thresh: float = 0.5
    tracker_match_thresh: float = 0.8
    model_hef_path: str = "/models/yolov8m.hef"
```

### cameras.json Extension

Add `seat_zones` and `capacity` to each camera entry in `cameras.json` at repo root:

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

Polygon coordinates are pixel-space `[x, y]` pairs for a 640×480 frame. The `seat_zones` array may be empty `[]` for exterior/platform cameras where seated classification is irrelevant.

### Event Envelope Pattern (from E4-S3 pipeline.py)

All events must be wrapped in the standard envelope before POSTing:

```python
envelope = {
    "event_id": str(uuid.uuid4()),
    "event_type": event_type,           # e.g. "OCCUPANCY_UPDATE"
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source": "inference",
    "payload": payload,                 # dict matching event-payload-schemas.md
}
await client.post(f"{settings.event_store_url}/api/v1/events", json=envelope)
```

### OCCUPANCY_UPDATE Payload Schema

```json
{
  "car_id": "car-1",
  "zone": null,
  "occupancy_count": 142,
  "occupancy_pct": 0.71,
  "capacity": 200,
  "confidence": 0.94,
  "service_tier": "standard"
}
```

`zone` is `null` for whole-car counts. `service_tier` comes from `cameras.json` or defaults to `"standard"`.

### OCCUPANCY_THRESHOLD_CROSSED Payload Schema

```json
{
  "car_id": "car-1",
  "zone": null,
  "threshold_pct": 0.80,
  "direction": "rising",
  "occupancy_pct": 0.82,
  "occupancy_count": 164,
  "capacity": 200,
  "service_tier": "standard"
}
```

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | pydantic-settings; all runtime knobs |
| `models.py` | `ZoneMask`, `Detection`, `TrackedPerson`, `OccupancyState`, `DetectionClass` StrEnum |
| `hailo_device.py` | HailoRT device init + model load; integration-only; excluded from coverage |
| `detector.py` | Class filter (PERSON/SUITCASE/BICYCLE); polygon zone masking; startup zone config assertion |
| `tracker.py` | BYTETracker wrapper; track ID assignment across frames |
| `zone_counter.py` | Per-zone count; 1 Hz rate limit per car; threshold crossing; POST OCCUPANCY_UPDATE / THRESHOLD_CROSSED |
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
│       ├── hailo_device.py       # integration-only; excluded from coverage
│       ├── detector.py
│       ├── tracker.py
│       ├── zone_counter.py
│       ├── budget.py
│       └── health.py
└── tests/
    ├── unit/
    │   ├── test_detector.py
    │   ├── test_zone_counter.py
    │   ├── test_budget.py
    │   ├── test_health.py
    │   └── test_security.py
    └── integration/
        └── test_hailo_device.py  # real Hailo-8; dev env only; @pytest.mark.integration
```

### Learnings from E4-S3 (rtsp-ingest)

- **Transition guard pattern** — don't call state-change callbacks on every tick; track `_was_active` / `_last_direction` and fire only on state transitions. Apply this to threshold crossing (`_check_threshold`) and budget throttle state.
- **AST security tests** — copy `_has_env_get()` helper verbatim from `test_security.py`. Don't reinvent.
- **`httpx.AsyncClient` at instance level** — created in `__init__`, closed in `aclose()`. Module-level clients cause ResourceWarnings in tests.
- **`respx.mock`** for httpx transport-level mocking — wrap the full `with respx.mock:` block around the async call, assert `route.called` and parse `route.calls[0].request.content`.
- **`anyio` for async tests** — `@pytest.mark.anyio` + `asyncio_mode = "auto"`. Never `@pytest.mark.asyncio`.
- **Loopback bind** — `host="127.0.0.1"` in uvicorn (established in E4-S3 code review; same reasoning applies here).
- **Duplicate entry guard** — `load_cameras` now raises ValueError on duplicate `camera_id`. Don't add duplicate entries in test fixtures.
- **`report_tops` hysteresis** — only log/set on state transition, not every call. Apply same pattern in `Budget.on_context_update`.
- **`test_context_post_malformed_payload_returns_422`** — in security tests, replace `assert True` with real TestClient assertion; FastAPI `dict[str, Any]` body param returns 422 on bad JSON.

### Learnings from E4-S2 (vlan-pollers)

- **`frozenset`/`tuple` for injected collections** — immutable to prevent accidental mutation. Apply to `detection_classes`.
- **Ruff B017** — never `pytest.raises(Exception)` — always use specific type (e.g. `pytest.raises(ValueError)`).
- **Ruff F841** — don't bind `as mock_x` in `with patch(...)` unless asserting on it.
- **`DEFAULT_RETRY` on event POST only** — not on the frame processing loop. Loop must survive retry exhaustion.
- **`dataclasses.asdict()`** for full equality comparison of state objects in tests.

### Test Strategy

- `hailo_device.py` excluded from unit coverage (`omit = ["*/hailo_device.py"]` in pyproject.toml).
- `main.py` NOT excluded (lesson from E4-S3 code review — only hardware-dependent files excluded).
- All tests in `tests/unit/` — integration tests gated by `@pytest.mark.integration`.
- Use `AsyncMock` for `zone_counter`'s event_store_client in budget tests.
- Use `respx.mock` + `httpx` for event-store POST assertions in zone_counter tests.
- Synthetic bounding boxes for zone mask tests — use simple axis-aligned rectangles, avoid floating-point edge cases.

### References

- Epic story: `_bmad-output/planning-artifacts/epics.md` — E4-S4
- Event schemas: `_bmad-output/planning-artifacts/event-payload-schemas.md` — OCCUPANCY_UPDATE, OCCUPANCY_THRESHOLD_CROSSED
- Architecture — Hailo-8, inference container: `_bmad-output/planning-artifacts/architecture.md` — §Container Scaffold, §Hailo-Apps Dependency Decision
- ADR-15 (camera primary): `_bmad-output/planning-artifacts/architecture.md`
- ADR-16 (static zone masks): `_bmad-output/planning-artifacts/architecture.md`
- ADR-18 (fusion rules): `_bmad-output/planning-artifacts/architecture.md`
- Previous story (E4-S3): `_bmad-output/implementation-artifacts/4-3-rtsp-ingest-camera-pipeline.md`
- Shared retry: `shared/src/oebb_shared/http/retry.py`
- cameras.json: repo root

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
