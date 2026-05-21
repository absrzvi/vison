# Story 4.10: `fusion` Coach Comfort Index

Status: review

<!-- Created 2026-05-21 by bmad-create-story.
     DEPENDS ON Story 4-9 (closed-ledger): reuses fusion's `/candidates/occupancy_update`
     POST endpoint and the ingest pattern resolved in 4-9 party-mode (D1-A).
     Uses the shipped CoachComfortIndexPayload shape, not the divergent epic-spec shape — see "Decisions" below. -->

## Story

As a control centre operator,
I want `fusion` to compute and publish a `COACH_COMFORT_INDEX` event per coach on station approach and on significant occupancy change,
so that the Control Centre Dashboard and capacity planning analytics have a single composite comfort signal per coach without re-deriving it from raw occupancy.

## Acceptance Criteria

1. **Compute on significant occupancy delta.** Given `fusion` receives an `OccupancyUpdatePayload` for `car_id` via `POST /candidates/occupancy_update` (the endpoint added in Story 4-9), when `|occupancy_pct - _last_emitted_pct[car_id]| > 0.10` (10 percentage points, configurable via `Settings.comfort_index_pct_threshold`), then a `COACH_COMFORT_INDEX` event is computed and POSTed to `event-store`; `_last_emitted_pct[car_id]` is updated.

2. **Emit on station_approach edge.** Given `ContextState.station_approach` transitions from `False` → `True`, when the edge is detected (in the `/context` push handler in `fusion/health.py`), then a `COACH_COMFORT_INDEX` event is POSTed for every coach that has at least one recorded `OccupancyUpdatePayload` in this journey, regardless of whether the 10% delta threshold was crossed. The edge handler completes within 2 seconds (architecture target — async dispatch is fine).

3. **Payload uses shipped `CoachComfortIndexPayload` shape.** Given a comfort index is computed, then the POSTed payload matches `CoachComfortIndexPayload` from `shared/src/oebb_shared/events/payloads.py:397`: `{ car_id, comfort_score, occupancy_pct, temperature_c, noise_db }`. `comfort_score = 1.0 - occupancy_pct` clamped to `[0.0, 1.0]`. `temperature_c` and `noise_db` are `None` at PoC (no environmental sensors yet — see Decisions D2 below). The divergent epic-spec shape `{ reserved_seats, occupied_seats, standing_count, service_tier }` is NOT used.

4. **First OCCUPANCY_UPDATE per coach establishes baseline, no emit.** Given the very first `OccupancyUpdatePayload` for a `car_id` in this journey arrives, when processed, then `_last_emitted_pct[car_id]` is seeded with the value but NO `COACH_COMFORT_INDEX` is emitted (there is no prior baseline to compare against — first emit happens either via AC1's next 10% delta or AC2's next station_approach edge). Mirrors 4-9's `both_seeded` cold-start pattern.

5. **Suppression-gate compliance.** Given `SuppressionGate.should_emit()` returns `False` (depot/maintenance/gps_invalid), when an emit would fire (AC1 or AC2 path), then the event is NOT POSTed; a DEBUG log is emitted with `reason: "comfort_index_suppressed"`, `car_id`, `occupancy_pct`. `_last_emitted_pct` is NOT updated under suppression — so when the gate re-opens, the next delta check runs against the last truly-emitted value.

6. **No emit when `ContextState.journey_id is None`.** Given fusion has not yet received its first `/context` push with a journey_id, when an OCCUPANCY_UPDATE arrives, then `Enrichment._build_envelope` returns `None` (existing behaviour) and a WARN log fires (`enrichment.skip_no_journey_id`). State is updated but no event escapes.

7. **Quality gates:**
   - `tests/unit/test_comfort_index.py` covers: first-OCCUPANCY no-emit (AC4); 10% delta emit (AC1); sub-10% no-emit; station_approach edge emit for all known coaches (AC2); station_approach steady-state (no edge) no-emit; comfort_score clamping at `occupancy_pct == 0.0` and `occupancy_pct == 1.0`; suppression-gate behaviour (AC5); no-journey-id skip (AC6).
   - `tests/unit/test_security.py` AST checks extended to `fusion/comfort_index.py` (no raw `os.environ.get`, no hardcoded secrets).
   - `mypy --strict src/` passes for all new and modified fusion files.
   - `pytest --strict-markers` achieves ≥90% coverage of `src/fusion/`.
   - `ruff check src/ tests/` zero violations.

## Decisions

Recorded inline rather than as a blocking checkpoint — both follow the precedent set in Story 4-9 party-mode resolution.

- **D1 — Payload shape: shipped `CoachComfortIndexPayload`, not epic-spec shape.** Epic spec (`epics.md` line 1550) describes `{ car_id, reserved_seats, occupied_seats, standing_count, comfort_score, service_tier }`. The shipped payload at `shared/src/oebb_shared/events/payloads.py:397` is `{ car_id, comfort_score, occupancy_pct, temperature_c, noise_db }`. Same precedent as 4-9 D3: use what's already in `shared/`, in event-store deserialisers, in existing contract tests. The shipped shape is also more aligned with ADR-15 (camera count is the authoritative signal; reservations are a side-channel that doesn't belong in the comfort payload).

- **D2 — `temperature_c` / `noise_db` are PoC-deferred.** No environmental sensors are wired in this PoC. Both fields are `Optional` in the payload and emit as `None`. When sensors arrive (post-PoC), this story does not need to be re-opened — the payload contract already supports them.

- **D3 — Reservations are NOT used in comfort scoring.** Epic spec's standing-vs-reserved math is dropped (depended on reservation data via `ContextState.reservations`). The shipped payload has no reservation fields. Comfort_score = `1.0 - occupancy_pct`, clamped. Simple and matches the field set.

- **D4 — Ingest reuses 4-9's `POST /candidates/occupancy_update`.** No new endpoint needed. The comfort-index code lives in a new module that the `/candidates/occupancy_update` handler calls *after* `CoachLedger.check_drift(...)`. Two consumers, one ingest path. This implicitly orders comfort-index emit after ledger drift emit, which is fine (independent emits).

- **D5 — `OccupancyUpdate` consumer ordering.** The `/candidates/occupancy_update` handler in fusion (from 4-9) will call: `ledger.check_drift(...)` → optional LEDGER_DRIFT_OBSERVATION emit → `comfort_index.on_occupancy_update(...)` → optional COACH_COMFORT_INDEX emit. Both emits flow through `Enrichment.emit_envelope` independently. Handler still returns 202 even if either downstream emit fails (mirrors existing `/candidates/door_obstruction` pattern).

## Tasks / Subtasks

### `fusion/` — config

- [x] `fusion/src/fusion/config.py`: add `comfort_index_pct_threshold: float = 0.10`

### `fusion/` — new `comfort_index.py`

- [x] Create `fusion/src/fusion/comfort_index.py`
  - [x] `ComfortIndexState` class with `_last_emitted_pct: dict[str, float]` and `_observed_coaches: set[str]` (AC2 needs the set to know which coaches to emit on station_approach edge)
  - [x] `on_occupancy_update(payload: OccupancyUpdatePayload) -> CoachComfortIndexPayload | None` — AC1, AC4; returns payload to emit, or `None` if no emit; mutates `_last_emitted_pct[car_id]` only when a payload is returned (AC5 invariant)
  - [x] `on_station_approach_edge() -> list[CoachComfortIndexPayload]` — AC2; returns one payload per coach in `_observed_coaches`; does NOT mutate `_last_emitted_pct` (station-edge emits are a separate trigger from delta-based emits)
  - [x] `_compute_payload(car_id, occupancy_pct) -> CoachComfortIndexPayload` — `comfort_score = max(0.0, min(1.0, 1.0 - occupancy_pct))`; `temperature_c=None`, `noise_db=None`

### `fusion/` — wire into health handlers

- [x] `fusion/src/fusion/health.py`:
  - [x] Extend `build_app` signature with `comfort: ComfortIndexState`
  - [x] In the `/candidates/occupancy_update` handler added by 4-9: after `ledger.check_drift(...)`, call `comfort.on_occupancy_update(payload)`; if it returns a payload, gate through `gate.should_emit()` → `enricher.emit_envelope(event_type_name="COACH_COMFORT_INDEX", payload=..., severity="info")`; wrap downstream errors so the handler still returns 202
  - [x] In the `/context` handler: detect station_approach false→true edge via `ContextState.observe_station_approach_edge()` (new method — see ContextState task below); if edge fires, dispatch `comfort.on_station_approach_edge()` and emit each returned payload through the same `gate → emit_envelope` pipeline

### `fusion/` — extend `ContextState`

- [x] `fusion/src/fusion/context_state.py`:
  - [x] Add `_prev_station_approach: bool = False` field
  - [x] Add `observe_station_approach_edge() -> bool` method — returns `True` only on `False → True` transitions, mirrors existing `observe_ramp_signal` pattern (architecture line ~106)
  - [x] Call this from `update_from_push` — set `_prev_station_approach` AFTER the existing `station_approach` field update so the next call sees the new prior

### `fusion/` — wire into lifespan

- [x] `fusion/src/fusion/main.py`: construct `ComfortIndexState()` in `lifespan`; pass to `build_app`

### Tests

- [x] `fusion/tests/unit/test_comfort_index.py` — cover all AC11 branches; `respx.mock` for event-store POSTs; `structlog.testing.capture_logs` for log assertions
- [x] `fusion/tests/unit/test_security.py` — extend module scan list to include `comfort_index`
- [x] `fusion/tests/unit/test_health.py` — add cases for comfort-index emit on `/candidates/occupancy_update` (success + downstream error → still 202) and on `/context` station_approach edge
- [x] `fusion/tests/unit/test_context.py` — add cases for `observe_station_approach_edge` mirroring existing `observe_ramp_signal` test cases

### Quality gates green

- [x] `cd fusion && pytest --strict-markers --cov=src/fusion --cov-fail-under=90 -q`
- [x] `cd fusion && mypy --strict src/ && ruff check src/ tests/`

## Security Tests

**fusion endpoints (no new endpoints — reuses 4-9's `/candidates/occupancy_update` and existing `/context`):**
- [x] No new auth surface added; existing 4-9 + `/context` 422 malformed-payload tests cover the input validation surface.

**OEBB-specific:**
- [x] No raw video, CCTV URL, or Hailo inference frame data appears in any comfort-index payload or log line.
- [x] `CoachComfortIndexPayload` is schema-validated via Pydantic v2 before POST (already enforced by `Enrichment.emit_envelope`).
- [x] No escalation state machine concern — this is informational telemetry, not an alert.

## Dev Notes

### Architecture — What This Story Adds

```
4-9 already ships:
  inference/zone_counter.py
    └─OCCUPANCY_UPDATE fire-forget──►fusion: POST /candidates/occupancy_update
                                              │
                                              ▼
                                     CoachLedger.check_drift(...)
                                              │
                                              ▼ (optional LEDGER_DRIFT_OBSERVATION)
                                     event-store

This story adds (in green):
                                     CoachLedger.check_drift(...)
                                              │
                                              ▼
                                     ComfortIndexState.on_occupancy_update(...)
                                              │
                                              ▼ (when |delta| > 10%)
                                     event-store: COACH_COMFORT_INDEX

And on station_approach false→true edge from /context push:
                                     ContextState.observe_station_approach_edge()
                                              │
                                              ▼
                                     ComfortIndexState.on_station_approach_edge()
                                              │
                                              ▼ (one per observed coach)
                                     event-store: COACH_COMFORT_INDEX
```

### Decisions Folded into AC Text — Quick Reference

| Decision | Folded into | Note |
|---|---|---|
| D1 shipped payload shape | AC3 | Per 4-9 D3 precedent — use what's in shared/ |
| D2 PoC-deferred env sensors | AC3 | Payload fields stay Optional, emit None |
| D3 no reservations | AC3 | Drop epic-spec standing-vs-reserved math |
| D4 reuse 4-9 ingest | AC1 + handler tasks | No new endpoint; piggyback on /candidates/occupancy_update |
| D5 consumer ordering | health.py handler task | ledger.check_drift → comfort.on_occupancy_update |

### Existing Files Being Modified (full reads completed)

**`fusion/src/fusion/context_state.py`** — current state:
- `ContextState` dataclass: journey_id, vehicle_id, speed_kmh, `station_approach: bool = False`, maintenance_mode, depot_mode, gps_valid, door_release, door_state, reservations, consist, `ramp_deployed: bool = False`, `_recent_accessibility`
- `update_from_push(model)` — applies push with present-replaces / absent-keeps semantics; logs suppression-flag changes
- `observe_ramp_signal(ramp_deployed)` — false→true edge detector for ramp (returns `True` only on the edge)
- **What changes:** Add `_prev_station_approach: bool = False`; add `observe_station_approach_edge() -> bool` (mirror of `observe_ramp_signal` for the station_approach field). Call site is in `/context` handler, not in `update_from_push` — the edge check needs to compare prior vs current AROUND the push apply, so keep the method as a caller-driven check rather than baking it into `update_from_push`.
- **What must be preserved:** All existing fields, the present-replaces/absent-keeps semantics, `observe_ramp_signal`, `note_accessibility`, `find_recent_accessibility`, `resolve_car_id`, `car_id_for_door`, `door_state_for`. None of these may be touched.

**`fusion/src/fusion/health.py`** — current state (post-4-9):
- `build_app(settings, ctx, gate, enricher, client, ledger)` — 4-9 added `ledger` param + three new `/candidates/wagon_*` and `/candidates/occupancy_update` handlers
- `/candidates/occupancy_update` (added by 4-9) calls `ledger.check_drift(...)` → optional LEDGER_DRIFT_OBSERVATION emit
- `/context` (existing) calls `ctx.update_from_push`, then `gate.on_context_changed`, then handles ramp edge via `ctx.observe_ramp_signal`
- **What changes:** Add `comfort: ComfortIndexState` parameter. Extend `/candidates/occupancy_update` to also call `comfort.on_occupancy_update` after the ledger call. Extend `/context` to check `ctx.observe_station_approach_edge()` and dispatch `comfort.on_station_approach_edge()` if edge fires.
- **What must be preserved:** All 4-9 ledger logic; ramp edge handling; suppression-gate semantics; 202 fail-safe wrapping on downstream errors; `_ReadinessCache`.

**`fusion/src/fusion/main.py`** — current state (post-4-9):
- Lifespan now constructs `CoachLedger(settings.ledger_db_path)` and passes to `build_app`
- **What changes:** Add `ComfortIndexState()` construction; pass to `build_app`.
- **What must be preserved:** All lifespan ordering, ledger construction, the bootstrap-then-append-routes pattern.

**`fusion/src/fusion/config.py`** — current state (post-4-9):
- Has `ledger_drift_threshold`, `ledger_drift_bucket_size`, `ledger_db_path`, `ledger_pending_timeout_s` from 4-9
- **What changes:** Add `comfort_index_pct_threshold: float = 0.10`.

**`fusion/src/fusion/enrichment.py`** — current state:
- `emit_envelope(event_type_name, payload, severity)` handles generic POSTs with skip-on-no-journey-id
- **What changes:** Nothing. `COACH_COMFORT_INDEX` flows through with `severity="info"`.

### New File: `fusion/src/fusion/comfort_index.py`

Key design decisions:
- **State ownership:** `ComfortIndexState` owns `_last_emitted_pct: dict[str, float]` and `_observed_coaches: set[str]`. Both in-memory, not persisted (per existing fusion pattern — `ContextState` is also in-memory).
- **Why `_observed_coaches` separately from `_last_emitted_pct`:** Cold-start (AC4) seeds `_last_emitted_pct` on the first OCCUPANCY for a coach WITHOUT emitting. So a coach can be "observed" but not yet have an `_last_emitted_pct` worth comparing — but it should still receive a station_approach-edge emit. The set tracks "have we seen at least one OCCUPANCY for this coach?"
- **Why emit on station_approach edge does NOT update `_last_emitted_pct`:** Station-edge emits are independent of delta-tracking. If we updated `_last_emitted_pct` here, the next legitimate delta-driven emit would compute against a stale baseline. Keep the two triggers separate.
- **Suppression invariant (AC5):** When `gate.should_emit()` returns False, we drop the emit but ALSO do not update `_last_emitted_pct`. Otherwise, when the gate re-opens, we'd compare against a value we never actually told event-store about. This is the same invariant `CoachLedger` uses for its `_last_drift_bucket`.
- **Comfort score formula:** `1.0 - occupancy_pct`, clamped to `[0.0, 1.0]`. Simple. Matches the shipped payload contract.

### Decisions Resolved Without Party-Mode

This story follows precedents already set by 4-9's roundtable. If any of the following turn out wrong, re-open in a focused checkpoint:

- **No new ingest endpoint.** Reuses 4-9's `/candidates/occupancy_update`. Two consumers per handler is fine (door_obstruction → ledger pattern not yet established, but this is the natural extension).
- **Use shipped payload shape, not epic spec.** Same reasoning as 4-9 D3: shipped contract wins over stale epic spec.
- **No operator-visible alert.** COACH_COMFORT_INDEX is informational telemetry for the dashboard analytics tab — no alert panel, no escalation, no operator action gating. Severity = `info`.

### Lessons Applied from 4-9

- **Cold-start gating (4-9's `both_seeded`):** AC4 mirrors this — first OCCUPANCY for a coach seeds state without emitting.
- **State-update only on successful emit (4-9 AC5/AC8 pattern):** AC5 invariant — under suppression, do not update `_last_emitted_pct`.
- **`/candidates/*` 202 fail-safe pattern:** Downstream emit failures must not break the handler's 202 response.

### Test Patterns

- `respx.mock` for HTTP assertions
- `structlog.testing.capture_logs` for log assertions
- `pytest-asyncio` `@pytest.mark.asyncio` for async tests
- `Settings(comfort_index_pct_threshold=0.05)` for tighter test thresholds where useful

### Quality Gate Command

```bash
cd fusion
pytest --strict-markers --cov=src/fusion --cov-fail-under=90 -q
mypy --strict src/
ruff check src/ tests/
```

### Project Structure Notes

- New file: `fusion/src/fusion/comfort_index.py` (alongside `enrichment.py`, `suppression.py`, `ledger.py` from 4-9)
- New test: `fusion/tests/unit/test_comfort_index.py`
- No new endpoints, no `docker-compose.dev.yml` change, no `shared/` change.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#E4-S10] — original epic spec (superseded by D1–D5 above on payload shape)
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-15] — camera-authoritative counting; comfort_score is derived from occupancy_pct, not from reservations
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-18] — comfort index belongs to fusion
- [Source: _bmad-output/implementation-artifacts/4-9-closed-ledger-reconciliation.md] — predecessor; provides `/candidates/occupancy_update` ingest, `ComfortIndexState` follows same `_last_emitted_pct` / suppression-invariant patterns
- [Source: shared/src/oebb_shared/events/payloads.py:397] — `CoachComfortIndexPayload` (shipped contract — DO NOT change)
- [Source: shared/src/oebb_shared/events/payloads.py:51] — `OccupancyUpdatePayload` (input shape)
- [Source: fusion/src/fusion/context_state.py:106] — `observe_ramp_signal` (pattern to mirror for `observe_station_approach_edge`)
- [Source: fusion/src/fusion/health.py] — `/candidates/*` handler pattern
- [Source: fusion/src/fusion/enrichment.py] — `emit_envelope` POST pipeline

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (bmad-dev-story workflow), 2026-05-21.

### Debug Log References

- One ruff `I001` fix (import ordering after `json` was inserted between `from __future__` and the rest of the imports in `test_health.py`).

### Completion Notes List

- **AC1** — `on_occupancy_update` returns a payload only when `|occupancy_pct − _last_emitted_pct[car_id]| > pct_threshold`. Strict greater (`> threshold`); delta exactly at threshold does not emit (pinned by `test_delta_exactly_at_threshold_no_emit`). Baseline advances only on emit.
- **AC2** — `/context` handler calls `ctx.observe_station_approach_edge()`; on `True`, dispatches `comfort.on_station_approach_edge()` and emits each returned payload through the standard `gate → emit_envelope` pipeline.
- **AC3** — `CoachComfortIndexPayload` is the shipped shape (D1). `comfort_score = max(0.0, min(1.0, 1.0 − occupancy_pct))`; `temperature_c=None`, `noise_db=None` (D2/D3).
- **AC4** — First OCCUPANCY for a coach seeds `_last_emitted_pct` and `_observed_coaches`, returns `None`. Pinned by `test_first_occupancy_seeds_baseline_no_emit`.
- **AC5** — Under suppression, the handler skips the call to `comfort.on_occupancy_update` entirely, so `_last_emitted_pct` is not advanced. Side-effect: a coach first observed during a suppression window won't appear in `_observed_coaches` until the gate re-opens — explicit comment in `health.py`. This is the conservative interpretation: no telemetry escapes, and `_observed_coaches` matches the set of coaches the system has actually published comfort signals for.
- **AC6** — Handled by `Enrichment._build_envelope` returning `None` when `ctx.journey_id is None` (existing behaviour); no change needed in this story.
- **AC11** — `pytest --cov=src/fusion --cov-fail-under=90` → 139 passed (121 baseline + 18 new), **94.03%** cov. `mypy --strict src/` clean. `ruff check src/ tests/` clean.

### File List

**Added:**
- `fusion/src/fusion/comfort_index.py`
- `fusion/tests/unit/test_comfort_index.py`

**Modified:**
- `fusion/src/fusion/config.py` — added `comfort_index_pct_threshold` (ge=0.0, le=1.0)
- `fusion/src/fusion/context_state.py` — added `_prev_station_approach` field + `observe_station_approach_edge()` method
- `fusion/src/fusion/health.py` — added `comfort` param to `build_app`; extended `/candidates/occupancy_update` with comfort emit; extended `/context` with station-approach-edge dispatch
- `fusion/src/fusion/main.py` — construct + pass `ComfortIndexState` in lifespan
- `fusion/tests/unit/test_health.py` — `_make_client` passes comfort; 5 new tests (delta emit, suppression, 202-on-failure, station-edge multi-coach, station-edge steady-state)
- `fusion/tests/unit/test_security.py` — `comfort_index.py` added to MODULES scan
- `fusion/tests/unit/test_context.py` — added `test_observe_station_approach_edge_trigger`
- `fusion/tests/contract/test_candidate_payload_contract.py` — fixture passes comfort
- `fusion/tests/integration/test_fusion_pipeline.py` — fixture passes comfort

### Change Log

- 2026-05-21 — Implemented Coach Comfort Index per Story 4-10 D1–D5. Added `ComfortIndexState` with delta-driven emit (AC1) and station-approach-edge multi-coach emit (AC2). Reused 4-9's `/candidates/occupancy_update` ingest path. Shipped `CoachComfortIndexPayload` shape (D1) with `temperature_c`/`noise_db=None` (D2). Suppression skips both emit and baseline advance (AC5 invariant). 139 fusion tests, fusion cov 94.03%, mypy/ruff clean. Inference (149) + shared (130) unaffected.
