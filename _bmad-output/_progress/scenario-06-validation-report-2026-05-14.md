---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 06 — Passenger with Pushchair Finds Accessible Space (5 documents)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 06 Specs

**Scope:** `D-UX-Design/scenario-06-specs/` — 5 documents
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** Cross-interface accessibility scenario (Conductor App × 2, Passenger Portal × 3); most complex spec set outside Scenario 10

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-accessibility-alert.md` | Alert Active — space available; alert feed item |
| 02 | `02-conductor-app-space-occupied-path.md` | Alert Active — space occupied; alternatives panel |
| 03 | `03-passenger-portal-pre-boarding-states.md` | Portal — Space Available; Space Occupied variants |
| 04 | `04-passenger-portal-journey-state.md` | Journey Mode — persistent accessibility strip |
| 05 | `05-passenger-portal-ramp-confirmed-state.md` | Ramp Confirmed transition state |

---

## Check 1 — Page Metadata

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ 06 | ✅ Conductor App | ✅ Alert Active — accessibility | ⚠️ References UX v2 (not Scenario 01 spec) | ✅ 2026-05-14 | ✅ Draft |
| 02 | ✅ 06 | ✅ Conductor App | ✅ Alert — space occupied | ✅ `01-conductor-app-accessibility-alert.md` | ✅ 2026-05-14 | ✅ Draft |
| 03 | ✅ 06 | ✅ Passenger Portal | ✅ Pre-boarding accessibility panel | ✅ Base portal spec | ✅ 2026-05-14 | ✅ Draft |
| 04 | ✅ 06 | ✅ Passenger Portal | ✅ Journey Mode + accessibility strip | ✅ Base portal Journey Mode | ✅ 2026-05-14 | ✅ Draft |
| 05 | ✅ 06 | ✅ Passenger Portal | ✅ Ramp Confirmed transition | ✅ `pp-accessibility-panel` State A (doc 03) | ✅ 2026-05-14 | ✅ Draft |

**Issue found:**
⚠️ Doc 01 base state references `2026-05-14-oebb-ux-design-v2.md § Interface 1` rather than `scenario-01-specs/01-conductor-app-home-screen.md` — same gap as in Scenario 02d doc 01.

**Status: ⚠️ NEEDS MINOR FIX** — Update doc 01 base state reference.

---

## Check 2 — State Flow Overview

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ Hailo-8 detection ≥ threshold | ✅ TCMS departure signal | ✅ Normal (en-route) predecessor |
| 02 | ✅ ASCII | ✅ Compound: detection + space occupied | ✅ TCMS departure signal | ✅ Normal predecessor |
| 03 | ✅ ASCII | ✅ Self-identification tap + space status query | ✅ TCMS ramp confirmed / departure | ✅ General guidance → pre-boarding → ramp confirmed |
| 04 | ✅ ASCII | ✅ TCMS departure signal | ✅ End of journey (final destination) | ✅ Ramp Confirmed + Pre-boarding paths |
| 05 | ✅ ASCII | ✅ TCMS ramp-ready signal | ✅ TCMS departure signal | ✅ Pre-boarding → Ramp Confirmed → Journey Mode |

**All 5 state flow diagrams present and entry/exit triggers defined. ✅**

**Issue found:**
⚠️ Doc 04 state flow shows two entry paths: "Ramp Confirmed (spec 05) OR Pre-Boarding (if departed before ramp confirmed)." The second path (departure before ramp confirmed) is documented in the edge case section of doc 05 — but the state flow diagram in doc 04 shows it as an entry from "Pre-boarding (if departed before ramp confirmed)" without a clean reference. The edge case is handled, but the diagram is slightly ambiguous about when this path applies.

**Status: ⚠️ NEEDS MINOR FIX** — Doc 04 state flow: label the second entry path as "TCMS departure signal (ramp not yet confirmed)" for clarity.

---

## Check 3 — Purpose & Story

| Doc | Purpose statement | "The Story" narrative | Trigger map connection |
|-----|------------------|----------------------|----------------------|
| 01 | ✅ "Conrad's role is to be present and offer assistance" | ✅ Conrad pockets phone and walks — pastoral | ✅ Pushchair/wheelchair = accessibility driving force |
| 02 | ✅ "pastoral presence to active intervention" | ✅ "His stomach drops slightly — he knows he needs to get there fast" | ✅ Conrad's professional anxiety — well-framed |
| 03 | ✅ "boarding decision... before they commit to a platform position" | ✅ Hanna on platform, 40 metres from coach 2 | ✅ Passenger self-determination before asking staff |
| 04 | ✅ "persistent throughout the journey" | ✅ Hanna glances at phone, sees Linz Hbf accessibility info | ✅ Continuity of care beyond boarding |
| 05 | ✅ "remove the final uncertainty before the passenger physically arrives at the door" | ✅ Hanna walking, sees text shift to "✓ Rampe bereit," picks up pace | ✅ Confirmation as permission to commit |

**Status: ✅ PASS** — The Scenario 06 narratives are the strongest across the entire spec set. The Hanna arc across docs 03, 05, 04 reads as a coherent journey: platform → confirmation → boarding → journey. Doc 02's "his stomach drops slightly" is the most human moment in any of the Conrad stories.

---

## Check 4 — Object ID Completeness

### Doc 01

| OBJECT ID | Type |
|-----------|------|
| `ca-accessibility-alert-detail` | New |
| `ca-accessibility-alert-feed-item` | New |

### Doc 02

| OBJECT ID | Type |
|-----------|------|
| `ca-accessibility-alternatives-panel` | New |
| `ca-accessibility-alert-detail` | Extension (space occupied state — same ID) |

### Doc 03

| OBJECT ID | Type |
|-----------|------|
| `pp-accessibility-panel` | New |

### Doc 04

| OBJECT ID | Type |
|-----------|------|
| `pp-accessibility-journey-strip` | New |

### Doc 05

No new OBJECT IDs — this spec describes changes to `pp-accessibility-panel` in a transition state.

**Total: 6 IDs across 5 documents (5 new + 1 extension). ✅**

**Issue found:**
⚠️ Doc 05 modifies `pp-accessibility-panel` in the Ramp Confirmed state and lists specific element changes (ramp status line, panel border, panel background, entry animation, `role` attribute). These modified elements are not assigned sub-element IDs — they are addressed by CSS property names. For a spec-to-implementation handoff, the ramp status line element should have an ID: `pp-accessibility-ramp-status`. This is referenced in the Timing and Latency section and the Accessibility section.

**Issue found:**
⚠️ The "Rollstuhl / Kinderwagen" entry link in the portal footer (doc 03, Rule 2) is referenced but never assigned an OBJECT ID. This is a navigation element present in the Coach Guidance Panel footer during station stops. Assign `pp-accessibility-entry-link`.

**Naming convention check:**
- `ca-` for Conductor App elements ✅
- `pp-` for Passenger Portal elements ✅
- No cross-namespace collisions ✅
- No duplicates across all 5 docs ✅

**Status: ⚠️ NEEDS MINOR FIX** — Assign `pp-accessibility-ramp-status` and `pp-accessibility-entry-link`.

---

## Check 5 — Section Order & Structure

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ | ✅ (5 rules) | ✅ (4 items) | ✅ | ✅ | ✅ |
| 02 | ✅ | ✅ | ✅ (diff table) | ✅ (4 rules) | ✅ (4 items) | ✅ | ✅ | ✅ |
| 03 | ✅ | ✅ | ✅ (State A + B + updates) | ✅ (6 rules) | ✅ (4 items) | ✅ | ✅ | ✅ |
| 04 | ✅ | ✅ | ✅ | ✅ (5 rules) | ✅ (4 items) | ✅ | ✅ | ✅ |
| 05 | ✅ | ✅ | ✅ (diff table + edge case) | ✅ (3 rules) | ✅ (3 items) | ✅ | ✅ | ✅ |

**Status: ✅ PASS** — All 5 docs follow the standard sequence including Accessibility. Doc 05 correctly includes the Edge Case section between state description and interaction rules — an appropriate addition for a transitional state with a known fallback.

---

## Check 6 — Object Registry

| OBJECT ID | Defined? | Referenced? |
|-----------|----------|-------------|
| `ca-accessibility-alert-detail` | ✅ (doc 01) | ✅ State flow, Rule 4 (doc 01); all differences in doc 02 |
| `ca-accessibility-alert-feed-item` | ✅ (doc 01) | ✅ Alert feed section |
| `ca-accessibility-alternatives-panel` | ✅ (doc 02) | ✅ Rule 3 (collapsed by default); doc 02 state description |
| `pp-accessibility-panel` | ✅ (doc 03) | ✅ State flow; entry trigger; doc 05 base state |
| `pp-accessibility-journey-strip` | ✅ (doc 04) | ✅ State description; all rules; Accessibility |
| `ca-accessibility-alert-detail` (occupied state) | ✅ (doc 02) | ✅ Explicitly "same ID, occupied state" — noted in spec |

**Note on same-ID extension (doc 02):** Using the same Object ID for two states of the same panel is a valid pattern — it reflects the UI element maintaining its identity while changing state. The spec correctly flags this: "OBJECT ID: `ca-accessibility-alert-detail` (same ID, occupied state)." Implementation teams will use state modifiers (CSS classes, conditional rendering) rather than separate components.

**Status: ✅ PASS** (pending ramp-status and entry-link IDs from Check 4)

---

## Check 7 — Design System Separation

**Doc 01 scan:**
- `--color-accessibility` ✅ token (flagged as potentially new — Open Question 3)
- `--color-warning-amber` ✅ token
- 20sp, 44px ⚠️ — legibility/touch target constraints ✅ acceptable

**Doc 02 scan:**
- `--color-accessibility`, `--color-warning-amber` ✅ tokens
- 18sp ⚠️ — legibility constraint ✅ acceptable

**Doc 03 scan:**
- `rgba(74,158,255,0.08)` ⚠️ — raw CSS value, not a token
- `rgba(74,158,255,0.25)` ⚠️ — raw CSS value
- `rgba(239,68,68,0.06)` ⚠️ — raw CSS value
- `rgba(239,68,68,0.30)` ⚠️ — raw CSS value
- `--text-primary`, `--text-secondary`, `--text-tertiary` ✅ tokens
- `--color-warning-red` ✅ token
- `--color-accessibility` ✅ token (referenced in Coach diagram section)
- 18sp, 22sp, 14sp, 12sp ⚠️ — font size constraints

**Doc 04 scan:**
- `rgba(74,158,255,0.06)`, `rgba(74,158,255,0.4)` ⚠️ — raw CSS values
- `--text-primary`, `--text-secondary`, `--text-tertiary` ✅ tokens
- 16sp, 14sp, 12sp ⚠️ — font size constraints
- `3px solid` border — implementation detail

**Doc 05 scan:**
- `rgba(74,158,255,0.25)`, `rgba(34,197,94,0.35)`, `rgba(34,197,94,0.08)`, `rgba(34,197,94,1.0)` ⚠️ — raw CSS values
- `--text-tertiary`, `--sev-normal` — `--sev-normal` ✅ token; `rgba` values ⚠️
- 400ms animation — implementation detail ⚠️

**Issue found:**
⚠️ Docs 03, 04, 05 use raw `rgba()` CSS values for panel backgrounds and borders. This is inherited from the portal base spec pattern (which uses direct CSS values as noted in the Scenario 10 validation report). The portal design system does not use a token layer for these values — this is a pre-existing architectural decision in the portal base spec, not introduced by Scenario 06 specs.

**Assessment:** The raw CSS values in portal specs are consistent with the base portal spec's established pattern. The font size constraints (18–22sp) are legibility requirements for a platform-distance display use case. Animation timing (400ms) is an interaction constraint. These are appropriate for specs, not implementation styling.

`--sev-normal` is a token but appears only in doc 05 — confirm this token is in the design system (it may be a custom token not yet established).

**Status: ⚠️ NEEDS MINOR CLARIFICATION** — `--sev-normal` token needs design system confirmation; raw `rgba()` values in portal specs are consistent with base portal pattern (pre-existing).

---

## Check 8 — SEO Compliance

**Not applicable.** Native app (docs 01, 02) and captive portal (docs 03, 04, 05). Skipped.

---

## Check 9 — Cross-Spec Consistency

| Concept | Reference | Scenario 06 | Consistency |
|---------|-----------|-------------|-------------|
| `--color-accessibility` (blue-teal) | New token | Used in docs 01, 02, 03, 05 | ✅ Consistent across all 06 docs; flagged as potentially new token in Open Questions |
| Auto-resolve on departure | Scenarios 02, 02b, 02c, 02d (auto-resolve on sensor clear) | Docs 01, 02: auto-resolve on TCMS departure signal | ✅ Same principle; trigger is departure not sensor clear (appropriate for this scenario) |
| "Unser Personal ist informiert" (not "is coming") | New in 06 | Docs 03, 02 consistent | ✅ Rationale explicitly stated; consistent across portal and Conrad's alert |
| TCMS ramp-ready signal | New — first use | Docs 05, 01 reference | ✅ Consistent — automatic deployment in all references |
| 15-second portal polling | Scenario 05 (30s) | Doc 03 Rule 3: 15s | ⚠️ See below |
| No manual dismiss | Scenario 02d | Doc 01 Rule 3 — no dismiss | ✅ Consistent for same reason |
| Self-identification trigger | New — portal only | Doc 03 — not automatic | ✅ Privacy rationale well-stated |

**Issue found:**
⚠️ Portal polling rate inconsistency. Scenario 05 uses 30-second polling (matching PIS exterior screens). Scenario 06 doc 03 uses 15-second polling for the accessibility panel. These are the same portal on the same train. The polling rate discrepancy needs justification: does the accessibility panel use a faster poll because space status is more time-critical? Or should both be 30 seconds? The Rationale section of doc 03 addresses the 15s choice ("15-second polling is sufficient for a 2–5 minute dwell") but doesn't acknowledge the difference from the load guidance polling rate.

**Conrad ↔ Portal consistency check:**

The key cross-interface scenario is: Hailo-8 detects pushchair → Conrad gets alert → Portal shows accessibility panel (after self-identification). The delay between detection and portal availability depends on the polling cycle. If the passenger opens the portal within 15 seconds of detection, the space status will be accurate. If they open it within 0–15 seconds, they may see the prior state. This is acceptable and acknowledged in Rule 3.

Conrad's alert fires on detection. The portal updates within 15 seconds. If Conrad's alert says "Ramp deploying" but the portal still says "Rampe wird vorbereitet" — that is consistent (preparing is the correct intermediate state).

**Status: ⚠️ NEEDS MINOR FIX** — Doc 03 should note that 15s polling is faster than load guidance (30s) specifically because accessibility space availability is time-critical for a boarding decision.

---

## Check 10 — Final Validation & Scenario Coverage

Cross-referencing Scenario 06 storyboard — pushchair/wheelchair passenger boards accessible coach via automatic ramp; Conrad is present; portal guides passenger to correct door.

| Storyboard need | Doc | Covered? |
|----------------|-----|---------|
| Hailo-8 detects accessibility need | 01 | ✅ Trigger defined |
| Conrad gets alert — calm, informational | 01 | ✅ Blue-teal, steady, pastoral |
| Ramp deploys automatically | 01 | ✅ TCMS automatic; Conrad not involved |
| Space occupied variant — Conrad active | 02 | ✅ Amber + pulsing; alternatives panel |
| Portal shows accessible coach and door | 03 | ✅ `pp-accessibility-panel` State A |
| Portal shows occupied state | 03 | ✅ `pp-accessibility-panel` State B |
| Real-time update (available ↔ occupied) | 03 | ✅ In-place panel update with transition |
| Ramp confirmed state on portal | 05 | ✅ Blue → green transition; `role="alert"` |
| Persistent strip in journey mode | 04 | ✅ `pp-accessibility-journey-strip` |
| Next stop accessibility info | 04 | ✅ ÖBB HAFAS supplementary data |
| Alert auto-resolves on departure | 01 | ✅ TCMS departure signal |

**All storyboard states covered. ✅**

**Edge case check:**

| Edge case | Specced? |
|-----------|---------|
| TCMS ramp signal not received before departure | ✅ Doc 05 edge case section |
| Space occupied → available during dwell | ✅ Doc 02 Rule 2; doc 03 real-time update |
| Multiple accessibility passengers at same stop | ✅ Doc 01 Rule 2 — deduplication at coach level |
| Passenger hides strip mid-journey | ✅ Doc 04 — collapses to single line, re-expandable |
| Accessible toilet location unknown | ✅ Doc 04 Rule 3 — static formation data; "unknown" case handled by omission |
| No accessibility data for next stop | ✅ Doc 04 Rule 4 — field omitted |
| Portal opened after departure (in journey mode) | ✅ Doc 04 — strip shown for self-identified passengers |
| Passenger with SN reduction but no pushchair/wheelchair detected | ⚠️ Hailo-8 triggers on visual detection (pushchair/wheelchair). A passenger who has a PRM reservation but uses a cane or other mobility aid not visible in the vestibule would not trigger detection. This gap is noted in Open Question 1 (confidence threshold) but not explicitly addressed as an edge case in the UX flow. |
| Station stop where ramp is not applicable (no ramp needed) | ⚠️ The spec assumes ramp deployment is always triggered by accessibility detection. Not all stops require a ramp (e.g., level boarding). Should the portal show "Ramp preparing" when level boarding is available? |

**Status: ⚠️ TWO MINOR GAPS** — PRM reservation without visual detection; level boarding case.

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🟡 Medium | Portal 15s vs 30s polling inconsistency undocumented | 03 | ✅ **Resolved** — Rule 3 extended: "Accessibility panel uses 15s polling (vs 30s for load guidance) because space availability is time-critical for a boarding passenger on a platform — the additional refresh cost is justified by the urgency context" |
| 🟡 Medium | Level boarding not addressed | 01, 03 | ✅ **Resolved** — Open Question added to doc 01: confirm whether TCMS ramp-ready signal is relevant at stations with level boarding. If not, docs 01 and 03 ramp status sections should show "Ramp not required" rather than "Ramp preparing …" for level boarding stations |
| 🟡 Medium | PRM reservation without visual detection | 03 | ✅ **Resolved** — Open Question added: accessibility panel trigger is Hailo-8 visual detection; passengers with PRM reservations who are not visually detectable (cane users, hidden disabilities) would self-identify via the "Rollstuhl / Kinderwagen" link but would NOT trigger Conrad's alert. This is acceptable design — Conrad's alert is for passive detection; the portal is for active self-identification. Gap noted for Nomad Digital product awareness. |
| 🟡 Medium | `--sev-normal` token needs confirmation | 05 | ✅ **Resolved** — Open Question added: confirm `--sev-normal` is in the design token set or replace with `--color-success-green` for consistency with Scenario 03 (`ca-capacity-flag-confirmation` toast) |
| 🟢 Low | Doc 01 base state incorrect reference | 01 | ✅ **Resolved** — Updated to `scenario-01-specs/01-conductor-app-home-screen.md` |
| 🟢 Low | Doc 04 state flow second entry path ambiguous | 04 | ✅ **Resolved** — Labelled "TCMS departure signal (ramp not yet confirmed) — bypasses Ramp Confirmed state" |
| 🟢 Low | `pp-accessibility-ramp-status` and `pp-accessibility-entry-link` missing IDs | 03, 05 | ✅ **Resolved** — IDs assigned in respective specs |

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
- ✅ Metadata (5 docs; Conductor App + Portal split correctly; base states complete)
- ✅ State Flow (all 5 diagrams present; Hanna arc flows correctly across docs 03→05→04)
- ✅ Purpose & Story (best narratives in the spec set; Conrad + Hanna both well-characterised)
- ✅ Object ID Completeness (8 IDs post-fix; `ca-`/`pp-` namespace clean; same-ID extension pattern documented)
- ✅ Section Order (all 5 docs complete; Edge Case section in doc 05 is appropriate addition)
- ✅ Object Registry (all IDs cross-referenced; occupied state extension documented)
- ✅ Design System Separation (`rgba` in portal specs consistent with base portal pattern; `--sev-normal` flagged for confirmation; token use correct elsewhere)
- ✅ Cross-Spec Consistency (15s vs 30s polling justified; Conrad↔Portal synchronisation verified)
- ✅ Scenario Coverage (all storyboard states; level boarding + PRM non-visual gaps open-questioned)

**External dependencies still open (not spec gaps):**
- ⏳ Hailo-8 confidence threshold for pushchair/wheelchair detection (ML team)
- ⏳ TCMS ramp deployment latency — time from command to ramp-ready signal (Stadler)
- ⏳ `--color-accessibility` blue-teal token — design system confirmation (Design system team)
- ⏳ `--sev-normal` token — design system confirmation (Design system team)
- ⏳ Accessible coach/door number per consist variation (Stadler / fleet management)
- ⏳ ÖBB CNA portal DOM update support (portal team)
- ⏳ ÖBB HAFAS station accessibility database coverage (ÖBB integration)
- ⏳ Accessible toilet location in Stadler formation data (Stadler / Nomad Digital fleet config)
- ⏳ Portal session timeout after phone lock (Nomad Digital portal team)
- ⏳ TCMS ramp-ready signal integration point (Stadler)
- ⏳ Level boarding ramp signal handling (Stadler / systems integration)

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
