### 02-cc-train-detail

**Previous Step:** ← [cc-analytics-panel](../scenario-04-specs/01-control-centre-analytics-panel.md)
**Next Step:** → (backlog complete — proceed to development)

---

# 02-cc-train-detail

## Page Metadata

| Property | Value |
|----------|-------|
| **Scenario** | 12 — Claudia Monitors the Live Fleet and Resolves an Escalation |
| **Page Number** | 12.2 |
| **Platform** | Desktop web |
| **Page Type** | Right panel / drawer (opens alongside fleet list in Live Monitoring tab) |
| **Viewport** | Desktop-first |
| **Interaction** | Mouse + keyboard |
| **Visibility** | Authenticated (Control Centre operators) |

---

## Overview

**Page Purpose:** Give Claudia a full per-train picture — coach-by-coach live occupancy, flow indicators, active alerts, and open escalations — without leaving the Live Monitoring fleet list. The panel opens to the right when she taps a train card; the fleet list narrows but stays visible, preserving ambient awareness.

**User Situation:** A train card in the fleet list catches Claudia's attention — a red badge, an alert icon on a coach, or a known chronic overcrowding train approaching peak. She taps it to drill in without losing sight of the rest of the fleet.

**Success Criteria:**
- Claudia sees coach-level detail within 2 seconds of tapping a train card.
- Live occupancy and flow indicators update without page refresh.
- Active alerts and open escalations are immediately visible and tappable to act on.
- Closing the panel returns the fleet list to full width instantly.

**Entry Points:**
- Tap a train card in the Live Monitoring fleet list
- Tap a train ID reference in the escalations inbox unified feed
- Deep-link from a staleness indicator in the fleet list

**Exit Points:**
- Close button → panel dismisses, fleet list returns to full width
- Tap an alert row or escalation row → escalation detail panel opens (cc-live-monitoring spec)

---

## Reference Materials

**Strategic Foundation:**
- [Scenario 12](../../C-UX-Scenarios/12-claudia-live-fleet-monitoring.md) — Full live monitoring scenario including train detail drill-in

**Related Pages:**
- [cc-live-monitoring](../scenario-12-specs/01-cc-live-monitoring.md) — Parent view; fleet list + escalation detail panel

---

## Layout Structure

Desktop only. Right panel opens alongside the fleet list — fleet list narrows to ~50% width, panel occupies the remaining ~50%. One panel open at a time.

```
+----------------------------------------------------------+
| APP SHELL — Top nav (shared)                              |
+----------------------------------------------------------+
| TAB BAR — Live Monitoring* | System Health | Analytics    |
+----------------------------------------------------------+
| KPI STRIP (full width — from cc-live-monitoring)          |
+----------------------------------------------------------+
| FLEET LIST (~50%)          | TRAIN DETAIL PANEL (~50%)   |
|                            |                              |
| [Train cards — narrowed]   | [td-train-id] [td-status]  [✕]|
|                            |                              |
| R5001C-031 🔴 ← selected   | COACH GRID                  |
| R5001C-022 🟡              | C1   C2   C3   C4   C5      |
| R5001C-001 🟢              | 45%  61%  94%  78%  52%    |
| ...                        | ↑↓        🧳               |
|                            |                              |
|                            | ACTIVE ALERTS               |
|                            | 🔴 Unattended item · C4     |
|                            | 🟡 Crowding · C3            |
|                            |                              |
|                            | OPEN ESCALATIONS            |
|                            | AI · Unattended item · C4   |
|                            | Conrad · Capacity flag      |
+----------------------------------------------------------+
```

`*` = active tab indicator

---

## Spacing

**Scale:** Inherits `--space-*` token scale from ÖBB dark ops design system (`colors_and_type.css`)

| Property | Token |
|----------|-------|
| Panel horizontal padding | `space-lg` |
| Panel vertical padding (top) | `space-md` |
| Fleet list → panel (horizontal) | `space-zero` (panel slides in flush — continuous surface) |
| Panel header → Coach grid | `space-sm` |
| Coach grid → Active alerts list | `space-md` |
| Active alerts list → Open escalations | `space-md` |
| Alert row → alert row | `space-zero` (flush rows, 1px divider) |
| Escalation row → escalation row | `space-zero` (flush rows, 1px divider) |
| Coach cell → coach cell (horizontal) | `space-sm` |

---

## Typography

**Scale:** ÖBB dark ops type scale (`colors_and_type.css`)

| Element | Semantic | Desktop size | Weight | Notes |
|---------|----------|-------------|--------|-------|
| Train ID heading | `h2` | `heading-xl` | 700 | Primary identity in panel |
| Status badge label | `p` | `heading-xxs` | 600 | "Operational" / "Attention" / "Alert" |
| Coach label | `p` | `heading-xxs` | 600 | "C1"… "C8" |
| Occupancy figure | `p` | `heading-sm` | 700 | Glanceable per-coach % |
| Flow indicator text | `p` | `heading-xxs` | 400 | "↑ boarding" / "12 moving" |
| Alert row text | `p` | `heading-xs` | 400 | Alert type + coach + time |
| Escalation row text | `p` | `heading-xs` | 400 | Source + summary + status |
| Empty state labels | `p` | `heading-xxs` | 400 | "No active alerts" etc. |
| Section sub-headings | `h3` | `heading-xs` | 600 | "Active Alerts" / "Open Escalations" |

---

## Page Sections

### Section: Panel Header

**OBJECT ID:** `td-panel-header`

| Property | Value |
|----------|-------|
| Purpose | Train identity, current severity, and close action — visible at all times as panel scrolls |
| Layout | Horizontal: train ID (left) · status badge (centre-left) · close button (right) |
| Padding | `space-md` vertical, `space-lg` horizontal |
| Position | Sticky top of panel |

---

#### Train ID Heading

**OBJECT ID:** `td-train-id`

| Property | Value |
|----------|-------|
| Component | Heading |
| Semantic tag | `h2` |
| EN | Train identifier, e.g. "R5001C-031" (dynamic) |
| Behavior | Display only — populated from tapped fleet card data |

---

#### Status Badge

**OBJECT ID:** `td-status-badge`

| Property | Value |
|----------|-------|
| Component | Status badge |
| EN (green) | "Operational" |
| EN (amber) | "Attention" |
| EN (red) | "Alert" |
| Behavior | Auto-updates via WebSocket when train severity changes. Mirrors the fleet list card badge in real time. |
| States | **Green:** `--obb-sev-ok` · **Amber:** `--obb-sev-warn` · **Red:** `--obb-sev-crit` |

---

#### Close Panel Button

**OBJECT ID:** `td-close-btn`

| Property | Value |
|----------|-------|
| Component | Icon button |
| Accessible label | "Close train detail" |
| Behavior | On tap → panel dismisses; fleet list returns to full width; focus returns to the tapped train card in the fleet list |
| States | **Default** · **Hover / Focus:** highlighted |

#### ↕ `td-v-space-sm` — panel header leads directly into coach grid

---

### Section: Coach Grid

**OBJECT ID:** `td-coach-grid`

| Property | Value |
|----------|-------|
| Purpose | Visual consist view — all coaches left to right in consist order, each showing live occupancy + flow state + alert indicator |
| Layout | Horizontal row of coach cells; wraps to second row if consist > 8 coaches |
| Padding | `space-md` |
| Cell gap | `space-sm` horizontal |

---

#### Coach Cell

**OBJECT ID:** `td-coach-cell`

| Property | Value |
|----------|-------|
| Component | Tile (repeating — one per coach in consist order) |
| Layout | Vertical stack: coach label · occupancy figure · flow indicator · alert icon |
| EN coach label | "C1", "C2" … "C8" (dynamic, consist order) |
| Behavior | On tap → highlights selected coach cell (border highlight using `--obb-sev-info`); scrolls `td-alerts-list` to filter alerts for that coach only. Tap same coach again or tap another → clears filter. |
| States | **Default** · **Selected** (highlighted border) · **Alert** (alert icon visible) · **Loading** (skeleton) |

---

#### Occupancy Figure

**OBJECT ID:** `td-coach-occupancy`

| Property | Value |
|----------|-------|
| Component | Text label (within coach cell) |
| EN | "78%" (dynamic) |
| Behavior | Auto-updates via WebSocket on each occupancy event. Number transitions smoothly — no flash. |

---

#### Flow Indicator

**OBJECT ID:** `td-coach-flow`

| Property | Value |
|----------|-------|
| Component | Directional indicator (within coach cell) |
| EN (at station — boarding) | "↑ boarding" |
| EN (at station — alighting) | "↓ alighting" |
| EN (in transit — movement) | "12 moving" (cumulative inter-coach count) |
| EN (in transit — no movement) | (hidden — no label shown) |
| Behavior | At station: sustained arrows driven by TCMS door open/close events — appear when doors open, clear when doors close. In transit: cumulative pulse count driven by BYTETracker cross-zone detection events; resets per journey segment. |
| States | **Hidden** (in transit, no movement) · **Boarding arrows** (at station) · **Alighting arrows** (at station) · **Pulse count** (in transit, movement detected) |

---

#### Coach Alert Icon

**OBJECT ID:** `td-coach-alert-icon`

| Property | Value |
|----------|-------|
| Component | Icon (conditional, within coach cell) |
| EN accessible label — luggage | "Unattended item alert" |
| EN accessible label — crowding | "Crowding alert" |
| EN accessible label — accessibility | "Accessibility flag" |
| Behavior | Auto-appears on coach cell when a new alert fires for that coach via WebSocket. Clears when alert resolves. |
| States | **Hidden** · **Luggage icon** · **Crowding icon** · **Accessibility icon** |

#### ↕ `td-v-space-md` — coach grid to active alerts list: distinct data surfaces

---

### Section: Active Alerts List

**OBJECT ID:** `td-alerts-list`

| Property | Value |
|----------|-------|
| Purpose | All current AI alerts for this train, sorted by severity. Tappable to act. Filterable by coach cell tap. |
| Layout | Vertical list |
| Padding | `space-md` horizontal, `space-sm` vertical |
| Row gap | `space-zero` (flush rows, 1px `--obb-surface-3` divider) |

---

#### Section Sub-heading

**OBJECT ID:** `td-alerts-heading`

| Property | Value |
|----------|-------|
| Semantic tag | `h3` |
| EN | "Active Alerts" |

---

#### Alert Row

**OBJECT ID:** `td-alert-row`

| Property | Value |
|----------|-------|
| Component | List row (repeating — one per active alert, sorted by severity) |
| EN examples | "Unattended item · Coach C4 · 11:23" · "Crowding · Coach C3 · 09:41" · "Accessibility flag · Coach C6 · 10:15" |
| Behavior | On tap → opens escalation detail panel (cc-live-monitoring spec) for the linked escalation. If no escalation exists yet (AI informational, not yet escalated) → opens read-only alert detail panel. |
| States | **Default** · **Hover** · **Tapped** (opens detail) |

---

#### Alerts Empty State

**OBJECT ID:** `td-alerts-empty`

| Property | Value |
|----------|-------|
| Component | Text label (conditional) |
| EN | "No active alerts" |
| Behavior | Display only. Shown when alerts list is empty. |

#### ↕ `td-v-space-md` — active alerts to open escalations: distinct data surfaces

---

### Section: Open Escalations

**OBJECT ID:** `td-escalations-list`

| Property | Value |
|----------|-------|
| Purpose | Open escalations for this train only — subset of the main escalations inbox. Links through to full escalation detail. |
| Layout | Vertical list |
| Padding | `space-md` horizontal, `space-sm` vertical |
| Row gap | `space-zero` (flush rows, 1px divider) |

---

#### Section Sub-heading

**OBJECT ID:** `td-escalations-heading`

| Property | Value |
|----------|-------|
| Semantic tag | `h3` |
| EN | "Open Escalations" |

---

#### Escalation Row

**OBJECT ID:** `td-escalation-row`

| Property | Value |
|----------|-------|
| Component | List row (repeating — one per open escalation for this train) |
| EN examples | "AI · Unattended item · Coach C4 · Unacknowledged" · "Conrad · Capacity flag · Acknowledged" · "Roland · Technical note · Info" |
| Behavior | On tap → opens escalation detail panel in the main escalations inbox (same panel as tapping the item directly in the unified feed). |
| States | **Unacknowledged** (pulse animation) · **Acknowledged** (calm) · **In review** · **Hover** · **Tapped** |

---

#### Escalations Empty State

**OBJECT ID:** `td-escalations-empty`

| Property | Value |
|----------|-------|
| Component | Text label (conditional) |
| EN | "No open escalations" |
| Behavior | Display only. |

---

## Page States

| State | When | Appearance | Actions available |
|-------|------|------------|-------------------|
| **Loading** | Panel first opens, data fetch in flight | Coach grid skeleton cells; alerts + escalations show skeleton rows | None — wait |
| **All clear** | Train operational, no alerts, no escalations | All coach cells green; both lists show empty states | Tap coach cell to filter; close panel |
| **Alerts present** | One or more active AI alerts | Alert icon(s) on relevant coach cells; `td-alerts-list` populated | Tap alert row, tap coach cell to filter, close panel |
| **Escalation active** | One or more open escalations | `td-escalations-list` populated; unacknowledged rows pulse | Tap escalation row → escalation detail |
| **At station** | TCMS door open event received | Coach flow indicators show sustained boarding/alighting arrows | All above |
| **In transit** | TCMS door closed, train moving | Coach flow indicators show inter-coach pulse counts (hidden if no movement) | All above |
| **WebSocket stale** | No update received > 60s | Occupancy figures dim; staleness label below panel header: "Data may be delayed" | Close panel |
| **Load error** | Panel data fetch fails | Error message: "Could not load train detail — try again" + retry button | Retry, close panel |

---

## Component States Summary

| OID | States |
|---|---|
| `td-status-badge` | Green (Operational) · Amber (Attention) · Red (Alert) |
| `td-coach-cell` | Default · Selected (highlighted border) · Alert (icon visible) · Loading (skeleton) |
| `td-coach-flow` | Hidden · Boarding arrows · Alighting arrows · Pulse count |
| `td-coach-alert-icon` | Hidden · Luggage · Crowding · Accessibility |
| `td-alert-row` | Default · Hover · Tapped |
| `td-escalation-row` | Unacknowledged (pulse) · Acknowledged · In review · Hover · Tapped |
| `td-close-btn` | Default · Hover / Focus |

---

## Validation & Errors

No form fields. System errors only:

| Error | Code | Message (EN) |
|---|---|---|
| Panel data fetch failed | `ERR_TRAIN_DETAIL_LOAD` | "Could not load train detail — try again" |
| WebSocket stale > 60s | `ERR_WS_STALE` | "Data may be delayed — last update 75s ago" |

---

## Conditional Sections

| Condition | Detail |
|-----------|--------|
| No active alerts | `td-alerts-empty` shown; `td-coach-alert-icon` hidden on all cells |
| No open escalations | `td-escalations-empty` shown |
| Coach cell selected | `td-alerts-list` filters to show only alerts for selected coach |
| At station (TCMS door open) | `td-coach-flow` shows boarding/alighting arrows |
| In transit, no inter-coach movement | `td-coach-flow` hidden on all cells |
| WebSocket stale | Staleness label shown below panel header; occupancy figures dim |
| Needs API data | → [data-api.instructions.md](../../4-ux-design/templates/instructions/data-api.instructions.md) |
| Final review | → [accessibility.instructions.md](../../4-ux-design/templates/instructions/accessibility.instructions.md) |
| Always | → [open-questions.instructions.md](../../4-ux-design/templates/instructions/open-questions.instructions.md) |

---

## Technical Notes

- **One panel at a time:** Opening a different train card closes the current panel and opens a new one. No multi-train detail view.
- **Coach cell filter is local UI state only:** Filtering `td-alerts-list` by coach tap does not fire a backend request — it filters the already-loaded alert list client-side.
- **Flow indicators — dual behaviour:**
  - *At station:* sustained arrows driven by TCMS door open/close events (from the `vlan-pollers` container via onboard event-store). Arrows appear on door open, clear on door close.
  - *In transit:* cumulative inter-coach pulse count driven by BYTETracker cross-zone detection (from `inference` → `fusion` → event-store). Count resets per journey segment.
- **Seated/standing columns:** ⚠️ TBC — per-coach seated/standing breakdown depends on `pose_estimation` feasibility. Not included in this spec. If confirmed viable, a seated/standing split would be added to each coach cell below the occupancy figure.
- **Consist length:** Dynamic — panel renders as many coach cells as the consist contains. Wraps to second row if > 8 coaches.
- **Real-time updates:** Same WebSocket channel as Live Monitoring (ADR-9). All data-driven fields update without page refresh.
- **Alert detail for non-escalated alerts:** If an alert row has no associated escalation (AI informational, below escalation confidence threshold), tapping it opens a read-only alert detail panel — this panel is not yet specced and is out of scope for Phase 4.

---

## Open Questions

| # | Question | Context | Status |
|---|----------|---------|--------|
| 1 | Is `pose_estimation` feasible for seated/standing inference per coach? | Determines whether seated/standing split is added to coach cells | 🔴 Open — Hailo-8 team |
| 2 | What is the inter-coach movement count reset boundary — per station stop, per journey, or rolling window? | Determines how `td-coach-flow` pulse count is displayed and reset | 🔴 Open |
| 3 | Should the panel show a consist diagram (visual train shape) or a flat horizontal cell row? | Visual consist diagram is richer but requires consist topology data from TCMS | 🔴 Open |
| 4 | What is the read-only alert detail panel for non-escalated AI informational alerts? | `td-alert-row` tap behaviour when no escalation linked — not yet specced | 🔴 Open — Phase 4 backlog |
| 5 | Does the panel persist across tab switches (System Health, Analytics) or close when leaving Live Monitoring tab? | Determines panel state management on tab bar interaction | 🔴 Open |

---

## Checklist

- [x] Page purpose clear
- [x] All Object IDs assigned (14 components)
- [x] Components reference design system tokens
- [x] Content specified in English
- [x] Page states documented (8)
- [x] Component states documented (22)
- [x] Conditional sections documented
- [x] Technical dependencies and open questions captured
- [x] TBC flag: seated/standing (pose_estimation dependency)

---

**Previous Step:** ← [cc-analytics-panel](../scenario-04-specs/01-control-centre-analytics-panel.md)
**Next Step:** → (Control Centre Dashboard design backlog complete — proceed to development)

---

_Created using Whiteport Design Studio (WDS) methodology — Phase 4 UX Design_
