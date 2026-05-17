---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 02c — Conrad Heads Off a Luggage Bottleneck (1 document)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 02c Specs

**Scope:** `D-UX-Design/scenario-02c-specs/` — 1 document
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Dual-trigger alert spec with PA + PIS exterior combined action

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-luggage-rack-saturation.md` | Luggage Alert Active · PA Sent · Actioned · Resolved |

---

## Check 1 — Page Metadata

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ Scenario 02c | ✅ Conductor App (handheld) | ✅ Alert Active — Luggage Rack Saturation | ✅ `scenario-01-specs/01-conductor-app-home-screen.md` | ✅ 2026-05-14 | ✅ Draft |

**Status: ✅ PASS**

---

## Check 2 — State Flow Overview

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Dual trigger: rack ≥85% AND boarding ≥15 pax | ✅ Post-boarding doors close (auto-dismiss) | ✅ Normal (en-route) named |

**Note:** The state flow correctly includes "Actioned (PA ± screens sent)" and "Resolved" as distinct states. The "Actioned" state leads to "Resolved" via boarding stop passing — this is the only scenario so far where the resolution trigger is temporal (stop passing) rather than sensor-based.

**Issue found:**
⚠️ State table uses "Alert fires only when BOTH conditions are true simultaneously" in the trigger logic section (below the table). The state table entry itself says "Both conditions met" as the entry trigger for the alert state — but does not list the conditions inline. Minor: the conditions are stated later in the same section, so they are findable. Not a structural gap.

**Issue found:**
⚠️ "Resolved" state exit trigger is blank (terminal state — same gap as Scenario 02b). Should be marked "Terminal — alert cleared; action logged."

**Status: ⚠️ NEEDS MINOR FIX** — Mark Resolved as terminal in state table.

---

## Check 3 — Purpose & Story

| Doc | Purpose statement | Narrative | Trigger map connection |
|-----|------------------|-----------|-----------------------|
| 01 | ✅ "minimum 6 minutes before arrival... preventing aisle blockage during boarding" | ✅ Passengers with large luggage + coaches 2/4 alternative route | ✅ Conrad intercepts before problem occurs — predictive pattern |

**Status: ✅ PASS** — This is the only predictive (pre-event) alert in the spec set. The Purpose correctly identifies lead time as the key value. Design rationale reinforces this.

---

## Check 4 — Object ID Completeness

| OBJECT ID | Type | Notes |
|-----------|------|-------|
| `ca-luggage-detail` | New | Full-screen detail panel |
| `ca-luggage-rack-inventory` | New | Rack occupancy + item breakdown |
| `ca-luggage-alternatives` | New | Adjacent coach availability table |
| `ca-luggage-actions` | New | Action strip |
| `ca-luggage-pa-modal` | New | PA pre-fill modal |
| `pis-exterior-luggage-available` | New | PIS exterior luggage variant state |

**Elements without OBJECT IDs:**
- Alert banner (luggage variant) — uses base `ca-alert-banner` ✅ correct
- Classification note ("⚠️ Oversized/bicycle classification is estimated") — inline text within `ca-luggage-rack-inventory` ✅ acceptable

**Naming convention check:**
- All `ca-` prefixed for Conductor App elements ✅
- `pis-exterior-luggage-available` uses `pis-exterior-` prefix — consistent with PIS exterior naming ✅
- No duplicates with prior scenario IDs ✅

**Status: ✅ PASS**

---

## Check 5 — Section Order & Structure

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ (alert banner + 4 layout sections + PIS state) | ✅ (4 rules) | ✅ (3 items) | ⚠️ Missing | ✅ | ✅ |

**Issue found:**
⚠️ No Accessibility section — same gap as Scenario 02b. This spec introduces the "I'll be at the door" action (logging action; minimum 44px touch target required) and the `pis-exterior-luggage-available` screen state (legibility at platform distance requirements).

**Status: ⚠️ NEEDS FIX** — Add Accessibility section.

---

## Check 6 — Object Registry

| OBJECT ID | Defined? | Referenced in Rules? |
|-----------|----------|----------------------|
| `ca-luggage-detail` | ✅ | ✅ Alert banner tap action |
| `ca-luggage-rack-inventory` | ✅ | ✅ Layout section |
| `ca-luggage-alternatives` | ✅ | ✅ Layout section; PA modal pre-fill source |
| `ca-luggage-actions` | ✅ | ✅ Layout section |
| `ca-luggage-pa-modal` | ✅ | ✅ PA action; Interaction Rule 4 |
| `pis-exterior-luggage-available` | ✅ | ✅ PA + screens action, Resolved Decisions |

**Issue found:**
⚠️ `ca-luggage-alternatives` is referenced as "two coaches with most rack space" in the PA pre-fill section, but the object itself shows three rows (Coach 2, Coach 4, Coach 3). The PA says "coaches 2 and 4 have the most available overhead space" — the spec should explicitly state the selection logic: "from `ca-luggage-alternatives`, select the two coaches with lowest rack occupancy for PA pre-fill." This is implied but not stated formally.

**Status: ⚠️ NEEDS MINOR FIX** — Document selection logic for PA pre-fill from `ca-luggage-alternatives`.

---

## Check 7 — Design System Separation

**Doc 01 scan:**
- `--color-warning-amber` ✅ token
- `--color-occupancy-red`, `--color-occupancy-green` ✅ tokens
- `--pis-background-default`, `--pis-text-primary` ✅ tokens
- 85% rack threshold — functional threshold ✅
- 15 pax boarding threshold — functional threshold ✅
- 6-minute lead time — functional constraint ✅
- 200 char max PA text — functional constraint ✅

**No pixel values without justification.** The PIS exterior screen spec for this state inherits the 96px / 72pt minimum from Scenario 01 PIS spec — not restated here but implied by cross-reference.

**Status: ✅ PASS**

---

## Check 8 — SEO Compliance

**Not applicable.** Native app + embedded display. Skipped.

---

## Check 9 — Cross-Spec Consistency

| Concept | Reference | Scenario 02c | Consistency |
|---------|-----------|-------------|-------------|
| Dual trigger logic | New — first instance | rack ≥85% AND boarding ≥15 | ✅ Documented clearly; rationale given |
| `ca-alert-banner` amber + pulsing | Scenarios 02, 02b | ✅ Same pattern | ✅ |
| PA pre-fill with dynamic data | Scenarios 02, 02b | ✅ Coach numbers from `ca-luggage-alternatives` | ✅ |
| Atomic combined action | Scenario 02b | PA + PIS exterior in one action | ✅ Same atomic pattern |
| Partial success toast | Scenario 02b | "PA sent · Screens unavailable" | ✅ Identical handling |
| Auto-dismiss on boarding completion | New — first instance | Doors close after boarding stop | ✅ Appropriate — rack state resolved at stop completion |
| PIS exterior left-edge bar | Scenario 01 | `pis-exterior-luggage-available` — no bar specified | ⚠️ See below |
| Accuracy caveat mandatory | New | "⚠️ Oversized/bicycle classification is estimated" | ✅ Well-justified in rationale |

**Issue found:**
⚠️ The `pis-exterior-luggage-available` state definition shows the screen layout (coach number + "Gepäckplatz verfügbar / Luggage space available ✓") but does NOT specify a left-edge colour bar. Scenario 01 PIS exterior states all use a 16px left-edge bar as the colour signal. If this state omits the bar, it is visually inconsistent with other PIS exterior states. The luggage available state should have a green bar (space = positive signal) matching State A (Space Available) in Scenario 01.

**Status: ⚠️ NEEDS MINOR FIX** — Add left-edge `--color-occupancy-green` 16px bar to `pis-exterior-luggage-available` spec.

---

## Check 10 — Final Validation & Scenario Coverage

| Storyboard need | Spec doc | Covered? |
|----------------|----------|---------|
| Alert when rack near capacity + large boarding | 01 | ✅ Dual trigger logic |
| 6-minute minimum lead time | 01 | ✅ Rule 1 |
| Rack inventory (current occupancy + item types) | 01 | ✅ `ca-luggage-rack-inventory` |
| Item classification accuracy caveat | 01 | ✅ Mandatory caveat in inventory section |
| Adjacent coach alternatives shown | 01 | ✅ `ca-luggage-alternatives` |
| PA pre-fill with specific coaches | 01 | ✅ Dynamic insertion from alternatives |
| PIS exterior screens show luggage available | 01 | ✅ `pis-exterior-luggage-available` |
| "I'll be at the door" personal presence log | 01 | ✅ Action 3 in action strip |
| Alert auto-dismisses after boarding stop | 01 | ✅ Rule 3 |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| <6 min to stop (insufficient lead time) | ✅ Rule 1 — alert fires immediately with "Less than 6 min to stop" note |
| PIS screens unavailable | ✅ Rule 4 — "PA sent · Screens unavailable" toast |
| All adjacent coaches also near capacity | ⚠️ Not explicitly addressed. If coaches 2 and 4 are also ≥85%, `ca-luggage-alternatives` would show no good alternatives. The PA pre-fill would have no coaches to insert. Should the alert show "No adjacent space available" or suppress the PA option? |
| Multiple racks saturated on same train | ⚠️ Spec addresses one coach (Coach 3). If coaches 3 and 5 both have saturated racks and boarding expected, do two alerts fire? Or is the most critical one shown? |

**Status: ⚠️ TWO MINOR GAPS** — All-coaches-full alternative and multi-coach saturation cases undocumented.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | Accessibility section missing | 01 | ✅ **Resolved** — Section added: `ca-luggage-rack-inventory` has `aria-label` with text equivalent of occupancy bar (e.g. "Coach 3 luggage racks — 94% full"); action buttons minimum 44px; PIS exterior state follows Scenario 01 legibility constraints (96px minimum font at platform distance) |
| 🟡 Medium | All-alternatives-full edge case | 01 | ✅ **Resolved** — `ca-luggage-alternatives` spec extended: if all adjacent coaches are also ≥85%, panel shows "No adjacent coaches with rack space available"; PA option changes to "PA — ask passengers to check for space" (generic, no coach named) |
| 🟡 Medium | Multi-coach saturation | 01 | ✅ **Resolved** — Open Question added: confirm whether multiple simultaneous rack alerts fire as separate banners or aggregate into one. Recommendation: single aggregated alert showing all affected coaches; scope decision for Nomad Digital product |
| 🟡 Medium | PIS exterior left-edge colour bar missing | 01 | ✅ **Resolved** — `pis-exterior-luggage-available` spec updated: left-edge `--color-occupancy-green` 16px vertical bar added (consistent with Scenario 01 Space Available state) |
| 🟢 Low | PA pre-fill selection logic not formal | 01 | ✅ **Resolved** — Selection logic stated: "PA pre-fills with the two coaches from `ca-luggage-alternatives` with lowest rack occupancy percentage" |
| 🟢 Low | "Resolved" state not marked terminal | 01 | ✅ **Resolved** — State table updated: "Terminal — alert dismissed; Conrad action logged" |

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
- ✅ State Flow (Resolved marked terminal; triggers clear)
- ✅ Purpose & Story (predictive pattern well-motivated)
- ✅ Object ID Completeness (6 IDs; PIS exterior included; no duplicates)
- ✅ Section Order (accessibility added)
- ✅ Object Registry (PA pre-fill selection logic formalised)
- ✅ Design System Separation (tokens throughout; no styling values)
- ✅ Cross-Spec Consistency (PIS exterior bar added for visual consistency with Scenario 01)
- ✅ Scenario Coverage (all storyboard states; edge cases addressed or Open-Questioned)

**External dependencies still open (not spec gaps):**
- ⏳ Hailo-8 rack-level detection accuracy for R5001C overhead rack configuration (ML team)
- ⏳ Expected boarding count source — HAFAS reservations only or + walk-up estimate (data team)
- ⏳ Multi-coach simultaneous rack alert behaviour — aggregate vs separate (Nomad Digital product)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
