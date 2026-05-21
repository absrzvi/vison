# Epic 4 Retrospective — Phase 2
**Date:** 2026-05-21
**Facilitator:** Amelia (Developer)
**Participants:** Amelia (Developer), Winston (Architect), Saga (Analyst), Freya (UX), Abbas (Project Lead)
**Epic:** E4 — Onboard Edge Pipeline (Phase 2: stories 4-9 + 4-10)
**Scope:** Phase 2 covers only 4-9 (closed-ledger reconciliation) and 4-10 (coach comfort index). Phase 1 (4-1 through 4-8 + 4-cs1) is covered in `epic-4-retro-2026-05-21.md`.

---

## Stories in Scope

| Story | Patches | Decisions | Final Coverage | Status |
|-------|--------:|----------:|---------------:|--------|
| 4-9 closed-ledger reconciliation | 17 | 5 resolved | 94.15 % | done |
| 4-10 coach comfort index | 5 | 4 resolved (all in code review) | 94.20 % | done |
| **Phase 2 totals** | **22** | **9** | | **2 / 2** |

**Epic 4 complete totals (phases 1 + 2):** 174 patches, 38 decisions, all 11 stories + 1 cloud-sync story done.

---

## Phase-1 Action Item Follow-Through

These were the 8 action items from the phase-1 retro. Phase-2 is the accountability pass.

| # | Action | Status | Evidence |
|---|--------|:------:|----------|
| **A1** | Story-pivot discipline: abort and re-spec rather than patch | ✅ N/A | Neither 4-9 nor 4-10 required an architectural pivot mid-flight. The phase-1 lesson was not tested here, but the pattern is codified. |
| **A2** | No story to review with red tests | ✅ Completed | Both 4-9 and 4-10 sent to review with full pass bars — 121 and 139 tests respectively, zero failures before review was opened. |
| **A3** | create-story spec-audit step | ✅ Completed | 4-9 create-story explicitly flagged the `LedgerDriftAlertPayload` shape divergence (epic spec vs shipped `shared/`) and D5 rename. 4-10 flagged the `{ reserved_seats, occupied_seats, standing_count }` divergence. Both were resolved in party-mode / story decisions, not silently patched. |
| **A4** | ADR freshness — add "current as of" date; update ADR-17 | ⏳ Partial | 4-9 D5 rename (LEDGER_DRIFT_ALERT → LEDGER_DRIFT_OBSERVATION) contradicts ADR-17's description. The rename shipped without an ADR-17 update. This slipped — see new A1 below. |
| **A5** | Triage deferred-work.md before next epic | ⏳ Not done | deferred-work.md grew again (4-10 added 4 new deferred items). No formal triage pass occurred. Carry forward. |
| **A6** | Consolidate round-2 reviews inside story files | ✅ Completed | 4-9 and 4-10 have a single story file each with all review rounds appended as sections. No `4-X-code-review-followup.md` orphans created. |
| **A7** | Fusion ingest pattern ADR | ⏳ Not done | D1-A (double-POST from inference) was used by 4-9 and piggy-backed by 4-10, but no ADR was written to lock the pattern. Carry forward. |
| **A8** | Run this phase-2 retro | ✅ Completed | This document. |

**Net:** 4 of 8 fully completed. A4, A5, A7 carry to the next epic's prep.

---

## What Went Well

### Both stories shipped clean on the first review pass
4-9 review produced 17 patches + 5 decisions, all applied in one batch, and the story moved straight to done. 4-10 review produced 5 patches + 4 decisions, also one-pass to done. Neither story required a round-2 review cycle — a direct improvement over the 4-5 and 4-8 patterns from phase 1.

### A2 held: no red tests in review
Both stories went to review with full pass bars. The 4-5 lesson (sent to review with 2 failing tests) was not repeated.

### 4-9 decisions produced a better design than the spec
Party-mode resolved D5 (rename ALERT → OBSERVATION) after Freya asked "what does the operator *do* when they see this?" This is the kind of cross-domain question that the single-agent dev loop misses. The rename avoided shipping a misleading contract to the landside team.

The `both_seeded` cold-start gate (D2) was also roundtable-refined — Amelia's addition of the dual-seeded check prevented spurious zero-vs-camera delta emits at journey start that the original "seed to zero" proposal would have caused.

### 4-10 two-phase baseline advance (P1) was the right call
The code-review finding that `on_occupancy_update` was atomically updating `_last_emitted_pct` before the HTTP emit succeeded was a real correctness bug. The P1 patch split the mutation into: return payload (no state change) → emit → `confirm_emit()` advances baseline. This is the same invariant as 4-9's drift-bucket pattern (`_last_drift_bucket` only updates on successful emit), so it's consistent across the two comfort/ledger state machines.

### peek/consume split (D3) preserved edge semantics under suppression
The original `observe_station_approach_edge()` consumed the edge unconditionally at call time. Under suppression, the edge was lost. The D3 fix (add `peek_station_approach_edge()` + `consume_station_approach_edge()`) let the handler check for the edge, decide whether to suppress, and only consume if it actually emitted. A small API change with non-trivial correctness implications — caught by code review, not by initial tests.

### spec-audit in create-story caught both payload divergences
4-9 and 4-10 create-story explicitly compared `epics.md` payload definitions against shipped `shared/` contracts. Both divergences were documented in story Decisions sections and resolved before dev, not during code review. This is the A3 lesson from phase 1 confirming it works.

### Coverage held above 94% on both stories
4-9: 94.15 %, 4-10: 94.20 %. Both well above the 90 % gate. The incremental test-writing approach (story tests live in dedicated `test_ledger.py` and `test_comfort_index.py` modules) kept the coverage meaningful rather than diluted.

---

## What Didn't Go Well

### Pattern 1: ADR-17 was not updated when 4-9 D5 shipped

4-9 renamed `LEDGER_DRIFT_ALERT` → `LEDGER_DRIFT_OBSERVATION` and changed the payload shape from aggregate to per-coach. ADR-17 still describes the old names and aggregate shape. The phase-1 retro flagged this (A4), 4-9 was the story that should have shipped the ADR update, and it didn't happen.

**Cost:** Any developer reading ADR-17 to understand the ledger design gets the wrong picture. The ADR is now actively misleading.

**Root cause:** "Update the ADR in the same commit" was listed as an action item but not codified as a checklist item in the story or in create-story's persistent_facts. It lived as guidance-in-a-retro-doc and was not surfaced again at story execution time.

**Lesson:** Action items that must happen in a specific story need to appear in that story's task list, not just in a retro doc. When create-story runs for a story that touches an ADR, the story's task list should include an explicit "update ADR-X" checkbox.

### Pattern 2: 4-10 test for D3 suppression was wrong on first write

The initial `test_comfort_index_station_edge_preserved_under_suppression` seeded a coach while the gate was already suppressed (maintenance_mode True), then tested the edge. But a coach seeded under suppression never had a baseline, so the "edge preserved" assertion was testing a degenerate case. The test had to be rewritten: seed the coach while the gate is open, then enter suppression + station_approach simultaneously, then verify the edge re-fires on the next clear push.

**Cost:** One test rewrite cycle during the same session. Small, but reveals a gap in the test scenario thinking.

**Root cause:** The scenario for D3 required reasoning about two orthogonal state machines (gate and context) together. The first test design only thought about one axis (gate open/closed) and missed the interaction with the coach observation state.

**Lesson:** When a test covers the intersection of two state machines (gate × context, ledger × context, etc.), write the scenario in three steps: (1) set up the non-suppressed baseline, (2) enter the combined suppressed+trigger state, (3) verify the recovery. This three-step pattern would have caught the degenerate seed scenario immediately.

### Pattern 3: deferred-work.md is not being triaged between stories

Phase 1 generated 4 deferred items for 4-8. Phase 2's 4-10 added 4 more. The file now has items from multiple stories across the epic, with no triage pass having occurred since it was last formally reviewed. Items in the file include W1 idempotency keys (from 4-8), the WS-subscription alternative (4-9 D1-B), car_id key space canonicalisation (4-10 D4), station-edge freshness (4-10 D1 snapshot contract), and the LEDGER_DRIFT_ALERT → alert promotion path (4-9 D5).

**Cost:** The list grows without anyone deciding which items belong in the next epic backlog. Real future scope is getting buried with noise.

**Root cause:** The triage step (phase-1 A5) was not scheduled as a concrete pre-epic task with an owner. It exists as a recommendation in a retro doc.

**Lesson:** The triage event needs to happen before the next epic's `create-story` run, not just "before the epic starts." Add an explicit "triage deferred-work.md" task to the epic planning workflow.

---

## Key Design Insights for Future Stories

### The two-phase emit invariant is now established across fusion state machines

Both `CoachLedger._last_drift_bucket` and `ComfortIndexState._last_emitted_pct` follow the same pattern: tentative result → HTTP emit → confirm mutation. This invariant should be documented in `fusion/CLAUDE.md` (or the project-context) as a first-class pattern for any new fusion state machine. Future state machines that update eagerly before emit will create the same class of correctness bug.

### The peek/consume pattern generalises

`ContextState.peek_station_approach_edge()` / `consume_station_approach_edge()` is a generalisation of the `observe_*` pattern. If future edge detectors need to survive suppression, this is the correct pattern. The existing `observe_ramp_signal()` still works for cases where consuming unconditionally is fine (ramp edge currently isn't suppression-gated), but the pattern library now has both forms.

### Fusion's `/candidates/*` POST pattern has two confirmed consumers per handler

`/candidates/occupancy_update` now serves: ledger drift check → comfort index check. The handler is growing. When a third consumer arrives, consider extracting a pipeline/chain pattern rather than adding more sequential calls. This is a potential refactor trigger to track.

---

## Action Items

| # | Action | Detail | When |
|---|--------|--------|------|
| **A1** | Update ADR-17 | Add "current as of" date. Correct the payload name (LEDGER_DRIFT_OBSERVATION), correct the shape (per-coach, not aggregate), correct the event type key. Do this before any next story that touches the ledger or event types. | Before next story touching fusion/ledger |
| **A2** | Codify two-phase emit invariant in fusion/CLAUDE.md | Document: any new fusion state machine that tracks "last emitted value" must use confirm_emit() pattern (return payload without mutating → emit → confirm). Reference comfort_index.py and ledger.py as canonical examples. | With next fusion story |
| **A3** | Triage deferred-work.md before next epic create-story | Pull all open items, categorise: next-epic backlog / post-PoC / dismiss. Owner: Abbas. Must complete before the first create-story run of the next epic. | Before next epic planning |
| **A4** | Fusion ingest pattern ADR (carry from phase-1 A7) | Document D1-A (double-POST from inference) as the current PoC approach. Note D1-B (WS fan-out) as the production-grade alternative. Lock the precedent so future stories don't re-litigate it. | Before next story adding a new fusion consumer |
| **A5** | create-story should add "update ADR-X" task when a story touches a known ADR | When a story's scope touches an architectural decision tracked in an ADR, the created story file should include an explicit checkbox: "[ ] Update ADR-X to reflect this story's changes." This prevents the A4/ADR-17 slip from recurring. | Codify in bmad-create-story persistent_facts |
| **A6** | Three-step pattern for cross-state-machine tests | Document in project-context or fusion/CLAUDE.md: tests covering two orthogonal state machines use the three-step scenario: (1) non-suppressed baseline, (2) combined suppressed+trigger state, (3) recovery. | With next fusion story that has cross-machine tests |

---

## Epic 4 Full Closure Summary

Epic 4 is the largest engineering undertaking in this project to date: 11 stories + 1 cloud-sync story, 174 review patches, 38 decisions, all under strict quality gates.

The quality loop worked. Every story shipped with `mypy --strict`, `ruff` clean, ≥90 % coverage, and an adversarial code review. Phase 2 improved on Phase 1: no round-2 review cycles, no red bars in review, coverage up to 94 %. The party-mode decision instrument produced two design improvements (D5 rename, `both_seeded` gate) that a single-agent loop would have missed.

The remaining gaps are process gaps, not code gaps. ADR-17 needs to catch up with shipped reality. deferred-work.md needs a triage pass. The two-phase emit invariant should be documented before a third state machine inherits the wrong pattern.

Epic 5 (Luggage Monitoring) is already done. The next planning decision is which epic follows — the lessons from Epic 4 should inform that backlog review, specifically the fusion ingest pattern (A4) and the deferred-work triage (A3) before any new story creation.
