# Story 2-3: Fleet List Passenger Count Sort

**Epic:** 2 — Control Centre Dashboard — Live Operations  
**Story:** 3  
**Story Key:** 2-3-fleet-list-passenger-count-sort  
**Status:** review  
**Date Created:** 2026-05-17  

---

## User Story

**As a** Control Centre operator,  
**I want** the fleet list to sort trains by total passengers aboard (descending) as the default sort,  
**so that** the busiest trains are always at the top and I can spot capacity pressure at a glance.

---

## Acceptance Criteria

- [x] **AC1** — Default sort is passengers descending (sum of `headCount` across all coaches); busiest train appears first within each severity band.
- [x] **AC2** — Equal passenger counts sub-sort by severity (red → amber → green).
- [x] **AC3** — Severity sort: red→amber→green primary; passenger count descending tiebreaker within same severity.
- [x] **AC4** — Switching back to "Passengers" sort reverts list correctly; toggle reflects active sort.
- [x] **AC5** — Sort preference stored in `localStorage` (`fleet-sort-pref`) and restored on page reload.
- [x] **AC6** — Normal trains (green severity) remain collapsed behind "Show N normal trains" toggle regardless of sort order.
- [x] **AC7** — Fleet list re-sorts automatically when passenger count updates via WebSocket; train card animates to new position (CSS transition).

---

## Tasks / Subtasks

- [x] **T1 — Update sort logic in LiveMonitoring**
  - [x] Change `fleetSort` default to read from `localStorage('fleet-sort-pref')` (fallback `'passengers'`)
  - [x] Write `localStorage` on sort change
  - [x] Update `sortedFleet` useMemo: `passengers` sort = totalPassengers desc, tiebreak by severity; `severity` sort = severity asc, tiebreak by totalPassengers desc
  - [x] Add `totalPassengers` helper: `train.coaches.reduce((s,c) => s + c.headCount, 0)`

- [x] **T2 — Update FleetList UI**
  - [x] Add `data-testid="fleet-sort-toggle"` to the sort toggle container
  - [x] Rename sort buttons: "Passengers" (was "Occupancy") and "Severity"
  - [x] Add "Show N normal trains" / "Hide normal trains" collapse toggle for green-severity trains
  - [x] Normal trains collapsed by default; toggle shows/hides them

- [x] **T3 — CSS transition for card reorder**
  - [x] Add `transition: all 0.3s ease` on `.train-card` in `FleetList.css`

---

## Dev Notes

### Key files
- `src/components/live/LiveMonitoring.jsx` — sort state + localStorage + sortedFleet logic
- `src/components/live/FleetList.jsx` — sort toggle rename + testid + normal trains toggle
- `src/components/live/FleetList.css` — CSS transition

### Data shape
- `train.coaches[i].headCount` — passenger count per coach
- `totalPassengers = train.coaches.reduce((s,c) => s + c.headCount, 0)`

### localStorage key
- `fleet-sort-pref` — values: `'passengers'` | `'severity'`

---

## Dev Agent Record

### Pre-Flight
**Assumptions:**
- Default sort `'passengers'` replaces old `'occupancy'`
- Sort toggle label "Occupancy" → "Passengers"
- Normal trains collapse toggle is new — not currently implemented in FleetList

**Surgical-Change Test:**
- `LiveMonitoring.jsx` — AC1, AC2, AC3, AC4, AC5, AC7
- `FleetList.jsx` — AC6, sort toggle rename + testid
- `FleetList.css` — AC7 animation

### Debug Log

### Completion Notes

Default sort changed to `passengers` (sum of coach `headCount`). Tiebreakers: passengers→severity, severity→passengers. `localStorage` key `fleet-sort-pref` persists preference. Normal trains collapsed behind "Show N normal trains" toggle. CSS transition added to `.train-card`. Sort toggle renamed Occupancy→Passengers. Verified in browser: Passengers sort active by default, Severity sort reorders correctly, localStorage writes on change, normal trains collapsed.

---

## File List

- `control-centre/src/components/live/LiveMonitoring.jsx`
- `control-centre/src/components/live/FleetList.jsx`
- `control-centre/src/components/live/FleetList.css`

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-17 | Story created and dev started |
