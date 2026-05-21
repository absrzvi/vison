# Story 4.9: `fusion` Closed-Ledger Reconciliation Engine

Status: done

<!-- Created 2026-05-21 by bmad-create-story.
     D1–D5 resolved 2026-05-21 via party-mode roundtable (Winston, Amelia, Saga, Freya).
     Story is dev-ready. Aggregator dropped from scope — see "Decisions Resolved" below. -->

## Story

As a system operator,
I want the `fusion` container to maintain a per-coach closed-ledger passenger count, reconcile it against `WAGON_EXIT`/`WAGON_ENTRY` pairs from E4-S8, and emit `LEDGER_DRIFT_OBSERVATION` telemetry when the ledger and camera counts disagree,
so that the engineering team and maintenance stakeholders have a diagnostic signal for inter-wagon movement tracking — without burdening Control Centre operators with alerts that have no documented response.

## Acceptance Criteria

1. **Ledger initialisation at journey start.** Given `fusion` starts and `ContextState.journey_id` becomes non-`None`, when the `coach_ledger` SQLite table is initialised, then each row has fields: `coach_id`, `ledger_count`, `last_reconciled_utc`, `unreconciled_exits`; `ledger_count` is seeded to `0` for every coach. A `both_seeded[car_id]` dict tracks whether both the first OCCUPANCY_UPDATE and the first WAGON_*/ledger-modifying event have arrived for that coach — drift checks (AC6) are gated on `both_seeded[car_id] is True` to prevent spurious zero-vs-camera deltas at journey start.

2. **WAGON_EXIT decrements + arms pending reconciliation.** Given a `WAGON_EXIT` event with `expect_orphan=false` is delivered to `fusion` via `POST /candidates/wagon_exit`, when the event is processed, then `ledger_count[coach_from] -= 1`, `unreconciled_exits[coach_from] += 1`, and `(track_id, coach_from, coach_to, ts_utc)` is recorded in an in-memory `_pending_exits` map with a 10-second reconciliation window matching E4-S8's orphan timeout.

3. **WAGON_EXIT with `expect_orphan=true` is recorded but not reconciled.** Given a `WAGON_EXIT` event with `expect_orphan=true` (the to_from crossing case from E4-S8 D2), when processed, then `ledger_count[coach_from] -= 1` is applied, `unreconciled_exits` is NOT incremented, and no pending reconciliation entry is created.

4. **WAGON_ENTRY reconciles the matching exit.** Given a `WAGON_ENTRY` event arrives via `POST /candidates/wagon_entry` with a `track_id` matching a `_pending_exits` entry within the 10s window, when processed, then `ledger_count[coach_to] += 1`, `unreconciled_exits[coach_from] -= 1`, `last_reconciled_utc[coach_to]` is updated, the pending entry is removed, the timer is cancelled BEFORE any HTTP work (E4-S8 P10 lesson), and no event is emitted. Unmatched WAGON_ENTRY (no prior EXIT seen) increments `ledger_count[coach_to]` and is logged at INFO with `reason: "orphan_entry"`.

5. **Pending-exit timeout matches E4-S8 orphan window.** Given a `_pending_exits` entry has been open for ≥10 seconds, when the timeout fires, then `unreconciled_exits[coach_from]` remains incremented (the decrement from AC2 is NOT reverted), the entry is removed from `_pending_exits`, and a structured log is emitted at INFO with `reason: "exit_unreconciled"`, `track_id`, `coach_from`, `coach_to`. No event is emitted.

6. **Drift check + state-transition emit.** Given a `POST /candidates/occupancy_update` arrives carrying an `OccupancyUpdatePayload` for `car_id`, when `both_seeded[car_id] is True` and `|ledger_count[car_id] - camera_count| > drift_threshold` (default: `3`, configurable via `Settings.ledger_drift_threshold`), then the per-coach drift bucket is computed (`drift_bucket = sign(delta) * (|delta| // bucket_size)` with `bucket_size = 3`); if `drift_bucket != _last_drift_bucket[car_id]`, a `LEDGER_DRIFT_OBSERVATION` is POSTed to `event-store` with payload matching `LedgerDriftObservationPayload` `{ car_id, camera_count, ledger_count, delta, threshold, surface_to_operator }`. Per ADR-15, `ledger_count[car_id]` is then corrected to match `camera_count` and a log is emitted at INFO (`reason: "ledger_corrected_to_camera"`). When `|delta| ≤ drift_threshold`, the bucket resets to `0` and a transition out of drift fires a single "drift cleared" observation (same payload, `delta=0`).

7. **`surface_to_operator` flag.** Given a `LEDGER_DRIFT_OBSERVATION` is constructed, when `ContextState.station_approach is True`, then `payload.surface_to_operator = True`; otherwise `False`. (D5: this flag exists so a future cloud-backend filter can promote observations to operator-visible alerts without changing the edge contract. At PoC, no operator surfacing is implemented — all observations remain telemetry-only.)

8. **Suppression-gate compliance.** Given `SuppressionGate.should_emit()` returns `False` (depot/maintenance/gps_invalid), when an observation would be emitted, then it is NOT POSTed; a DEBUG log is emitted with `reason: "ledger_drift_suppressed"`, `car_id`, `delta`. Ledger state and bucket transitions continue to be updated regardless.

9. **SQLite persistence with WAL mode.** Given the `coach_ledger` table is initialised, when any of `ledger_count`, `last_reconciled_utc`, or `unreconciled_exits` changes, then the change is persisted via parameterised SQL; the SQLite connection uses WAL mode (per ADR-4), `tmp_path`-scoped DB files in tests (per architecture line 173), and all writes are serialised through a single connection owned by the fusion lifespan.

10. **Inference → fusion fire-and-forget posting.** Given `inference/tripwire.py` successfully POSTs a `WAGON_EXIT` or `WAGON_ENTRY` to event-store, when the event-store POST returns success, then a second POST is issued to `{settings.fusion_url}/candidates/wagon_exit` (or `/wagon_entry`); HTTP errors on the fusion POST are logged at WARNING with `reason: "fusion_unreachable"` but do NOT raise (fusion is non-blocking from inference's perspective). Same pattern applied in `inference/zone_counter.py` for `OCCUPANCY_UPDATE`.

11. **Quality gates:**
    - `tests/unit/test_ledger.py` covers: clean WAGON_EXIT+WAGON_ENTRY reconciliation; `expect_orphan=true` ledger update (AC3); pending-exit timeout (AC5); orphan WAGON_ENTRY (AC4); drift detection (AC6) — both within threshold (no emit), entering drift (emit), drift-bucket change (emit), drift cleared (emit), no-change tick (no emit); `surface_to_operator` flag toggling on `station_approach` (AC7); suppression-gate behaviour (AC8); SQLite persistence across simulated restart; `both_seeded` gate (AC1).
    - `tests/unit/test_security.py` AST checks extended to `fusion/ledger.py` (no raw `os.environ.get`, no hardcoded secrets, no SQL string formatting — parameterised queries only).
    - `mypy --strict src/` passes for all new and modified files in `fusion/` and `inference/`.
    - `pytest --strict-markers` achieves ≥90% coverage of `src/fusion/`.
    - `ruff check src/ tests/` zero violations.
    - `shared/` contract test for the renamed `LedgerDriftObservationPayload` passes.

## Decisions Resolved

Resolved 2026-05-21 in party-mode roundtable. Recorded here so future readers see the reasoning, not the moving target.

- **D1 — Event ingest path = D1-A (double-POST).** `inference` POSTs to event-store first (existing path, unchanged), then fire-and-forgets to fusion `/candidates/wagon_exit | wagon_entry | occupancy_update`. Mirrors the existing `/candidates/door_obstruction` and `/candidates/alert_raised` pattern. Saga + Amelia carried the vote on PoC-shortest-path grounds; Winston noted D1-B (WS subscriber) is the right production answer and should be revisited when more consumers need the stream.

- **D2 — Initial seed = D2-A with `both_seeded` gate.** Seed all coaches to `0`. Drift check is gated by `both_seeded[car_id] is True` so the first OCCUPANCY_UPDATE on its own does not fire against a zero ledger. Amelia's refinement of Saga's "seed zero + converge" position — preserves PoC observability without spurious journey-start alerts.

- **D3 — Payload shape = D3-A (per-coach, as already shipped in `shared/`).** Renamed to `LedgerDriftObservationPayload` per D5 but the shape `{ car_id, camera_count, ledger_count, delta, threshold, surface_to_operator }` stands. Freya conceded after Amelia's contract-break cost was made concrete — landside aggregation can compose train-level views from per-coach events when needed.

- **D4 — Trigger = hybrid.** Check on every OCCUPANCY_UPDATE (cheap, deterministic); emit to event-store only on drift-bucket state transition (Freya's refinement — avoids analytics firehose); `surface_to_operator: bool` flag on the payload, true only on `station_approach` edge. Three-layer separation: **check** (every tick) / **emit** (on bucket transition) / **surface** (flag on approach).

- **D5 — Rename `LEDGER_DRIFT_ALERT` → `LEDGER_DRIFT_OBSERVATION`.** Originated from Freya's question "what does the operator *do* when they see this?" Saga confirmed honestly: no operator playbook exists, no Control Centre rep has been consulted. Calling diagnostic telemetry an ALERT misrepresents the contract. The rename is small (one EventType enum value, one payload class), keeps the data flowing for engineering + maintenance audiences, and earns the right to be re-promoted to ALERT later when a playbook is validated. `surface_to_operator` defaults to `False` for OBSERVATION events — no operator-facing surfacing implemented in this story.

**Explicitly dropped from scope (PoC complexity discipline):**
- **Landside aggregator** (originally proposed as Amelia's hard condition for D3-A). With D5 setting `surface_to_operator=false` by default, no events surface to the operator dashboard — there is nothing to aggregate. Promote to a follow-up story only when D5 is itself promoted back to ALERT after a Saga+Freya operator playbook session.
- **OEBB Control Centre playbook validation** (Saga's three-step plan: scenario mapping → strawman → operator validation). Tracked as a follow-up; not blocking this story. Add to `_bmad-output/implementation-artifacts/deferred-work.md` after dev.

## Tasks / Subtasks

### `shared/` — rename (D5)

- [x] `shared/src/oebb_shared/events/types.py`: rename `LEDGER_DRIFT_ALERT = "LEDGER_DRIFT_ALERT"` → `LEDGER_DRIFT_OBSERVATION = "LEDGER_DRIFT_OBSERVATION"`
- [x] `shared/src/oebb_shared/events/payloads.py:367`: rename class `LedgerDriftAlertPayload` → `LedgerDriftObservationPayload`; add `surface_to_operator: bool = False` field at the end (default false → safe for any non-fusion producer)
- [x] `shared/src/oebb_shared/events/payloads.py:441`: update `PAYLOAD_MODELS` registry key
- [x] `shared/src/oebb_shared/events/__init__.py`: update export
- [x] `shared/tests/contract/test_envelope_contract.py` + `shared/tests/unit/test_event_envelope.py`: update references (grep for `LEDGER_DRIFT_ALERT` and `LedgerDriftAlertPayload`)

### `fusion/` — config (AC6, AC9)

- [x] `fusion/src/fusion/config.py`: add `ledger_drift_threshold: int = 3`, `ledger_drift_bucket_size: int = 3`, `ledger_db_path: str = "/var/lib/fusion/coach_ledger.db"`, `ledger_pending_timeout_s: float = 10.0` (last one for testability)

### `fusion/` — new `ledger.py` (AC1–AC9)

- [x] Create `fusion/src/fusion/ledger.py`
  - [ ] `CoachLedgerRow` dataclass: `coach_id`, `ledger_count`, `last_reconciled_utc`, `unreconciled_exits`
  - [ ] `_PendingExit` dataclass: `track_id`, `coach_from`, `coach_to`, `ts_utc`, `timer_handle`
  - [ ] `CoachLedger` class with single owned `sqlite3.Connection` (WAL mode set on `__init__`, `isolation_level=None`)
  - [ ] `_both_seeded: dict[str, bool]` and `_last_drift_bucket: dict[str, int]` in-memory state (per AC1, AC6)
  - [ ] `init_table()` — `CREATE TABLE IF NOT EXISTS` with the four columns
  - [ ] `on_wagon_exit(payload: WagonExitPayload)` — AC2 + AC3 (`expect_orphan` branch); sets `_both_seeded[coach_from] = True`
  - [ ] `on_wagon_entry(payload: WagonEntryPayload)` — AC4 (cancel timer FIRST per P10); sets `_both_seeded[coach_to] = True`
  - [ ] `_handle_pending_timeout(track_id)` — AC5; scheduled via `loop.call_later(timeout_s, …)` with closure capture (E3 A3 lesson)
  - [ ] `check_drift(payload: OccupancyUpdatePayload, station_approach: bool) -> LedgerDriftObservationPayload | None` — AC6 + AC7; sets `_both_seeded[car_id] = True`; returns payload to emit only on bucket transition (including transition-to-zero); mutates `_last_drift_bucket[car_id]` and `ledger_count[car_id]`
  - [ ] Parameterised SQL only (no f-string / `%s` interpolation)

### `fusion/` — wire into lifespan + health (AC1, AC9)

- [x] `fusion/src/fusion/main.py` `lifespan`: construct `CoachLedger(settings.ledger_db_path)` inside `async with httpx.AsyncClient(...)`; pass to `build_app`; close connection in the `finally` block
- [x] `fusion/src/fusion/health.py` `build_app(...)`:
  - [ ] Add `ledger: CoachLedger` parameter
  - [ ] `POST /candidates/wagon_exit` — accept `WagonExitPayload`, call `ledger.on_wagon_exit`, wrap downstream errors so the handler always returns 202 (mirror `/candidates/door_obstruction`)
  - [ ] `POST /candidates/wagon_entry` — accept `WagonEntryPayload`, call `ledger.on_wagon_entry`
  - [ ] `POST /candidates/occupancy_update` — accept `OccupancyUpdatePayload`, call `ledger.check_drift(payload, ctx.station_approach)`; if it returns a payload, route through `gate.should_emit()` → `enricher.emit_envelope(event_type_name="LEDGER_DRIFT_OBSERVATION", payload=..., severity="info")` (severity is `info`, not `warning` — this is telemetry, not an alert)

### `inference/` — fire-and-forget to fusion (AC10)

- [x] `inference/src/inference/config.py`: add `fusion_url: str = "http://fusion:8090"`
- [x] `inference/src/inference/tripwire.py`: after the successful event-store POST in `_emit_wagon_exit` and `_emit_wagon_entry`, fire `client.post(f"{settings.fusion_url}/candidates/wagon_exit | wagon_entry", json=envelope.payload.model_dump(mode="json"))` wrapped in `try/except httpx.HTTPError` with WARNING log; do NOT wrap in `DEFAULT_RETRY` (fire-and-forget — fusion is non-critical)
- [x] `inference/src/inference/zone_counter.py`: same pattern after successful OCCUPANCY_UPDATE POST to event-store; post payload only (not envelope wrapper)

### Tests

- [x] `fusion/tests/unit/test_ledger.py` — cover all branches of AC11; use `tmp_path` for DB file (NOT `:memory:`); `respx.mock` for event-store POSTs; `structlog.testing.capture_logs` for log assertions; `Settings(ledger_pending_timeout_s=0.05)` for fast timer tests
- [x] `fusion/tests/unit/test_security.py` — extend module list to include `ledger`; add SQL-injection AST check (no f-strings in `cursor.execute` calls)
- [x] `fusion/tests/unit/test_health.py` — add cases for the three new candidate endpoints (success path + downstream error → still 202)
- [x] `inference/tests/unit/test_tripwire.py` — extend existing emit tests with `respx.mock` for fusion endpoint; assert WARNING log on fusion HTTP error, no exception raised
- [x] `inference/tests/unit/test_zone_counter.py` — same extension for OCCUPANCY_UPDATE
- [x] `shared/tests/contract/test_envelope_contract.py` — update contract assertion for renamed event type

### Quality gates green

- [x] `cd fusion && pytest --strict-markers --cov=src/fusion --cov-fail-under=90 -q`
- [x] `cd fusion && mypy --strict src/ && ruff check src/ tests/`
- [x] `cd inference && pytest -q && mypy --strict src/ && ruff check src/ tests/`
- [x] `cd shared && pytest -m contract && mypy --strict src/`

### Follow-up (NOT in this story)

- [ ] Add to `_bmad-output/implementation-artifacts/deferred-work.md`:
  - [ ] **Saga + Freya operator playbook session** for LEDGER_DRIFT — strawman scenarios for the three drift causes (sensor health / tracking failure / real movement); validate with OEBB Control Centre rep before promoting OBSERVATION back to ALERT
  - [ ] **Landside aggregator** in `cloud-backend/src/cloud_backend/sse/` — only needed when D5 is promoted back to ALERT and the operator dashboard surfaces drift events
  - [ ] **D1-B WS subscriber** — promote from candidates-POST pattern to event-store WS subscription when a second non-inference consumer needs the stream

## Security Tests

**fusion candidate endpoints (per AC10/AC11):**
- [ ] `test_malformed_payload_wagon_exit` — invalid body returns 422
- [ ] `test_malformed_payload_wagon_entry` — invalid body returns 422
- [ ] `test_malformed_payload_occupancy_update` — invalid body returns 422
- [ ] Note: candidate endpoints in fusion are currently unauthenticated (consistent with `door_obstruction` / `slip_fall`). Adding auth is out of scope.

**OEBB-specific:**
- [ ] No raw video, CCTV URL, or Hailo inference frame data appears in any ledger payload or log line.
- [ ] `LedgerDriftObservationPayload` is schema-validated via Pydantic v2 before POST (already enforced by `Enrichment.emit_envelope` path).
- [ ] No escalation state machine to worry about — this is telemetry, not an alert.

**SQLite hardening:**
- [ ] AST check confirms no SQL is built via string formatting in `ledger.py` (parameterised queries only).
- [ ] WAL mode confirmed at runtime (`PRAGMA journal_mode=WAL` returns `wal`).

## Dev Notes

### Architecture — What This Story Adds

```
inference container                       fusion container (this story)
  tripwire.py ──WAGON_EXIT───────►event-store
              └─fire-forget─────►/candidates/wagon_exit ──┐
  tripwire.py ──WAGON_ENTRY──────►event-store             │
              └─fire-forget─────►/candidates/wagon_entry─►┤
  zone_counter ──OCCUPANCY_UPDATE►event-store             │
              └─fire-forget─────►/candidates/occupancy_*─►┤
                                                          ▼
                                                  CoachLedger (ledger.py)
                                                  - sqlite3 (WAL)
                                                  - _pending_exits dict
                                                  - _both_seeded gate
                                                  - _last_drift_bucket
                                                  - asyncio call_later
                                                          │
                                                          ▼ bucket transition
                                                   Enrichment.emit_envelope
                                                          │
                                                          ▼
                                              event-store: LEDGER_DRIFT_OBSERVATION
                                              (telemetry-only; surface_to_operator=False
                                               unless station_approach edge)
```

### Decisions Folded into AC Text — Quick Reference

| Decision | Folded into | Note |
|---|---|---|
| D1-A double-POST | AC10 + handler tasks | Mirrors existing /candidates pattern |
| D2-A zero-seed + `both_seeded` | AC1, AC6 gate | Amelia's refinement |
| D3-A per-coach payload | AC6 payload shape | Renamed per D5 |
| D4 hybrid (check/emit/surface split) | AC6 + AC7 | Three layers in `check_drift()` |
| D5 OBSERVATION rename | shared/ tasks + AC7 default | severity=info, surface_to_operator=False by default |

### Existing Files Being Modified (full reads completed)

**`fusion/src/fusion/main.py`** — current state:
- Lifespan constructs `httpx.AsyncClient`, `ContextState`, `Enrichment`, `SuppressionGate`, `build_app`
- Routes appended into bootstrap app via `app.router.routes.append`
- **What changes:** Add `CoachLedger(settings.ledger_db_path)` construction inside `lifespan`; pass to `build_app`; close ledger connection in the `finally` block.
- **What must be preserved:** The bootstrap-then-append route pattern. The single shared `httpx.AsyncClient`. The `log.info("fusion.started"/...)` pair.

**`fusion/src/fusion/health.py`** — current state:
- `build_app` takes `settings, ctx, gate, enricher, client`
- Routes: `/health/live`, `/health/ready`, `/context`, `/candidates/door_obstruction`, `/candidates/alert_raised`, `/candidates/accessibility_detected`
- Candidate handlers wrap event-store errors so inference receives 202 even when downstream is unreachable
- **What changes:** Add `ledger: CoachLedger` parameter to `build_app`; add three new candidate handlers (`wagon_exit`, `wagon_entry`, `occupancy_update`). Pattern matches `candidate_door_obstruction` exactly.
- **What must be preserved:** `_ReadinessCache`, ramp edge-trigger logic, `ContextState.resolve_car_id` / `car_id_for_door` resolution, all existing candidate routes and their 202 fail-safe semantics.

**`fusion/src/fusion/config.py`** — current state:
- `Settings(BaseSettings)` with `event_store_url`, `vehicle_id`, `schema_version`, `host`, `port`, `accessibility_recent_window_s`, `calibration_drift_threshold`
- `env_prefix="FUSION_"`; no `os.environ.get` anywhere (Rule 8)
- **What changes:** Add four new settings (see config task above).
- **What must be preserved:** The pydantic-settings-only pattern. No `os.environ.get`. The deliberate absence of `Settings.journey_id`.

**`fusion/src/fusion/enrichment.py`** — current state:
- `emit_envelope(event_type_name, payload, severity)` already handles generic POSTs to event-store
- **What changes:** Nothing. `LEDGER_DRIFT_OBSERVATION` flows through the existing path with `severity="info"`.
- **What must be preserved:** Fail-closed `_severity_for`, `_build_envelope` skip-on-None-journey-id, single `_post_envelope` POST path.

**`inference/src/inference/tripwire.py`** — current state (from E4-S8):
- `_emit_wagon_exit` and `_emit_wagon_entry` POST envelope to `{settings.event_store_url}/api/v1/events` via `DEFAULT_RETRY`
- **What changes:** After the existing POST succeeds, fire-and-forget POST to fusion. Do NOT wrap in `DEFAULT_RETRY` — fusion-unreachable is a WARNING log, not a retry condition.
- **What must be preserved:** The event-store POST path, the orphan timer, the `_pending_exits` map, the LRU eviction on `_last_side`, the cancel-before-emit ordering (P10). None of these may be touched.

**`inference/src/inference/zone_counter.py`** — current state:
- POSTs `OCCUPANCY_UPDATE` envelope to event-store
- **What changes:** Add fire-and-forget POST to fusion after event-store success. Same pattern as tripwire.py.
- **What must be preserved:** The `_build_envelope` path, the budget gating, the per-coach state.

### New File: `fusion/src/fusion/ledger.py`

Key design decisions:
- **SQLite ownership:** Single `sqlite3.Connection` owned by `CoachLedger`; lifecycle bound to fusion lifespan. WAL mode set on `__init__`. `isolation_level=None` + explicit `BEGIN/COMMIT` for write transactions.
- **Pending-exit state:** In-memory `dict[int, _PendingExit]` keyed by `track_id`. Not persisted — 10s window is short, next OCCUPANCY_UPDATE resyncs via AC6.
- **`_both_seeded` gate:** `dict[str, bool]` keyed by `car_id`. Set to `True` on first observation of either a WAGON_* event or an OCCUPANCY_UPDATE for that coach. Drift check no-ops until True. Protects against the cold-start zero-vs-camera spurious alert.
- **`_last_drift_bucket` state-transition tracking:** `dict[str, int]` keyed by `car_id`. Drift bucket = `sign(delta) * (|delta| // bucket_size)`. Emit only when current bucket ≠ last bucket. Transitions back to bucket `0` emit a "drift cleared" observation (same payload, `delta=0`) so consumers can close out the diagnostic.
- **Timer pattern:** `loop.call_later(timeout_s, lambda: asyncio.ensure_future(self._handle_pending_timeout(track_id)))` — captures `track_id` in closure (E3 retro A3). Store `TimerHandle` on `_PendingExit` so `on_wagon_entry` can cancel BEFORE applying ledger update (E4-S8 P10).
- **Stale-closure guard:** When the timer fires or cancellation runs, re-check `_pending_exits` membership — entry may have been removed by concurrent WAGON_ENTRY.
- **Async/sync boundary:** `CoachLedger` methods are `async` (called from FastAPI handlers). SQLite calls are blocking but tiny — acceptable inside async handlers per current fusion convention (door_obstruction handler does same).

### Event Models — Post-Rename

```python
# shared/src/oebb_shared/events/types.py:33 — RENAMED
class EventType(StrEnum):
    ...
    LEDGER_DRIFT_OBSERVATION = "LEDGER_DRIFT_OBSERVATION"   # was: LEDGER_DRIFT_ALERT

# shared/src/oebb_shared/events/payloads.py:367 — RENAMED + new field
class LedgerDriftObservationPayload(_BasePayload):
    """LEDGER_DRIFT_OBSERVATION — diagnostic telemetry; ledger vs camera disagreement.

    Renamed from LEDGER_DRIFT_ALERT (party-mode 2026-05-21 D5) — no validated
    operator playbook exists yet. surface_to_operator gates future promotion to
    an operator-visible alert without changing this payload contract.
    """
    car_id: _NonEmptyStr
    camera_count: int
    ledger_count: int
    delta: int
    threshold: int
    surface_to_operator: bool = False
```

### ADR Compliance

- **ADR-4 (SQLite WAL):** New `coach_ledger.db` follows the WAL pattern. Tests use `tmp_path`-scoped files (architecture line 173).
- **ADR-15 (Camera-Authoritative Counting):** Camera count beats ledger count in every drift case. Story emits an observation, then corrects the ledger to match the camera — `OCCUPANCY_UPDATE` is never modified by this story.
- **ADR-17 (Inter-Wagon Movement Ledger):** This story is the implementation of the `coach_ledger` table + reconciliation loop referenced by the ADR. **Note:** ADR-17 §line 452 currently uses `LEDGER_DRIFT_ALERT` and describes aggregate sum-across-coaches reconciliation. After this story, ADR-17 should be updated to reflect the per-coach OBSERVATION shape; tracked as part of the deferred-work entry.

### Lessons Applied from E4-S8 (predecessor)

- **Round-2 P10 (race between concurrent crossings):** When `on_wagon_entry` arrives for a track_id with a pending exit, cancel the timer BEFORE applying the ledger update.
- **Round-2 P9 (LRU eviction):** `_pending_exits` is bounded by 10s window + per-track_id keys. `_handle_pending_timeout` must always remove its entry to avoid leaks.
- **Round-1 D3 (orphan log level):** Mirror E4-S8 — `exit_unreconciled` log at INFO (not WARNING) since the OBSERVATION emit is the engineering-facing signal.
- **E3 retro A1 (read full UPDATE files):** Done — `main.py`, `health.py`, `config.py`, `enrichment.py`, `tripwire.py`, `zone_counter.py` all read in full with current state, change scope, preservation requirements documented above.
- **E3 retro A3 (async stale closure):** Documented in the timer pattern above.

### Test Patterns (from sibling stories)

- `respx.mock` for HTTP assertions
- `structlog.testing.capture_logs` for log assertions
- `pytest-asyncio` `@pytest.mark.asyncio` for async tests
- For timeout tests: use `Settings(ledger_pending_timeout_s=0.05)` rather than real 10s waits
- For SQLite: `tmp_path / "ledger.db"` fixture, NOT `:memory:` (architecture line 173)

### Quality Gate Command

```bash
cd fusion
pytest --strict-markers --cov=src/fusion --cov-fail-under=90 -q
mypy --strict src/
ruff check src/ tests/

cd ../inference
pytest -q && mypy --strict src/ && ruff check src/ tests/

cd ../shared
pytest -m contract && mypy --strict src/
```

### Project Structure Notes

- New file: `fusion/src/fusion/ledger.py` (alongside `enrichment.py`, `suppression.py`, `context_state.py`)
- New test: `fusion/tests/unit/test_ledger.py` (matches existing `test_enrichment.py`, `test_suppression.py` siblings)
- DB path `/var/lib/fusion/coach_ledger.db` follows event-store convention; volume mount needs to be added to `docker-compose.dev.yml` — flag in completion notes; out of scope to author the compose change here.

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-17] — coach_ledger table (note: needs update after this story per D5)
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-15] — camera-authoritative; ledger never overrides
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-4] — SQLite WAL; `:memory:` not allowed in tests (line 173)
- [Source: _bmad-output/planning-artifacts/epics.md#E4-S9] — original epic spec (superseded by D1–D5 above)
- [Source: _bmad-output/implementation-artifacts/4-8-gangway-tripwire-ingest.md] — upstream WAGON_EXIT/ENTRY emitter
- [Source: shared/src/oebb_shared/events/payloads.py:367] — payload to rename
- [Source: fusion/src/fusion/health.py] — candidate handler pattern to mirror
- [Source: fusion/src/fusion/enrichment.py] — `emit_envelope` POST pipeline
- [Source: fusion/src/fusion/main.py] — lifespan pattern
- [Source: inference/src/inference/tripwire.py] — upstream emit path to extend with fusion fire-forget

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Amelia / bmad-dev-story workflow), 2026-05-21.

### Debug Log References

- Initial run: `test_close_is_idempotent_for_safety` failed because `sqlite3.Connection.close()` is idempotent in Python 3.11 — reworked the test to verify the connection releases the DB file by re-opening on the same path.
- Initial tripwire/zone_counter test failures: `structlog` reserves the `event` keyword argument; renamed the fire-forget WARNING field to `kind=` to avoid `meth() got multiple values for argument 'event'`.

### Completion Notes List

- **AC1** — `coach_ledger` table created with WAL mode; zero-seed via `seed_coach`; AC1 gate implemented as two-set design (`_seen_occupancy`, `_seen_wagon`) — drift checks no-op until BOTH signals seen for a given `car_id`. The story's `both_seeded[car_id]` dict semantics are equivalent (`car_id in _seen_occupancy AND car_id in _seen_wagon`).
- **AC2/AC3** — `on_wagon_exit` decrements ledger; arms timer + `unreconciled_exits++` only when `expect_orphan=False`.
- **AC4** — `on_wagon_entry` cancels the pending timer FIRST (P10), then mutates state; orphan WAGON_ENTRY still increments destination ledger and logs `reason="orphan_entry"`.
- **AC5** — `_handle_pending_timeout` retains decrement, drops pending entry, logs `reason="exit_unreconciled"`.
- **AC6** — Drift bucket = `sign(delta) * (|delta| // bucket_size)`; emit only on bucket transition. ADR-15 ledger correction applied AFTER snapshotting `ledger_count` into the observation payload. Drift-cleared transition emits one final observation with `delta=0` and `ledger_count=camera_count`.
- **AC7** — `surface_to_operator` populated from the `station_approach` argument passed by `health.py` handler.
- **AC8** — Suppression check happens at handler layer (`candidate_occupancy_update`) after `check_drift` returns a payload but before `enricher.emit_envelope`. Ledger state continues to mutate regardless (per AC8).
- **AC9** — Single owned `sqlite3.Connection` in `__init__`; `isolation_level=None`, `check_same_thread=False`, WAL pragma; all SQL uses placeholders. AST test enforces no f-string / `%`-format inside `.execute()` calls.
- **AC10** — `tripwire.py._emit_wagon_exit` / `_emit_wagon_entry` fire-and-forget POST to `{fusion_url}/candidates/wagon_exit | wagon_entry` (no `DEFAULT_RETRY`); errors logged at WARNING with `reason="fusion_unreachable"`. `zone_counter.py._post_occupancy_update` does the same for `OCCUPANCY_UPDATE`. Payload (not envelope) is sent — payload model matches the fusion candidate handler.
- **AC11 quality gates** — `pytest --cov=src/fusion --cov-fail-under=90` → 119 passed, 94.66% (gate ≥90). `mypy --strict` clean across `fusion/src/` (12 files), `inference/src/` (11 files), `shared/src/` (17 files). `ruff check src/ tests/` clean for `fusion` and `inference`. `shared` ruff has 9 pre-existing violations unrelated to this story (verified against baseline by stash). `shared` contract suite (61 tests) green with renamed `LEDGER_DRIFT_OBSERVATION`.

**Deployment note (out of scope to author):** `docker-compose.dev.yml` needs a volume mount for `/var/lib/fusion/coach_ledger.db` so the SQLite file survives container restarts. Flagged here per architecture line 297.

**ADR-17 update needed (out of scope):** ADR-17 §line 452 still references `LEDGER_DRIFT_ALERT` and aggregate sum-across-coaches reconciliation. After this story it should be updated to reflect the per-coach OBSERVATION shape — track via the follow-up section.

### File List

**Added:**
- `fusion/src/fusion/ledger.py`
- `fusion/tests/unit/test_ledger.py`

**Modified:**
- `shared/src/oebb_shared/events/types.py` — `LEDGER_DRIFT_ALERT` → `LEDGER_DRIFT_OBSERVATION`
- `shared/src/oebb_shared/events/payloads.py` — class rename + `surface_to_operator: bool = False` field + registry key
- `shared/tests/contract/test_envelope_contract.py` — fixture key rename, added `surface_to_operator` field
- `shared/tests/unit/test_event_envelope.py` — expected EventType set
- `fusion/src/fusion/config.py` — added `ledger_drift_threshold`, `ledger_drift_bucket_size`, `ledger_db_path`, `ledger_pending_timeout_s`
- `fusion/src/fusion/health.py` — `build_app(ledger=...)` param + three new candidate endpoints
- `fusion/src/fusion/main.py` — construct + pass + close `CoachLedger` in lifespan
- `fusion/tests/unit/test_health.py` — `_make_client` passes ledger; 6 new tests for candidate endpoints + malformed-payload security
- `fusion/tests/unit/test_security.py` — `ledger.py` added to MODULES; new AST test for SQL injection in `.execute()` calls
- `fusion/tests/contract/test_candidate_payload_contract.py` — fixture passes ledger to `build_app`
- `fusion/tests/integration/test_fusion_pipeline.py` — fixture passes ledger to `build_app`
- `inference/src/inference/tripwire.py` — fire-forget POST to fusion after both event-store posts (`_emit_wagon_exit`, `_emit_wagon_entry`)
- `inference/src/inference/zone_counter.py` — fire-forget POST to fusion after `_post_occupancy_update`
- `inference/tests/unit/test_tripwire.py` — three AC10 tests (success, 503 logs WARNING, wagon_entry counterpart)
- `inference/tests/unit/test_zone_counter.py` — two AC10 tests (success, 503 logs WARNING)

### Change Log

- 2026-05-21 — Implemented closed-ledger reconciliation engine per Story 4-9 D1–D5. Renamed `LEDGER_DRIFT_ALERT` → `LEDGER_DRIFT_OBSERVATION` and added `surface_to_operator` field. Added per-coach `CoachLedger` with WAL-mode SQLite, drift-bucket state-transition emit, ADR-15 camera-authoritative correction, and AC1 two-set seeding gate. Three new fusion candidate endpoints (`wagon_exit`, `wagon_entry`, `occupancy_update`). Inference now double-POSTs to fusion via fire-and-forget after event-store. 119 fusion tests, 148 inference tests, 130 shared tests — all green. Fusion coverage 94.66% (gate ≥90%).

## Senior Developer Review (AI) — Round 1

**Reviewer:** Opus 4.7 via `bmad-code-review` workflow, 2026-05-21.
**Layers:** Blind Hunter (24 findings) + Acceptance Auditor (10) + Edge Case Hunter (30 walks, 10 unhandled).
**Triage outcome:** 5 decision-needed, 14 patch, 5 defer, 5 dismissed.

### Review Findings

#### Decision needed

- [x] [Review][Decision] **`LEDGER_DRIFT_ALERT` enum-rename ships with no backwards-compat alias** — Wire-protocol rename of a `StrEnum` value with no dual-registration. Any persisted events or in-flight queue items will fail enum parsing. PoC may have no live consumers, but the story does not state this. Options: (a) accept PoC scope and ship; (b) add temporary alias in `EventType` and `PAYLOAD_MODELS`; (c) write a migration for any persisted events. [shared/src/oebb_shared/events/types.py, payloads.py]
- [x] [Review][Decision] **Inference "fire-and-forget" actually `await`s fusion POST** — `tripwire.py` and `zone_counter.py` `await self._client.post(fusion_url/...)`; fusion latency is added to inference critical path. True fire-and-forget would be `asyncio.create_task`. Story copy says "non-blocking" but the implementation blocks. Options: (a) ship as-is — matches existing `/candidates/door_obstruction` pattern; (b) wrap in `asyncio.create_task` (need to track tasks for shutdown). [inference/src/inference/tripwire.py:434, 472; zone_counter.py:215]
- [x] [Review][Decision] **`CoachLedger` has no `asyncio.Lock`; concurrent same-`track_id` fires can double-mutate** — methods are sync internally so single-coro interleaving is safe, but two coroutines hitting `on_wagon_exit(track_id=5)` back-to-back will double-decrement and bump `unreconciled_exits` twice. Inference is supposed to fire unique track_ids per crossing — collision plausible only on retries. Options: (a) ship without lock (PoC); (b) add `asyncio.Lock` per-coach; (c) dedup `track_id` already-pending at the ledger layer (see Patch finding for the duplicate-decrement fix). [fusion/src/fusion/ledger.py — class-level]
- [x] [Review][Decision] **`_pending_exits` keyed by global `track_id` only — cross-camera collisions unhandled** — Tripwire trackers reset on stream restart; two cameras can assign track_id=1 to different physical people. Composite key `(camera_id, track_id)` is correct but requires schema/contract change. Options: (a) PoC scope — ship; (b) extend `_pending_exits` key to `(camera_id, track_id)` (need to plumb camera_id into payloads — already present on `WagonExitPayload.camera_id`). [fusion/src/fusion/ledger.py:418]
- [x] [Review][Decision] **Restart loses `_pending_exits`; post-restart paired ENTRY treated as `orphan_entry` → phantom +1 passenger** — `_load_rows` only loads `coach_ledger` table. After a crash, in-flight pending EXITs lose timer + state. A subsequent matching ENTRY increments destination ledger (already incremented by the persisted EXIT-side decrement on the source coach). Net: phantom +1. Options: (a) PoC accept — flag in deferred follow-up; (b) persist `_pending_exits` to a sibling SQLite table; (c) log a startup warning that pre-restart pendings are lost and zero `unreconciled_exits` columns. [fusion/src/fusion/ledger.py:111-122 (`_load_rows`)]

#### Patch (unresolved)

- [x] [Review][Patch] **AC1 `_seen_occupancy` is dead state — gate only checks `_seen_wagon`** [fusion/src/fusion/ledger.py:323] — Three reviewers agree. Dev notes claim "two-set design"; code only reads `_seen_wagon`. Fix: either actually check both, or remove `_seen_occupancy` and update the Completion Notes. (Currently functional only because `check_drift` is the only call site.)
- [x] [Review][Patch] **Duplicate WAGON_EXIT for same `track_id` double-decrements ledger** [fusion/src/fusion/ledger.py:177-179] — At-least-once delivery (fire-forget pattern admits this) corrupts ledger. Add dedup: if `track_id` already in `_pending_exits`, return early (and log).
- [x] [Review][Patch] **`LedgerDriftObservationPayload` not exported from `shared/.../events/__init__.py`** [shared/src/oebb_shared/events/__init__.py] — Spec task line was marked `[x]` but the file is unchanged. Add the export and `__all__` entry. Functional today only because `fusion/ledger.py` imports via the deep path.
- [x] [Review][Patch] **`except Exception` in inference fire-forget violates spec `except httpx.HTTPError`** [inference/src/inference/tripwire.py:438-446, 472-481; zone_counter.py:217-224] — Spec explicitly says `except httpx.HTTPError`. Current `except Exception` masks programming errors (bad JSON, attribute errors) as "fusion_unreachable". Tighten the except clause.
- [x] [Review][Patch] **`_handle_pending_timeout` has no closed-flag check; timer firing after `close()` is implicitly safe but undefended** [fusion/src/fusion/ledger.py:240-251] — Add a `_closed` flag and early-return at top of `_handle_pending_timeout`. Defends against future evolution where the handler touches `_conn`.
- [x] [Review][Patch] **`asyncio.get_running_loop()` captured in `on_wagon_exit` may fire on a closed loop** [fusion/src/fusion/ledger.py:196-202] — Wrap the `loop.create_task` lambda in try/except so a closed-loop fire logs instead of raising.
- [x] [Review][Patch] **`ledger_drift_threshold` not validated; 0 or negative silently misbehaves** [fusion/src/fusion/config.py] — Add pydantic `ge=0` (or sensible minimum) on the field.
- [x] [Review][Patch] **`PRAGMA journal_mode=WAL` return value discarded; silent fallback on tmpfs/NFS** [fusion/src/fusion/ledger.py:104] — Read the PRAGMA return value; log WARNING if not `"wal"`.
- [x] [Review][Patch] **Missing test — AC8 suppression-gate `should_emit=False` branch** [fusion/tests/unit/test_health.py] — AC11 explicitly lists "suppression-gate behaviour (AC8)" as a required test. Add a test where `gate.should_emit()` is False and assert the envelope POST does not happen but ledger state still mutates.
- [x] [Review][Patch] **Missing test — Security Tests claim "no raw video / CCTV URL in ledger payload or log line"** [fusion/tests/unit/test_security.py] — Mirror existing `test_no_raw_video_or_stream_url_in_envelope` for `LedgerDriftObservationPayload`.
- [x] [Review][Patch] **`test_wagon_exit_fires_to_fusion_candidate_endpoint` does not verify ordering** [inference/tests/unit/test_tripwire.py] — AC10 says "AFTER successful event-store POST". Add a test: mock event-store 500 → assert fusion never POSTed.
- [x] [Review][Patch] **Drift-cleared test has stream-of-consciousness comments** [fusion/tests/unit/test_ledger.py — `test_drift_cleared_emits_once_with_delta_zero`] — Strip "We need to drive bucket back to 0 explicitly..." prose; tighten the assertion to also check `_last_drift_bucket` is 0.
- [x] [Review][Patch] **Three log-assertion tests use permissive `reason OR event` matchers** [fusion/tests/unit/test_ledger.py — `test_orphan_wagon_entry_increments_and_logs`, `test_pending_exit_timeout_decrement_not_reverted`, `test_entry_cancels_timer_before_state_mutation`] — Tighten to `entry.get("reason") == "<expected>"` only; will silently pass if the implementation drops the `reason` field.
- [x] [Review][Patch] **Pending-timeout test relies on 3× wall-clock margin (`asyncio.sleep(0.15)` vs 0.05s timeout)** [fusion/tests/unit/test_ledger.py — `test_pending_exit_timeout_decrement_not_reverted`] — Bump margin to ~10× or use `asyncio.Event` driven by the timeout handler for deterministic completion.

#### Deferred (pre-existing or out of scope)

- [x] [Review][Defer] **`unreconciled_exits` monotonically grows; never decremented on timeout** [fusion/src/fusion/ledger.py:240-251] — AC3 + AC5 explicitly say don't decrement on `expect_orphan` exits or on timeout. Per spec, but counter has no reset on journey change. Track for journey-lifecycle follow-up.
- [x] [Review][Defer] **`ledger_count` can go arbitrarily negative pre-reconciliation** [fusion/src/fusion/ledger.py:177] — ADR-15 design accepts negatives until next drift transition. Spec-deferred.
- [x] [Review][Defer] **`_last_drift_bucket`, `_seen_wagon`, `_seen_occupancy` never reset on journey change** [fusion/src/fusion/ledger.py:295-298] — Process-lifetime hidden state survives journey transitions. No journey-change hook in fusion today. Real concern; out of scope for 4-9.
- [x] [Review][Defer] **Drift bucket transition consumed during suppression — observation entirely within suppression window never reported** [fusion/src/fusion/health.py:218-247] — Dev-note interpretation of AC8 (state mutates regardless). User may want a different policy when promoting OBSERVATION to ALERT post-D5. Track for the operator-playbook follow-up.
- [x] [Review][Defer] **`mkdir parents=True, exist_ok=True` masks permission failures on writable-parent-of-unwritable directories** [fusion/src/fusion/ledger.py:121-124] — Deployment concern; story already flags compose volume mount as out-of-scope.

#### Dismissed

- `except Exception` in candidate handlers — mirrors existing `/candidates/door_obstruction` pattern, explicit in dev notes.
- DEFAULT_RETRY duplicating fusion POSTs — walked by Edge Case Hunter; `raise_for_status` for event-store happens BEFORE fusion POST, so fusion only fires on event-store success (exactly one POST per crossing).
- `test_malformed_payload_occupancy_update_returns_422` ambiguous — Edge F27 verified `_NonNegInt` rejects negative at pydantic layer; behaviour correct, test is just imprecise.
- `inference/config.py fusion_url` task checkbox bookkeeping — field already existed pre-story at `inference/src/inference/config.py:28`; box correctly checked because nothing needed to be added.
- Drift-cleared `ledger_count = camera_count` — defensible reading of "same payload, delta=0"; tested.
