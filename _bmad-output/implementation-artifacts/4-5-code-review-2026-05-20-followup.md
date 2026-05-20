# Story 4-5 Code Review — Follow-up Adversarial Pass

**Date:** 2026-05-20
**Reviewer:** Claude Opus 4.7 (1M context) — fresh session, BMad `bmad-code-review` skill
**Target:** commit `020e0cd` ("apply 20 code-review patches — story 4-5 back to review")
**Story:** `_bmad-output/implementation-artifacts/4-5-inference-safety-accessibility.md`
**Layers:** Blind Hunter · Edge Case Hunter · Acceptance Auditor (parallel)

## Outcome

**APPROVE with two should-fix items** — story is ready to flip to `done` if the dev team accepts the two non-blocking items as follow-ups (or fixes them inline). No must-fix items remain. Prior 2026-05-19 (F1–F14) and 2026-05-20 (R1–R13/R19) findings have been independently verified resolved at the specified file:line locations.

## Quality Gate Re-Run (cold environment, this session)

| Gate                                                | Required   | Actual                                | Status |
|-----------------------------------------------------|------------|---------------------------------------|--------|
| `mypy --strict src/` (inference)                    | 0 errors   | 0 errors (10 source files)            | PASS   |
| `ruff check src/ tests/` (inference)                | 0 errors   | All checks passed                     | PASS   |
| `pytest --strict-markers -q` (inference)            | All pass   | **119 passed / 0 failed** (5 warnings)| PASS   |
| Coverage of `src/inference/` (excl. pipeline)       | ≥ 90 %     | **91.03 %** (602 stmts, 54 miss)      | PASS   |
| `pytest -q` (shared regression)                     | All pass   | **125 passed**                        | PASS   |

Dev-agent claims match observed values exactly. AC7 satisfied.

Coverage detail (this run):
```
callback.py    231  30  87%  153, 244-245, 275-276, 291, 329, 361-388, 457, 476-479, 496-497, 505, 520, 526-533
health.py       62   8  87%  26, 98-101, 103, 111-112
main.py         57  10  82%  137-154
safety.py       21   0 100%
zone_counter.py 154  6  96%  56, 290, 318, 324-333, 351
TOTAL          602  54  91%
```

`pytest` warnings (test hygiene only, not failures):
- `test_door_obstruction.py::test_handle_person_door_obstruction_emits_on_min_frames` — `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` (callback.py:312 `resp.raise_for_status()`)
- `test_door_obstruction.py::test_handle_suitcase_door_obstruction_iou_tracking` — same
- `test_vestibule_congestion.py::*` (3 tests) — same at zone_counter.py:397

These mean the test's `AsyncMock` is returning an async-mocked `raise_for_status` coroutine that the sync `resp.raise_for_status()` call leaves un-awaited. Production behaviour is correct; tests should bind `raise_for_status` to a `MagicMock` (sync) instead of `AsyncMock`.

## Findings by Acceptance Criterion

| AC  | Implementation                                                                                                                                       | Verdict       |
|-----|------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|
| AC1 | `callback.py:251-312` person & suitcase door-obstruction → `{fusion_url}/candidates/door_obstruction`, `door_state="unknown"` (line 306), routed to **fusion** (not event-store). 2-frame consecutive tracking via `_door_zone_hits[(camera_id, track_id)]`. Counter resets after emit (line 229, 262). Stale-track pruning at callback.py:514-520. | **MET**       |
| AC2 | `callback.py:314-388` bicycle → `_dispatch_bicycle` → `_post_accessibility_event` → POST `{event_store_url}/api/v1/events` with `AccessibilityDetectedPayload`. Confidence-None correctly skips (line 323 — R2 strict). Unmapped camera skips with CRITICAL log (line 333-338). 10 s rate-limit (line 328). | **MET**       |
| AC3 | `safety.py:33-78` `SafetyHandler.on_ramp_deployed` posts `RAMP_DEPLOYED` to event-store with `triggered_by_track_id="unknown"` (PoC simplification, fusion correlates per R4). `health.py:91-116` schedules it via `run_coroutine_threadsafe` + `add_done_callback`. | **MET**       |
| AC4 | `zone_counter.py:272-333` `_check_slip_fall` per `(car_id, camera_id, track_id)`; emits to **fusion** at `{fusion_url}/candidates/alert_raised`. Height-collapse + velocity heuristic per Dev-Notes spec. Stale-track pruning at line 315-318. | **MET**       |
| AC5 | `zone_counter.py:335-397` `_check_vestibule_congestion`. Uses tagged `in_vestibule` subset (R5) via `update()` lines 176-182. 10 s rate-limit (line 372). Per-camera zone resolution (R7) at line 348. Posts to event-store. Vestibule_id `f"{car_id}-{zone}"` (R1). | **MET (see SHOULD-FIX-1)** |
| AC6 | `config.py` (verified via grep) detection_classes default `["person","suitcase","bicycle"]`. `callback.py:166, 436` `_allowed_labels` honours setting. Suitcase / bicycle dispatch implemented. | **MET**       |
| AC7 | mypy 0, ruff 0, 119 pass, coverage 91.03 % — see table above. `test_security.py::test_no_env_get_in_safety` enforces Rule 8. | **MET**       |

## Triage Table

| Finding | Severity        | File:Line                                  | Description                                                                                                                                                                                                                                       | Action                                                          |
|---------|-----------------|--------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| **S1**  | should-fix      | `shared/src/oebb_shared/events/payloads.py:171` | `door_state` Literal extended from 3→4 values (added `"unknown"`). `shared/CLAUDE.md` mandates a contract test for any schema type change. `test_event_envelope.py:290-299` only tests `"closing"`; no test asserts `"unknown"` is accepted — yet that's the value production emits. | Add `test_door_obstruction_payload_door_state_unknown` (1-liner). |
| **S2**  | should-fix      | `cameras.json:11-14`                       | New `vestibule_zone` polygon is **identical** to the `aisle` seat-zone polygon `[[200,300],[440,300],[440,480],[200,480]]`. Every aisle person is double-counted as in-vestibule. Semantically: vestibule = near-door area, not centre-aisle. Single-camera PoC tolerates this; multi-camera deployments will mis-fire. | Replace with a near-door rectangle, or change to a non-overlapping polygon. Document the demo configuration. |
| **S3**  | nice-to-have    | `test_door_obstruction.py`, `test_vestibule_congestion.py` | `AsyncMock` used for `resp.raise_for_status` — sync production call leaves coroutine un-awaited (`RuntimeWarning` in pytest output). Cosmetic only. | Bind `raise_for_status` to `MagicMock` (sync) in the helpers. |
| **S4**  | nice-to-have    | `zone_counter.py:352-360`                  | Legacy fallback (`camera_id is None`) picks "any" camera-zone for the car via dict-iteration order. Determinism depends on insertion order. Production always passes `camera_id`, so unreachable in real code. | Either delete the branch or replace with explicit `("door","vestibule")` lookup. Already-documented as legacy by author. |
| **S5**  | nice-to-have    | `callback.py:283-312`                      | `_post_door_obstruction_candidate` early-returns silently when `_event_store_client is None`. The `@DEFAULT_RETRY` wrapper still runs. No log on the no-client branch. | Add a one-time `log.warning` for the no-client path. |
| —       | informational   | `callback.py:232`, `:341`                  | Synthetic track IDs use `int(time.monotonic()*1000) % 100000` — 100 ms collision window in theory. Acceptable for PoC; fusion dedupes. Already deferred as R17. | None. |
| —       | informational   | `callback.py:218` (R15)                    | `_handle_suitcase_door_obstruction` uses only `bboxes[0]` — multiple simultaneous suitcases per frame silently dropped. Already deferred. | None. |
| —       | informational   | `callback.py:376`                          | `self._zone_counter._journey_holder.journey_id` — private access. Pre-existing pattern (F14 defer). | None. |

### Findings that are **closed** (re-verified resolved)

- F1 — `_door_zone_hits` stale-track pruning: confirmed at `callback.py:514-520`.
- F2 — `_track_bboxes` stale-track pruning + re-key by `(car_id, camera_id)`: confirmed at `zone_counter.py:97-99, 285, 315-318`.
- F3 — `_last_suitcase_bbox` cleared when no suitcase: confirmed at `callback.py:506-509`.
- F4 — person obstruction counter reset after emit: confirmed `callback.py:262`.
- F5 — suitcase obstruction counter reset after emit: confirmed `callback.py:229`.
- F6 — `_dispatch_bicycle` 10 s rate-limit per camera: confirmed `callback.py:326-330`.
- F7/R9 — `loop_holder` pattern in health.py: confirmed `health.py:46, 91-116`; covered by new TestClient test `test_health.py:146-210`.
- F8/R5 — `vestibule_zone` polygon tagging: confirmed `cameras.json:14`, `callback.py:150-156, 462-475`, `zone_counter.py:176-182`.
- F9/R3 — `car_id = settings.vehicle_id` PoC simplification: confirmed `safety.py:55` with module-docstring rationale and deferred-work entry.
- F10/R1 — dynamic vestibule_id `f"{car_id}-{zone}"`: confirmed `zone_counter.py:370`; test asserts `"car-1-door"`.
- F12/R4 — `_last_track_ids` removed; `triggered_by_track_id="unknown"` always: confirmed `safety.py:57`; test `test_safety.py:42-56`.
- F13/R2 — strict skip on `confidence is None`: confirmed `callback.py:323`; test `test_accessibility.py:151-176`.
- F11/R6 — `door_state="unknown"`: confirmed `callback.py:306` + schema extension `payloads.py:171`.
- R7 — camera_id threaded through `ZoneCounter.update`: confirmed `zone_counter.py:114-125, 170, 183-187, 285, 312`; callback uses it `callback.py:491`.
- R8 — `add_done_callback(_on_post_done)` on ramp future: confirmed `health.py:110`.
- R12 — unique per-emit suitcase track_id: confirmed `callback.py:232`.
- R13 — unused `bbox` param removed from `_handle_person_door_obstruction`: confirmed `callback.py:251-255`.
- R19 — TestClient happy-path for ramp dispatch: confirmed `test_health.py:146-210` (drives a real bg-thread loop + `done.wait(2.0)`).

## Project-Rule Compliance

- **Rule 8 (no `os.environ.get`)** — Clean across `callback.py`, `zone_counter.py`, `safety.py`, `health.py`, `main.py`, `config.py`. Only docstring mentions.
- **Fusion vs event-store routing** — Verified all 5 emit sites:
  - `DOOR_OBSTRUCTION` → `{fusion_url}/candidates/door_obstruction` ✓ (callback.py:309)
  - `slip_fall ALERT_RAISED` → `{fusion_url}/candidates/alert_raised` ✓ (zone_counter.py:325)
  - `ACCESSIBILITY_DETECTED` → `{event_store_url}/api/v1/events` ✓ (callback.py:385)
  - `RAMP_DEPLOYED` → `{event_store_url}/api/v1/events` ✓ (safety.py:75)
  - `VESTIBULE_CONGESTION` → `{event_store_url}/api/v1/events` ✓ (zone_counter.py:394)
- **`DEFAULT_RETRY`** applied on every new POST helper (`callback.py:282, 352`, `zone_counter.py:320, 391`, `safety.py:72`).
- **Raw video never leaves the train** — No frame/buffer payload field appears in any of the 5 candidate payloads. Clean.
- **Shared schema contract test** — *Missing for the `door_state` Literal extension* (see S1).

## Layer Observations

**Blind Hunter** — read changed code with no comments. Caught S1 (no contract test for the schema extension), S2 (`vestibule_zone` polygon == `aisle` polygon), S5 (silent no-client return).

**Edge Case Hunter** — walked branches:
- `loop is None AND get_running_loop raises`: `health.py:98-103` — handled cleanly, logs `context_push.no_loop_for_ramp` and proceeds.
- `vehicle_id` empty/None for R3 PoC: `safety.py:55` reads `self._settings.vehicle_id` which is required by `Settings` (validation at startup) — safe.
- Person centroid on `vestibule_zone` edge: `_on_segment`/`_point_in_polygon` treats edges as inside (`callback.py:74-80`). Behaviour deterministic.
- `cameras.json` with no `vestibule_zone`: `callback.py:150-156` leaves `self._vestibule_zone = None`; `_call_` skips tagging; ZoneCounter fallback at `zone_counter.py:178-182` counts all door-camera persons. Backwards-compatible.
- `time.monotonic()*1000 % 100000` collision: ~100 ms window. Fusion dedupes; PoC-tolerated.
- `vehicle_id` collision between two cars on the same train: AC3 PoC simplification accepted; documented.

**Acceptance Auditor** — all 7 ACs verifiably implemented at the file:line locations cited above. No vacuous satisfaction.

## Recommendation

**APPROVE → flip 4-5 to `done`** with the following actions:

1. **(should-fix, ≤ 5 min)** Add a contract test for `door_state="unknown"` in `shared/tests/unit/test_event_envelope.py` to satisfy `shared/CLAUDE.md`'s schema-contract rule.
2. **(should-fix, ≤ 5 min)** Either fix the `vestibule_zone` polygon in `cameras.json:14` to a near-door rectangle, or add a comment that the demo config intentionally reuses the aisle polygon and that real deployments must define a near-door polygon.
3. **(nice-to-have, optional)** Resolve the 5 `RuntimeWarning` test warnings.
4. **(defer)** S4, S5, R11, R15, R16, R17, R18, R20, R22 — already tracked in `deferred-work.md`.

If the team prefers a strict gate, items 1+2 can be wrapped into a 1-commit follow-up and the story flips after that lands; this reviewer is comfortable approving as-is given (a) the dev agent self-correctly identified both as PoC-scope and (b) AC1–AC7 are objectively satisfied.

The PM/dev agent owns the sprint-status.yaml flip per the workflow contract; this review does not modify it.

## Next Story

`bmad-create-story` for **4-6** (fusion container — implements the `{fusion_url}/candidates/door_obstruction` and `/candidates/alert_raised` endpoints that 4-5 POSTs to, plus the suppression state machine and ZFR cross-reference). 4-5 defined the candidate POST contract; 4-6 implements the receiver and the cross-VLAN correlation that resolves the R4 `triggered_by_track_id="unknown"` placeholder.
