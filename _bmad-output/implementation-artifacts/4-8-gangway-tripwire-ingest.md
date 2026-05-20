# Story 4.8: `inference` Gangway Tripwire Ingest (Inter-Wagon Movement)

Status: review

<!-- Created 2026-05-20 by bmad-create-story. EXTENDS the existing inference
container (not bootstrap). Adds tripwire.py + updates callback.py routing for
gangway-zone cameras. No new container; no changes to zone_counter.py or safety.py. -->

## Story

As a system operator,
I want the `inference` container to detect persons crossing gangway boundaries between coaches using virtual tripwires at gangway camera feeds, emitting `WAGON_EXIT` and `WAGON_ENTRY` events,
so that `fusion` can maintain a closed-ledger per-coach count and detect inter-wagon movement that would otherwise cause occupancy drift.

## Acceptance Criteria

1. **cameras.json gangway camera schema + startup validation:** Given `cameras.json` includes a camera entry with `zone: "gangway-fwd"` or `zone: "gangway-aft"` and a `tripwire` field specifying a polygon line across the camera frame, when `rtsp-ingest` starts, then each gangway camera is loaded with its tripwire configuration `{ coach_from, coach_to, direction_axis, tripwire_polygon }`; a missing `tripwire` field on a gangway-zone camera raises a startup error (sys.exit or RuntimeError caught by the pipeline thread).

2. **WAGON_EXIT emission:** Given `hailotracker` is tracking a `track_id` in a gangway camera frame, when the tracked person's bounding box centroid crosses the tripwire polygon from the `coach_from` side to the `coach_to` side, then a `WAGON_EXIT` event is POSTed to `event-store` via `DEFAULT_RETRY` with payload matching `WagonExitPayload`: `{ track_id: int, coach_from, coach_to, camera_id, direction, confidence }`; `direction` is `"forward"` or `"backward"` relative to train direction of travel.

3. **WAGON_ENTRY emission:** Given a `WAGON_EXIT` event has been emitted for a `track_id`, when the same `track_id` is subsequently detected crossing the entry tripwire on the adjacent coach's gangway camera, then a `WAGON_ENTRY` event is POSTed to `event-store` with the same `track_id`, `coach_from`, `coach_to`, and `direction`; the pair is linked by `track_id`.

4. **Low-confidence suppression:** Given a tripwire crossing is detected with `confidence < 0.70`, when the event would be emitted, then the event is NOT posted; a structured log is emitted at DEBUG with `reason: "low_confidence"`, `track_id`, `confidence`; the track continues to be monitored.

5. **Orphaned-exit timeout + fusion notification:** Given a `track_id` exits via `WAGON_EXIT` but no matching `WAGON_ENTRY` arrives within 10 seconds, when the timeout expires, then a structured log is emitted at WARNING with `reason: "orphaned_exit"`, `track_id`, `coach_from`, `coach_to`; `fusion` is notified via its `/context` endpoint so it can flag the ledger as unreconciled.

6. **P1 priority — never throttled:** Gangway cameras are always `priority: "P1"` in `cameras.json`. The existing `Budget.should_process()` already passes all P1 cameras unconditionally — no Budget changes needed. AC verified by test.

7. **Quality gates:**
   - `tests/unit/test_tripwire.py` covers centroid crossing detection with synthetic bounding box sequences: tripwire crossed (forward), tripwire crossed (backward), not crossed, partial crossing (low confidence < 0.70) — no Hailo-8 required.
   - `tests/unit/test_security.py` AST checks extended to `inference/tripwire.py` (no raw `os.environ.get`, no hardcoded secrets).
   - `mypy --strict src/` passes for all new and modified files.
   - `pytest --strict-markers` achieves ≥90% coverage of `src/inference/` excluding `pipeline.py`.
   - `ruff check src/ tests/` zero violations.

## Tasks / Subtasks

- [x] Add `WagonExitPayload` and `WagonEntryPayload` to shared imports in inference (AC: 2, 3)
  - [x] Confirm both payload classes already exist in `shared/src/oebb_shared/events/payloads.py` (they do — lines 339–362). No shared changes needed.
  - [x] Confirm `EventType.WAGON_EXIT` and `EventType.WAGON_ENTRY` already exist in `shared/src/oebb_shared/events/types.py` (they do — lines 31–32). No shared changes needed.
  - [x] Add `WagonExitPayload`, `WagonEntryPayload` to exports in `shared/src/oebb_shared/events/__init__.py` (were missing from `__all__`).

- [x] Create `inference/src/inference/tripwire.py` (AC: 1–6)
  - [x] `TripwireConfig` dataclass, `_PendingExit` dataclass, `TripwireHandler` class
  - [x] Startup validation: missing `tripwire` field or wrong zone → `RuntimeError`
  - [x] `_centroid_side()` using cross-product of directed tripwire segment
  - [x] `process_frame()` sync entry; `_handle_detection()` async core
  - [x] gangway-fwd → WAGON_EXIT + orphan timer; gangway-aft → WAGON_ENTRY directly
  - [x] Low-confidence suppression (< 0.70) with DEBUG log
  - [x] Orphan timer with stale-closure-safe lambda capture (E3 retro A3)
  - [x] `_handle_orphaned_exit()` → WARNING log + fusion `/context` POST
  - [x] `_build_envelope()` matching zone_counter pattern

- [x] Update `cameras.json` to add gangway camera entries (AC: 1, 6)
  - [x] `C3_GANGWAY_FWD` (gangway-fwd, P1, car-3→car-4) and `C4_GANGWAY_AFT` (gangway-aft, P1)

- [x] Wire `TripwireHandler` into `OccupancyCallback` (AC: 1, 2, 3, 4, 5)
  - [x] `tripwire_handler: TripwireHandler | None = None` param added to `__init__`
  - [x] Gangway early-return branch in `__call__` (before `zone_counter.update()`)
  - [x] All non-gangway paths preserved unchanged
  - [x] `main.py` `wire()`: TripwireHandler construction + startup validation (sys.exit on missing tripwire)

- [x] Write `tests/unit/test_tripwire.py` (AC: 7)
  - [x] 11 test cases covering all ACs + edge cases
  - [x] `respx.mock` for all HTTP assertions, `structlog.testing.capture_logs` for log assertions
  - [x] `pytest-asyncio` for async tests

- [x] Extend `tests/unit/test_security.py` AST checks to cover `tripwire.py` (AC: 7)
  - [x] `test_no_env_get_in_tripwire`, `test_hailo_pipeline_not_imported_in_tripwire`
  - [x] `test_wagon_exit_payload_schema_valid`, `test_wagon_entry_payload_schema_valid`

- [x] Validate `pytest --strict-markers` ≥90% coverage, mypy --strict, ruff clean (AC: 7)
  - [x] 134 passed, 90.78% coverage, mypy 0 errors, ruff 0 violations

## Dev Notes

### Architecture — What This Story Adds

```
cameras.json (zone: gangway-fwd/aft + tripwire field)
    │
    ▼
main.py wire() ──► TripwireHandler (new tripwire.py)
                        │
    OccupancyCallback   │ process_frame() [sync, streaming thread]
    __call__()          │      │
    [gangway zone] ─────┘      ▼
                      _handle_detection() [async, event loop]
                        │               │
                   WAGON_EXIT      WAGON_ENTRY
                   → event-store   → event-store
                        │
                  orphan timer
                  → fusion /context
```

**Gangway cameras bypass ZoneCounter entirely.** When `self._camera_zone in ("gangway-fwd", "gangway-aft")`, `OccupancyCallback.__call__` calls `TripwireHandler.process_frame()` and returns. It does NOT call `self._zone_counter.update()`. This is intentional — gangway headcount is tracked by `fusion`'s closed ledger (E4-S9), not by the per-coach ZoneCounter.

### Existing Files Being Modified

**`inference/src/inference/callback.py`** — current state:
- `OccupancyCallback.__init__` takes: `camera, zone_masks, zone_counter, budget, settings, loop_holder, readiness, cameras_json, event_store_client, safety_handler`
- `__call__` routing is: budget check → extract detections → person/bicycle/suitcase dispatch → `zone_counter.update()` → door obstruction → bicycle accessibility
- **What changes:** Add `tripwire_handler: TripwireHandler | None = None` param; add early-return branch for gangway zones before `zone_counter.update()`
- **What must be preserved:** All existing `_camera_zone == "door"` paths (suitcase IoU tracking, person door obstruction hit counting, stale prune). The `zone_counter.update()` call. The `bicycle` dispatch. The `_bbox_space_verified` first-frame check. The `_on_post_done` error logging. None of these may be touched.

**`inference/src/inference/main.py`** — current state:
- `wire()` constructs one `OccupancyCallback` per camera; `_zone_masks_for_camera()` validates `seat_zones` (sys.exit on missing)
- `_load_cameras_data()` returns `(cameras, full_json_dict)`
- **What changes:** In `wire()`, for gangway-zone cameras, construct `TripwireHandler` and pass it to `OccupancyCallback`. Add startup validation: if `cam["zone"]` in gangway zones and `"tripwire"` not in `cam`, log CRITICAL + `sys.exit(1)` (matches the `seat_zones` missing pattern at line 51-55)
- **What must be preserved:** The `strict=True` zip of cameras and readiness. The lifespan pattern. The `_bootstrap_budget`/`_bootstrap_journey` pattern. The route-appending trick. None of these may be touched.

**`cameras.json`** — current state:
- Three cameras: `C1_DOOR_01` (door/P1), `C1_INT_01` (interior/P2), `C1_EXT_01` (exterior/P3)
- `door_camera_map` present
- **What changes:** Add two gangway cameras with required fields. Existing cameras unchanged.

### New File: `inference/src/inference/tripwire.py`

Key design decisions:
- **Tripwire crossing detection:** The tripwire is a polygon line (list of 2+ `[x, y]` points forming a polyline). Centroid side is determined by which side of the directed line segment the centroid falls (cross-product sign). For a vertical line `[[320, 0], [320, 480]]` with `direction_axis: "x"`, `coach_from` side is `cx < 320`, `coach_to` side is `cx >= 320`.
- **State tracking:** `_pending_exits: dict[int, ...]` maps `track_id → (coach_from, coach_to, direction, confidence, orphan_asyncio_handle)`. When a track crosses the exit tripwire, it's added. When WAGON_ENTRY arrives (same track_id on adjacent camera), it's removed and the timer cancelled.
- **Orphan timer:** Use `loop.call_later(10.0, ...)` to schedule `_handle_orphaned_exit`. Must cancel the handle when WAGON_ENTRY arrives. The timer fires on the asyncio loop — no threading concerns.
- **Multi-camera tracking:** Each gangway camera has its own `TripwireHandler` instance. WAGON_EXIT is emitted by the `gangway-fwd` camera's handler. WAGON_ENTRY must be emitted by the adjacent `gangway-aft` camera's handler when it sees the same `track_id`. The handlers do NOT share state — each independently detects crossings on their own tripwire. `track_id` is the correlation key at the `event-store` level (E4-S9/fusion reads it).
- **Async/sync boundary:** Same pattern as `OccupancyCallback`: `process_frame()` is sync (called from GStreamer streaming thread); uses `asyncio.run_coroutine_threadsafe(self._handle_detection(...), loop)` with `_on_post_done` callback for error logging.
- **`_build_envelope` pattern:** Copy from `zone_counter._build_envelope` exactly — `journey_holder.journey_id`, `settings.vehicle_id`, `settings.schema_version`, source `"inference"`.

### Payload Models (already in `oebb_shared`)

```python
# WagonExitPayload — shared/src/oebb_shared/events/payloads.py:339
class WagonExitPayload(_BasePayload):
    track_id: int
    coach_from: _NonEmptyStr
    coach_to: _NonEmptyStr
    camera_id: _NonEmptyStr
    direction: Literal["forward", "backward"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

# WagonEntryPayload — shared/src/oebb_shared/events/payloads.py:350
class WagonEntryPayload(_BasePayload):
    track_id: int
    coach_from: _NonEmptyStr
    coach_to: _NonEmptyStr
    camera_id: _NonEmptyStr
    direction: Literal["forward", "backward"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
```

Both `EventType.WAGON_EXIT` and `EventType.WAGON_ENTRY` exist in `shared/src/oebb_shared/events/types.py` (lines 31–32). **No changes to `shared/` needed.**

### Imports to Add in `tripwire.py`

```python
from oebb_shared.events import (
    EventEnvelope,
    EventType,
    WagonExitPayload,
    WagonEntryPayload,
)
from oebb_shared.http.retry import DEFAULT_RETRY
from inference.config import Settings
from inference.models import JourneyHolder, LoopHolder
```

### `cameras.json` Gangway Camera Structure

The `tripwire` field shape expected by `TripwireHandler`:
```json
"tripwire": {
  "tripwire_polygon": [[320, 0], [320, 480]]
}
```
Top-level camera fields `coach_from`, `coach_to`, `direction_axis` are siblings of `tripwire` (not nested inside it), matching `TripwireConfig` construction from `camera` dict.

### Budget / Priority

`Budget.should_process(camera_id, priority)` already passes P1 unconditionally (line 47: `if priority == "P2" and self._p2_throttled: return False; return True`). Gangway cameras must be `"priority": "P1"` in `cameras.json`. No Budget changes required.

### Test Patterns from Prior Stories

- `respx.mock` for HTTP assertions → see `test_accessibility.py`, `test_zone_counter.py`
- `pytest-asyncio` with `@pytest.mark.asyncio` for async tests
- Patch `inference.callback.hailo` for sync callback tests (not needed here — `tripwire.py` is pure async, no GStreamer dependency)
- `test_security.py` scans modules list — add `"tripwire"` to the scan list

### E3 Retrospective Lessons Applied

- **A1 (read full UPDATE files):** Full `callback.py` and `main.py` read above — current state, change scope, preservation requirements all documented.
- **A2 (CSS tokens):** Not applicable — no CSS in this story.
- **A3 (async stale closure):** The orphan timer uses `loop.call_later` which schedules a sync callback. If the callback needs to access state, use a closure that captures the specific values (`track_id`, `coach_from`, `coach_to`) at schedule time — not `self._pending_exits` (which may have changed). Schedule via `asyncio.ensure_future(self._handle_orphaned_exit(...))` inside the `call_later` callback, not a direct coroutine reference.

### Quality Gate Command

```bash
cd inference
pytest --strict-markers --cov=src/inference --cov-fail-under=90 \
  --ignore=src/inference/pipeline.py -q
mypy --strict src/
ruff check src/ tests/
```

### Event-Store POST Pattern (copy from zone_counter.py)

```python
@DEFAULT_RETRY
async def _emit_wagon_exit(self, ...) -> None:
    payload = WagonExitPayload(
        track_id=track_id,
        coach_from=self._config.coach_from,
        coach_to=self._config.coach_to,
        camera_id=self._camera_id,
        direction=direction,
        confidence=confidence,
    )
    envelope = self._build_envelope(
        EventType.WAGON_EXIT, payload.model_dump(), severity="info"
    )
    resp = await self._event_store_client.post(
        f"{self._settings.event_store_url}/api/v1/events",
        json=envelope.model_dump(mode="json"),
    )
    resp.raise_for_status()
```

## Story Progress

- [ ] `inference/src/inference/tripwire.py` — NEW
- [ ] `inference/src/inference/callback.py` — UPDATE (gangway early-return branch)
- [ ] `inference/src/inference/main.py` — UPDATE (TripwireHandler wiring + validation)
- [ ] `cameras.json` — UPDATE (gangway camera entries)
- [ ] `inference/tests/unit/test_tripwire.py` — NEW
- [ ] `inference/tests/unit/test_security.py` — UPDATE (add tripwire to scan list)
