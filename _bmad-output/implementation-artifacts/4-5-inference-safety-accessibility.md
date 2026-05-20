# Story 4.5: `inference` Safety & Accessibility Detection

Status: done

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

claude-sonnet-4-6 (initial implementation)
claude-opus-4-7-1M (2026-05-20 — code-review follow-up to address R1–R19 + F1–F13)

### Debug Log References

N/A — implementation completed without blockers.

### Completion Notes List

- Expanded `Settings` with 8 new fields: `fusion_url`, `accessibility_confidence_threshold`, `door_obstruction_min_frames`, `vestibule_congestion_threshold`, `vestibule_congestion_score_threshold`, `slip_fall_height_collapse_threshold`, `slip_fall_velocity_threshold`, `pipeline_fps`
- `callback.py`: extended `__call__` to dispatch suitcase (IoU-based consecutive tracking) and bicycle (confidence threshold) detections; added `_handle_suitcase_door_obstruction`, `_handle_person_door_obstruction`, `_post_door_obstruction_candidate`, `_dispatch_bicycle`, `_post_accessibility_event`; `door_state` set to `"open"` (not "unknown" — schema enforces literal)
- `safety.py` (NEW): `SafetyHandler` with `on_ramp_deployed`, `update_last_track`, `_post_ramp_deployed`; `triggered_by_track_id` falls back to `"unknown"` when no accessibility track recorded
- `health.py`: extended `ContextPushModel` with `ramp_deployed`, `ramp_door_id`, `ramp_station_id`; `build_app` now accepts optional `safety_handler`; ramp event fires via `asyncio.ensure_future`
- `zone_counter.py`: added `_check_slip_fall` (height collapse + centroid velocity), `_post_slip_fall_candidate` (→ fusion), `_check_vestibule_congestion` (→ event-store, 10s rate-limit), `_post_vestibule_congestion`
- `main.py`: `_load_cameras_data` returns tuple (cameras, full json); `wire()` instantiates `SafetyHandler` and threads it through callbacks and `build_app`
- **Quality gates** (2026-05-19): mypy 0 errors, ruff 0 violations, 119 tests pass, 91.62% coverage (≥90% threshold)

#### 2026-05-20 review follow-up (claude-opus-4-7-1M)

- ✅ Resolved review finding [BLOCKER R1]: vestibule_id `f"{car_id}-{zone}"` kept; test updated to expect `"car-1-door"`
- ✅ Resolved review finding [Decision R2]: strict — skip emit when `confidence is None`; test inverted to assert no emit
- ✅ Resolved review finding [Decision R3]: PoC simplification — `car_id = settings.vehicle_id`; deferred coach-level resolution to E4-S6
- ✅ Resolved review finding [Decision R4]: dropped `_last_track_ids` correlation; `triggered_by_track_id="unknown"` always; fusion (E4-S6) correlates
- ✅ Resolved review finding [Decision R5]: added optional `vestibule_zone` polygon to cameras.json schema; callback tags `in_vestibule` per person; ZoneCounter uses the tagged subset
- ✅ Resolved review finding [Decision R6]: `door_state="unknown"` (AC1 authoritative); shared schema Literal already accepts it
- ✅ Resolved review finding [Decision R7]: `camera_id` threaded through `ZoneCounter.update()`; `_track_bboxes` re-keyed by `(car_id, camera_id)` for multi-camera-per-car
- ✅ Resolved review finding [Patch R8]: `add_done_callback(_on_post_done)` on ramp-deployed schedule
- ✅ Resolved review finding [Patch R9]: `loop_holder.loop` + `run_coroutine_threadsafe` pattern; threaded through `build_app()`
- ✅ Resolved review finding [Patch R10]: collapsed by R4 deletion
- ✅ Resolved review finding [Decision R12]: unique per-emit suitcase track_id `f"suitcase-{ms}"`
- ✅ Resolved review finding [Patch R13]: removed unused `bbox` parameter from `_handle_person_door_obstruction`
- ✅ Added R19: TestClient happy-path test for `POST /context ramp_deployed=True → safety_handler.on_ramp_deployed`
- **Quality gates (2026-05-20)**: mypy 0 errors, ruff 0 violations, **119 pass / 0 fail**, coverage 91.03% (≥90%); shared 125 pass

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
inference/tests/unit/test_health.py
cameras.json
shared/src/oebb_shared/events/payloads.py
shared/tests/contract/test_envelope_contract.py
_bmad-output/implementation-artifacts/deferred-work.md
_bmad-output/implementation-artifacts/4-5-code-review-2026-05-20-followup.md

### Change Log

- 2026-05-19: Story 4-5 implemented — safety & accessibility detection: door obstruction (AC1), accessibility detected (AC2), ramp deployed (AC3), slip/fall (AC4), vestibule congestion (AC5), detection class expansion (AC6), quality gates (AC7)
- 2026-05-20: Addressed code review findings — 20 items resolved (R1–R13/R19 + F1–F13/F-decision-merged). Key changes: dropped `_last_track_ids` correlation (R4), threaded `camera_id` through `ZoneCounter.update()` for multi-camera-per-car (R7), added optional `vestibule_zone` polygon to cameras.json schema (R5), `door_state="unknown"` per AC1 (R6), unique per-emit suitcase track_id (R12), strict `confidence is None` skip (R2), `loop_holder` threaded through `build_app()` (R9). 119 tests pass, coverage 91.03%, mypy/ruff clean.
- 2026-05-20: Post-followup code review (Opus 4.7) — **APPROVED**. Added S1 contract tests for `DoorObstructionPayload.door_state` Literal in `shared/tests/contract/test_envelope_contract.py` (4 parametrized + 1 rejection). S2 (vestibule_zone polygon = aisle polygon in PoC cameras.json) and S3 (AsyncMock test-hygiene warnings) deferred to `deferred-work.md`. Story flipped `review → done`.

## Senior Developer Review (AI)

**Review Date:** 2026-05-19
**Review Outcome:** Changes Requested
**Layers:** Blind Hunter · Edge Case Hunter · Acceptance Auditor (claude-opus-4-7)

### Action Items

- [x] [Review][Decision] F11: `door_state` value — resolved 2026-05-20: schema Literal extended to include `"unknown"`; impl emits `"unknown"` per AC1. Dev Notes line 106 ("`open`" recommendation) superseded. [callback.py:297, shared/.../payloads.py:171]
- [x] [Review][Patch] F1: `_door_zone_hits` pruned each frame for tracks that left the scene [callback.py:496-503]
- [x] [Review][Patch] F2: `_track_bboxes` pruned each frame for disappeared tracks; also re-keyed by `(car_id, camera_id)` so multi-camera-per-car doesn't clobber [zone_counter.py:289-297]
- [x] [Review][Patch] F3: `_last_suitcase_bbox` cleared when no suitcase detected in frame [callback.py:489-492]
- [x] [Review][Patch] F4: Person obstruction counter reset to 0 after threshold emit [callback.py:254]
- [x] [Review][Patch] F5: Suitcase IoU obstruction counter reset to 0 after threshold emit [callback.py:221]
- [x] [Review][Patch] F6: `_dispatch_bicycle` rate-limited to one emit per camera per 10s [callback.py:317-321]
- [x] [Review][Patch] F7: health.py uses `loop_holder.loop` (with `get_running_loop` fallback for tests); both via `run_coroutine_threadsafe` + `add_done_callback` [health.py:93-120]
- [x] [Review][Patch] F8: Resolved 2026-05-20 via R5 — vestibule_zone polygon added to `cameras.json` schema; callback tags persons whose centroid is in the vestibule polygon; ZoneCounter counts the tagged subset rather than whole-car count [callback.py:_call_, zone_counter.py:165-176]
- [x] [Review][Patch] F9: Resolved 2026-05-20 as PoC simplification — `car_id = settings.vehicle_id`; deferred coach-level resolution to E4-S6 with ZFR per-coach signals (see deferred-work.md R3 entry, safety.py module docstring) [safety.py:55]
- [x] [Review][Patch] F10: Resolved 2026-05-20 — `vestibule_id = f"{car_id}-{zone}"` (dynamic per camera zone); test updated to match [zone_counter.py:328, test_vestibule_congestion.py:50]
- [x] [Review][Patch] F12: Resolved 2026-05-20 via R4 — `_last_track_ids` and `update_last_track` removed entirely; `triggered_by_track_id = "unknown"` unconditionally on inference side; fusion (E4-S6) correlates [safety.py]
- [x] [Review][Patch] F13: `_dispatch_bicycle` skips emit when `confidence is None` (strict interpretation of AC2) [callback.py:317]
- [x] [Review][Defer] F14: Private access `self._zone_counter._journey_holder.journey_id` in `_post_accessibility_event` [callback.py] — deferred, pre-existing pattern in codebase

## Review Follow-ups (AI)

- [x] [AI-Review][Decision] F11: door_state canonical value resolved to `"unknown"` (AC1 wins); shared schema Literal extended
- [x] [AI-Review][Patch] F1: Prune `_door_zone_hits` for disappeared tracks
- [x] [AI-Review][Patch] F2: Prune `_track_bboxes` for disappeared tracks
- [x] [AI-Review][Patch] F3: Prune `_last_suitcase_bbox` for disappeared cameras/frames
- [x] [AI-Review][Patch] F4: Reset person obstruction counter after threshold emit
- [x] [AI-Review][Patch] F5: Reset suitcase obstruction counter after threshold emit
- [x] [AI-Review][Patch] F6: Add rate-limit / de-dup to `_dispatch_bicycle`
- [x] [AI-Review][Patch] F7: Fix `asyncio.get_event_loop()` in health.py — uses `loop_holder.loop`
- [x] [AI-Review][Patch] F8: Pass vestibule-zone person count (via `in_vestibule` tag), not whole-car count
- [x] [AI-Review][Patch] F9: car_id stays as vehicle_id (PoC simplification); deferred to E4-S6
- [x] [AI-Review][Patch] F10: Use `zone` in `vestibule_id` construction (`f"{car_id}-{zone}"`)
- [x] [AI-Review][Patch] F12: `SafetyHandler._last_track_ids` removed; `triggered_by_track_id="unknown"` always
- [x] [AI-Review][Patch] F13: Enforce confidence threshold even when `confidence is None` (skip emit)

## Review Findings — Fresh BMAD Code Review (2026-05-20)

**Review Date:** 2026-05-20
**Review Outcome:** Changes Requested — BLOCKER: AC7 quality gate violated (2 of 119 tests fail on master)
**Layers:** Blind Hunter · Edge Case Hunter · Acceptance Auditor (claude-opus-4-7-1M)
**Quality Gate Evidence:** mypy --strict PASS · ruff PASS · coverage 90.92% (above 90%) · **pytest 117 PASS / 2 FAIL**

### Decision Needed

- [x] [Review][Decision] R2: Resolved 2026-05-20 — strict: skip emit when `confidence is None` (AC2 wording "confidence >= threshold" — None is not >=). Test `test_bicycle_none_confidence_still_emits` renamed to `test_bicycle_none_confidence_skips_emit` and inverted. [callback.py:317, test_accessibility.py:152]
- [x] [Review][Decision] R3: Resolved 2026-05-20 — `car_id = settings.vehicle_id` as PoC simplification. Coach-level resolution deferred to E4-S6 (see deferred-work.md). [safety.py:55]
- [x] [Review][Decision] R4: Resolved 2026-05-20 — feature dropped entirely; `_last_track_ids` and `update_last_track` removed; `triggered_by_track_id="unknown"` always. Fusion (E4-S6) correlates. [safety.py]
- [x] [Review][Decision] R5: Resolved 2026-05-20 — added optional `vestibule_zone` polygon to cameras.json schema; callback tags persons whose centroid falls in the vestibule polygon via `in_vestibule` field; ZoneCounter uses the tagged subset count. [cameras.json:14, callback.py:_call_, zone_counter.py:165-176]
- [x] [Review][Decision] R6: Resolved 2026-05-20 — `"unknown"` wins (AC1 authoritative); shared `door_state` Literal already permits `"unknown"`. Dev Notes line 106 superseded. [callback.py:297, shared/.../payloads.py:171]
- [x] [Review][Decision] R7: Resolved 2026-05-20 — `camera_id` threaded through `ZoneCounter.update()` → `_check_slip_fall` → `_post_slip_fall_candidate`; also re-keyed `_track_bboxes` by `(car_id, camera_id)` so multi-camera-per-car doesn't clobber. [zone_counter.py:109-117, 252-258, 286, callback.py:_call_]
- [x] [Review][Decision] R12: Resolved 2026-05-20 — unique per-emit track_id `f"suitcase-{int(time.monotonic()*1000)%100000}"` so fusion can dedupe. [callback.py:225]

### Patch (BLOCKER — must fix to satisfy AC7)

- [x] [Review][Patch] R1: Resolved 2026-05-20 — kept impl `f"{car_id}-{zone}"`; updated `test_vestibule_congestion_threshold_crossing` to assert `"car-1-door"` (matches the camera's zone). [zone_counter.py:328, test_vestibule_congestion.py:57]

### Patch (Non-blocker)

- [x] [Review][Patch] R8: `add_done_callback(_on_post_done)` attached to `run_coroutine_threadsafe` future in `health.context_push`. [health.py:113-120]
- [x] [Review][Patch] R9: `loop_holder` threaded through `build_app()`; sync handler schedules via `run_coroutine_threadsafe(coro, loop_holder.loop)` with a `get_running_loop()` fallback for tests. [health.py:48, 93-120, main.py:113-119]
- [x] [Review][Patch] R10: Resolved by R4 deletion — `_last_accessibility_track` removed entirely; nothing left to reorder. [callback.py:332]
- [x] [Review][Patch] R13: `bbox` parameter removed from `_handle_person_door_obstruction`. [callback.py:243, 503]
- [x] [Review][Patch] R19: Added `test_context_push_ramp_deployed_invokes_safety_handler` in test_health.py — drives FastAPI TestClient against a real loop-holder thread + stub safety handler, asserts the scheduled coroutine actually runs. [test_health.py:145-204]

### Defer (pre-existing or future work)

- [x] [Review][Defer] R11: `OccupancyCallback._event_store_client` is used to POST to `fusion_url` — variable name misleading. Cross-cutting rename to `_http_client`. Pre-existing single-client architecture decision. [callback.py — all `_event_store_client.post(fusion_url...)` sites]
- [x] [Review][Defer] R15: `_handle_suitcase_door_obstruction` accepts `list[bbox]` but only processes `bboxes[0]` — multiple suitcases per frame silently dropped. PoC simplification; document at function level.
- [x] [Review][Defer] R16: Slip/fall has no rate-limit / in-flight suppression at the source — relies on fusion suppression (E4-S6). Document the contract.
- [x] [Review][Defer] R17: Suitcase obstruction `track_id` non-unique across emissions — deferred pending fusion contract (E4-S6).
- [x] [Review][Defer] R18: Multi-camera-per-car not supported — `_car_zone[car_id]` keeps last camera's zone only; `_track_bboxes` keyed by car_id (not camera) clobbers across cameras. Current `cameras.json` is 1-cam-per-car so PoC works; document the constraint.
- [x] [Review][Defer] R20: `zone_counter.update()` serially awaits 4 POSTs (occupancy → threshold → slip_fall → vestibule) — safety event prioritization inverted vs occupancy. Architectural; fusion suppression mitigates.
- [x] [Review][Defer] R22: Person/suitcase obstruction emit cadence is every 2 frames (~666ms at 3fps) after counter reset — relies on fusion suppression. Document contract.

### Dismissed (not reported)

- R14 dismissed: `_valid_types` defensive coercion to "unknown" in `_post_door_obstruction_candidate` is impl-internal noise; callers never pass invalid values.
- R21 dismissed: `_dispatch_bicycle` rate-limit dict race — asyncio loop serializes all `_dispatch_bicycle` invocations on a single loop, so the read-modify-write is atomic in practice.

### Quality Gate Summary (rerun 2026-05-20)

| Gate | Required | Actual | Status |
|---|---|---|---|
| `mypy --strict src/` | 0 errors | 0 errors (10 files) | PASS |
| `ruff check src/ tests/` | 0 violations | 0 violations | PASS |
| Coverage of `src/inference/` excl pipeline | ≥90% | 90.92% | PASS |
| `pytest --strict-markers` | All pass | 117 PASS / 2 FAIL | **FAIL** |

Failing tests:
1. `tests/unit/test_vestibule_congestion.py::test_vestibule_congestion_threshold_crossing` — `vestibule_id` mismatch (R1)
2. `tests/unit/test_accessibility.py::test_bicycle_none_confidence_still_emits` — F13 patch contradicts test expectation (R2)

### Recommendation

Status: **not-ready-for-done** → back to `in-progress` until AC7 quality gate passes. The two test failures alone block story completion. R3/R4/R5 (decision-needed) carry semantic implications for fusion (E4-S6) and should be resolved before the next epic story to avoid cascading rework.

### Resolution (2026-05-20)

All R1-R13/R19 items addressed (see ticks above). Quality gates re-run on the same HEAD:

| Gate | Required | Actual | Status |
|---|---|---|---|
| `mypy --strict src/` | 0 errors | 0 errors (10 files) | PASS |
| `ruff check src/ tests/` | 0 violations | 0 violations | PASS |
| Coverage of `src/inference/` excl pipeline | ≥90% | 91.03% | PASS |
| `pytest --strict-markers` | All pass | 119 PASS / 0 FAIL | PASS |
| Shared regression (`oebb-shared`) | All pass | 125 PASS | PASS |

R3 (car_id), R11, R15, R16, R17, R18, R20, R22 carry forward as deferred items in `deferred-work.md` under the 2026-05-20 heading. Status flipped `in-progress` → `review`.

### Code Review (post-followup) — 2026-05-20

**Reviewer:** Claude Opus 4.7 (1M context), fresh session, BMad `bmad-code-review` skill
**Target:** commit `020e0cd` (20-patch series)
**Outcome:** **APPROVE — recommend `review` → `done`** with two non-blocking should-fix follow-ups.
**Full report:** [`4-5-code-review-2026-05-20-followup.md`](./4-5-code-review-2026-05-20-followup.md)

Quality gates re-run cold this session (independent of dev agent claims):

| Gate                                                | Required | Actual                | Status |
|-----------------------------------------------------|----------|-----------------------|--------|
| `mypy --strict src/` (inference)                    | 0 errors | 0 errors (10 files)   | PASS   |
| `ruff check src/ tests/` (inference)                | 0        | 0                     | PASS   |
| `pytest --strict-markers -q` (inference)            | All pass | 119 pass / 0 fail     | PASS   |
| Coverage of `src/inference/` excl. `pipeline.py`    | ≥ 90 %   | 91.03 %               | PASS   |
| `pytest -q` (shared)                                | All pass | 125 pass              | PASS   |

All 7 ACs verified at file:line locations. All prior F1–F14 and R1–R13/R19 findings independently re-verified resolved. Adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor) raised:

- **S1 (should-fix):** Schema `door_state` Literal extended (`"unknown"` added) without a contract test — `shared/CLAUDE.md` requires one. Add a 1-liner to `shared/tests/unit/test_event_envelope.py`.
- **S2 (should-fix):** `cameras.json:14` `vestibule_zone` polygon is identical to the `aisle` seat-zone — every aisle person double-counted as in-vestibule. Replace with a near-door rectangle or document the demo configuration.
- **S3–S5 (nice-to-have):** `RuntimeWarning` on un-awaited `AsyncMock.raise_for_status` (5 tests); legacy `camera_id=None` fallback in `_check_vestibule_congestion`; silent no-client return in `_post_door_obstruction_candidate`.

No must-fix items. Project-rule compliance (Rule 8, fusion-vs-event-store routing, `DEFAULT_RETRY`, no raw-video leakage) all clean.

**Recommendation:** PM/dev agent flips `sprint-status.yaml` 4-5 → `done` and proceeds to `bmad-create-story` for 4-6 (fusion container). S1+S2 can either be folded into the 4-6 prep commit or carried as known-acceptable PoC scope.

### Closed — `done` (2026-05-20)

**Action taken:** S1 fixed inline (cheap, rule-required). S2 + S3 deferred to `deferred-work.md` under the 2026-05-20 post-followup heading.

- **S1 fixed:** Added `contract` marker tests in `shared/tests/contract/test_envelope_contract.py`:
  - `test_door_obstruction_door_state_literal_accepts_all_values` — parametrized over all 4 valid values (`open`, `closing`, `closed`, `unknown`). Pins the contract so a future contraction breaks CI.
  - `test_door_obstruction_door_state_rejects_unknown_literal` — guards against silent coercion of invalid values like `"ajar"`.
- **S2 deferred:** `cameras.json:14` `vestibule_zone` polygon equals the `aisle` polygon. Tolerated in single-camera PoC; needs ops/UX polygon data to fix properly.
- **S3 deferred:** 5 `RuntimeWarning` on un-awaited `AsyncMock.raise_for_status`. Test hygiene only; no production impact.

Final gates (post-S1):

| Gate | Required | Actual | Status |
|---|---|---|---|
| `mypy --strict src/` (shared) | 0 errors | 0 errors (17 files) | PASS |
| `pytest -m contract -q` (shared) | All pass | 61 pass (+5 new) | PASS |
| `pytest -q` (shared, full) | All pass | 130 pass | PASS |
| `mypy --strict src/` (inference) | 0 errors | 0 errors | PASS |
| `ruff check src/ tests/` (inference) | 0 | 0 | PASS |
| `pytest --strict-markers -q` (inference) | All pass | 119 pass | PASS |
| Coverage (inference) | ≥ 90 % | 91.03 % | PASS |

Story `Status: review → done`. Sprint-status updated. Next: `bmad-create-story` for 4-6.
