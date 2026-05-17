---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 05 — Passenger Guided to a Free Coach via Platform Screen (1 document)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 05 Specs

**Scope:** `D-UX-Design/scenario-05-specs/` — 1 document
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Passenger-facing portal spec (CNA portal; no alert flow; information surface for boarding)

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-passenger-portal-load-guidance.md` | Coach Guidance Panel — Load View (Space Available / Nearly Full / Full); Guidance Banner; No-Data state |

---

## Check 1 — Page Metadata

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ Scenario 05 | ✅ Passenger Portal (CNA, served from R5001C) | ✅ Coach Guidance Panel — Load Indicators | ✅ `E-Passenger-Portal/passenger-portal-ux-design.md` states 1–3 | ✅ 2026-05-14 | ✅ Draft |

**Status: ✅ PASS**

---

## Check 2 — State Flow Overview

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Portal open + train at platform + doors open | ✅ TCMS departure signal | ✅ "Journey Mode" named as successor |

**Note:** The state flow correctly shows "Coach Guidance — Load View" leading to "Journey Mode" on departure. The Refresh and Sync section adds detail on the departure transition behaviour (load diagram fades, replaced by Journey Mode panel).

**Issue found:**
⚠️ The state flow table shows only 2 states (Load View and Journey Mode) but the spec describes 3 distinct visual states: Space Available, Nearly Full, and Full/Redirect. These are sub-states within the Load View — transitions between them are driven by occupancy threshold crossing. They should either be represented in the state flow or explicitly noted as in-state updates (not state transitions). The Resolved Decisions table says "30-second refresh" — transitions between load bands happen on refresh, not on user action.

**Status: ⚠️ NEEDS MINOR FIX** — Clarify that Space Available / Nearly Full / Full are in-state visual updates (driven by occupancy data on 30s refresh), not separate navigable states.

---

## Check 3 — Purpose & Story

| Doc | Purpose statement | "The Story" | Trigger map connection |
|-----|------------------|-------------|-----------------------|
| 01 | ✅ "walk to the right door before they board, without asking staff or guessing" | ✅ Mia on the concourse stairs — concrete pre-boarding scenario | ✅ Passenger self-service — reduces Conrad's redirection workload |

**Status: ✅ PASS** — The Mia narrative is the best passenger story in the spec set. It is specific (Linz Hbf, concourse stairs, 20 seconds from diagram to seat), action-oriented, and communicates the design's value in one paragraph.

---

## Check 4 — Object ID Completeness

| OBJECT ID | Type | Notes |
|-----------|------|-------|
| `pp-coach-load-diagram` | New | Interactive train diagram |
| `pp-coach-load-card` | New | Per-coach card (instance: `pp-coach-load-card-[N]`) |
| `pp-coach-load-detail` | New | Inline expansion on coach tap |
| `pp-load-guidance-banner` | New | Above-diagram recommendation banner |

**Total: 4 new Object IDs. ✅**

**Elements without OBJECT IDs:**
- No-data state visual treatment ("greyed diagram + check platform screens message") — should be `pp-coach-load-no-data`.
- Departure transition behaviour (load diagram fades out) — this is a state transition, not a separate element. Acceptable without ID.
- Accessibility footer link ("Rollstuhl / Kinderwagen") — this is referenced in Interaction Rule 4 as "remains in the panel footer." It is a navigation element that should have an ID from the base portal spec. If not defined there, assign `pp-accessibility-footer-link` here.

**Issue found:**
⚠️ The no-data state is described in the Refresh and Sync table but has no OBJECT ID. Given the state has a specific visual treatment (greyed diagram + specific message text), it should be formally named.

**Naming convention check:**
- `pp-` prefix consistent for all portal elements ✅
- No duplicates with prior scenario IDs ✅

**Status: ⚠️ NEEDS MINOR FIX** — Assign `pp-coach-load-no-data` for the no-data state.

---

## Check 5 — Section Order & Structure

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ (diagram, banner, refresh/sync) | ✅ (5 rules) | ✅ (3 items) | ✅ | ✅ | ✅ |

**Status: ✅ PASS** — Standard section order maintained. The Refresh and Sync section is a useful addition between state description and interaction rules.

---

## Check 6 — Object Registry

| OBJECT ID | Defined? | Referenced in Rules? |
|-----------|----------|----------------------|
| `pp-coach-load-diagram` | ✅ | ✅ State flow; Interaction Rules 1, 2 |
| `pp-coach-load-card` | ✅ | ✅ Rule 3; Accessibility |
| `pp-coach-load-detail` | ✅ | ✅ Rule 3; Accessibility |
| `pp-load-guidance-banner` | ✅ | ✅ Guidance Banner section; Rule 5 (implicit); Accessibility |

**Issue found:**
⚠️ `pp-load-guidance-banner` Interaction Rule 5 says "The portal does not show the exact passenger count — only the three-band classification." This rule is about the portal generally but is placed after the guidance banner description. It should reference `pp-coach-load-card` explicitly (the element that doesn't show counts) rather than being stated as a general rule.

**Status: ⚠️ NEEDS MINOR FIX** — Update Rule 5 to reference `pp-coach-load-card` by ID.

---

## Check 7 — Design System Separation

**Doc 01 scan:**
- `--color-occupancy-green`, `--color-occupancy-amber`, `--color-occupancy-red` ✅ tokens
- 44px coach card touch target ⚠️ — accessibility constraint ✅ acceptable
- 30-second refresh cycle — system spec ✅ acceptable
- <75% / 75–89% / ≥90% thresholds — functional thresholds ✅ acceptable

**Note:** The portal base spec (`E-Passenger-Portal/passenger-portal-ux-design.md`) uses direct CSS values rather than tokens — as noted in the Scenario 10 validation. This spec correctly uses only tokens for the new elements introduced, inheriting the base spec's CSS pattern for existing elements.

**Status: ✅ PASS**

---

## Check 8 — SEO Compliance

**Partial — CNA portal is web-based.** However, this is a boarding-time UI displayed at a platform — not a publicly indexed page. The portal is served from the train's onboard network (R5001C) and is a captive portal, not indexed by search engines. SEO not applicable. Skipped.

---

## Check 9 — Cross-Spec Consistency

| Concept | Reference | Scenario 05 | Consistency |
|---------|-----------|-------------|-------------|
| Occupancy thresholds | Scenario 01 (PIS) | ✅ <75% / 75–89% / ≥90% | ✅ Identical — explicitly required in Purpose section |
| Data source | Scenario 01 (PIS) | ✅ Same Hailo-8 source | ✅ "Same data source" explicit |
| 30-second refresh | Scenario 01 (PIS) | ✅ 30 seconds | ✅ Identical |
| No exact passenger counts | Scenario 01 (PIS implicit) | ✅ Three-band only | ✅ Consistent across portal and PIS |
| Guidance banner (up to 2 coaches) | Scenario 02c (PA names 2 coaches) | ✅ Up to 2 coaches named | ✅ Consistent naming convention |
| Portal 4-band threshold (known divergence) | Scenario 10 validation, 06 specs | ✅ This spec uses 3-band (matching PIS) | ✅ Confirmed: this is the boarding guidance view (matches PIS); the seat selection view uses 4-band |
| Accessibility footer link | Scenario 06 (portal accessibility panel) | ✅ Rule 4 — link remains accessible | ✅ Correctly preserved; cross-reference to Scenario 06 spec |
| L2 dependency | PIS (Scenarios 01, 02b, 02c) | Not applicable — portal is passenger-pull, not system-push | ✅ Correctly absent — portal polls, does not receive push |

**Note on 3-band vs 4-band:** This spec uses 3-band (matching PIS), which is consistent with the intent (boarding guidance = match the platform screen). The Scenario 10 validation report documented the 4-band portal seat selection view as intentional for post-boarding coach choice. No conflict.

**Status: ✅ PASS** — Cross-spec consistency is the strongest in the spec set for this document; the explicit "must mirror PIS exactly" requirement forces alignment.

---

## Check 10 — Final Validation & Scenario Coverage

Cross-referencing Scenario 05 storyboard — passenger on platform opens portal, sees load diagram, chooses coach.

| Storyboard need | Doc | Covered? |
|----------------|-----|---------|
| Live train diagram on portal while boarding | 01 | ✅ `pp-coach-load-diagram` automatic on platform |
| Three-band colour matching PIS | 01 | ✅ Same thresholds, same tokens |
| Tap-to-detail for specific coach | 01 | ✅ `pp-coach-load-detail` inline expansion |
| Recommendation banner naming best coaches | 01 | ✅ `pp-load-guidance-banner` — up to 2 coaches |
| Same data as PIS (no divergence) | 01 | ✅ Same source; ≤30s sync |
| No exact passenger counts | 01 | ✅ Rule 5 |
| Transitions to Journey Mode on departure | 01 | ✅ TCMS departure signal → fade transition |
| No-data fallback | 01 | ✅ Greyed diagram + "check platform screens" |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| All coaches ≥ 90% (no green coaches for banner) | ✅ Banner shows "Train heavily loaded — limited space" |
| All coaches < 75% (no imbalance) | ✅ Banner not shown; diagram is sufficient |
| Train not yet at platform (passenger opens portal on approach) | ⚠️ Not addressed — if the portal is opened while the train is still approaching (not at platform, doors closed), what does the Coach Guidance panel show? The entry trigger is "doors open" — but the portal could be opened earlier |
| Coach number vs letter labelling | ⚠️ The portal uses "Coach [N]" — ÖBB uses "Wagen [N]." Spec shows bilingual "Wagen [N] / Coach [N]" for the detail expansion but not the diagram cards themselves. Confirm whether coach cards show "W[N]" or "[N]" on the card |
| Direction cue accuracy | ⚠️ `pp-coach-load-detail` shows "← Board here" or "Board here →" but the source of train direction is an Open Question. If direction is unavailable, cue should be omitted |

**Status: ⚠️ THREE MINOR GAPS** — Pre-platform state; coach label format; direction cue fallback.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | Pre-platform state not defined | 01 | ✅ **Resolved** — Interaction Rule 1 extended: "If portal is opened before doors open (train approaching or between stations), load diagram is shown but cards are greyed-out with 'Boarding data available at next stop' message — not `pp-coach-load-no-data` (which is a connection failure state)" |
| 🟡 Medium | Direction cue fallback not defined | 01 | ✅ **Resolved** — `pp-coach-load-detail` spec extended: "If train direction is unavailable, direction cue is omitted; coach detail shows status label and reservation note only — no direction arrow" |
| 🟡 Medium | 3 load bands are in-state updates, not state transitions | 01 | ✅ **Resolved** — State flow note added: "Space Available / Nearly Full / Full are visual updates within the Load View state, driven by occupancy threshold crossing on 30s refresh — not separate navigable states" |
| 🟢 Low | No-data state lacks OBJECT ID | 01 | ✅ **Resolved** — `pp-coach-load-no-data` assigned: greyed `pp-coach-load-diagram` + single-line message "Live load data unavailable — check platform screens"; reverts to standard display on data recovery |
| 🟢 Low | Rule 5 doesn't reference specific element | 01 | ✅ **Resolved** — Rule 5 updated: "`pp-coach-load-card` shows three-band classification only — no exact passenger count is displayed" |
| 🟢 Low | Coach card label format ambiguous | 01 | ✅ **Resolved** — Coach cards confirmed: show "[N]" (number only, space-constrained); bilingual "Wagen [N] / Coach [N]" label in `pp-coach-load-detail` expansion only |

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
- ✅ Metadata complete
- ✅ State Flow (in-state visual updates vs state transitions clarified)
- ✅ Purpose & Story (Mia narrative — strongest passenger story in the set)
- ✅ Object ID Completeness (5 IDs post-fix; no-data state named)
- ✅ Section Order (standard sequence maintained)
- ✅ Object Registry (all IDs referenced; Rule 5 element-specific)
- ✅ Design System Separation (tokens used; 3-band/4-band divergence correctly resolved)
- ✅ Cross-Spec Consistency (PIS threshold alignment enforced; strongest in spec set)
- ✅ Scenario Coverage (pre-platform state; direction cue fallback; label format resolved)

**External dependencies still open (not spec gaps):**
- ⏳ CNA portal dynamic component support — static vs 30s live update (portal team)
- ⏳ Train direction of travel source for direction cue (systems integration)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
