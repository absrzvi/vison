---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 03 — Conrad Escalates a Chronic Overcrowding Pattern to Claudia (1 document)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 03 Specs

**Scope:** `D-UX-Design/scenario-03-specs/` — 1 document
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Form-based capacity planning input (non-alert, non-urgent flow)

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-capacity-flag.md` | Coach Detail Panel — flag entry; Capacity Flag Form; Confirmation toast |

---

## Check 1 — Page Metadata

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ Scenario 03 | ✅ Conductor App (handheld) | ✅ Coach Detail Panel — Flag for Capacity Review | ✅ `ca-coach-detail-panel` in `scenario-01-specs/01-conductor-app-home-screen.md` | ✅ 2026-05-14 | ✅ Draft |

**Status: ✅ PASS** — Notably, this spec correctly references the specific element (`ca-coach-detail-panel`) within the base state doc, not just the doc itself. Most precise base state reference in the spec set.

---

## Check 2 — State Flow Overview

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Tap "Flag for capacity review" in coach detail | ✅ Send / Cancel | ✅ Coach Detail Panel → Form → Confirmation |

**Note:** The state flow is a clean linear 3-step: coach detail → form → confirmation. No branching needed — this is not an alert response, it is a structured submission. The simplicity is appropriate and correctly represented.

**Issue found:**
⚠️ The confirmation state (`ca-capacity-flag-confirmation`) is a toast — it appears over the home screen after the modal closes. The state flow diagram ends at "Confirmation" but does not show where Conrad lands after the toast dismisses (he should be back on the home screen, not the coach detail panel). Minor — the dismissal destination should be explicit.

**Status: ⚠️ NEEDS MINOR FIX** — State flow confirmation exit: "Toast dismisses after 4s → Home Screen (coach detail panel closed)."

---

## Check 3 — Purpose & Story

| Doc | Purpose statement | Narrative | Trigger map connection |
|-----|------------------|-----------|-----------------------|
| 01 | ✅ "Surface the pattern to Claudia with evidence attached, in under 60 seconds, without writing a report" | ✅ "Third consecutive Friday, same pattern" — Conrad's voice | ✅ Conrad cannot fix chronic overcrowding; his value is the pattern observation |

**Note:** The purpose statement is the most concise and precise in the spec set. The 60-second benchmark is concrete and testable — this is good spec writing.

**Status: ✅ PASS**

---

## Check 4 — Object ID Completeness

| OBJECT ID | Type | Notes |
|-----------|------|-------|
| `ca-capacity-flag-form` | New | Full-screen modal form |
| `ca-capacity-flag-confirmation` | New | Toast overlay |

**Elements without OBJECT IDs:**
- "Flag for capacity review" action row in `ca-coach-detail-panel` — this is an **extension** of the base element, not a new element. Acceptable without a distinct ID. However, for traceability (especially the "already flagged" state), consider assigning `ca-capacity-flag-trigger` as the entry row ID.
- 7-day trend sparkline inside `ca-capacity-flag-form` — inline data visualisation within the form. Should it have an ID? Given `aria-label` is specified in Accessibility, the element is accessible. An ID would help traceability. Consider `ca-capacity-flag-trend`.
- Additional coaches chip picker — inline within the form. Consider `ca-capacity-flag-coach-picker`.

**Issue found:**
⚠️ Three sub-elements within `ca-capacity-flag-form` lack IDs. While each is described and accessible, the spec would be cleaner if the form's interactive sub-components had IDs for implementation traceability.

**Naming convention check:**
- Both IDs use `ca-` prefix ✅
- Consistent with naming pattern ✅
- No duplicates with prior scenario IDs ✅

**Status: ⚠️ NEEDS MINOR FIX** — Assign IDs to trend graph and coach picker for implementation traceability.

---

## Check 5 — Section Order & Structure

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ (3 states: entry row, form, confirmation) | ✅ (5 rules) | ✅ (3 items) | ✅ | ✅ | ✅ |

**Status: ✅ PASS** — Standard section sequence maintained including Accessibility. The form is well-structured with pre-filled and editable fields clearly separated.

---

## Check 6 — Object Registry

| OBJECT ID | Defined? | Referenced in Rules? |
|-----------|----------|----------------------|
| `ca-capacity-flag-form` | ✅ | ✅ Rule 2 (trend unavailable), Rule 3 (coach picker), Rule 5 (one per journey) |
| `ca-capacity-flag-confirmation` | ✅ | ✅ Send button action; Resolved Decisions (reference number) |

**Issue found:**
⚠️ The "Flagged — ref #[XXXX]" state (when Conrad has already flagged this service) replaces the entry row in `ca-coach-detail-panel` — but this state is not named or given an ID. It is a distinct UI state of the flag trigger that needs to be identifiable. Consider `ca-capacity-flag-already-sent` as the state label.

**Issue found:**
⚠️ The routing preview text ("This flag will be sent to the Control Centre...") is described as "below the form, before the Send button" but has no element ID. It is functionally important (sets Conrad's expectations about urgency) — label as `ca-capacity-flag-routing-preview` for traceability.

**Status: ⚠️ NEEDS MINOR FIX** — Two additional elements need IDs.

---

## Check 7 — Design System Separation

**Doc 01 scan:**
- `--color-secondary` ✅ token
- `--color-success-green` ✅ token
- 56px send button ⚠️ — touch target constraint ✅ acceptable
- 4-second toast duration — functional constraint ✅ acceptable
- ≥75% threshold for showing flag entry — functional threshold ✅ acceptable
- 200 char max note — functional constraint ✅ acceptable

**Status: ✅ PASS**

---

## Check 8 — SEO Compliance

**Not applicable.** Native handheld app. Skipped.

---

## Check 9 — Cross-Spec Consistency

| Concept | Reference | Scenario 03 | Consistency |
|---------|-----------|-------------|-------------|
| `ca-coach-detail-panel` entry point | Scenario 01 | ✅ "Flag for capacity review" row added | ✅ Consistent extension of base element |
| 75% threshold | Scenario 01 (amber threshold) | ✅ Flag entry shown at ≥75% | ✅ Consistent with amber band start |
| En-route-only restriction | Scenario 01 Rule 7 | ✅ Stated in Rule 1 | ✅ Consistent |
| Claudia analytics panel | Scenario 04 | ✅ Flag routes to analytics panel | ✅ Cross-spec closure confirmed |
| 7-day trend data | Scenario 04 analytics | ✅ Same data shown in both Conrad's flag and Claudia's detail view | ✅ Confirmed shared evidence base |
| Reference number | Scenario 02d escalation | ✅ Used here for confirmation toast | ✅ Reference system referenced for both alert and planning flows |
| Conrad flag indicator on Claudia's exception card | Scenario 04 | ✅ "Conrad flagged this service" indicator | ✅ The closed loop is confirmed on both sides |

**Critical cross-spec check — Scenario 03 ↔ Scenario 04:**

Doc 01 Rule 4 states: "The capacity flag is routed to Claudia's Control Centre dashboard (Scenario 04 analytics panel) — not to her operational escalations inbox."
Scenario 04 doc defines `cc-analytics-exception-card` with "Conrad flag indicator" — ✅ confirmed.
Scenario 04 doc defines `cc-capacity-review-modal` with "Add to capacity review queue" — ✅ this is the downstream action after Claudia reviews Conrad's flag.

The loop is closed correctly. Both specs see the same data (7-day trend); both specs reference each other. This is the "closed loop" value the design is meant to demonstrate.

**Status: ✅ PASS** — Cross-scenario consistency between 03 and 04 is the strongest closed loop in the spec set.

---

## Check 10 — Final Validation & Scenario Coverage

Cross-referencing Scenario 03 storyboard — Conrad observes chronic overcrowding, raises a structured flag to Claudia with trend data attached.

| Storyboard need | Doc | Covered? |
|----------------|-----|---------|
| Conrad raises flag from coach detail | 01 | ✅ Entry row in `ca-coach-detail-panel` |
| Flag pre-fills with service + occupancy data | 01 | ✅ Read-only pre-filled fields |
| 7-day trend included in flag | 01 | ✅ Sparkline + auto-generated trend summary |
| Conrad adds qualitative note | 01 | ✅ Optional 200-char note |
| Flag routes to Claudia (analytics, not ops) | 01 | ✅ Rule 4 + routing preview |
| Conrad gets confirmation with reference | 01 | ✅ `ca-capacity-flag-confirmation` toast |
| No duplicate flags for same service | 01 | ✅ Rule 5 — one per service per conductor per journey |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| Historical trend data unavailable | ✅ Rule 2 — "unavailable" message; form still submittable |
| Conrad adds all coaches to flag | ✅ Rule 3 — chip picker supports multi-select |
| Conrad cancels mid-form | ✅ Cancel button → returns to coach detail panel |
| Conrad already flagged this service | ✅ Rule 5 — row replaced by "Flagged — ref #[XXXX]" |
| Flag submitted during dwell (boarding) | ✅ Rule 1 — flag entry not shown during dwell |
| Coach occupancy drops below 75% after form opens | ⚠️ If Conrad opens the form when occupancy is 82% and it drops to 72% during the 60 seconds he's filling it in, should the flag be blocked on submit? The rule blocks the entry row at <75%, but the form is already open. This is an edge case with low frequency — recommend: allow submission regardless (Conrad's observation at time of entry was valid) |

**Status: ⚠️ ONE MINOR GAP** — Occupancy threshold at submit time vs form-open time.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | Occupancy threshold at submit vs form-open | 01 | ✅ **Resolved** — Rule 1 extended: "If occupancy drops below 75% while the form is open, the form remains submittable — Conrad's observation at form-open time is valid. The submitted occupancy value is the value at form-open time, not the current value at submission." |
| 🟢 Low | Confirmation exit destination unclear | 01 | ✅ **Resolved** — State flow updated: "Toast dismisses after 4s → Home Screen (modal closed; `ca-coach-detail-panel` not re-opened)" |
| 🟢 Low | Sub-elements of form missing IDs | 01 | ✅ **Resolved** — IDs assigned: `ca-capacity-flag-trend` (7-day sparkline), `ca-capacity-flag-coach-picker` (chip picker), `ca-capacity-flag-routing-preview` (routing preview text) |
| 🟢 Low | Already-flagged state not named | 01 | ✅ **Resolved** — State named `ca-capacity-flag-already-sent`: entry row shows "Flagged — ref #[XXXX]" in `--color-secondary` with lock icon; non-tappable |

### Overall Status — Post-Fix

| Check | Result |
|-------|--------|
| 1 — Metadata | ✅ PASS |
| 2 — State Flow | ✅ PASS |
| 3 — Purpose & Story | ✅ PASS |
| 4 — Object ID Completeness | ✅ PASS |
| 5 — Section Order | ✅ PASS |
| 6 — Object Registry | ✅ PASS |
| 7 — Design System Separation | ✅ PASS |
| 8 — SEO | N/A |
| 9 — Cross-Spec Consistency | ✅ PASS |
| 10 — Scenario Coverage | ✅ PASS |

**Overall: ✅ READY FOR HANDOFF**

---

## Quality Audit

**Status:** ✅ READY FOR HANDOFF
**Audit Date:** 2026-05-14
**Audited By:** Sally (WDS UX Designer — Validation Mode)

**Compliance:**
- ✅ Metadata (most precise base state reference in the spec set)
- ✅ State Flow (linear 3-step; exit destination clarified)
- ✅ Purpose & Story (60-second benchmark; Conrad's voice in example note)
- ✅ Object ID Completeness (IDs assigned to all interactive sub-elements)
- ✅ Section Order (standard sequence; accessibility complete)
- ✅ Object Registry (all elements cross-referenced; already-sent state named)
- ✅ Design System Separation (tokens used; constraints documented)
- ✅ Cross-Spec Consistency (03↔04 closed loop confirmed — strongest inter-spec link in set)
- ✅ Scenario Coverage (all storyboard states; occupancy-at-submit edge case resolved)

**External dependencies still open (not spec gaps):**
- ⏳ Historical occupancy data store query key — train number vs route-and-timeslot (data team)
- ⏳ Reference number series — shared vs separate for flags and escalations (Nomad Digital product)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
