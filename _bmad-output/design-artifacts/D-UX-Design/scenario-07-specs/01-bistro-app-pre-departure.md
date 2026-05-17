# Page Spec — Bistro App: Pre-Departure Stock Preparation View

**Scenario:** 07 — Brigitte Preps Stock Before Departure
**Interface:** Bistro Staff App (tablet or handheld)
**State:** Home Screen — Pre-Departure Mode
**Base state:** This document IS the base state for the Bistro App. Referenced by Scenario 08.
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Before departure, Brigitte checks the Bistro App to calibrate how much stock to pull from storage. She needs one number (total passengers) and one recommendation (light / moderate / heavy service). Everything else is secondary.

The app is designed for a busy person standing in a moving preparation environment. Large text, high contrast, glanceable at arm's length. No navigation required to reach the key information.

---

## Home Screen Layout

### Section 1: App Header — `ba-header`

**OBJECT ID:** `ba-header`

| Element | Content |
|---------|---------|
| Train ID | "[Train number]" |
| Route | "[Origin] → [Destination]" |
| Next stop | "Departing: [Station] · T-[N] min" (pre-departure) |
| Current time | "[HH:MM]" |
| Demand pill | "HIGH / MEDIUM / LOW demand" — coloured pill (red/amber/green) |

The demand pill is the headline signal — Brigitte sees it in the header before reading anything else.

---

### Section 2: Passenger Count — `ba-passenger-count`

**OBJECT ID:** `ba-passenger-count`

| Element | Content |
|---------|---------|
| Count | "[N] passengers" — large format (48sp minimum), `--text-primary` |
| Capacity context | "of [N] capacity · [N]%" — secondary, 20sp |
| Trend arrow | ↑ (still boarding) / → (stable) / ↓ (alighting) with label "Trending [up/stable/down]" |
| Last updated | "Updated [N] sec ago" — muted, 14sp |

The trend arrow is critical pre-departure — if the train is still boarding at T-6 minutes, Brigitte should prep for the eventual peak, not the current count.

---

### Section 3: Stock Recommendation — `ba-stock-recommendation`

**OBJECT ID:** `ba-stock-recommendation`

| Demand level | Label | Sub-text |
|-------------|-------|---------|
| HIGH (≥85% occupancy) | "Heavy service — prepare full stock allocation" | "Expect high demand across all categories" |
| MEDIUM (60–84%) | "Moderate service — standard stock allocation" | "Typical demand — monitor mid-journey" |
| LOW (<60%) | "Light service — reduced stock allocation" | "Lower demand expected — avoid over-preparation" |

The recommendation is a single line — not a table, not a breakdown by product category. Brigitte knows what "full allocation" means from training. The app does not micromanage her stock decisions; it gives her the signal she needs to apply her own expertise.

---

### Section 4: Coach Load Strip — `ba-coach-load-strip`

**OBJECT ID:** `ba-coach-load-strip`

A compact horizontal row of all coaches with directional indicators — shows Brigitte which end of the train has the most passengers and where demand will concentrate during her trolley run.

| Element | Content |
|---------|---------|
| Coach cards | All coaches, colour-coded green/amber/red (same thresholds as Conductor App) |
| Directional arrows | Arrows pointing toward bistro car on the heaviest coaches — "flow toward bistro" |
| Bistro car indicator | Bistro car marked with a coffee cup icon |

This view answers "where is the demand relative to where I am?" — Brigitte can see if the heavy coaches are adjacent to the bistro car or at the far end of the train.

---

### Section 5: Next Stops Boarding Forecast — `ba-boarding-forecast`

**OBJECT ID:** `ba-boarding-forecast`

| Stop | Expected boarders | Demand impact |
|------|------------------|---------------|
| [Next stop] | [N] pax expected | "Moderate increase" / "Large increase" / "Minimal" |
| [Stop +1] | [N] pax expected | — |
| [Stop +2] | [N] pax expected | — |

Maximum 3 stops shown. Expected boarding data from HAFAS reservation + historical boarding patterns. Shown as a simple list — not a chart. Brigitte glances at it to know if she should hold back stock for a later surge.

---

### Section 6: Stock Alert — `ba-stock-alert`

**OBJECT ID:** `ba-stock-alert`

Shown only when triggered. AI recommendation based on occupancy data and journey segment:

Example: "Restock hot drinks at Salzburg Hbf — 42% of journey remaining, high demand"

Shown as a single-line banner in amber. Dismissed by swipe. Not shown if no restock recommendation is active.

---

## Mid-Journey Re-check Behaviour

The home screen updates continuously throughout the journey — Brigitte can re-check at any point without navigating. The key changes mid-journey:

| Element | Pre-departure | Mid-journey |
|---------|--------------|-------------|
| Header | "Departing: [Station] · T-[N] min" | "Next: [Station] · [N] min" |
| Demand pill | Based on current boarding | Based on current coach occupancy |
| Passenger count | Building (trend ↑) | Stable or declining |
| Stock recommendation | Pre-departure allocation | Mid-journey restock guidance |

No mode switch is needed — the screen adapts based on train state (TCMS departure signal received or not).

---

## Interaction Rules

1. The home screen is the only screen Brigitte needs for this scenario — no navigation required.
2. All text minimum 20sp. Recommendation text minimum 24sp. Count minimum 48sp. Bistro staff read at arm's length in a busy preparation environment.
3. High contrast mode is always on — the bistro car environment has variable lighting. `--color-background` is always dark; `--text-primary` is always white or near-white.
4. The demand pill in the header is the single fastest read — Brigitte should be able to action it from the notification bar without opening the app if the OS shows it.
5. No alert system for Brigitte — she does not receive occupancy alerts from the Passenger AI. The Bistro App is a pull-information surface, not a push-alert surface. Brigitte checks when she needs to; the system does not interrupt her.

---

## Design Rationale

**Why a recommendation label (Light/Moderate/Heavy) rather than just a percentage?**
Percentages require Brigitte to translate: "74% means… moderate? Heavy?" The recommendation label removes the translation step. "Heavy service — prepare full stock allocation" is directly actionable. Brigitte has been doing this for years — she knows what full allocation looks like. She doesn't need the number to decide; she needs the category.

**Why show the trend arrow rather than the current count alone?**
Pre-departure, the train is still boarding. The current count at T-10 minutes may be 120; at departure it will be 187. If Brigitte preps for 120, she's under-stocked. The trend arrow tells her: "this number is still going up — prep for the peak."

**Why no navigation required to reach the core information?**
Brigitte has 15 minutes before departure, is prepping stock, and may be interrupted multiple times. Every tap between "app opens" and "I know what I need to know" is a moment where she loses context and has to restart. The information is on the home screen by default — no taps required.

---

## Accessibility (App UI)

- Demand pill colour (red/amber/green) supplemented by text label — not colour alone
- All text minimum 20sp — exceeds standard minimum, appropriate for bistro environment
- `ba-stock-recommendation` uses `role="status"` — screen reader announces changes without requiring focus

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Primary information | Total passenger count (large) + recommendation label + trend arrow |
| Recommendation labels | Heavy / Moderate / Light — not raw percentages |
| Thresholds | HIGH ≥85% / MEDIUM 60–84% / LOW <60% — configurable per operator |
| Alert model | No push alerts — pull-information surface only |
| Mid-journey | Same home screen, state-adapted content — no mode switch |
| Text sizing | 48sp count / 24sp recommendation / 20sp minimum — bistro environment |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Is the Bistro App on a tablet or handheld? The spec assumes tablet (larger screen) but the UX design v2 says "tablet or handheld." The minimum font sizes and layout proportions should be validated on both form factors. | Nomad Digital product / ÖBB bistro operator |
| 2 | Is expected boarding count (for `ba-boarding-forecast`) from HAFAS reservations only, or also from historical walk-up patterns? Walk-up patterns significantly affect actual boarding at major stations. | Nomad Digital backend / data team |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-08-specs/01-bistro-app-trolley-routing.md` | Trolley routing view — accessed from this home screen |
| `2026-05-14-oebb-ux-design-v2.md § Interface 3` | Bistro App UX design v2 overview |
