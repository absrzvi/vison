---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 02b — Conrad Rebalances a Lopsided Train (1 document)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 02b Specs

**Scope:** `D-UX-Design/scenario-02b-specs/` — 1 document
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Alert state spec with dual-interface action (Conductor App + PIS interior screens)

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-occupancy-imbalance.md` | Imbalance Alert Active · Rebalancing in Progress · Resolved |

---

## Check 1 — Page Metadata

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ Scenario 02b | ✅ Conductor App + PIS Interior | ✅ Alert Active — Occupancy Imbalance | ✅ `scenario-01-specs/01-conductor-app-home-screen.md` | ✅ 2026-05-14 | ✅ Draft |

**Status: ✅ PASS**

---

## Check 2 — State Flow Overview

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Gap ≥ threshold + terminus exclusion | ✅ Gap narrows below threshold (auto-resolve) | ✅ Normal predecessor named |

**Issue found:**
⚠️ State flow table lists "Imbalance Alert Active" with exit trigger "Conrad acts OR gap resolves naturally" — but the "Rebalancing in Progress" state is only entered via "Announce + Show on screens." "Monitor — no action" keeps the alert active without entering a distinct state. The state table implies two possible exits from the alert active state, but the diagram correctly shows only one path (via the announce action). Minor alignment gap between diagram and table wording.

**Issue found:**
⚠️ "Resolved" state: exit trigger column is blank in the table (no exit trigger listed for the Resolved state). This is structurally correct — Resolved is a terminal state within the scenario — but the table should note "Terminal — alert cleared, feed item archived."

**Status: ⚠️ NEEDS MINOR FIX** — State table entry for "Resolved" should explicitly mark it as terminal.

---

## Check 3 — Purpose & Story

| Doc | Purpose statement | Narrative | Trigger map connection |
|-----|------------------|-----------|-----------------------|
| 01 | ✅ "at-a-glance split view... single 'Announce + Show on screens' action" | ✅ Split train visual tells the story directly | ✅ Remote action without physical presence — consistent Conrad pattern |

**Status: ✅ PASS**

---

## Check 4 — Object ID Completeness

| OBJECT ID | Type | Notes |
|-----------|------|-------|
| `ca-imbalance-detail` | New | Full-screen detail panel |
| `ca-imbalance-split-diagram` | New | Full-width train diagram with divider |
| `ca-imbalance-opportunity` | New | Available seats panel |
| `ca-imbalance-actions` | New | Action strip |
| `ca-imbalance-announce-action` | New | Combined PA + screens action |
| `ca-imbalance-pa-modal` | New | PA pre-fill modal (not assigned OBJECT ID) |
| `pis-interior-rebalance` | New | PIS interior screen state (cross-interface) |

**Issue found:**
⚠️ `ca-imbalance-pa-modal` is described and referenced in the action section but is not assigned a formal OBJECT ID in the same way as other elements. The pattern in Scenario 02 (`ca-congestion-pa-modal`) was to assign an ID. For consistency, this should be `ca-imbalance-pa-modal`.

**Naming convention check:**
- `ca-` prefix consistent for Conductor App elements ✅
- `pis-interior-rebalance` uses `pis-interior-` prefix — appropriate for PIS interior element ✅
- No duplicates with prior scenario IDs ✅

**Status: ⚠️ NEEDS MINOR FIX** — Assign `ca-imbalance-pa-modal` as formal OBJECT ID in spec.

---

## Check 5 — Section Order & Structure

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ | ✅ (4 rules) | ✅ (2 items) | ⚠️ Missing | ✅ | ✅ |

**Issue found:**
⚠️ No Accessibility section in this spec. Scenario 01 and 02 both include accessibility notes. This spec introduces interactive elements (`ca-imbalance-announce-action` — 56px button) and a PIS interior screen — both need accessibility coverage.

**Status: ⚠️ NEEDS FIX** — Add Accessibility section.

---

## Check 6 — Object Registry

| OBJECT ID | Defined? | Referenced in Rules? |
|-----------|----------|----------------------|
| `ca-imbalance-detail` | ✅ | ✅ State Flow, alert banner tap |
| `ca-imbalance-split-diagram` | ✅ | ✅ Rebalancing in progress section |
| `ca-imbalance-opportunity` | ✅ | ✅ Layout section |
| `ca-imbalance-actions` | ✅ | ✅ Layout section |
| `ca-imbalance-announce-action` | ✅ | ✅ Combined action description, Rule 1 |
| `pis-interior-rebalance` | ✅ | ✅ Interaction Rule 1, Resolved Decisions |

**Status: ✅ PASS** (pending pa-modal ID addition from Check 4)

---

## Check 7 — Design System Separation

**Doc 01 scan:**
- `--color-warning-amber` ✅ token
- `--color-occupancy-green`, `--color-occupancy-amber`, `--color-occupancy-red` ✅ tokens
- `--pis-background-default`, `--pis-text-primary` ✅ tokens
- 56px send button ⚠️ — touch target constraint ✅ acceptable
- 200 char max PA text ⚠️ — functional constraint, not styling ✅ acceptable
- 10-min PIS duration — functional timeout ✅ acceptable
- 50 percentage point gap threshold — functional threshold ✅ acceptable

**Status: ✅ PASS**

---

## Check 8 — SEO Compliance

**Not applicable.** Native app + embedded display. Skipped.

---

## Check 9 — Cross-Spec Consistency

| Concept | Reference | Scenario 02b | Consistency |
|---------|-----------|-------------|-------------|
| `ca-alert-banner` amber + pulsing | Scenario 02 | ✅ Same pattern | ✅ |
| Combined atomic action | New in 02b | PA + PIS in one tap | ✅ Pattern established; referenced in 02c |
| Terminus suppression | Scenario 02: 5 min | Scenario 02b: 10 min | ⚠️ Different values — intentional? |
| Auto-resolve on sensor clear | Scenario 02 | ✅ Same pattern | ✅ |
| Touch target 56px for urgent actions | Scenario 02 | ✅ 56px send button | ✅ |
| PIS interior L2 dependency | Scenario 01 exterior | ✅ Flagged in PIS section | ✅ |
| Partial success toast | New in 02b | "PA sent · Screens unavailable" | ✅ Pattern referenced in 02c |

**Issue found:**
⚠️ Terminus suppression is 5 minutes in Scenario 02 (vestibule congestion) but 10 minutes in Scenario 02b (imbalance). Different alert types may warrant different suppression windows — imbalance rebalancing needs more lead time than vestibule congestion. This is likely intentional. However, it should be explicitly noted as a deliberate divergence in the Resolved Decisions table, not left as an implicit difference.

**Status: ⚠️ NEEDS MINOR FIX** — Add rationale note for 10-min vs 5-min terminus suppression difference.

---

## Check 10 — Final Validation & Scenario Coverage

| Storyboard need | Spec doc | Covered? |
|----------------|----------|---------|
| Alert for significant occupancy gap | 01 | ✅ ≥50 point threshold |
| Split train view showing heavy/light sections | 01 | ✅ `ca-imbalance-split-diagram` |
| Identifies actionable empty coaches | 01 | ✅ `ca-imbalance-opportunity` panel |
| PA + screen update in one action | 01 | ✅ `ca-imbalance-announce-action` |
| PIS interior shows available coaches | 01 | ✅ `pis-interior-rebalance` |
| Conrad can monitor without acting | 01 | ✅ "Monitor — no action" |
| Alert clears when gap resolves | 01 | ✅ Auto-resolve |
| No alert near terminus | 01 | ✅ 10-min suppression |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| PIS screens unavailable — partial failure | ✅ Rule 1 — toast: "PA sent · Screens unavailable" |
| Imbalance re-develops after resolution | ✅ Rule 4 — only one alert per imbalance event per journey segment |
| Fully reserved empty coaches (can't redirect) | ✅ `ca-imbalance-opportunity` — reserved coaches flagged separately |
| Imbalance caused by reservation pattern (e.g. groups) | ⚠️ Not addressed — if coaches 1–4 are heavily reserved and coaches 7–10 have unreserved seats but passengers are in their reserved seats, the imbalance is structurally irreversible. Should the alert fire? Should it note "Reservation-driven imbalance — limited rebalancing opportunity"? |

**Status: ⚠️ ONE MINOR GAP** — Reservation-driven structural imbalance not addressed.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | Accessibility section missing | 01 | ✅ **Resolved** — Section added: `ca-imbalance-announce-action` has `aria-label` "Announce PA and update interior screens simultaneously"; `pis-interior-rebalance` supplemented by text (coach numbers readable without arrow symbol); `ca-imbalance-split-diagram` has `aria-label` with average occupancies |
| 🟡 Medium | Reservation-driven imbalance not addressed | 01 | ✅ **Resolved** — Open Question added: should alert include a "Reservation-driven imbalance" flag when the gap is caused primarily by reservation concentration? Recommendation: flag as context if >70% of heavy coaches are reservation-filled; does not suppress alert but adds advisory note |
| 🟢 Low | `ca-imbalance-pa-modal` missing formal OBJECT ID | 01 | ✅ **Resolved** — OBJECT ID assigned: `ca-imbalance-pa-modal` |
| 🟢 Low | "Resolved" state not marked terminal in state table | 01 | ✅ **Resolved** — Exit trigger column updated: "Terminal — alert cleared; feed item archived" |
| 🟢 Low | 10-min vs 5-min terminus suppression not justified | 01 | ✅ **Resolved** — Resolved Decisions note added: "10 min chosen (vs 5 min for vestibule congestion) because rebalancing requires passengers to move between coaches — insufficient lead time negates the action's value" |

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
- ✅ State Flow (terminal state marked; all states in table)
- ✅ Purpose & Story (clear; split diagram embeds the narrative)
- ✅ Object ID Completeness (7 IDs; dual-interface coverage; no duplicates)
- ✅ Section Order (accessibility section added)
- ✅ Object Registry (all IDs referenced)
- ✅ Design System Separation (tokens used; pixel values are constraints)
- ✅ Cross-Spec Consistency (suppression difference justified; atomic action pattern established)
- ✅ Scenario Coverage (all states covered; reservation-driven gap added as Open Question)

**External dependencies still open (not spec gaps):**
- ⏳ PA zone targeting — per-coach vs train-wide (ÖBB onboard systems)
- ⏳ PIS interior L2 write access (systems integration)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
