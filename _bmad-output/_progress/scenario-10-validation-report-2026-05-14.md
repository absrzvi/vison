---
date: 2026-05-14
auditor: Sally (WDS UX Designer — Validation Mode)
scope: Scenario 10 — Station Dwell specs (6 documents)
stepsCompleted: [1,2,3,4,5,6,7,8,9,10]
---

# Validation Report — Scenario 10 Specs

**Scope:** `D-UX-Design/scenario-10-specs/` — 6 documents
**Date:** 2026-05-14
**Auditor:** Sally / Freya (WDS UX Designer)
**Adapted for:** State-extension specs (not full page specs — sketch embeds and SEO checks not applicable)

---

## Documents Audited

| # | File | States covered |
|---|------|---------------|
| 01 | `01-conductor-app-pre-arrival-dashboard.md` | Pre-Arrival Mode |
| 02 | `02-conductor-app-alighting-mode.md` | Alighting Mode |
| 03 | `03-conductor-app-boarding-mode.md` | Boarding Mode |
| 04 | `04-conductor-app-pre-departure-summary.md` | Pre-Departure Summary |
| 05 | `05-pis-exterior-dwell-states.md` | PIS Hold State + Boarding Guidance |
| 06 | `06-passenger-portal-dwell-states.md` | Ramp Confirmed + Journey Mode |

---

## Check 1 — Page Metadata

Validates: scenario context, interface, state, base state, date, status.

| Doc | Scenario | Interface | State | Base state | Date | Status |
|-----|----------|-----------|-------|-----------|------|--------|
| 01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |
| 02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |
| 03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |
| 04 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |
| 05 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |
| 06 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Draft |

**Status: ✅ PASS** — All documents have complete metadata headers.

---

## Check 2 — State Flow Overview

Validates: entry/exit triggers defined, predecessor/successor states named, state diagram present.

| Doc | State diagram | Entry trigger | Exit trigger | Prev/Next named |
|-----|--------------|--------------|-------------|----------------|
| 01 | ✅ ASCII | ✅ GPS+schedule ≤60s | ✅ Doors open signal | ✅ |
| 02 | ✅ ASCII | ✅ Doors open | ✅ Alighting rate threshold | ✅ |
| 03 | ✅ ASCII | ✅ Alighting rate drop | ✅ T-2min dwell timer | ✅ |
| 04 | ✅ ASCII | ✅ T-2min auto | ✅ Conrad one-tap / GPS fallback | ✅ |
| 05 | ✅ ASCII | ✅ Both states covered | ✅ Both exit triggers | ✅ |
| 06 | ✅ ASCII | ✅ Conrad ramp tap / departure confirm | ✅ Departure / journey end | ✅ |

**Issue found — Doc 02:**
⚠️ The state table header says "Entry trigger / Doors open signal from train (or manual door release confirmation)" — but the Resolved Decisions section confirms automatic only. The "or manual door release confirmation" fallback is now stale. Minor inconsistency.

**Issue found — Doc 01:**
⚠️ Related Specs table references `04-pis-exterior-hold-state.md` — this file does not exist. The PIS spec is `05-pis-exterior-dwell-states.md`. Stale filename reference.

**Issue found — Doc 02:**
⚠️ Related Specs table references `07-passenger-portal-ramp-status.md` — this file does not exist. The portal spec is `06-passenger-portal-dwell-states.md`. Stale filename reference.

**Status: ⚠️ NEEDS MINOR FIXES** — 3 stale references, easy to resolve.

---

## Check 3 — Purpose & Story

Validates: each state has a clear Purpose statement and a narrative "The Story" that connects to Conrad's mental state and trigger map.

| Doc | Purpose statement | "The Story" narrative | Trigger map connection |
|-----|------------------|-----------------------|----------------------|
| 01 | ✅ | ✅ Salzburg Hbf, 45s out | ✅ Implicit — pre-position before problem |
| 02 | ✅ | ✅ Dropping coach bars | ✅ Implicit — knows before walking |
| 03 | ✅ | ✅ Boarding surge, coach 4 | ✅ Explicit — remote monitoring decision |
| 04 | ✅ | ✅ T-2min, coach 6 obstruction | ✅ Explicit — delay attribution |
| 05 | ✅ | ✅ Two stories (hold + boarding) | ✅ Passenger perspective correct |
| 06 | ✅ | ✅ Hanna on platform | ✅ Accessibility driving force |

**Status: ✅ PASS**

---

## Check 4 — Object ID Completeness

Validates: every UI element introduced has a unique OBJECT ID, IDs follow consistent naming convention (`ca-` for Conductor App, `pp-` for Passenger Portal, `pis-` implied for PIS).

### Conductor App Object IDs (across docs 01–04)

| OBJECT ID | Doc | Type |
|-----------|-----|------|
| `ca-dwell-timer` | 01 | New |
| `ca-coach-diagram-alighting-band` | 01 | New |
| `ca-dwell-detail-panel` | 01 | New |
| `ca-coach-descent-rate` | 02 | New |
| `ca-accessibility-alight-alert` | 02 | New |
| `ca-alighting-complete-chip` | 02 | New |
| `ca-boarding-mode-transition-toast` | 02 | New |
| `ca-coach-boarding-rate` | 03 | New |
| `ca-coach-projected-load` | 03 | New |
| `ca-forecast-alert` | 03 | New |
| `ca-forecast-alert-strip` | 03 | New |
| `ca-feed-item-forecast` | 03 | New |
| `ca-predeparture-table` | 04 | New |
| `ca-departure-ready-btn` | 04 | New |
| `ca-departure-confirmation-modal` | 04 | New |
| `ca-departure-event-log` | 04 | New |
| `ca-departure-toast` | 04 | New |
| `ca-door-obstruction-late` | 04 | New |

### PIS Object IDs (doc 05)

⚠️ **Issue:** No formal OBJECT IDs defined for PIS elements. PIS specs describe the screen layout and content directly without `pis-` prefixed OBJECT IDs. This is intentional given PIS screens are not interactive and have no components to test by ID — but it creates a gap if the PIS spec ever needs traceability to implementation.

### Passenger Portal Object IDs (doc 06)

| OBJECT ID | Doc | Type |
|-----------|-----|------|
| `pp-journey-coach-suggestion` | 06 | New |

⚠️ **Issue:** The ramp confirmed state (State 8) modifies existing portal panel elements but does not assign OBJECT IDs to them. The existing portal spec (`passenger-portal-ux-design.md`) uses a different spec format without OBJECT IDs (it uses direct HTML/CSS references). State 8 is documented as differences — but without IDs on the base elements being modified, traceability is incomplete.

**Naming convention check:**
- `ca-` prefix used consistently across all Conductor App elements ✅
- `pp-` prefix used for the one new Portal element ✅
- No cross-namespace ID collisions found ✅
- No duplicate IDs found across the 6 documents ✅

**Status: ⚠️ NEEDS MINOR FIXES**
- PIS: no OBJECT IDs — acceptable given non-interactive nature, but should be documented as intentional
- Portal State 8: base elements modified without IDs — either add IDs or note explicitly that IDs are defined in the base portal spec

---

## Check 5 — Section Order & Structure

Validates: standard WDS section sequence maintained (Purpose → State Flow → State description → Interaction Rules → Design Rationale → Accessibility → Resolved Decisions / Open Questions → Related Specs).

| Doc | Purpose | State Flow | State desc | Interaction Rules | Rationale | Accessibility | Decisions | Related |
|-----|---------|-----------|-----------|------------------|-----------|--------------|-----------|---------|
| 01 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 02 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 03 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 04 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 05 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ open Qs only | ✅ |
| 06 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ open Qs only | ✅ |

**Note on docs 05 and 06:** These have Open Questions, not Resolved Decisions — correct, as those questions are pending external confirmation (tech team, ÖBB ops). Structure is appropriate.

**Status: ✅ PASS**

---

## Check 6 — Object Registry

Validates: all introduced OBJECT IDs are consistently referenced in change tables and element specs, no orphan IDs.

Cross-referencing IDs mentioned in "Changes from X" tables against element spec definitions:

| OBJECT ID | Defined as element? | Referenced in change table? |
|-----------|--------------------|-----------------------------|
| `ca-dwell-timer` | ✅ | ✅ (docs 01, 02, 03, 04) |
| `ca-coach-diagram-alighting-band` | ✅ | ✅ (docs 01, 02) |
| `ca-dwell-detail-panel` | ✅ | ✅ (doc 01) |
| `ca-coach-descent-rate` | ✅ | ✅ (doc 02) |
| `ca-accessibility-alight-alert` | ✅ | ✅ (doc 02) |
| `ca-alighting-complete-chip` | ✅ | ✅ (docs 02, 03) |
| `ca-boarding-mode-transition-toast` | ✅ | ✅ (doc 02) |
| `ca-coach-boarding-rate` | ✅ | ✅ (docs 03, 04 clears) |
| `ca-coach-projected-load` | ✅ | ✅ (docs 03, 04 clears) |
| `ca-forecast-alert` | ✅ | ✅ (docs 03, 04 clears) |
| `ca-forecast-alert-strip` | ✅ | ✅ (doc 03) |
| `ca-feed-item-forecast` | ✅ | ✅ (doc 03) |
| `ca-predeparture-table` | ✅ | ✅ (doc 04) |
| `ca-departure-ready-btn` | ✅ | ✅ (doc 04) |
| `ca-departure-confirmation-modal` | ✅ | ✅ (doc 04) |
| `ca-departure-event-log` | ✅ | ✅ (doc 04) |
| `ca-departure-toast` | ✅ | ✅ (doc 04) |
| `ca-door-obstruction-late` | ✅ | ✅ (doc 04) |
| `pp-journey-coach-suggestion` | ✅ | ✅ (doc 06) |

**Issue found:**
⚠️ `ca-door-obstruction-late` is introduced in doc 04 as a named element, but it is described as "a distinct state within Pre-Departure Summary — it does not replace the summary, it overlays an urgent alert." It is treated as both a state and an OBJECT ID — the dual role is slightly ambiguous. Consider renaming to `ca-door-obstruction-predeparture-alert` to clarify it is an alert element, not a state.

**Status: ✅ PASS (with one naming suggestion)**

---

## Check 7 — Design System Separation

Validates: no raw hex codes, font sizes, CSS values, or implementation details in specs. Colour references use design tokens.

Scanning all 6 documents:

**Doc 01:**
- `--color-dwell` ✅ token
- `--color-amber` ✅ token
- `--color-warning-red` ✅ token
- `--color-alighting` ✅ token
- 44px height on `ca-dwell-timer` ⚠️ — pixel value in spec

**Doc 02:**
- All colours use tokens ✅
- 56px touch target on ramp button ⚠️ — pixel value in spec (same issue)
- 15s inference cycle — this is a data/system spec, not styling ✅ acceptable

**Doc 03:**
- All colours use tokens ✅
- 4px height for projected load bar ⚠️ — pixel value in spec

**Doc 04:**
- 64px departure button height ⚠️ — pixel value in spec
- All colours use tokens ✅

**Doc 05:**
- 16px font minimum, 72pt equivalent, 48×48px wheelchair icon ⚠️ — pixel values in spec
- Colour vocabulary (green/amber/orange/red) described semantically, not as hex ✅
- "16px horizontal band at top of screen" ⚠️ — pixel value

**Doc 06:**
- Multiple pixel/colour values inherited from existing portal spec (Inter font, rgba values, px sizes) ⚠️ — these exist because doc 06 extends the portal spec which uses direct CSS values rather than tokens

**Assessment:**
The pixel values in docs 01–04 are all **touch target and critical dimension specs**, not styling. These are intentional accessibility and interaction constraints (44px minimum touch target, 56px for urgent actions, 64px for primary departure action). They belong in specs as interaction requirements, not design system tokens.

Doc 05 pixel values are legibility and physical display constraints (minimum character height for platform-distance readability, minimum icon size for accessibility). These are similarly appropriate in specs.

Doc 06's CSS/rgba inheritance from the base portal spec is a pre-existing pattern in that document — not introduced by these specs.

**Status: ✅ PASS** — Pixel values present are all interaction/accessibility constraints, not styling values. Colour references use tokens throughout Conductor App specs. Portal spec follows its own established pattern.

---

## Check 8 — SEO Compliance

**Not applicable.** These are native mobile app and PIS screen specs — no SEO requirements. Portal specs inherit SEO from ÖBB's CNA portal shell which Nomad Digital does not control. Skipped.

---

## Check 9 — Cross-Spec Consistency

Validates: shared concepts defined consistently across all 6 documents. Thresholds, trigger values, and colour tokens used identically.

| Concept | Doc 01 | Doc 02 | Doc 03 | Doc 04 | Doc 05 | Doc 06 |
|---------|--------|--------|--------|--------|--------|--------|
| Dwell colour token | `--color-dwell` | `--color-dwell` | `--color-dwell` | `--color-dwell` | N/A | N/A |
| Hailo-8 inference cycle | 15s | 15s | 15s | N/A | 30s (PIS refresh) | 30s (portal refresh) |
| Alighting threshold | defined | 2 pax/30s | referenced | N/A | "same signal" | N/A |
| PIS redirect threshold | N/A | N/A | 85% projected | N/A | "85% projected" | N/A |
| Forecast alert threshold | N/A | N/A | 90% projected | 90% (actual = real) | N/A | N/A |
| Occupancy thresholds (green/amber/red) | green/amber/red | green/amber/red | green/amber/red | green/amber/red | <75/75–89/≥90 | same as PIS |
| Touch target minimum | 44px | 44px/56px | 44px | 44px/64px | N/A | 44px |
| Ramp sync latency target | N/A | <3s | N/A | N/A | N/A | <3s |

**Issue found:**
⚠️ Occupancy thresholds are inconsistently stated. Docs 01–04 use qualitative labels (green/amber/red) without explicit percentages. Doc 05 states `<75% / 75–89% / ≥90%`. Doc 06 inherits from the existing portal spec which uses `0–60% / 61–85% / 86–100% / >100%` (four bands, different breakpoints). 

This is a **significant inconsistency.** The Conductor App uses a 3-band system with one set of thresholds; the Passenger Portal uses a 4-band system with different breakpoints. If these share the same data source (Hailo-8), the visual representation diverges at the threshold boundaries — a passenger might see "Mäßig besetzt" (61–85%) on the portal while Conrad sees amber (75–89%) for the same coach. They do not agree.

**Issue found:**
⚠️ Doc 01 `ca-dwell-detail-panel` contents list references "Platform number (if available from HAFAS/ÖBB data)" — but the Resolved Decisions section says platform number IS available from PIS feed and should be "included without caveat." The body text was not updated when the open question was resolved. Stale conditional phrasing.

**Status: ⚠️ NEEDS FIX — one significant threshold inconsistency, one stale conditional**

---

## Check 10 — Final Validation & Scenario Coverage

Validates: all UI states introduced in Scenario 10 storyboard are specced; no storyboard states missing from specs.

Cross-referencing against Scenario 10 storyboard (`C-UX-Scenarios/10-station-dwell-embarkation-disembarkation.md`) "New UI States Introduced" table:

| Storyboard state | Spec doc | Covered? |
|-----------------|----------|---------|
| Pre-arrival dashboard | 01 | ✅ |
| Alighting-in-progress | 02 | ✅ |
| PIS hold state | 05 | ✅ |
| Pre-boarding forecast alert | 03 | ✅ |
| Pre-departure summary | 04 | ✅ |
| Portal ramp status | 06 | ✅ |
| Portal accessible space occupied | 06 | ✅ (State 8 "Not needed" path) |
| Journey mode (portal) | 06 | ✅ |

**All 8 storyboard states are covered. ✅**

**Additional coverage check — edge cases from storyboard:**

| Edge case | Specced? |
|-----------|---------|
| Stop skipped operationally | ✅ Doc 01 — "Stop cancelled" state |
| Multiple stops in quick succession | ✅ Doc 01 — state resets cleanly |
| Conrad does not respond to forecast alert (60s timeout) | ✅ Doc 03 — auto-redirect fires |
| Conrad taps "Monitor remotely" | ✅ Doc 03 — logged, PIS continues |
| Door obstruction at T-30s | ✅ Doc 04 — `ca-door-obstruction-late` |
| Conrad does not tap departure confirmation | ✅ Doc 04 — `departure_unconfirmed` logged |
| Ramp "Not needed" (false positive) | ✅ Doc 06 — portal stays in State 4, no error |
| PIS no data / Hailo offline | ⚠️ Doc 05 — not addressed. What does the PIS screen show if the Nomad system loses connection during the dwell? |

**Status: ⚠️ ONE GAP — PIS offline/no-data state during dwell not specced**

---

## Summary

### Issues — Resolution Log

| Priority | Issue | Doc | Resolution |
|----------|-------|-----|------------|
| 🔴 High | Occupancy threshold inconsistency | 01–04 vs 06 | ✅ **Resolved** — 4-band portal confirmed intentional. Threshold split rationale documented in `01` and `05`. Staff = 3 bands (triage speed), passengers = 4 bands (routing precision). |
| 🟡 Medium | PIS offline/no-data state not specced | 05 | ✅ **Resolved** — State 4 (No Data / Offline) added: silent fallback to route/destination display, recovers automatically on data resume. |
| 🟡 Medium | Stale filename references | 01, 02 | ✅ **Resolved** — Updated to `05-pis-exterior-dwell-states.md` and `06-passenger-portal-dwell-states.md`. |
| 🟡 Medium | Stale conditional in `ca-dwell-detail-panel` | 01 | ✅ **Resolved** — "if available from HAFAS/ÖBB data" removed; platform number confirmed always available from PIS feed. |
| 🟡 Medium | Doc 02 manual fallback in state table | 02 | ✅ **Resolved** — Entry trigger updated to "Doors open signal from Stadler system via SNMP (automatic)." |
| 🟢 Low | `ca-door-obstruction-late` dual role ambiguity | 04 | ✅ **Resolved** — Naming note added clarifying dual usage; rename to `ca-door-obstruction-predeparture-alert` offered as optional at implementation. |
| 🟢 Low | PIS elements have no OBJECT IDs | 05 | ✅ **Resolved** — OBJECT ID scope note added: non-interactive display surfaces, IDs not applicable, referenced by position and content. |
| 🟢 Low | Portal State 8 base elements without IDs | 06 | ✅ **Resolved** — OBJECT ID scope note added: portal follows CSS selector pattern from base spec; compliance deferred to base spec update. |

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
All 8 issues resolved. 3 external confirmations remain open (PIS latency, arrow convention, L2 write access) — these are integration dependencies, not spec gaps. Specs are complete and decision-consistent.

---

## Quality Audit

**Status:** ✅ READY FOR HANDOFF
**Audit Date:** 2026-05-14
**Audited By:** Sally (WDS UX Designer — Validation Mode)

**Compliance:**
- ✅ Metadata (scenario, interface, state, base state, date, status)
- ✅ State Flow (entry/exit triggers, predecessor/successor, state diagrams)
- ✅ Purpose & Story (narrative + trigger map connection per state)
- ✅ Object ID Completeness (19 new IDs, no duplicates, no orphans)
- ✅ Section Order (consistent across all 6 docs)
- ✅ Object Registry (all IDs cross-referenced)
- ✅ Design System Separation (tokens used, pixel values are interaction constraints only)
- ✅ Cross-Spec Consistency (thresholds, triggers, colour tokens aligned; intentional differences documented)
- ✅ Scenario Coverage (all 8 storyboard states covered, all edge cases specced)

**External dependencies still open (not spec gaps):**
- ⏳ PIS write latency <3s — confirm with portal infrastructure team
- ⏳ Arrow direction tiebreaker — confirm with ÖBB operations
- ⏳ L2 network write access — existing open dependency from Scenarios 01 and 05

---

*Generated by Sally (WDS UX Designer — Validation Mode) · 2026-05-14*
