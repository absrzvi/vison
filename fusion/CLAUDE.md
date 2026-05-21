# fusion — CLAUDE.md

Python 3.11 + FastAPI. Onboard event fusion: alert correlation, suppression, ledger reconciliation, comfort index. No React, no PostgreSQL. SQLite (WAL mode) for ledger state.

## Test commands

```bash
cd fusion
pytest --strict-markers --cov=src/fusion --cov-fail-under=90 -q   # full suite
pytest tests/unit/test_health.py -q                               # handler tests
mypy --strict src/
ruff check src/ tests/
```

## Key modules

| File | Role |
|------|------|
| `src/fusion/health.py` | FastAPI app + all route handlers (`build_app`) |
| `src/fusion/comfort_index.py` | `ComfortIndexState` — per-coach delta + station-edge emit |
| `src/fusion/ledger.py` | `CoachLedger` — SQLite-backed closed-ledger reconciliation |
| `src/fusion/context_state.py` | `ContextState` — vlan-poller context push + edge detectors |
| `src/fusion/suppression.py` | `SuppressionGate` — depot/maintenance/gps_invalid gate |
| `src/fusion/enrichment.py` | `Enrichment.emit_envelope` — generic event-store POST |
| `src/fusion/main.py` | Lifespan + container wiring |
| `src/fusion/config.py` | `Settings` (pydantic-settings) |

## Patterns every new story in fusion must follow

### 1. Two-phase baseline advance

Any state machine that tracks "last emitted value" (e.g. `_last_emitted_pct`, `_last_drift_bucket`) **must not mutate state until after the HTTP emit succeeds**.

Correct pattern (see `comfort_index.py` and `ledger.py`):
```python
# Step 1: compute payload, return WITHOUT mutating state
payload = state.on_event(input)
if payload is not None:
    try:
        await enricher.emit_envelope(...)
        state.confirm_emit(...)   # Step 2: advance state ONLY on success
    except httpx.HTTPError:
        log.warning(...)
        # state NOT advanced — next tick will retry from last confirmed baseline
```

Mutating state before the emit means: if the POST fails, the last emitted value and the last confirmed value diverge — the consumer received nothing but the producer thinks it did.

**Canonical implementations:** `ComfortIndexState.confirm_emit()`, `CoachLedger._last_drift_bucket` mutation after successful `emit_envelope`.

### 2. peek/consume for suppression-safe edge detectors

When an edge detector (false→true transition) must survive suppression, use peek/consume:

```python
# Check without committing
if ctx.peek_station_approach_edge():
    if gate.should_emit():
        ctx.consume_station_approach_edge()  # commit only after emit
        ...emit...
    else:
        ...log suppressed...  # edge NOT consumed — fires again next push
```

`observe_*()` methods (unconditional consume) are fine when the edge does not need to survive suppression. Use `peek/consume` when it does.

**Canonical implementation:** `ContextState.peek_station_approach_edge()` / `consume_station_approach_edge()` (added story 4-10 D3).

### 3. Handler fail-safe — always 202

All `/candidates/*` handlers must return 202 even when downstream emits fail:

```python
try:
    await enricher.emit_envelope(...)
    state.confirm_emit(...)
except httpx.HTTPError as exc:
    log.warning("fusion.emit_failed", reason=str(exc))
# fall through to return Response(status_code=202)
```

Inference fire-and-forgets to fusion — a 500 from fusion will cause inference to log a warning but not retry. Always return 202; let the structured log carry the failure signal.

### 4. Three-step pattern for cross-state-machine tests

When a test covers two orthogonal state machines (e.g. `SuppressionGate` × `ContextState`, or `CoachLedger` × `ContextState`), write the scenario in three steps:

1. **Set up non-suppressed baseline** — observe enough events to seed state while the gate is open.
2. **Enter the combined suppressed+trigger state** — apply the combination you're testing.
3. **Verify recovery** — clear the suppression and confirm the expected behaviour fires.

This prevents the degenerate case where state is seeded inside the suppressed window (wrong baseline) and the test passes for the wrong reason.

**Reference test:** `test_comfort_index_station_edge_preserved_under_suppression` in `tests/unit/test_health.py`.

### 5. Gate check discipline

`gate.should_emit()` is a pure predicate (no side effects, cheap). Call it once per handler block, not once per emit call. If the same handler has multiple emit paths (e.g. ledger drift + comfort index), gate each path independently — they are separate decisions with separate structured logs.

## Event-ingest pattern (story 4-9 D1-A — current PoC)

Inference POSTs to event-store first, then fire-and-forgets to `fusion POST /candidates/<event>`. This is the **double-POST pattern** — same as `/candidates/door_obstruction`. Fusion POST failures are non-blocking from inference's perspective.

The WS-subscription alternative (D1-B) is the production-grade approach: fusion subscribes to event-store WS fan-out instead of receiving direct inference POSTs. Revisit when multiple onboard containers need the same event stream. Document as an ADR (phase-2 retro A4).

## Suppression gate semantics

`SuppressionGate.should_emit()` returns `False` when: `depot_mode`, `maintenance_mode`, or `gps_valid is False`. Under suppression:
- Do NOT advance any "last emitted" baseline (`_last_emitted_pct`, `_last_drift_bucket`).
- Do NOT call `confirm_emit()`.
- Log at DEBUG with `reason: "<event_type>_suppressed"`, `car_id`, relevant metric.
- State machines continue to update internally (ledger counts, observed coaches sets) — only the emit is suppressed.

## Journey lifecycle

`ContextState.journey_id` changes when a new journey starts. On journey change:
- `ComfortIndexState.reset()` clears `_last_emitted_pct` and `_observed_coaches`.
- `CoachLedger` journey-lifecycle hook is currently missing — tracked in deferred-work.md (story 4-9 deferred item). Until it's added, `_last_drift_bucket`, `_seen_wagon`, `_seen_occupancy` carry over across journey boundaries.

Journey change detection is in the `/context` handler in `health.py`:
```python
prev_journey_id = ctx.journey_id
ctx.update_from_push(payload)
if ctx.journey_id != prev_journey_id:
    comfort.reset()
```
