# Story 4.5: `inference` Safety & Accessibility Detection

Status: review

## Story

As a system operator,
I want the `inference` container to detect door obstructions, wheelchair/pushchair presence, ramp deployment signals, slip/fall events, and vestibule congestion,
so that safety-critical alerts reach conductors and the Control Centre within the station dwell window.

## Acceptance Criteria

1. **Door obstruction candidate:** Given `detector.py` (i.e. `callback.py`) detects a `person` or `suitcase` bounding box overlapping a configured door zone AND the overlap persists for ≥2 consecutive frames, then a `DOOR_OBSTRUCTION` candidate is emitted to `fusion` via HTTP POST (NOT to `event-store` directly — fusion is authoritative per FR7); payload: `car_id`, `door_id`, `obstruction_type` (`person|object`), `track_id`, `camera_id`, `confidence` (None if unavailable), `door_state: "unknown"` (ZFR cross-reference happens in fusion).

2. **Accessibility detected:** Given `callback.py` detects a `bicycle` class detection (COCO proxy for wheelchair/pushchair) in a vestibule or door zone with confidence ≥ configured threshold (default: 0.80), then an `ACCESSIBILITY_DETECTED` event is POSTed directly to `event-store` (no fusion needed) via `oebb_shared.http.retry.DEFAULT_RETRY` with payload matching `AccessibilityDetectedPayload`: `car_id`, `zone`, `track_id`, `assistance_type` (`["wheelchair"]` for bicycle class), `camera_id`, `confidence` (None if unavailable), `near_door_id` (from `cameras.json` `door_camera_map`).

3. **Ramp deployed (context-driven):** Given `vlan-pollers` context state includes a `ramp_deployed: true` signal arriving via `POST /context`, then `inference` POSTs a `RAMP_DEPLOYED` event to `event-store` with `car_id`, `door_id`, `triggered_by_track_id` (last known accessibility track, or `"unknown"` if none), `deployed_by: "auto"`, `station_id` (from context push or `"unknown"`).

4. **Slip/fall detection:** Given a person's tracked bounding box height/aspect ratio across consecutive frames indicates a fall (height collapse > configured threshold AND centroid velocity > threshold), when detected in `zone_counter.py` using hailotracker output, then an `ALERT_RAISED` event with `alert_type: "slip_fall"` is emitted to `fusion` (NOT event-store directly) for enrichment and suppression check; pose keypoints are deferred to post-PoC.

5. **Vestibule congestion:** Given person count in vestibule zone exceeds configured limit, when detected by `zone_counter.py`, then a `VESTIBULE_CONGESTION` event is POSTed directly to `event-store` with `car_id`, `vestibule_id` (from zone name), `congestion_score` (person_count / threshold as float 0..1 capped at 1.0), `person_count`, `dwell_time_avg_s` (0.0 for PoC — requires dwell tracking deferred), `threshold_score`.

6. **Detection class expansion:** `callback.py` now forwards `person`, `suitcase`, and `bicycle` detections (per D1 verdict from 4-4: suitcase and bicycle were explicitly deferred to this story). Update `Settings.detection_classes` default to `["person", "suitcase", "bicycle"]`.

7. **Quality gates:** `tests/unit/test_slip_fall.py` covers bounding box height/velocity heuristic thresholds with synthetic tracking sequences; `tests/unit/test_accessibility.py` covers bicycle detection → ACCESSIBILITY_DETECTED payload; `tests/unit/test_security.py` AST checks extended to any new modules; `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥90% coverage of `src/inference/` excluding `pipeline.py`; `ruff check src/ tests/` zero violations.

## Tasks / Subtasks

- [x] Expand detection classes in config and callback (AC: 6)
  - [x] Update `Settings.detection_classes` default to `["person", "suitcase", "bicycle"]`
  - [x] Update `callback.py` `_allowed_labels` to pass suitcase and bicycle detections through
  - [x] Add `accessibility_confidence_threshold: float = 0.80` to `Settings`
  - [x] Add `door_obstruction_min_frames: int = 2` to `Settings`
  - [x] Add `vestibule_congestion_threshold: int = 8` (person count) and `vestibule_congestion_score_threshold: float = 0.75` to `Settings`
  - [x] Add `slip_fall_height_collapse_threshold: float = 0.5` and `slip_fall_velocity_threshold: float = 50.0` to `Settings`
  - [x] Add `fusion_url: str = "http://fusion:8090"` to `Settings` (fusion receives door obstruction + slip_fall candidates)

- [x] Write security tests RED phase for new modules (AC: 7)
  - [x] Add `test_no_env_get_in_safety_detector` to `test_security.py` — AST walk of new module(s)

- [x] Implement door obstruction tracking in `callback.py` (AC: 1)
  - [x] Add `_door_zone_hits: dict[tuple[str, int], int]` (camera_id, track_id) → consecutive frame count
  - [x] For `suitcase` or `person` label in a door-zone camera: increment frame counter; if ≥ `door_obstruction_min_frames` emit candidate to fusion via `_post_door_obstruction_candidate()` (async, scheduled via `run_coroutine_threadsafe`)
  - [x] Clear counter when track_id disappears from frame
  - [x] `_post_door_obstruction_candidate()`: POST to `{fusion_url}/candidates/door_obstruction` with `DoorObstructionPayload` dict (door_state="open"); use `DEFAULT_RETRY`
  - [x] `near_door_id` lookup: use `cameras.json` `door_camera_map` reversed — map camera_id → door_id(s); use first match or `"unknown"` if unmapped

- [x] Implement accessibility detection in `callback.py` (AC: 2)
  - [x] For `bicycle` label with `confidence >= settings.accessibility_confidence_threshold`: emit `ACCESSIBILITY_DETECTED` directly to event-store via new async helper `_post_accessibility_event()`
  - [x] Track last accessibility `track_id` per camera in `_last_accessibility_track: dict[str, str]` for ramp deployment correlation (AC: 3)
  - [x] Payload: `AccessibilityDetectedPayload(car_id=..., zone=zone_name, track_id=str(track_id), assistance_type=["wheelchair"], camera_id=..., confidence=None, near_door_id=...)`
  - [x] Use `_build_envelope()` pattern from `zone_counter.py` — same `EventEnvelope` construction; severity `"warning"`

- [x] Implement ramp deployment handler in `health.py` (AC: 3)
  - [x] Extend `ContextPushModel` with `ramp_deployed: StrictBool = False`, `ramp_door_id: str | None = None`, `ramp_station_id: str | None = None`
  - [x] In `POST /context` handler: if `payload.ramp_deployed` is True, call `safety_handler.on_ramp_deployed(door_id, station_id)` (injected at build_app time)
  - [x] Create `inference/src/inference/safety.py` — `SafetyHandler` class with `on_ramp_deployed(door_id, station_id)` that POSTs `RAMP_DEPLOYED` event to event-store; holds `_last_track_ids: dict[str, str]` updated by callback when accessibility detected

- [x] Implement slip/fall detection in `zone_counter.py` (AC: 4)
  - [x] Add `_track_bboxes: dict[str, dict[int, tuple[float,float,float,float]]]` (car_id → track_id → last bbox) to `ZoneCounter`
  - [x] In `update()`: after updating tracks, call `_check_slip_fall(car_id, detections)` 
  - [x] `_check_slip_fall()`: for each tracked person, compare consecutive bboxes; compute height ratio `h2/h1`; if `< (1 - height_collapse_threshold)` AND centroid vertical velocity `> velocity_threshold`, emit `ALERT_RAISED` to fusion via POST to `{fusion_url}/candidates/alert_raised` with `{"alert_type": "slip_fall", "car_id": ..., "track_id": ..., "camera_id": "unknown"}`
  - [x] Write `tests/unit/test_slip_fall.py` RED phase before implementing: synthetic bbox sequences triggering and not-triggering fall detection; no Hailo-8 required

- [x] Implement vestibule congestion in `zone_counter.py` (AC: 5)
  - [x] Identify vestibule zones by zone name containing `"vestibule"` OR camera `zone == "door"` (configurable, use camera `zone` field)
  - [x] After occupancy update: if camera zone is vestibule/door, compute `congestion_score = min(person_count / threshold, 1.0)`; if `> settings.vestibule_congestion_score_threshold`, POST `VESTIBULE_CONGESTION` event to event-store
  - [x] Rate-limit: one emit per vestibule per 10 s (separate `_vestibule_last_emit: dict[str, float]` dict, not shared with 1 Hz occupancy timer)
  - [x] `vestibule_id` = `f"{car_id}-vestibule"` where zone is door or vestibule
  - [x] Add `tests/unit/test_vestibule_congestion.py` covering: threshold crossing, rate-limit, score calculation

- [x] Wire `SafetyHandler` into `main.py` (AC: 3)
  - [x] Instantiate `SafetyHandler(settings, event_store_client, journey_holder)` in `wire()`
  - [x] Pass to `build_app(readiness, budget, journey_holder, safety_handler=safety_handler)`
  - [x] Pass `safety_handler` reference to `OccupancyCallback.__init__` so callback can update `_last_accessibility_track`

- [x] Run quality gates (AC: 7)
  - [x] `mypy --strict src/inference/` — 0 errors
  - [x] `pytest --strict-markers -q` — 91.62% coverage (≥90%)
  - [x] `ruff check src/ tests/` — zero violations

## Security Tests

**OEBB-specific:**
- [x] `test_no_env_get_in_safety` — `safety.py` must not call `os.environ.get()` (Rule 8)
- [x] `test_door_obstruction_payload_schema_valid` — POSTed `DOOR_OBSTRUCTION` candidate payload matches `DoorObstructionPayload` required fields
- [x] `test_accessibility_payload_schema_valid` — POSTed `ACCESSIBILITY_DETECTED` payload matches `AccessibilityDetectedPayload` required fields
- [x] `test_ramp_deployed_payload_schema_valid` — `RAMP_DEPLOYED` event payload matches `RampDeployedPayload` required fields
- [x] `test_context_push_ramp_malformed_returns_422` — `POST /context` with `ramp_deployed: "yes"` (string not bool) returns 422 (StrictBool enforces this)
- [x] `test_fusion_candidate_not_written_to_event_store` — assert door obstruction and slip_fall candidates POST to `fusion_url`, NOT `event_store_url`

## Dev Notes

### Architecture Rules (Must Follow)

1. **Rule 8 — No `os.environ.get()`** anywhere in new modules. All config from injected `Settings`.

2. **D1 verdict from 4-4:** `person` is tracked by `hailotracker`. `suitcase` and `bicycle` do NOT need tracking (suitcase = dwell-timer/IoU approach, bicycle = single-frame confidence trigger). Do NOT pass `suitcase`/`bicycle` through hailotracker — they don't need track_id continuity. The hailotracker `TRACKER_PIPELINE(class_id=0)` stays person-only; suitcase/bicycle come through as frame-by-frame detections.

3. **Fusion vs event-store routing (CRITICAL — must not get this wrong):**
   - POST to **fusion** (`fusion_url`): `DOOR_OBSTRUCTION` candidates, `ALERT_RAISED` (slip_fall) — fusion applies ZFR cross-reference and suppression state machine
   - POST **directly to event-store**: `ACCESSIBILITY_DETECTED`, `RAMP_DEPLOYED`, `VESTIBULE_CONGESTION` — these need no cross-VLAN correlation

4. **`DoorObstructionPayload` from shared** — use canonical `oebb_shared.events.DoorObstructionPayload`. Note: `door_state` is required (`Literal["open","closing","closed"]`). When posting to fusion as a candidate, `door_state="open"` is the safest default (ZFR will provide the authoritative state). However — the fusion interface is being defined here for E4-S6. Use `door_state="unknown"` only if shared allows it; if the schema enforces the literal, use `"open"` as placeholder and note the limitation in a log.

   **Check `shared/src/oebb_shared/events/payloads.py:162-175` before writing.** The field is `Literal["open", "closing", "closed"]` — `"unknown"` is NOT valid. Use `"open"` as the inference-side default; fusion corrects via ZFR state.

5. **`AccessibilityDetectedPayload` fields:** `assistance_type` must be a non-empty list (`min_length=1`). For bicycle class: `["wheelchair"]`. `near_door_id` is required and non-empty — use `door_camera_map` reverse lookup; if unmapped, this is a config issue. Log CRITICAL and skip emitting rather than using empty string (which fails `_NonEmptyStr`).

6. **Consecutive frame tracking for door obstruction:** GStreamer fires callbacks per frame. The `_door_zone_hits` counter in `callback.py` must be keyed by `(camera_id, track_id)`. Track IDs come from hailotracker and are ints. Suitcase detections have no track_id from hailotracker — for suitcase, use bbox-IoU to maintain pseudo-track across frames (simple: if IoU > 0.5 with previous frame's suitcase bbox, count as same detection). For PoC simplicity, suitcase with no IoU match resets the counter.

7. **`DEFAULT_RETRY` pattern** — already established in `zone_counter.py`. Copy the same `@DEFAULT_RETRY` + `resp.raise_for_status()` pattern for all new event POSTs. Import from `oebb_shared.http.retry`.

8. **`_build_envelope()` — reuse from `zone_counter.py`'s pattern.** The `SafetyHandler` and any new posting in `callback.py` must construct `EventEnvelope` via the canonical Pydantic model (9 fields: `journey_id`, `vehicle_id`, `event_type`, `severity`, `source`, `schema_version`, `payload`, `timestamp`, `event_id`). Source field = `"inference"`.

9. **`asyncio.run_coroutine_threadsafe` pattern for callback** — all new async POSTs from `callback.py` (door obstruction, accessibility) must follow the established `run_coroutine_threadsafe(coro, loop_holder.loop)` + `fut.add_done_callback(_on_post_done)` pattern with M11 `try/except RuntimeError` guard.

10. **`SafetyHandler` needs `httpx.AsyncClient`** — do NOT create a new client; receive the same shared client from `main.py` wire(). One client per container (FastAPI lifespan owns it, as established in 4-4).

11. **Slip/fall: bbox coordinate space** — same pixel-space convention as 4-4. Height = `bbox[3] - bbox[1]` (y_max - y_min). Velocity = change in centroid y-position per frame (`|(cy2 - cy1)|`). No frame timestamps available — treat as consecutive frames at ~3 fps (configurable via `pipeline_fps: float = 3.0` in Settings, used only for logging/context, not physics calculation).

### Files to Create (NEW)

```
inference/src/inference/safety.py        # SafetyHandler class
inference/tests/unit/test_slip_fall.py   # BDD bounding-box heuristic tests
inference/tests/unit/test_accessibility.py  # bicycle → ACCESSIBILITY_DETECTED
```

### Files to Update (READ FIRST — current state documented below)

**`inference/src/inference/config.py`**
- Current: Settings has `detection_classes: list[str] = ["person"]`, no fusion_url, no safety thresholds
- Add: `detection_classes` default → `["person", "suitcase", "bicycle"]`; `fusion_url: str = "http://fusion:8090"`; `accessibility_confidence_threshold: float = 0.80`; `door_obstruction_min_frames: int = 2`; `vestibule_congestion_threshold: int = 8`; `vestibule_congestion_score_threshold: float = 0.75`; `slip_fall_height_collapse_threshold: float = 0.5`; `slip_fall_velocity_threshold: float = 50.0`; `pipeline_fps: float = 3.0`
- Preserve: all existing fields; `INFERENCE_` env prefix; `env_file=".env"`; `extra="ignore"`

**`inference/src/inference/callback.py`**
- Current: `_allowed_labels` = `{"person"}` only; `OccupancyCallback.__call__` dispatches person detections to `zone_counter.update()` only
- Add: `_door_zone_hits: dict[tuple[str, int], int]` instance var; suitcase bbox-IoU consecutive tracking; `_last_accessibility_track: dict[str, str]` (camera_id → track_id); `_post_door_obstruction_candidate()` async method; `_post_accessibility_event()` async method; `_is_door_zone_camera()` helper (checks camera `zone == "door"`)
- Preserve: all existing person-detection path; `_bbox_in_any_zone()` polygon logic; `_verify_bbox_space()` first-frame check; `run_coroutine_threadsafe` + M11 TOCTOU guard pattern; `_on_post_done` callback

**`inference/src/inference/zone_counter.py`**
- Current: Tracks person counts per car; emits `OCCUPANCY_UPDATE` and `OCCUPANCY_THRESHOLD_CROSSED`; locks per car, in-flight suppression, 1 Hz rate limit
- Add: `_track_bboxes` dict for slip/fall detection; `_check_slip_fall()` method; vestibule congestion check + rate limit; POST to `fusion_url` for slip_fall candidates; POST to event-store for `VESTIBULE_CONGESTION`
- Preserve: ALL existing occupancy logic (lock, in-flight, rate-limit, threshold crossing, deadband); `_build_envelope()` signature; `update_journey_id()` public method

**`inference/src/inference/health.py`**
- Current: `ContextPushModel` has `p2_throttled: StrictBool`, `journey_id: str | None`; `build_app(readiness, budget, journey_holder)`
- Add: `ramp_deployed: StrictBool = False`, `ramp_door_id: str | None = None`, `ramp_station_id: str | None = None` to `ContextPushModel`; `safety_handler: SafetyHandler | None = None` param to `build_app()`; ramp logic in `/context` handler
- Preserve: existing `p2_throttled` logic; journey_id update; readiness aggregation logic (all/some/none)

**`inference/src/inference/main.py`**
- Add: `SafetyHandler` instantiation in `wire()`; pass to `build_app()` and to `OccupancyCallback.__init__()` for accessibility track updates
- Preserve: single `wire()` call inside lifespan (M1 fix); `_in_flight` guard; JourneyHolder wiring; per-camera ReadinessHolder list

**`inference/src/inference/models.py`**
- Add (if needed): no new models required — `SafetyHandler` state lives in the class itself

**`inference/tests/unit/test_security.py`**
- Add: `test_no_env_get_in_safety` AST check for `safety.py`

### Key Patterns from 4-4 to Copy Verbatim

```python
# AST security check pattern (copy from test_security.py)
def _has_env_get(source: str) -> bool:
    ...

# run_coroutine_threadsafe + TOCTOU guard (callback.py lines 224-234)
try:
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    fut.add_done_callback(_on_post_done)
except RuntimeError as exc:
    log.warning("callback.schedule_during_shutdown", ...)

# DEFAULT_RETRY + raise_for_status (zone_counter.py lines 146+)
@DEFAULT_RETRY
async def _post_something(self, ...) -> None:
    resp = await self._client.post(url, json=...)
    resp.raise_for_status()

# EventEnvelope construction (_build_envelope in zone_counter.py lines 227-243)
envelope = EventEnvelope(
    journey_id=self._journey_holder.journey_id,
    vehicle_id=self._settings.vehicle_id,
    event_type=EventType.ACCESSIBILITY_DETECTED,
    severity="warning",
    source="inference",
    schema_version=self._settings.schema_version,
    payload=payload.model_dump(),
)
```

### Shared Payload Models Available (Already in `oebb_shared`)

```python
from oebb_shared.events import (
    AccessibilityDetectedPayload,   # car_id, zone, track_id, assistance_type, camera_id, confidence, near_door_id
    DoorObstructionPayload,          # car_id, door_id, obstruction_type, track_id, camera_id, confidence, door_state
    RampDeployedPayload,             # car_id, door_id, triggered_by_track_id, deployed_by, station_id
    VestibuleCongestionPayload,      # car_id, vestibule_id, congestion_score, person_count, dwell_time_avg_s, threshold_score
    EventType,
    EventEnvelope,
)
```

**Do NOT redefine these.** They live in `shared/src/oebb_shared/events/payloads.py`.

### `cameras.json` — Door Zone and Vestibule Identification

Current cameras.json has:
- `C1_DOOR_01` (car-1, zone="door", P1) — door zone camera; maps to `"door-1A"` in `door_camera_map`
- `C1_INT_01` (car-2, zone="interior", P2) — interior only
- `C1_EXT_01` (car-3, zone="exterior", P3) — exterior

Door camera identification: `camera["zone"] == "door"` OR camera appears in `door_camera_map` values.
Vestibule congestion: treat `zone == "door"` cameras as vestibule proxy for PoC (vestibule zone is near the door).
`vestibule_id` = `f"{car_id}-vestibule"` (simplification for PoC).

Reverse `door_camera_map` for `near_door_id` lookup:
```python
# Build at startup: camera_id → door_id
_cam_to_door: dict[str, str] = {}
for door_id, cams in door_camera_map.items():
    for cam in cams:
        _cam_to_door[cam] = door_id
```

### Slip/Fall Heuristic (No Hailo Pose — PoC)

```
for each person track_id in current frame:
    prev_bbox = _track_bboxes[car_id].get(track_id)  # previous frame
    if prev_bbox:
        h1 = prev_bbox[3] - prev_bbox[1]   # height prev
        h2 = curr_bbox[3] - curr_bbox[1]   # height curr
        cy1 = (prev_bbox[1] + prev_bbox[3]) / 2
        cy2 = (curr_bbox[1] + curr_bbox[3]) / 2
        height_ratio = h2 / h1 if h1 > 0 else 1.0
        velocity = abs(cy2 - cy1)
        if height_ratio < (1 - settings.slip_fall_height_collapse_threshold) \
           and velocity > settings.slip_fall_velocity_threshold:
            → emit ALERT_RAISED to fusion
    _track_bboxes[car_id][track_id] = curr_bbox  # update
```

### Fusion Candidate POST Interface (Defined Here for E4-S6)

The fusion container (E4-S6, next story) will implement these endpoints. **Do not implement fusion in this story** — only the inference side. POST the following JSON structures:

**Door obstruction candidate:**
```
POST {fusion_url}/candidates/door_obstruction
Body: DoorObstructionPayload.model_dump() — fusion wraps it in EventEnvelope
```

**Slip/fall candidate:**
```
POST {fusion_url}/candidates/alert_raised
Body: {"alert_type": "slip_fall", "car_id": ..., "track_id": ..., "camera_id": ...}
```

In unit tests, mock these endpoints with `respx.mock` pointing to `http://fusion:8090`.

### Testing Patterns

```python
# test_slip_fall.py — no Hailo required; pure bbox math
def test_fall_detected_on_height_collapse_and_velocity():
    bboxes_prev = (100, 100, 200, 400)  # h=300 (standing)
    bboxes_curr = (100, 350, 200, 450)  # h=100 (collapsed) + centroid moved
    # Assert: _check_slip_fall posts to fusion

def test_no_fall_on_height_collapse_alone():
    # height collapses but velocity < threshold → no emit

# test_accessibility.py — mock hailo, test bicycle dispatch
def test_bicycle_detection_emits_accessibility_event():
    # mock detection with label="bicycle", confidence > 0.80
    # assert ACCESSIBILITY_DETECTED POSTed to event-store (not fusion)

def test_bicycle_below_confidence_threshold_suppressed():
    # confidence = 0.70 → no emit
```

### Edge Cases / Gotchas

- **Bicycle has no hailotracker track_id** (hailotracker is `class_id=0` = person only). For bicycle detections, `uid_list` will be empty. Use a synthetic track_id: `f"acc-{camera_id}-{int(time.monotonic() * 1000) % 100000}"` — unique enough for PoC, clearly prefixed. Do not send `None` to `AccessibilityDetectedPayload.track_id` (it is `_NonEmptyStr`).
- **Suitcase also has no track_id.** For door obstruction, use bbox IoU to correlate consecutive suitcase frames. IoU > 0.5 = same object (increment counter); else reset.
- **`near_door_id` unmapped camera:** If `camera_id` not in `_cam_to_door`, log WARNING and skip emitting `ACCESSIBILITY_DETECTED` — do not use empty string (schema rejects it).
- **`door_state` in `DoorObstructionPayload`:** Must be one of `"open"`, `"closing"`, `"closed"`. Use `"open"` as inference-side default. Log: `"door_state defaults to open; fusion will cross-reference ZFR"`.
- **`assistance_type` empty list:** Schema requires `min_length=1`. Always pass `["wheelchair"]` for bicycle class. No other assistance types detectable in PoC.
- **`dwell_time_avg_s` in `VestibuleCongestionPayload`:** Set to `0.0` for PoC (dwell tracking not implemented). Field is `_NonNegFloat` so `0.0` is valid.

### References

- Epic story: `_bmad-output/planning-artifacts/epics.md` — E4-S5
- Event schemas: `_bmad-output/planning-artifacts/event-payload-schemas.md` — §Safety, §Accessibility, §Congestion
- Shared payloads: `shared/src/oebb_shared/events/payloads.py:116-210`
- Shared event types: `shared/src/oebb_shared/events/types.py`
- Previous story: `_bmad-output/implementation-artifacts/4-4-inference-detection-tracking-occupancy.md`
- cameras.json: repo root — door_camera_map, zone field per camera
- ADR-15: camera is primary for occupancy; APC is calibration only
- Fusion interface: E4-S6 story (TBD) — this story defines the candidate POST contract

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

N/A — implementation completed without blockers.

### Completion Notes List

- Expanded `Settings` with 8 new fields: `fusion_url`, `accessibility_confidence_threshold`, `door_obstruction_min_frames`, `vestibule_congestion_threshold`, `vestibule_congestion_score_threshold`, `slip_fall_height_collapse_threshold`, `slip_fall_velocity_threshold`, `pipeline_fps`
- `callback.py`: extended `__call__` to dispatch suitcase (IoU-based consecutive tracking) and bicycle (confidence threshold) detections; added `_handle_suitcase_door_obstruction`, `_handle_person_door_obstruction`, `_post_door_obstruction_candidate`, `_dispatch_bicycle`, `_post_accessibility_event`; `door_state` set to `"open"` (not "unknown" — schema enforces literal)
- `safety.py` (NEW): `SafetyHandler` with `on_ramp_deployed`, `update_last_track`, `_post_ramp_deployed`; `triggered_by_track_id` falls back to `"unknown"` when no accessibility track recorded
- `health.py`: extended `ContextPushModel` with `ramp_deployed`, `ramp_door_id`, `ramp_station_id`; `build_app` now accepts optional `safety_handler`; ramp event fires via `asyncio.ensure_future`
- `zone_counter.py`: added `_check_slip_fall` (height collapse + centroid velocity), `_post_slip_fall_candidate` (→ fusion), `_check_vestibule_congestion` (→ event-store, 10s rate-limit), `_post_vestibule_congestion`
- `main.py`: `_load_cameras_data` returns tuple (cameras, full json); `wire()` instantiates `SafetyHandler` and threads it through callbacks and `build_app`
- **Quality gates**: mypy 0 errors, ruff 0 violations, 119 tests pass, 91.62% coverage (≥90% threshold)

### File List

inference/src/inference/config.py
inference/src/inference/callback.py
inference/src/inference/zone_counter.py
inference/src/inference/health.py
inference/src/inference/main.py
inference/src/inference/safety.py
inference/tests/unit/test_security.py
inference/tests/unit/test_slip_fall.py
inference/tests/unit/test_accessibility.py
inference/tests/unit/test_safety.py
inference/tests/unit/test_vestibule_congestion.py
inference/tests/unit/test_door_obstruction.py

### Change Log

- 2026-05-19: Story 4-5 implemented — safety & accessibility detection: door obstruction (AC1), accessibility detected (AC2), ramp deployed (AC3), slip/fall (AC4), vestibule congestion (AC5), detection class expansion (AC6), quality gates (AC7)
