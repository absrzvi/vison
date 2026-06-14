---
baseline_commit: c2db726
---

# Story 6.4: vlan-pollers↔fusion `/context` Push Contract Reconciliation

Status: ready-for-dev

<!-- Created 2026-06-14 via bmad-create-story (Amelia / Opus 4.8). P1 — NEW fourth story in Epic 6 (Fusion Hardening).
     Source: surfaced by the 10-4 dwell-time-KPI code review (wf_eb03b492 + wf_4b4c0912) as a PRE-EXISTING integration
     hole independent of 10-4. Corroborated by deferred-work.md F21 (non-atomic _push_context_delta) and the
     DEFAULT_RETRY-on-4xx finding (line 412). This is a fusion/vlan-pollers hardening story — no new feature. -->

## Story

As a **system operator running long PoC sessions**,
I want **the vlan-pollers `/context` state push to actually be accepted by fusion (not silently 422-rejected) so fusion receives speed, occupancy, reservations, and PIS deltas**,
so that **fusion's suppression gate, comfort index, and alert enrichment operate on live train state instead of stale defaults — closing a pre-existing integration hole that the 10-4 review exposed**.

## Context — why this story exists

The 10-4 dwell-time-KPI code review (Round 1, wf_eb03b492) found, and the Round-2 re-review (wf_4b4c0912) **empirically confirmed**, that the vlan-pollers→fusion full-delta `/context` push **returns HTTP 422 and never lands**:

> Loading `ContextPushModel` with the real `_state_to_dict` key set raises `ValidationError` with 4 errors — `alarms`, `occupancy`, `pis`, `trip_number` are rejected by `model_config extra='forbid'`. So the full-delta push (`_push_context_delta`) 422s entirely; only the narrow `set_station_approach` push survives.

**Consequence in production today (pre-existing, not caused by 10-4):** every `_push_context_delta`-driven update — `update_speed`, `update_occupancy`, `update_reservations`, `update_pis`, `update_journey`, `update_alarm` ([vlan-pollers/context_state.py:55-106](../../vlan-pollers/src/vlan_pollers/context_state.py)) — fails to deliver to fusion. fusion's `ContextState.speed_kmh`, `reservations`, `occupancy` (and, pre-10-4, `scheduled_departure`) stay at their initialised defaults. This silently degrades:
- **`_severity_for`** ([fusion/enrichment.py](../../fusion/src/fusion/enrichment.py)) — door-fault severity is speed-correlated; with `speed_kmh` never updated (stuck at the `None`/`0.0` default) it can mis-severity (fail-closed `None`→critical masks it, but it's not reading live speed).
- **`ComfortIndexState`** — uses `reservations` + `occupancy`, which never arrive via this path.
- **`SuppressionGate`** — `maintenance_mode`/`depot_mode`/`gps_valid` DO reach fusion (they're declared on `ContextPushModel`), but they ride the same full-delta push that 422s — so they only update if a push happens to carry only declared fields (it never does once `pis`/`occupancy` are present).

10-4 sidestepped this for **its** one field by adding a targeted `{scheduled_departure, journey_id}` push (the `set_station_approach` pattern). That made the KPI work but left the broader hole open. This story closes it.

### The decisive asymmetry (read before choosing the approach)

The **same** full body is POSTed to BOTH fusion and inference ([_push_context_delta:108-111](../../vlan-pollers/src/vlan_pollers/context_state.py)):
- **inference** ([inference/health.py:29-32](../../inference/src/inference/health.py)) — `ContextPushModel` uses `ConfigDict(strict=True)` with **no `extra='forbid'`** → Pydantic default `extra='ignore'` → **inference ACCEPTS the full body**, silently ignoring `pis`/`alarms`/`occupancy`/`trip_number`.
- **fusion** ([fusion/models.py:31](../../fusion/src/fusion/models.py)) — `ConfigDict(strict=True, extra='forbid')` → **fusion REJECTS** the full body (422).

**Fusion is the outlier.** The `extra='forbid'` was a deliberate 2026-05-20 code-review decision (strict validation: unknown fields fail loudly), pinned by two tests — but it was made before anyone replayed the *real* producer body against it, so it has been silently 422-ing every full-delta push since.

## Acceptance Criteria

**AC1 — The real vlan-pollers `/context` body is accepted by fusion (no 422)**
Given the exact body produced by `vlan_pollers.context_state._state_to_dict(state)` for a fully-populated `ContextState` (with `pis`, `occupancy`, `reservations`, `alarms`, `trip_number`, `speed_kmh`, `station_approach`, `journey_id`, `vehicle_id`),
when it is POSTed to fusion's `/context` endpoint,
then fusion returns **200** (not 422), and `ContextState.speed_kmh`, `reservations`, and `station_approach` are updated from the push. A **contract test** replays the real `_state_to_dict` body through fusion's `/context` and asserts 200 + the declared fields land.

**AC2 — fusion still rejects genuinely-unknown fields (strict-validation intent preserved)**
Given a `/context` push carrying a field that is NOT part of the agreed producer contract (e.g. `{"made_up_field": true}`),
when validated by fusion's `ContextPushModel`,
then it is still rejected (422) — the existing `test_context_push_extra_field_rejected` and `test_context_push_strict_bool_rejects_strings` ([fusion/tests/unit/test_context.py:11-22](../../fusion/tests/unit/test_context.py)) **must still pass** (strict-bool + unknown-field rejection are non-negotiable safety properties). The reconciliation accepts the *known producer keys*, not *all* keys.

**AC3 — fusion reads PIS `scheduled_departure` from the canonical nested location (de-duplicate the 10-4 targeted push)**
Given the full-delta push now lands and carries `pis: {scheduled_departure, ...}`,
when fusion processes it,
then `ContextState.scheduled_departure` is populated from `pis.scheduled_departure` (the canonical wire location). The 10-4 targeted `{scheduled_departure, journey_id}` push ([vlan-pollers/context_state.py update_pis](../../vlan-pollers/src/vlan_pollers/context_state.py)) becomes **redundant** — remove it OR keep it as a belt-and-braces fast path, but document the decision; do not leave two divergent delivery paths silently. A test asserts `scheduled_departure` lands from the nested `pis` body.

**AC4 — `_push_context_delta` per-service error isolation (deferred F21)**
Given `_push_context_delta` POSTs sequentially to fusion then inference,
when the fusion POST fails (timeout/connection error),
then the inference POST is still attempted (one consumer's failure does not starve the other), and each failure is logged with the target service. (This closes deferred-work.md **F21**: "sequential posts may leave consumers divergent on retry failure".) Test simulates a fusion failure and asserts inference still receives the push.

**AC5 — No 50-second retry burn on a (now-eliminated) 422**
Given the reconciliation removes the 422,
then the `DEFAULT_RETRY`-on-4xx burn (deferred-work.md line 412: "burns 50s of retries on a 422") no longer triggers on the `/context` path. Note: this story **eliminates the 422 trigger**; it does NOT fix `DEFAULT_RETRY` itself (that is Epic 7 story **7-1** `shared-retry-policy-exclude-4xx`). State in Dev Notes that 7-1 remains the proper fix for the retry policy; 6-4 just stops feeding it a 422 on this path.

**AC6 — Quality gates**
`fusion` full suite green at `--cov-fail-under=90`; `mypy --strict src/` clean; `ruff` clean. `vlan-pollers` full suite green; `mypy`/`ruff` clean. No regression in the suppression/comfort/ledger behaviour that depends on `ContextState`.

## Decisions (review before dev — one is genuinely open)

- **D1 — RECONCILIATION APPROACH (the core decision; recommendation = Option B).** Three viable shapes; pick one and record it in the Dev Agent Record:
  - **Option A — relax fusion to `extra='ignore'` (match inference).** Smallest diff. **Rejected by default:** it breaks `test_context_push_extra_field_rejected` and discards the deliberate strict-validation safety property (a typo'd field would now be silently swallowed, exactly the bug class the 2026-05-20 decision guarded against). Only choose this if the team explicitly retires the strict-validation decision.
  - **Option B — declare the real producer keys on fusion's `ContextPushModel` (RECOMMENDED).** Add `pis` as a typed optional sub-model (so fusion can read `pis.scheduled_departure` — AC3), and add `trip_number`/`alarms`/`occupancy` as optional accepted fields (typed if fusion will use them, else `accept-and-ignore` with a comment). Keep `extra='forbid'` so genuinely-unknown keys still 422 (AC2 stays green). This preserves strict validation AND accepts the real body AND lets fusion use PIS natively. Most work, lowest risk, best long-term contract.
  - **Option C — per-consumer bodies in `_push_context_delta`.** vlan-pollers sends fusion only fusion-known fields and inference the full body. Keeps both strict; but couples vlan-pollers to each consumer's schema (it must know what fusion declares) — brittle as the contract evolves. Reasonable fallback if declaring `occupancy`/`alarms` on fusion is undesirable.
  - **Recommendation: Option B.** It is the only option that keeps strict validation, makes the real body land, and unifies the PIS delivery path (AC3). Surface the choice in the story record; do not silently pick A.

- **D2 — Scope boundary: this is NOT the DEFAULT_RETRY fix.** AC5 eliminates the 422 *trigger*; the retry-on-4xx policy fix is Epic 7 **7-1**. Do not modify `oebb_shared.http.retry.DEFAULT_RETRY` here (it's a shared contract touched by multiple containers — cross-container coordination, Tier 3). Cross-reference 7-1.

- **D3 — Decide the 10-4 targeted-push fate (AC3).** With the full-delta push landing and carrying `pis.scheduled_departure`, the 10-4 targeted `update_pis` push is redundant. Options: (a) remove it (single canonical path — cleaner, but re-touches the just-shipped 10-4 code), or (b) keep it as a belt-and-braces fast path (PIS arrives one push earlier). Recommend **(a) remove** for a single source of truth, but it MUST be paired with a test proving `scheduled_departure` still lands via the nested `pis` body — otherwise removing it silently re-breaks 10-4. If (b), document why two paths exist.

- **D4 — Will fusion actually USE `occupancy`/`alarms`/`trip_number`, or just accept-and-ignore?** `ContextState` already has `reservations`; `ComfortIndexState` consumes `occupancy` + `reservations`. Verify whether fusion's comfort index is currently fed occupancy from anywhere else (it may rely on direct `/candidates/occupancy_update` POSTs, not the context push). If comfort index does NOT need occupancy from the context push, declare `occupancy`/`alarms`/`trip_number` as accept-and-ignore (don't wire them into `ContextState` unless something reads them — Karpathy: no speculative plumbing). Read `comfort_index.py` + the `/candidates/*` handlers before deciding what to actually store vs merely accept.

## Tasks / Subtasks

- [ ] **T0 — Explore pass (FULL-FILE-READS rule)** — read in full before editing: `fusion/src/fusion/models.py` (ContextPushModel), `fusion/src/fusion/context_state.py` (update_from_push), `fusion/src/fusion/comfort_index.py` (does it need occupancy from context?), `inference/src/inference/health.py` (the asymmetry reference), `vlan-pollers/src/vlan_pollers/context_state.py` (_state_to_dict + _push_context_delta + the 10-4 update_pis targeted push), `vlan-pollers/src/vlan_pollers/models.py` (PisState). Document current-state / what-changes / what-must-preserve for each.

- [ ] **T1 — RED: real-producer contract test** (AC1, AC2)
  - [ ] Write a fusion contract test that POSTs the actual `_state_to_dict(state)` body (fully-populated, incl. nested `pis`) to `/context` and asserts **200** + declared fields land. Watch it FAIL (422) against the current model.
  - [ ] Confirm `test_context_push_extra_field_rejected` + `test_context_push_strict_bool_rejects_strings` still express the strict-validation intent you must keep.

- [ ] **T2 — Reconcile `ContextPushModel`** (AC1, AC2, AC3, D1, D4)
  - [ ] Per D1 Option B (unless team overrides): add a typed optional `pis` sub-model (with `scheduled_departure` etc.) + `trip_number`/`alarms`/`occupancy` as optional accepted fields; keep `extra='forbid'`.
  - [ ] In `update_from_push`, read `scheduled_departure` from the nested `pis` (AC3). Only store `occupancy`/`alarms`/`trip_number` into `ContextState` if something actually reads them (D4) — else accept-and-ignore.
  - [ ] GREEN the T1 contract test; AC2 tests stay green.

- [ ] **T3 — Resolve the 10-4 targeted-push fate** (AC3, D3)
  - [ ] Per D3: remove the redundant `update_pis` targeted push (recommended) OR document why it's kept. If removed, add/keep a test proving `scheduled_departure` lands via the nested `pis` body so 10-4's feature is not silently re-broken.

- [ ] **T4 — `_push_context_delta` per-service error isolation** (AC4, F21)
  - [ ] Wrap each service POST so one failure doesn't skip the other; log per-service. RED test: fusion POST raises → inference still receives.

- [ ] **T5 — Quality gates + cross-references** (AC5, AC6, D2)
  - [ ] Note in Dev Notes that 7-1 owns the DEFAULT_RETRY-on-4xx fix (this story only removes the 422 trigger). Update deferred-work.md: mark F21 resolved; cross-link the 422/retry interaction to 7-1.
  - [ ] fusion suite (cov≥90) + mypy --strict + ruff; vlan-pollers suite + mypy + ruff — all green.
  - [ ] Per CLAUDE.md git rule: stage only this story's files, commit `fix(...)`/`refactor(...)` with the agent block, push `origin master`.

## Dev Notes

### Shipped-contract ground truth (cite, don't reinvent)

- **Producer body** — `_state_to_dict` ([vlan-pollers/context_state.py:114-125](../../vlan-pollers/src/vlan_pollers/context_state.py)) keys: `journey_id, trip_number, vehicle_id, speed_kmh, station_approach, alarms, pis, occupancy, reservations`. `pis` is `dataclasses.asdict(PisState)` — nested, carries `scheduled_departure`, `next_station`, `actual_departure`, `platform`, `delay_min`, `next_station_arrival_utc` ([vlan-pollers/models.py:30-36](../../vlan-pollers/src/vlan_pollers/models.py)).
- **fusion consumer** — `ContextPushModel` ([fusion/models.py:25-65](../../fusion/src/fusion/models.py)): `ConfigDict(strict=True, extra='forbid')`. Declares `journey_id, vehicle_id, speed_kmh, station_approach, maintenance_mode, depot_mode, gps_valid, door_release, door_state, reservations, consist, ramp_*, door_firmware_version, scheduled_departure` (flat, added by 10-4). Does NOT declare `pis`, `trip_number`, `alarms`, `occupancy` → these 4 cause the 422.
- **inference consumer (the asymmetry)** — `ContextPushModel` ([inference/health.py:29-32](../../inference/src/inference/health.py)): `ConfigDict(strict=True)` only → `extra='ignore'` (default) → accepts the full body. **Do not** make inference stricter; bring fusion to a workable contract.
- **Strict-validation tests to keep green** — `test_context_push_extra_field_rejected`, `test_context_push_strict_bool_rejects_strings` ([fusion/tests/unit/test_context.py:11-22](../../fusion/tests/unit/test_context.py)). These encode the 2026-05-20 decision; AC2 preserves them.
- **10-4 targeted push (the interim workaround this story supersedes)** — `update_pis` sends `{scheduled_departure, journey_id}` to fusion; `fusion/context_state.py:41-44` + `models.py:62-65` carry the flat `scheduled_departure` field. See [10-4 story](10-4-dwell-time-aware-alert-framing-and-kpi.md) Round-2 review for the full chain.

### Related deferred items this story touches

- **F21** ([deferred-work.md:354](deferred-work.md)) — `_push_context_delta` non-atomic across fusion+inference. **AC4 closes it.**
- **DEFAULT_RETRY retries on 4xx** ([deferred-work.md:412](deferred-work.md)) — burns 50s on a 422. **6-4 removes the 422 trigger; 7-1 owns the retry-policy fix** (D2). Cross-reference, don't fix here.
- **R3-D1** ([deferred-work.md:489](deferred-work.md)) — `door_firmware_version=""` overwrites the `"unknown"` default in `update_from_push`. Same model + method you're touching. **Optional:** fold in a `min_length=1` / treat-`""`-as-None guard while here (note it in the record if you do; don't if it expands scope).

### Failure scenarios this story must survive (OEBB-specific)

1. **Partial push delivery under one-consumer outage:** fusion is briefly unreachable while inference is up. The push to inference must still land (AC4); fusion catches up on the next push. Neither consumer should be starved by the other's failure, and no exception should propagate out of `update_*` (the poller's `try/except` swallows, but the push helper should isolate per-service first).
2. **PIS delivery parity after removing the targeted push (D3):** if T3 removes the 10-4 targeted `update_pis` push, a journey's first PIS update must still populate `ctx.scheduled_departure` via the nested `pis` body BEFORE the first pre-departure alert fires — otherwise 10-4's KPI silently regresses. The contract test must prove this exact path.

### Project Structure Notes

- Containers touched: `fusion/` (model + update_from_push + tests), `vlan-pollers/` (`_push_context_delta` error isolation; possibly remove the 10-4 targeted push). Read each subpackage CLAUDE.md first (fusion: cov≥90 + mypy --strict; shared has no FastAPI dep — N/A here).
- **No new event types, no payload-schema change, no migration, no CSS, no UI.** ADR-FRESHNESS rule: this changes the `/context` push *contract* between vlan-pollers and fusion — check whether any ADR documents that contract (grep architecture.md for ContextPushModel / `/context` / context-push). If an ADR describes it, add a task to update it; the 10-4 dwell work added no ADR, and the original context-push contract may be undocumented — if so, consider whether this reconciliation warrants a short ADR (decide, note in record).

### Permission Tiers

| Action | Tier | Note |
|---|---|---|
| fusion `ContextPushModel` + `update_from_push`, tests | 2 (local edits) | normal dev mode |
| vlan-pollers `_push_context_delta` error isolation, targeted-push removal | 2 | normal dev mode |
| (Explicitly NOT in scope) `oebb_shared.http.retry.DEFAULT_RETRY` | 3 | shared contract — owned by 7-1, default permission mode if ever touched |

### References

- [Source: 10-4 story Round-1 + Round-2 reviews] — the empirical 422 confirmation + the targeted-push workaround this story supersedes
- [Source: epics.md#Epic-6 (lines 1859-1897)] — Fusion Hardening epic objectives, NFR1/NFR3
- [Source: deferred-work.md F21 (line 354), DEFAULT_RETRY (line 412), R3-D1 (line 489)]
- [Source: inference/health.py:29-32] — the `extra='ignore'` asymmetry proving fusion is the outlier
- [Source: vlan-pollers/context_state.py:108-125] — `_push_context_delta` + `_state_to_dict` (the producer)

## Dev Agent Record

### Context Reference
<!-- dev populates -->

### Agent Model Used
<!-- dev populates -->

### Pre-Flight
<!-- dev populates: assumptions, open questions (D1 approach if not Option B), simplicity check, surgical-change test -->

### Debug Log References
<!-- dev populates -->

### Completion Notes List
<!-- dev populates; MUST record the D1 reconciliation approach chosen + the D3 targeted-push fate + whether R3-D1 was folded in -->

### File List
<!-- dev populates -->

### Change Log
<!-- dev populates -->
