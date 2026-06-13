---
baseline_commit: 89cc1b9816b0c9282cd1e34333451496366e4e4f
---

# Story 10.3: Critical-Alert Operational SOP & Drill Cadence

Status: ready-for-dev

<!-- Created 2026-06-13 via bmad-create-story (Claude). P1 — fourth story in Epic 10 (Operator Adoption & Trust).
     Source of truth: re-scoped E10-S3 in epics.md:2277-2303 (committed ca01651) + gap analysis Gap 1
     (owning-the-gap-ai-pm-analysis.md §1, now marked superseded by the actor-model correction).
     This is a DOCUMENTATION-ONLY story: it authors operational procedures + a drill cadence. No source code. -->

## Story

As an **AI PM preparing for ÖBB pilot kickoff**,
I want **a documented SOP for critical alerts that branches on train type (conductorless vs Fernverkehr) and acknowledgement channel, a decision matrix binding (alert_code × confidence × speed × location × train type) to a routing/priority decision, and a drill cadence wired to the pilot kickoff checklist**,
so that **when a critical alert fires there is a written and rehearsed sequence — not a UI screen and a hope**.

## Context — why this story exists

Gap 1 of the AI PM gap analysis ([owning-the-gap-ai-pm-analysis.md §1](../planning-artifacts/owning-the-gap-ai-pm-analysis.md)) found that the escalation sequence is **designed but not operationalised**: the UX scenarios (02d, 12) show the screens, but there is no SOP, no drill schedule, no defined "critical confidence" threshold, and no written procedure for the failure branches. An ÖBB executive will probe this in the first procurement conversation, and "the UI shows it" is not an answer.

The work landed in code across 10-1 (confidence metadata + kill-switch), 10-6 (server-side ack/resolve lifecycle), and 10-2 (behavioural telemetry). What is missing is the **human procedure** that wraps those mechanisms: who acknowledges, on which train type, through which channel, and what happens when the primary path is unavailable.

This story produces three operational documents and wires a drill cadence into pilot kickoff. It ships **no code** — it consumes the contracts those three stories already shipped.

### Actor model — the correction that reshapes this story (2026-06-13)

> ⚠ The original Gap 1 text and scenarios 02d/12 describe a **two-actor "Conrad assess → escalate → Claudia acknowledge → resolve"** sequence. **The PoC does not use that model.** This story must be written against the corrected model below, not the historical scenario text.

- **"Conrad" = the virtual on-train conductor = the onboard AI platform that *raises* alerts.** It is **not a human in the response loop**. Conrad does not "assess", cannot be "unreachable", and has no SOP routing branch — platform liveness is the 10-1 `INFERENCE_HEARTBEAT` / AI-pipeline-health concern, not an SOP step.
- **Acknowledgement authority is train-type-conditional:**
  - **Conductorless trains** (regional / Nahverkehr) — the **default and primary PoC case**: only the **landside Fleet Manager / remote staff (Claudia)** can acknowledge + resolve. There is **no onboard human step**.
  - **Fernverkehr trains** (long-distance): an **onboard human conductor may also acknowledge** from the Conductor App; if they don't, the escalation falls through to landside after the amber window.
- **Out of PoC scope (do not write into the SOP):** the ÖBB police/station security-handoff contract and the "ÖBB security notified" outcome tag — the single-landside-actor model has no police/station hop. Open Question 1 in scenario-02d is closed by *removing* the security-handoff branch, not by signing a contract.

> **⚠ Dangling reference to fix (see Decisions D5).** Both epics.md:2279 and owning-the-gap-ai-pm-analysis.md:7 cite `memory project-actor-model-conrad` as the authority for this correction, but **that memory file does not exist on disk** (verified: only `project_container_map.md` is present in the memory directory, and MEMORY.md does not index it). The authoritative inline statements of the corrected model live in [10-6's story file](10-6-escalation-lifecycle-persistence.md) (lines 29, 64) and the epics.md re-scope. This story should not depend on a memory that was never written.

## Acceptance Criteria

**AC1 — Critical-alert SOP document**
Given a critical alert fires (critical class per D2 — shipped codes `slip_fall`, `door_obstruction`/`door_fault` at speed; plus spec'd-but-not-yet-emitted `fire`/`unattended_item` — gated by `confidence_score >= 0.85` where a score is present, D3), raised by the on-train platform (Conrad),
when the operational team responds,
then `_bmad-output/operational-procedures/critical-alert-sop.md` exists and documents, with an explicit decision flow, all four branches:
1. **Conductorless-train branch** (default / primary): landside Fleet Manager / remote staff acknowledge + resolve. No onboard-human step.
2. **Fernverkehr branch**: onboard conductor may acknowledge from the Conductor App; if not acknowledged within the amber window it **falls through to landside**.
3. **Landside-unreachable branch**: a secondary Control Centre operator is paged.
4. **Dead-zone branch**: the event is queued onboard and the escalation surfaces on reconnect (matches the event-store sync-cursor behaviour — it is not lost).

The SOP states the **critical-confidence threshold = `confidence_score >= 0.85`** explicitly, and names which `alert_code` values are "critical class" (see D2). Each branch has a named ÖBB ops role and a time budget (the amber window).

**AC2 — Critical-alert decision matrix**
Given the matrix in `_bmad-output/operational-procedures/alert-routing-matrix.md`,
when an alert is emitted,
then the matrix defines, **per `alert_code`**, the priority/handling decision as a function of: `confidence_score` bucket, train speed bucket (in-station / in-transit), location (in-station vs in-transit), **and train type (conductorless vs Fernverkehr)**.
Each row carries a **signoff date column** and an **ÖBB ops owner column** (left as `TBD — ÖBB signoff` placeholders since signoff is a pilot-kickoff process boundary, not a dev deliverable). The matrix's outputs are decisions like `{landside-immediate, fernverkehr-onboard-first-then-landside, advisory-only}` — no `police/station` output exists.

**AC3 — Drill cadence document + pilot-kickoff-checklist wiring**
Given `_bmad-output/operational-procedures/drill-cadence.md`,
then it defines: **monthly tabletop drills** (the landside team — and, for Fernverkehr, an onboard conductor — walk the SOP for a randomly selected critical alert class) and **quarterly live drills** (a planted test event on a non-revenue service).
And a **pilot kickoff checklist** entry is added that references the drill cadence. Since no `pilot-kickoff-checklist.md` exists yet, this story **creates** `_bmad-output/operational-procedures/pilot-kickoff-checklist.md` with the drill-cadence line item (and a stub for the other kickoff gates), rather than editing a non-existent file.

**AC4 — Cross-linking from the gap analysis**
Given the gap analysis Gap 1,
then both `critical-alert-sop.md` and `alert-routing-matrix.md` are linked from [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md) Gap 1 (in the superseded-notice block or a new "Closed by E10-S3" line), so a reader of the gap analysis can navigate to the operational closure.

**AC5 — Internal consistency with shipped contracts**
Given the SOP and matrix reference system behaviour,
then every referenced mechanism matches what 10-1/10-6/10-2 actually shipped:
- the amber-window fall-through corresponds to the escalation `unacknowledged → acknowledged` lifecycle in the `escalations` table (10-6), not an invented timer;
- the resolve action tags referenced are exactly the four landside tags (`resolved_remotely`, `field_team_dispatched`, `false_alarm`, `no_action_needed`) — **no** `Police alerted` / `Station notified` / `Conrad instructed` (those were removed in 10-6 AC9);
- the confidence threshold and `confidence_basis` language matches the shipped `AlertRaisedPayload` (10-1).

**AC6 — Scope discipline (no out-of-scope content)**
Given the corrected actor model,
then the SOP contains **no** "Conrad assesses / Conrad unreachable" branch, **no** police/station handoff contract, and **no** "ÖBB security notified" tag. Any unavoidable reference to the historical two-actor model is explicitly marked as superseded.

## Decisions (locked — review before dev)

- **D1 — Documentation-only story; no code, no migrations.** Deliverables are four markdown files under `_bmad-output/operational-procedures/` (which does not yet exist — this story creates the directory). Permission tier is **Tier 2** (git-reviewable file edits). The Tier-3 boundary on this story is the **ÖBB signoff process** for each artefact, which is a pilot-kickoff gate, NOT a dev action — leave signoff/owner cells as `TBD — ÖBB signoff` placeholders.

- **D2 — `alert_code` is a free-form string, not an enum, and the epic's English names ≠ the shipped codes (PAYLOAD SPEC AUDIT — CRITICAL).** Verified against the shipped contract: `AlertRaisedPayload.alert_code` is `_NonEmptyStr` ([payloads.py:102,146,540](../../shared/src/oebb_shared/events/payloads.py)) — a non-empty string, **not** a closed/validated enum. The `AlarmType` literal (`emergency_brake|fire|passenger_call|intrusion|other`, [payloads.py:275](../../shared/src/oebb_shared/events/payloads.py)) is a **different** field (TCMS/diagnostics alarm types), NOT the vision `alert_code`.
  - **The epic prose uses English labels ("fall", "door-at-speed", "unattended item") that do NOT match the actual emitted strings.** Verified producer set (grep of `alert_code=` across `fusion/src/`):
    - `door_obstruction` → [door_obstruction.py:74](../../fusion/src/fusion/door_obstruction.py) — the epic's "door-at-speed" is this code at high speed (speed-correlated severity at [enrichment.py:38](../../fusion/src/fusion/enrichment.py)).
    - `door_fault` → referenced in the severity-escalation map ([enrichment.py:38](../../fusion/src/fusion/enrichment.py)).
    - `slip_fall` → [health.py:218](../../fusion/src/fusion/health.py) — this is the epic's "fall".
  - **`fire` and `unattended_item` have NO shipped fusion producer** — they appear in the epic prose but are not emitted by any current `emit_alert` call site. The matrix must mark these as **spec'd-but-not-yet-emitted** (forward-looking rows), not as live codes. Do NOT invent code strings for them; use a clearly-labelled placeholder and note the producer is not yet implemented.
  - **Consequence for the matrix:** key rows on the **verified strings** (`door_obstruction`, `door_fault`, `slip_fall`) for live codes; add forward-looking rows for `fire`/`unattended_item` flagged as pending a producer. Note that `alert_code` is a producer-defined string, not an enforced enum — an unknown code is "unknown class → default advisory-only", not a validation error. Do not write the matrix as if `alert_code` were a fixed enum.

- **D3 — `confidence_score` can be `None`; the 0.85 threshold only applies when present.** `confidence_score` is `None` when `confidence_basis == "sensor"` ([payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py)). The SOP/matrix "critical confidence ≥ 0.85" gate therefore applies only to model/fused-basis alerts; sensor-basis critical alerts (e.g. a TCMS fire alarm) are critical by **class**, not by score. State this explicitly so the SOP doesn't imply a fire alarm is downgraded for lacking a score.

- **D4 — Amber window references the 10-6 lifecycle, not a new timer.** The "falls through to landside after the amber window" language must map to the escalation staying `unacknowledged` in the `escalations` table past a threshold ([10-6 AC3](10-6-escalation-lifecycle-persistence.md)). The PoC does not yet implement an automatic timed fall-through in code (no auto-page job ships in this epic) — so the SOP describes the **operational** expectation and notes the automation is a **Phase 2 / Epic 11 follow-up** (do not claim an automatic pager exists). Pick a concrete window for the document (the historical specs used **10 minutes**); flag it as `PoC default pending ÖBB confirm`.

- **D5 — Fix or write the dangling `project-actor-model-conrad` memory.** epics.md:2279 and owning-the-gap-ai-pm-analysis.md:7 cite a memory that does not exist. Two acceptable resolutions (dev picks, non-blocking): (a) add a task to write that memory file capturing the corrected actor model so the citation resolves, OR (b) leave the memory out and ensure the SOP itself is the self-contained authority. Recommended: (a) — the citation already exists in two committed docs, so the memory should exist. This is the project's own memory dir (`.claude/projects/.../memory/`), out of the git tree; writing it is a Tier-2-equivalent local action.

- **D6 — Train-type metadata source is an open ÖBB dependency (non-blocking for authoring).** The matrix's train-type column needs per-vehicle "conductorless vs Fernverkehr" metadata. epics.md:2300 flags: "confirm source with ÖBB (fleet config) before the matrix's train-type column can be populated." This blocks **populating** the column with real fleet data, not **authoring** the matrix structure. Write the matrix with the train-type column and a `TBD — ÖBB fleet-config source` note; do not invent a metadata source.

## Tasks / Subtasks

- [ ] **T1 — Create the operational-procedures directory + critical-alert SOP** (AC1, AC5, AC6)
  - [ ] Create `_bmad-output/operational-procedures/` (new directory).
  - [ ] Write `critical-alert-sop.md`: critical-class definition (alert_codes + `confidence_score >= 0.85` gate per D2/D3), the four branches (conductorless / Fernverkehr / landside-unreachable / dead-zone), each with a named ÖBB ops role and the amber-window time budget (D4).
  - [ ] Ensure NO Conrad-as-human branch, NO police/station handoff, NO "ÖBB security notified" tag (AC6).
  - [ ] Reference the four shipped landside action tags by their canonical keys (AC5).
- [ ] **T2 — Critical-alert decision matrix** (AC2, AC5, D2, D6)
  - [ ] Write `alert-routing-matrix.md` as a table keyed on `alert_code`, with columns: confidence bucket, speed bucket, location, train type, routing decision, ÖBB ops owner (`TBD`), signoff date (`TBD`).
  - [ ] List concrete critical-class `alert_code` strings (grep fusion `emit_alert` call sites for the real producer strings — do not invent); mark unknown codes → advisory-only default.
  - [ ] Add the `TBD — ÖBB fleet-config source` note on the train-type column (D6).
- [ ] **T3 — Drill cadence + pilot kickoff checklist** (AC3)
  - [ ] Write `drill-cadence.md`: monthly tabletop + quarterly live drills, with the Fernverkehr onboard-conductor participation note.
  - [ ] Create `pilot-kickoff-checklist.md` with the drill-cadence line item + stubs for other kickoff gates (ÖBB signoffs, train-type metadata confirmation).
- [ ] **T4 — Cross-link from gap analysis** (AC4)
  - [ ] Add "Closed by E10-S3 →" links to `critical-alert-sop.md` and `alert-routing-matrix.md` in [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md) Gap 1.
- [ ] **T5 — Resolve the dangling memory reference** (D5)
  - [ ] Either write the `project-actor-model-conrad` memory file (recommended) or confirm the SOP is self-contained and note the citation is illustrative.
- [ ] **T6 — Self-review against AC5/AC6 consistency** before handoff
  - [ ] Verify every shipped-contract reference (action tags, confidence basis, escalation lifecycle) matches 10-1/10-6/10-2 — no invented mechanisms.

## Dev Notes

### This is a documentation story — no UPDATE source files

Per the FULL-FILE-READS persistent rule: the rule targets *source files marked UPDATE*. This story's only edit to an existing file is the gap-analysis cross-link (T4) — a 2-line addition to [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md), whose full current state I have already read (it carries the superseded-notice block at line 7). Everything else is NEW markdown. There is no code, no payload, no CSS, and no ADR change (CSS-TOKEN and ADR-FRESHNESS persistent rules are N/A here — confirmed: this story changes no EventType, no payload class, no fusion endpoint).

### Shipped-contract ground truth (cite these, don't reinvent)

- **Action tags (4, landside-only):** `resolved_remotely`, `field_team_dispatched`, `false_alarm`, `no_action_needed` — canonical keys, UI labels are display-only. Source: [10-6 AC9 + D3](10-6-escalation-lifecycle-persistence.md). The stale `Police alerted / Station notified / Conrad instructed / Passenger assisted` set was **removed** in 10-6 — do not reference it.
- **Escalation lifecycle:** `unacknowledged → acknowledged → resolved` in the `escalations` table; ack endpoint `POST /api/v1/escalations/{escalation_id}/acknowledge`. Source: [10-6 AC1–AC5](10-6-escalation-lifecycle-persistence.md). The "amber window fall-through" = staying `unacknowledged` past the window (D4).
- **Confidence:** `AlertRaisedPayload.confidence_score: float | None`, `confidence_basis: Literal["model","sensor","fused"]`. `None` score iff `sensor` basis. Source: [payloads.py:102,116-120](../../shared/src/oebb_shared/events/payloads.py), [epics.md:2223](../planning-artifacts/epics.md).
- **`alert_code` is `_NonEmptyStr`, not an enum** (D2) — the single most likely dev mistake on this story is treating it as a closed enum.
- **Platform liveness ≠ an SOP branch:** "Conrad unreachable" in the historical text is now the 10-1 `INFERENCE_HEARTBEAT` / AI-pipeline-health Red state — a System Health concern, not a critical-alert routing branch.

### Failure scenarios this SOP must survive (OEBB-specific)

1. **Dead-zone during a critical alert (conductorless train):** a fire alert fires while the train is in a tunnel with no landside connectivity. The SOP's dead-zone branch + event-store sync cursor must ensure the escalation is queued onboard and surfaces on reconnect — it is NOT silently dropped, and the amber window does not "expire" the alert during the outage.
2. **Fernverkehr fall-through race:** an onboard conductor opens the alert but navigates away without acknowledging (the 10-2 silent-dismissal case). The SOP must define that this still falls through to landside — onboard *viewing* is not *acknowledging*.

### Project Structure Notes

- New directory `_bmad-output/operational-procedures/` aligns with the deliverable paths named in epics.md:2301. No conflict with existing structure.
- These are planning/operational artefacts, not application code — they live under `_bmad-output/`, not in any of the four code subpackages.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-E10-S3 (lines 2277-2303)] — re-scoped story spec
- [Source: _bmad-output/planning-artifacts/owning-the-gap-ai-pm-analysis.md#1] — Gap 1 (superseded-notice block has the corrected actor model)
- [Source: _bmad-output/implementation-artifacts/10-6-escalation-lifecycle-persistence.md] — shipped escalation lifecycle + 4-tag taxonomy + actor-model statement
- [Source: shared/src/oebb_shared/events/payloads.py:102,116-120,275] — `alert_code`/`confidence_score`/`confidence_basis`/`AlarmType` contracts
- [Source: _bmad-output/design-artifacts/C-UX-Scenarios/02d-conrad-unattended-bag.md] — historical two-actor scenario (READ AS SUPERSEDED)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
