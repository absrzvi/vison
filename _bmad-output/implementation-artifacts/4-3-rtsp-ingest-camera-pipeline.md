# Story 4.3: rtsp-ingest Camera Pipeline

Status: ready-for-dev

## Story

As a system operator,
I want the `rtsp-ingest` container to connect to 25–30 RTSP camera streams, enforce P1/P2/P3 priority frame rates, and activate P3 exterior cameras only during station windows,
so that the Hailo-8 TOPS budget is managed correctly and downstream inference always receives frames at the right priority.

## Acceptance Criteria

1. **Camera config load + health gate:** Given `cameras.json` at repo root defines 25–30 cameras with fields `{ rtsp_url, camera_id, coach_id, zone, priority }`, when `rtsp-ingest` starts, it loads `cameras.json`, initialises a `hailo-apps` `multisource` GStreamer pipeline for all entries, and connects to each stream; `GET /health/ready` returns HTTP 200 only when at least one P1 stream is active.

2. **Priority frame rates enforced:** Given the pipeline is running, when frames are being processed, P1 cameras (door/vestibule) deliver at 10 fps always; P2 cameras (interior) deliver at 5 fps always; P3 cameras (exterior/platform) deliver at 8 fps only during the station window — at all other times P3 cameras are gated off.

3. **TOPS budget throttle:** Given `scheduler.py` monitors the TOPS budget, when the budget exceeds the configured threshold (default: 90% of 26 TOPS), P2 cameras are throttled to 2 fps; a structured log is emitted at WARNING: `budget_pressure`, `tops_used_pct`, `throttled_tier="P2"`, `recoverable=True`; P1 cameras are never throttled.

4. **P3 station window gate:** Given `gate.py` receives a context state update from `vlan-pollers` with `next_station` and `speed_kmh < 20`, when the station window condition is met (speed below threshold AND door release signal received), P3 cameras are activated within 500ms; when `speed_kmh > 20` again P3 cameras are deactivated.

5. **RTSP disconnect + reconnect:** Given a P1 camera stream drops (RTSP disconnect), when the disconnect is detected by the GStreamer pipeline, a `CAMERA_DEGRADED` event is POSTed to `event-store` with `camera_id`, `coach_id`, `reason`; reconnect is attempted with `DEFAULT_RETRY` exponential backoff; on reconnect a `CAMERA_RECOVERED` event is posted.

6. **Door-release P1 override (internal):** Given `rtsp-ingest` exposes `POST /context` and receives a `door_release` push from `vlan-pollers`, when the push payload includes `{ event: "door_release", car_id, door_id }`, `gate.py` looks up the `camera_ids` associated with that `door_id` in `cameras.json`, raises their priority to P1 for 120 seconds, and emits a `STREAM_PRIORITY` internal command; this command is NOT written to `event-store` and NOT published via MQTT — it is internal to `rtsp-ingest` only (ADR-18 Trigger 1); after the 120-second window the cameras revert to their configured priority.

7. **Quality gates:** `tests/unit/test_scheduler.py` covers P2 throttle trigger and recovery conditions with synthetic TOPS readings; `tests/unit/test_gate.py` covers P3 activation/deactivation with synthetic speed + door state inputs, and door-release P1 override with a 120-second timeout; `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/rtsp_ingest/` excluding `pipeline.py` (hardware-dependent; marked `integration`).

## Tasks / Subtasks

- [ ] Scaffold `rtsp-ingest/` package structure (AC: 1, 7)
  - [ ] Create `rtsp-ingest/pyproject.toml` — package name `rtsp-ingest`, Python 3.11, dependencies: `pydantic-settings`, `structlog`, `httpx`, `fastapi`, `uvicorn`; dev deps: `pytest`, `pytest-anyio`, `mypy`, `ruff`
  - [ ] Create `rtsp-ingest/src/rtsp_ingest/__init__.py` (empty)
  - [ ] Create `rtsp-ingest/src/rtsp_ingest/models.py` — `CameraConfig(camera_id, coach_id, rtsp_url, zone, priority)`, `CameraState(camera_id, active, current_fps, override_until)` as dataclasses; `Priority` enum: `P1=1, P2=2, P3=3`
  - [ ] Create `rtsp-ingest/src/rtsp_ingest/config.py` — `pydantic-settings` `Settings`: `cameras_json_path: str = "cameras.json"`, `tops_budget_pct_threshold: float = 0.90`, `tops_total: float = 26.0`, `p1_fps: float = 10.0`, `p2_fps: float = 5.0`, `p2_throttled_fps: float = 2.0`, `p3_fps: float = 8.0`, `station_speed_threshold_kmh: float = 20.0`, `door_release_override_s: float = 120.0`, `event_store_url: str = "http://event-store:8000"`, `context_push_port: int = 8080`; NO `os.environ.get()` anywhere
  - [ ] Create `cameras.json` at repo root — schema with 3 example cameras (1 P1, 1 P2, 1 P3); fields: `rtsp_url`, `camera_id`, `coach_id`, `zone`, `priority`

- [ ] Implement `config.py` loader and `models.py` (AC: 1)
  - [ ] `load_cameras(path: str) -> list[CameraConfig]` in `models.py` — reads JSON, validates each entry has required fields, raises `ValueError` on malformed entry; no `os.environ.get()`
  - [ ] Write `tests/unit/test_models.py` — valid JSON → list of CameraConfig; missing field → ValueError; empty list → []

- [ ] Implement `scheduler.py` — TOPS budget enforcement (AC: 2, 3)
  - [ ] `Scheduler.__init__(self, cameras: list[CameraConfig], settings: Settings)` — builds dict of `camera_id → CameraState`
  - [ ] `def apply_fps(self, camera_id: str) -> float` — returns current fps for camera based on state (active/throttled/gated)
  - [ ] `def report_tops(self, tops_used: float) -> None` — if `tops_used / settings.tops_total > threshold`: set P2 cameras to throttled fps and log WARNING with `budget_pressure`, `tops_used_pct`, `throttled_tier="P2"`, `recoverable=True`; else restore P2 to normal fps; P1 fps is never changed
  - [ ] `def gate_p3(self, active: bool) -> None` — activates or deactivates all P3 cameras
  - [ ] `def override_to_p1(self, camera_ids: list[str], duration_s: float) -> None` — sets `override_until = now + duration_s` for each; `apply_fps` respects override window
  - [ ] Write RED tests in `tests/unit/test_scheduler.py` BEFORE implementation:
    - `test_p2_throttled_on_budget_pressure` — TOPS at 95% → P2 fps = 2.0
    - `test_p1_never_throttled` — TOPS at 95% → P1 fps = 10.0 always
    - `test_p2_restored_on_budget_recovery` — TOPS drops to 80% → P2 fps = 5.0
    - `test_p3_gated_off_by_default` — P3 fps = 0 when not in station window
    - `test_p3_activated_in_station_window` — gate_p3(True) → P3 fps = 8.0
    - `test_door_release_override_sets_p1_fps` — override_to_p1 → fps = 10.0 for that camera

- [ ] Implement `gate.py` — P3 station window + door-release override (AC: 4, 6)
  - [ ] `Gate.__init__(self, cameras: list[CameraConfig], scheduler: Scheduler, settings: Settings)`
  - [ ] `def on_context_update(self, payload: dict) -> None` — receives context delta from `vlan-pollers`; reads `speed_kmh` and `next_station`; if `speed_kmh < threshold AND next_station` is set → call `scheduler.gate_p3(True)` else `scheduler.gate_p3(False)`
  - [ ] `def on_door_release(self, car_id: str, door_id: str) -> None` — look up cameras matching `door_id` in `cameras` list; call `scheduler.override_to_p1(camera_ids, settings.door_release_override_s)`; emit `STREAM_PRIORITY` internal log event — do NOT POST to event-store, do NOT publish MQTT
  - [ ] Write RED tests in `tests/unit/test_gate.py` BEFORE implementation:
    - `test_p3_activated_when_speed_low_and_station_set` — speed=15, next_station="Wien Hbf" → gate_p3(True)
    - `test_p3_deactivated_when_speed_high` — speed=80 → gate_p3(False)
    - `test_p3_not_activated_when_speed_low_but_no_station` — speed=10, next_station=None → gate_p3(False)
    - `test_door_release_overrides_camera_to_p1` — door_release payload → override_to_p1 called with correct camera_ids, duration=120
    - `test_door_release_stream_priority_not_posted_to_event_store` — mock httpx client; on_door_release → no HTTP call made
    - `test_p3_activation_within_500ms` — measure time from on_context_update call to gate_p3 call < 0.5s

- [ ] Implement `health.py` — readiness endpoint (AC: 1)
  - [ ] `GET /health/ready` — FastAPI route; returns HTTP 200 if `scheduler.active_p1_count() >= 1` else HTTP 503
  - [ ] `GET /health/live` — always returns HTTP 200 (liveness)
  - [ ] `POST /context` — FastAPI route accepting context delta JSON from `vlan-pollers`; calls `gate.on_context_update(payload)` and `gate.on_door_release(...)` for `door_release` events
  - [ ] Write `tests/unit/test_health.py`:
    - `test_ready_returns_200_when_p1_active`
    - `test_ready_returns_503_when_no_p1_active`
    - `test_context_post_dispatches_to_gate`

- [ ] Implement `pipeline.py` stub (AC: 1, 5) — hardware-dependent; unit-testable logic only
  - [ ] `Pipeline.__init__(self, cameras: list[CameraConfig], scheduler: Scheduler, event_store_url: str)` — stores config; does NOT start GStreamer (real pipeline is integration-only)
  - [ ] `async def on_stream_degraded(self, camera_id: str, reason: str) -> None` — POST `CAMERA_DEGRADED` event to `event-store`; log WARNING with `camera_id`, `reason`, `recoverable=True`; call `DEFAULT_RETRY` on reconnect attempt
  - [ ] `async def on_stream_recovered(self, camera_id: str) -> None` — POST `CAMERA_RECOVERED` event to `event-store`
  - [ ] Mark entire module `# integration` in docstring — skip in unit coverage
  - [ ] Write `tests/unit/test_pipeline_events.py` (mock httpx only — no GStreamer):
    - `test_degraded_posts_camera_degraded_event`
    - `test_recovered_posts_camera_recovered_event`
    - `test_no_env_get_in_pipeline` — AST rule check (Rule 8)

- [ ] Implement `main.py` — entry point (AC: 1, 6)
  - [ ] Load `Settings()` via pydantic-settings; load cameras from `cameras.json`
  - [ ] Instantiate `Scheduler`, `Gate`, `Pipeline` with injected deps
  - [ ] Start FastAPI app with `/health/ready`, `/health/live`, `/POST /context` routes from `health.py`
  - [ ] No `os.environ.get()` — all config through `Settings`

- [ ] Write security tests (AC: 7)
  - [ ] `test_no_env_get_in_scheduler` — AST walk of `scheduler.py` (Rule 8)
  - [ ] `test_no_env_get_in_gate` — AST walk of `gate.py` (Rule 8)
  - [ ] `test_no_env_get_in_config` — AST walk of `config.py` (Rule 8)
  - [ ] `test_context_post_malformed_payload_returns_422` — FastAPI validation
  - [ ] `test_stream_priority_not_in_event_store` — door_release flow; mock event-store; assert no POST with `STREAM_PRIORITY`

- [ ] Update `docker-compose.dev.yml` — synthetic camera sources (AC: 1)
  - [ ] Add `rtsp-ingest` service: build from `./rtsp-ingest`, ports `8080:8080`, depends on `vlan-pollers`
  - [ ] Add `mock-rtsp` service (or note that a synthetic RTSP source can be added later — hardware pipeline is integration-only for PoC)
  - [ ] Set env: `CAMERAS_JSON_PATH=/app/cameras.json`, `EVENT_STORE_URL=http://event-store:8000`

- [ ] Run quality gates (AC: 7)
  - [ ] `mypy --strict src/rtsp_ingest/` — all modules pass
  - [ ] `pytest --strict-markers -q` from `rtsp-ingest/` — ≥90% coverage excluding `pipeline.py`
  - [ ] `ruff check src/ tests/` — zero violations (100-char limit, B017, F841, E501)

## Security Tests

**OEBB-specific:**
- [ ] `test_no_env_get_in_scheduler` — `scheduler.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_no_env_get_in_gate` — `gate.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_no_env_get_in_config` — `config.py` config loading must not call `os.environ.get()` directly in business logic (Rule 8)
- [ ] `test_no_env_get_in_pipeline` — `pipeline.py` must not call `os.environ.get()` (Rule 8)
- [ ] `test_stream_priority_not_posted_to_event_store` — door_release flow must emit zero HTTP POSTs to event-store with `STREAM_PRIORITY` type (ADR-18)
- [ ] `test_stream_priority_not_logged_as_event` — `STREAM_PRIORITY` must not appear in any event-store POST body
- [ ] `test_context_post_malformed_payload_returns_422` — `POST /context` with invalid JSON returns 422 with no internal detail
- [ ] No raw RTSP credentials appear in structured log output (rtsp_url redacted in logs)

## Dev Notes

### Critical Architecture Rules (Must Not Break)

1. **Rule 8 — No `os.environ.get()`** anywhere in business logic. All config comes from `pydantic-settings` `Settings` class injected via constructor. Enforced by AST security tests (same pattern as E4-S1, E4-S2).

2. **ADR-18 Trigger 1 — `STREAM_PRIORITY` is internal only.** When `gate.py` handles a `door_release` event and promotes cameras to P1, the resulting `STREAM_PRIORITY` command MUST NOT be:
   - POSTed to `event-store`
   - Published via MQTT
   - Written anywhere outside `rtsp-ingest` process memory
   This is a hard architecture boundary. The security test `test_stream_priority_not_posted_to_event_store` enforces it.

3. **P1 cameras are never throttled.** `scheduler.report_tops()` may only reduce P2 fps. P1 fps is always `settings.p1_fps`. Enforced by `test_p1_never_throttled`.

4. **`pipeline.py` is hardware-dependent — skip in unit coverage.** All GStreamer/HailoRT code lives in `pipeline.py`. Unit tests only cover `on_stream_degraded` / `on_stream_recovered` with mocked httpx. Mark integration tests with `@pytest.mark.integration` and exclude from standard `pytest` run.

5. **Dependency injection everywhere.** `Pipeline`, `Scheduler`, `Gate` all receive dependencies via constructor — no internal instantiation of adapters or HTTP clients. Same pattern as `vlan-pollers` E4-S2.

6. **`DEFAULT_RETRY` from `oebb_shared.http.retry`** — apply on `on_stream_degraded` reconnect helper only (not on the run loop itself; the loop must survive retry exhaustion).

7. **`asyncio_mode = "auto"` in `pyproject.toml`** — no `@pytest.mark.asyncio` needed on any test. Use `@pytest.mark.anyio` for async tests (same as vlan-pollers). Blind exception `pytest.raises(Exception)` is forbidden (ruff B017) — always use specific types.

### Key Design Decisions

**P3 gate timing (AC 4):** `gate.py` must activate P3 within 500ms of receiving the context update. This is a synchronous call chain — `on_context_update → scheduler.gate_p3(True)`. No async sleep between. The `test_p3_activation_within_500ms` test times this with `time.perf_counter()`.

**Door-release lookup:** `cameras.json` maps `door_id` to cameras via the `zone` field or a `door_ids` list. The story epics show `gate.py` "looks up the `camera_ids` associated with that `door_id` in `cameras.json`". Implement by filtering `cameras` list for entries whose `zone` includes the door or by a direct `door_id → [camera_id]` map in the JSON schema. Choose the simpler approach — a top-level `"door_camera_map": { "door-1A": ["C1_EXT_01"] }` dict in `cameras.json`.

**`cameras.json` schema:** Place at repo root (per architecture spec). Dev agent must create this file with at least 3 cameras (1 P1, 1 P2, 1 P3) and a `door_camera_map`. Schema:
```json
{
  "cameras": [
    {
      "camera_id": "C1_DOOR_01",
      "coach_id": "car-1",
      "rtsp_url": "rtsp://cam-host:554/stream/C1_DOOR_01",
      "zone": "door",
      "priority": "P1"
    }
  ],
  "door_camera_map": {
    "door-1A": ["C1_DOOR_01"]
  }
}
```

**Structured log fields (mandatory):** Every `log.warning(...)` call must include at minimum one ID field (`camera_id`, `coach_id`, or `event_id`) plus a descriptive keyword. Pattern from E4-S2: `log.warning("camera_degraded", camera_id="C3_INT", recoverable=True)`.

**RTSP credential security:** `rtsp_url` in `cameras.json` may include credentials (e.g. `rtsp://user:pass@host/stream`). Never log the full URL — log only `camera_id`. Enforce in `on_stream_degraded`.

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | pydantic-settings; TOPS thresholds, fps values, URL config |
| `models.py` | `CameraConfig`, `CameraState`, `Priority` enum; `load_cameras()` |
| `scheduler.py` | TOPS budget enforcement; per-camera fps state; P2 throttle; P3 gate; override window |
| `gate.py` | Context update dispatch; P3 station window logic; door-release P1 override; STREAM_PRIORITY (internal) |
| `health.py` | FastAPI routes: `/health/ready`, `/health/live`, `POST /context` |
| `pipeline.py` | GStreamer multisource wrapper; CAMERA_DEGRADED / CAMERA_RECOVERED event posting; reconnect retry |
| `main.py` | Entry point; wires all components; starts uvicorn |

### Learnings from E4-S2 (vlan-pollers)

- **AST security tests** are written exactly as in `test_apc_poller.py` — `ast.walk(tree)` checking for `os.environ.get()` attribute calls. Copy pattern verbatim.
- **`frozenset` / `tuple` for injected collections** — immutable to prevent accidental mutation during polling. Apply to `car_ids` lists → `tuple`; to `camera_id` sets → `frozenset`.
- **`dataclasses.asdict()`** for full equality comparison of state objects — use in `gate.py` if comparing context payloads.
- **Ruff B017** — never `pytest.raises(Exception)` — always use specific exception type.
- **Ruff F841** — don't bind `as mock_log` in `with patch(...)` unless you assert on `mock_log`.
- **`DEFAULT_RETRY`** applied to single fetch helpers, never to the run loop.
- **`httpx.AsyncClient` at instance level** — created in `__init__`, closed in `aclose()`. Module-level clients caused issues in tests.
- **`anyio` for async tests** — `@pytest.mark.anyio` + `asyncio_mode = "auto"` in pyproject.toml.
- **`respx.mock`** for httpx transport-level mocking — use for event-store POST tests.

### Test Strategy

- `pipeline.py` is excluded from unit coverage — mark with `# pragma: no cover` on GStreamer-dependent lines, or use `--ignore=src/rtsp_ingest/pipeline.py` in coverage config.
- All tests in `tests/unit/` — no integration tests run in CI.
- Use `AsyncMock` for `scheduler` in gate tests, `scheduler` in health tests.
- Use `respx.mock` + `httpx` for event-store POST assertions in pipeline event tests.

### Directory Structure (Final)

```
rtsp-ingest/
├── Dockerfile                          # FROM hailo-software-suite:4.23
├── pyproject.toml
├── .env.example
├── src/
│   └── rtsp_ingest/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       ├── pipeline.py                 # hardware-dependent; integration only
│       ├── scheduler.py
│       ├── gate.py
│       └── health.py
└── tests/
    ├── unit/
    │   ├── test_models.py
    │   ├── test_scheduler.py
    │   ├── test_gate.py
    │   ├── test_health.py
    │   └── test_pipeline_events.py
    └── integration/
        └── test_rtsp_connect.py        # real RTSP; dev env only
cameras.json                            # repo root; 3 example cameras + door_camera_map
```

### References

- Epic 4 Story 3 spec: `_bmad-output/planning-artifacts/epics.md` — E4-S3
- Architecture ADR-18 (Trigger 1): `_bmad-output/planning-artifacts/architecture.md` — Operational Telemetry Fusion Rules
- Architecture container directory layout: `_bmad-output/planning-artifacts/architecture.md` — Project Structure section
- Previous story patterns (E4-S2): `_bmad-output/implementation-artifacts/4-2-vlan-pollers-apc-pis-reservation.md`
- Security Rule 8: CLAUDE.md + all subpackage CLAUDE.md files
- `DEFAULT_RETRY`: `shared/src/oebb_shared/http/retry.py`
- `oebb_shared.adapters.apc`: `shared/src/oebb_shared/adapters/apc/`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6 (story creation) / claude-opus-4-7 (implementation)

### Debug Log References

### Completion Notes List

### File List

### Change Log
