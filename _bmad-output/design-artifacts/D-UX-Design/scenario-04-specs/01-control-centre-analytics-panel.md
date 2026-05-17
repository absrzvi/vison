# 01-cc-analytics-panel

**Previous Step:** ← [cc-system-health](../scenario-11-specs/01-cc-system-health.md)
**Next Step:** → [cc-train-detail](../scenario-12-specs/02-cc-train-detail.md)

---

## Page Metadata

| Property | Value |
|----------|-------|
| **Scenario** | 04 — Claudia Runs Her Morning Fleet Occupancy Review · 03 — Conrad Escalates Chronic Overcrowding |
| **Page Number** | 04.1 |
| **Platform** | Desktop web |
| **Page Type** | Tab view (within Control Centre Dashboard) — 4 sub-tabs |
| **Viewport** | Desktop-first |
| **Interaction** | Mouse + keyboard |
| **Visibility** | Authenticated (Control Centre operators) |

---

## Overview

**Page Purpose:** Surface fleet-wide capacity analytics across four lenses — exceptions requiring action, occupancy patterns by route and hour, dwell time performance by station, and AI detection quality — so Claudia can complete her morning review in under 10 minutes and take targeted action on chronic overcrowding without building queries.

**User Situation:** Claudia arrives at 07:45. The dashboard is already open. She opens the Analytics tab as a daily habit. She starts with Capacity Exceptions — exceptions-first, trend visible, act or dismiss, done. She then checks Occupancy Heatmap for route-hour patterns, Dwell Time for station performance, and AI Detection Quality to validate data confidence.

**Success Criteria:**
- Claudia identifies all actionable capacity exceptions in < 10 minutes with evidence already attached.
- Conrad's capacity flags are visually prominent and linked to the relevant exception card.
- Each sub-tab delivers a standalone insight without requiring cross-tab navigation.
- Export produces a management-ready CSV without manual data extraction.

**Entry Points:**
- Tab bar in the Control Centre Dashboard (from Live Monitoring or System Health tab)
- Conrad capacity flag escalation in the Live Monitoring escalations inbox (deep-links to relevant exception card)

**Exit Points:**
- Tab bar — back to Live Monitoring or System Health
- "Add to capacity review queue" → capacity review modal → fleet planning queue
- "Export CSV" → file download

---

## Layout Structure

Desktop only. Full-height tab panel with a shared tab bar (sub-tabs) + date range selector at the top, and sub-tab-specific content below.

```
+----------------------------------------------------------+
| APP SHELL — Top nav (shared)                              |
+----------------------------------------------------------+
| TAB BAR — Live | System Health | Analytics*               |
+----------------------------------------------------------+
| SUB-TAB BAR                            | Range: [7d][14d][30d] | [Export CSV] |
| [Capacity Exceptions] [Occupancy Heatmap] [Dwell Time] [AI Detection Quality] |
+----------------------------------------------------------+
| SUMMARY STRIP (sub-tab-specific)                          |
+----------------------------------------------------------+
| SUB-TAB CONTENT (scrollable)                              |
+----------------------------------------------------------+
```

`*` = active tab indicator

---

## Shared Controls

### Date Range Selector

**OBJECT ID:** `ca-date-range`

| Property | Value |
|----------|-------|
| Component | Segmented button group |
| Options | 7d · 14d · 30d |
| Default | 7d |
| Behavior | On change → all four sub-tabs reload their data for the selected window. State persists while navigating between sub-tabs within the Analytics tab. Resets to 7d on tab close/reopen. |
| Position | Right end of sub-tab bar, left of Export CSV button |

### Export CSV Button

**OBJECT ID:** `ca-export-btn`

| Property | Value |
|----------|-------|
| Component | Button (secondary) |
| EN | "Export CSV" |
| Behavior | Exports data for the currently active sub-tab + selected date range. Fields vary by sub-tab (see per-tab technical notes). |
| States | Default · Loading (spinner) · Error ("Export failed — try again") |

---

## Sub-Tab 1: Capacity Exceptions

**OBJECT ID:** `ca-exceptions`

### Layout

Two-column: exception list (left ~300px fixed) + service detail (right, flex). Right column shows placeholder until a card is selected.

```
+------------------------+----------------------------------+
| EXCEPTION LIST          | SERVICE DETAIL                   |
|                         |                                  |
| WIEN → SALZBURG    [2]  | R5001C-031 · Wien→Salzburg · date|
| ● R5001C-031 · 17:42   | [RED badge]                      |
|   Coaches C3, C4 · 94% |                                  |
|   ↑ 3 consecutive weeks | 🚩 Conrad flagged this service   |
|   🚩 Conrad flagged     |                                  |
|                         | COACH OCCUPANCY CHART            |
| GRAZ → WIEN        [1]  | C3 ████████████████████ 94%  ▲  |
| ● R5001C-022 · 18:05   | C4 ████████████████████████ 98% ▲|
|   Coach C5 · Peak 91%  | C1 ████████           42%        |
|   ↑ 2 consecutive weeks |    0    50%   85%  100%         |
|                         |                                  |
| [Show dismissed (2)]    | 7-DAY PEAK CHART (bar)           |
|                         |                                  |
+------------------------+ [Add to queue] [No action req'd] |
```

### Summary Strip

**OBJECT ID:** `ca-exc-summary`

| Sub-OID | Element | Content |
|---------|---------|---------|
| `ca-exc-services` | Services operated | "{N} services operated" |
| `ca-exc-counts` | Exception counts | "{N} red · {N} amber exceptions" |
| `ca-exc-flags` | Conrad flags | "{N} Conrad flag{s}" |
| `ca-exc-date` | Date range | "{Label} · {from} – {to}" |

### Exception List

**OBJECT ID:** `ca-exception-list`

Exceptions are **grouped by route**. Each route group has a header showing the route name and exception count badge. Groups sort red-first (any red exception in group → group sorts before amber-only groups).

#### Route Group Header

**OBJECT ID:** `ca-route-group`

| Property | Value |
|----------|-------|
| Component | Section label row |
| Content | Route name (e.g. "WIEN → SALZBURG") + count badge |
| Behavior | Display only — not interactive |

#### Exception Card

**OBJECT ID:** `ca-exception-card`

| Property | Value |
|----------|-------|
| Component | Card (repeating within route group) |
| Behavior | On click/Enter/Space → opens Service Detail in right column. Toggle: clicking selected card deselects it. |
| Keyboard | `tabIndex=0`, `role="button"`, `aria-pressed`, `onKeyDown` Enter/Space |
| States | Default · Hover · Selected (highlighted border + blue outline) · In Review ("In review" pill) · Dismissed (opacity 0.45) |

Sub-elements:

| Sub-OID | Element | Content |
|---------|---------|---------|
| `ca-card-sev` | Severity dot | Red (≥90%) / Amber (75–89%) |
| `ca-card-service` | Service ID + departure | "R5001C-031 · 17:42" |
| `ca-card-date` | Date (14d/30d only) | "2026-05-08" — shown when exception is from a prior week |
| `ca-card-pill` | Status pill | "In review" (blue) / "Dismissed" (grey) — conditional |
| `ca-card-coaches` | Coaches + peak | "Coaches C3, C4 · Peak: 94%" |
| `ca-card-trend` | Trend badge | "↑ 3 consecutive weeks" / "New" / "Improving ↓" / "Stable" |
| `ca-card-flag` | Conrad flag | "🚩 Conrad flagged" — own row below trend badge; only shown if flag exists |

#### Dismissed Toggle

**OBJECT ID:** `ca-dismissed-toggle`

| Property | Value |
|----------|-------|
| Component | Ghost button, full-width, at bottom of list |
| EN (hidden) | "Show dismissed ({N})" |
| EN (visible) | "Hide dismissed ({N})" |
| Behavior | Toggles visibility of dismissed exception cards. Dismissed cards appear below active cards under a "Dismissed" section label. Only shown when dismissedCount > 0. |

#### Dismissed Section Label

**OBJECT ID:** `ca-dismissed-label`

| Property | Value |
|----------|-------|
| Component | Section label (conditional) |
| EN | "Dismissed" |
| Behavior | Shown between active and dismissed cards when dismissed toggle is on |

#### Empty State

**OBJECT ID:** `ca-exception-empty`

| Property | Value |
|----------|-------|
| EN | "No exceptions in {range label} — all services within threshold." |

### Service Detail Panel

**OBJECT ID:** `ca-service-detail`

Scrolls independently. Resets to top on each card selection.

#### Detail Header

| Property | Value |
|----------|-------|
| EN | "{trainId} · {route} · {date}" |
| Component | h2 + severity badge (Red/Amber pill) |

#### Conrad Flag Box (Conditional)

**OBJECT ID:** `ca-detail-flag-box`

| Property | Value |
|----------|-------|
| Component | Info box (blue border + background) |
| Content | "🚩 Conrad flagged this service" · timestamp · quoted note |
| Conditional | Only rendered when conradFlag exists |

#### Coach Occupancy Chart

**OBJECT ID:** `ca-coach-chart`

Replaces the occupancy timeline chart. Answers the immediate operator question: *which coaches were over threshold and by how much?*

| Property | Value |
|----------|-------|
| Component | Horizontal bar chart — one row per coach |
| Layout | Grid: coach label (28px) · bar track (flex) · % value (40px) · flag indicator (14px) |
| Bar track | Full 0–100% range. 85% threshold line overlaid on every row (vertical dashed line) |
| Bar colour | ≥90% → critical red · 85–89% → warning amber · <85% → normal green |
| Flag indicator | ▲ shown next to coaches that exceeded threshold, coloured by severity |
| X-axis | Tick labels at 0 / 50% / 85% / 100%. 85% label in warning amber. |
| Data source | Peak occupancy per coach derived from timeline data (max value across all timestamps) |
| Aria label | "Peak occupancy by coach — {trainId} · {departure}" |

#### 7-Day Peak Chart

**OBJECT ID:** `ca-trend-chart`

| Property | Value |
|----------|-------|
| Component | Bar chart (SVG, viewBox 400×100, no preserveAspectRatio distortion) |
| X axis | Relative day labels: −6, −5 … −1, Today |
| Y axis | Peak occupancy % — gridlines at 0, 50, 85, 100 |
| Threshold | Dashed line at 85% |
| Bar colour | ≥85% → critical red · <85% → warning amber |
| Aria label | "7-day trend — {trainId}" |

#### Action Strip

**OBJECT ID:** `ca-action-strip`

| Status | Controls shown |
|--------|---------------|
| `unreviewed` | "Add to capacity review queue" (primary) + "No action required" (secondary) |
| `in_review` | "Queued for capacity review · Priority: {X}" + "Added at {HH:MM}" |
| `dismissed` | "Marked no action required" + "Reopen" (ghost button) |

#### Capacity Review Modal

**OBJECT ID:** `ca-review-modal`

| Sub-OID | Field | Type | Constraints |
|---------|-------|------|-------------|
| `ca-modal-note` | Note | Textarea | 200 char max, optional |
| `ca-modal-priority` | Priority | Pill selector | Low / Medium / High — required |
| `ca-modal-confirm` | Confirm | Primary button | Disabled until priority selected |
| `ca-modal-cancel` | Cancel | Ghost button | — |

Validation: priority required before confirm. Error: "Select a priority to continue".

On confirm: exception gains `in_review` status + "In review" pill. `queuedAt` timestamp recorded (HH:MM local time).

---

## Sub-Tab 2: Occupancy Heatmap

**OBJECT ID:** `ca-heatmap`

### Layout

Single scrollable column. Top: section title + unit note. Middle: heatmap grid. Bottom: legend + peak hour table.

### Section Title

EN: "Occupancy Heatmap — Avg % by route × hour (last {N} days)" + italic note "· Values shown are average occupancy %"

### Heatmap Grid

**OBJECT ID:** `ca-heatmap-grid`

| Property | Value |
|----------|-------|
| Axes | Routes (rows) × Hours 05:00–23:00 (columns, 19 total) |
| Cell size | 44px × 32px |
| Cell content | "{occupancy}%" — average for the selected date range |
| Null cells | Hours outside the range shift show "—" with null styling (dimmed, `occ-heatmap__cell--null`) |
| Scroll | Horizontal scroll when viewport narrower than grid. Fade overlay on right edge when overflowing (JS-detected). |

#### Cell Colour Bands

| Band | Occupancy | Background | Text |
|------|-----------|------------|------|
| Very low | <40% | Dark green | Light green |
| Low-medium | 40–59% | Medium green | Light green |
| Medium | 60–74% | Dark yellow | Light yellow |
| High | 75–89% | Dark orange | Light orange |
| Critical | ≥90% | Dark red | Light red |

#### Cell Interaction

| Property | Value |
|----------|-------|
| Hover | Cell scales to 1.15×, white outline. Fixed-position tooltip: "{route} · {hour} · {N}% avg occupancy" — clamped to viewport right edge |
| Keyboard | `tabIndex=0`, `role="gridcell"`, `aria-label`, focus shows tooltip via `onFocus/onBlur` |
| Focus ring | `outline: 2px solid --obb-blue-accent` via `:focus-visible` |

### Legend

5 swatches matching the 5 colour bands, labelled: <40% · 40–59% · 60–74% · 75–89% · ≥90%

### Peak Hour Per Route Table

**OBJECT ID:** `ca-peak-hour-table`

One row per route. CSS grid layout: `160px 52px 1fr 44px auto` — shared by axis row and data rows so labels align precisely.

| Column | Content |
|--------|---------|
| Route | Route name |
| Hour | Peak hour (HH:MM) |
| Bar | Horizontal bar, 0–100% track, `overflow: visible`. 85% threshold line extends ±2px beyond bar height, z-index 2. |
| % | Peak occupancy %, coloured by severity |
| Days note | "{N}/{total} days ≥85%" — shown when daysOver85 > 0, in warning amber |

Axis row (above data rows): tick labels at 50% and 85% positions, absolutely positioned within the bar column.

---

## Sub-Tab 3: Dwell Time

**OBJECT ID:** `ca-dwell`

### Layout

Single scrollable column. Section 1: bar chart (actual vs scheduled per station). Section 2: scatter plot (crowding vs dwell correlation).

### Section 1: Dwell Bar Chart

**Title:** "Avg dwell time by station — actual vs scheduled (last {N} days)"

**Legend:** Two items — "Scheduled (tick)" with a grey line swatch · "Actual" with a coloured block swatch.

**Bar Rows:** Sorted descending by actual dwell time. Each row is a CSS grid: `160px 1fr` × 2 rows.

| Grid position | Element |
|--------------|---------|
| col 1, row 1 | Station name |
| col 2, row 1 | Bar track (`overflow: visible`) containing: actual bar + scheduled tick wrapper |
| col 1–2, row 2 | Values row: actual time · "sched Xs" · delta (excess or under-schedule) |
| col 1–2, below | Top cause (italic, dim) — conditional |
| col 1–2, below | Breach count — conditional, coloured by severity |

#### Actual Bar

Coloured by delay ratio (actual / scheduled):
- ≥140% → critical red
- ≥115% → medium amber
- <100% → normal green
- Otherwise → normal green

#### Scheduled Tick

A 12px-wide wrapper div (`dwell-bar-row__scheduled-wrap`) positioned absolutely at the scheduled proportion, with `cursor: default`. A 2px vertical line inside. On hover → fixed-position tooltip: "Scheduled: {Xs}".

#### Values Row (grid-row 2 — below bar, not overlapping)

- Actual value (coloured by severity, bold mono)
- "sched {Xs}" (dim)
- Over-schedule: "+{Xs}" in severity colour (shown when excess > 0)
- Under-schedule: "−{Xs} within schedule" in green (shown when actual < scheduled)

#### Breach Count

"{N} breach{es} {period label}" — e.g. "12 breaches last 14 days". Period label varies: "this week" / "last 14 days" / "last 30 days". Breach counts accumulate (×1/×2/×4 for 7d/14d/30d).

#### Empty State

"No dwell data available for this period."

### Section 2: Scatter Plot

**Title:** "Platform crowding vs dwell time — correlation"

**Layout:** Y-axis label + tick container (left) + plot area (flex). X-axis below. Insight block. Station legend.

#### Y-Axis

Absolute-positioned ticks at `bottom: toPlotY(v)%` for v in [40, 80, 120, 160]. `transform: translateY(50%)` to centre each label on its gridline. Label: "Dwell (s)".

#### Plot Area

- Horizontal gridlines at the same Y positions
- SVG trend line (dashed, blue, 35% opacity) — linear regression from scatter data
- Scatter dots: 8px circles, coloured by station (9-station palette), `opacity: 0.75`. On hover → fixed-position tooltip: "{station} · Crowding {N}% · Dwell {Xs}" — viewport-clamped.

#### X-Axis

Absolute-positioned tick labels at `left: toPlotX(v)%` for v in [20, 40, 60, 80, 90]. `transform: translateX(-50%)`. Label: "Platform crowding (%)".

#### Coordinate Mapping

- Crowding: 15–95% mapped to 0–100% plot width
- Dwell: 40–170s mapped to 0–100% plot height

#### Insight Block

Left-border accent block (blue). Content: "{correlationLabel} positive correlation (R²={value}) — each 10% increase in platform crowding adds approximately **{N}s** of dwell time."

Correlation label derived from R²: ≥0.7 → "Strong" · 0.4–0.69 → "Moderate" · <0.4 → "Weak"

#### Station Legend

Colour-coded dot + label for each of the 9 stations. Wraps to multiple rows.

#### fmtSec Rules

- <60s: "{N}s"
- ≥60s, remainder 0: "{M}m" (no trailing "0s")
- ≥60s, remainder >0: "{M}m {R}s"

---

## Sub-Tab 4: AI Detection Quality

**OBJECT ID:** `ca-ai`

### Layout

Single scrollable column. KPI strip → detection events chart → per-train uptime list.

### KPI Strip

**OBJECT ID:** `ca-ai-kpis`

4 tiles separated by vertical dividers:

| Tile | Content | Colour rule |
|------|---------|-------------|
| Events | "{N} Events · last {N} days" | Default |
| FP Rate | "{N}% False positive rate" | >10% → amber · ≤10% → green · null (no data) → "—" dim + "(no data)" label |
| Avg Confidence | "{N}%" | Always green |
| Fleet Uptime | "{N}%" | <95% → amber · ≥95% → green |

FP rate null state: when both totalEvents and totalFP are zero, show "—" rather than "0%" to distinguish no-data from zero false positives.

### Detection Events Chart

**Title:** "Detection events by type — last {N} days ({barLabel})"
- 7d: daily bars (Mon–Sun), `barLabel = "Mon–Sun"`
- 14d/30d: weekly aggregate bars (W1, W2…), `barLabel = "weekly totals"`. Data is deterministic (baked constants, no `Math.random()`), memoised on `dateRange`.

**Legend:** Three items (Unattended · Overcrowded · Oversized) — on their own row. FP note on separate line below: "False positives shown separately below bars — excluded from event totals".

**Bar columns:**

| Element | Detail |
|---------|--------|
| Total label | Above bar, dim mono |
| Stacked bar | Segments bottom-up: Unattended / Overcrowded / Oversized. `flex` sizing. `min-height: 0` (no stub on empty columns). |
| FP label | Below bar: "{N} FP" — shown when falsePositive > 0 |
| Day label | Below FP label |
| Empty column | `detection-bar-col--empty` class: total label dimmed, stack hidden |
| Hover tooltip | Fixed-position: "{day} · {total} events" + per-type breakdown rows |

Chart container: `min-height: 180px`, not fixed height — bars can't clip labels.

`maxBar` floored at 1 to prevent divide-by-zero when all bars are zero.

### Per-Train Uptime List

**Title:** "AI inference uptime by train (last {N} days)"

**Incident definition note:** "Incidents = inference gaps > 5 min (container restart or loss of connectivity)" — italic, dim.

**Axis row** (above list): relative labels at 70% / 85% / 100% of the bar track width. Warning threshold line at 85% position. Axis labels positioned absolutely within the track column.

Data varies by date range: incidents accumulate (×1/×2/×4), uptime % drifts slightly (−0/−0.5/−1.2pp). Sorted ascending by uptime (lowest first).

**Bar rows:** sorted lowest uptime first.

| Column | Content |
|--------|---------|
| Train ID | Mono, 110px |
| Bar track | Maps 70–100% uptime range to 0–100% bar width. `overflow: hidden`. |
| % value | Coloured: ≥95% green · 85–94% amber · <85% red |
| Incidents | "{N} incident{s}" — dim |

Bar colour matches % colour rule above.

---

## Page States (Shared)

| State | When | Appearance |
|-------|------|------------|
| Loading | Sub-tab opens or range changes | Skeleton content |
| No data | No records for selected range | Sub-tab-specific empty state message |
| Data present | Records available | Full sub-tab content |
| Export loading | CSV generation in progress | Export button spinner, disabled |
| API error | Data fetch fails | Error banner with retry |

---

## Conditional Sections

| Condition | Detail |
|-----------|--------|
| Conrad flag on exception | `ca-detail-flag-box` renders; `ca-card-flag` row on card; Reopen available after dismiss |
| No Conrad flag | Both hidden — no empty state shown |
| No exceptions | `ca-exception-empty` shown; detail panel shows placeholder |
| Dismissed exceptions > 0 | `ca-dismissed-toggle` shown at bottom of list |
| showDismissed = true | `ca-dismissed-label` section header + dismissed cards appear |
| FP rate = null | KPI shows "—" + "(no data)" label |
| Bar column total = 0 | `detection-bar-col--empty`: total dimmed, stack hidden |
| Uptime daysOver85 > 0 | Days note shown on peak hour table row |

---

## Technical Notes

- **Exception threshold:** Configurable per operator. Default: ≥85% average occupancy for ≥30 minutes during the service.
- **Date range scope:** All four sub-tabs share the same 7d/14d/30d selector. Range resets to 7d on tab close/reopen.
- **Breach counts:** Discrete event accumulation — not smoothed. 7d baseline × 1; 14d × 2; 30d × 4.
- **Weekly aggregation (AI tab):** Deterministic baked constants per week, memoised. No `Math.random()` in render path.
- **Scatter correlation:** Linear regression (slope, intercept, R²) computed module-level from `DWELL_SCATTER`. `correlationLabel` derived from R².
- **Uptime bar range:** 70–100% mapped to full bar width. Not 0–100% — differences in the 88–99% range are visible.
- **SVG charts:** All SVGs use real pixel `viewBox` (e.g. `400×100`) without `preserveAspectRatio="none"`. Text renders at proper sizes and is never stretched.
- **Tooltip clamping:** All fixed-position tooltips check `clientX + tooltipWidth > window.innerWidth` and flip left when near right edge.
- **Null occupancy cells (heatmap):** Hours shifted outside the source array for a given date range return `occupancy: null` and render as "—" cells — not silently clamped.
- **7-day trend labels:** Relative (−6…−1, Today), not calendar day names — correct regardless of service day of week.
- **Export CSV fields (Capacity Exceptions):** Service ID, route, date, flagged coaches, peak occupancy %, 7-day trend, Conrad flag (yes/no + note), action taken (dismissed / in review / none).
- **Fleet planning queue:** Destination of "Add to capacity review queue". Integration format TBC.
- **No live data in this tab:** Analytics is historical only. Live occupancy is in the Live Monitoring tab.

---

## Validation Rules

| Field | Rule | Error | Code |
|-------|------|-------|------|
| `ca-modal-note` | Max 200 characters | "Note must be 200 characters or fewer" | `ERR_NOTE_TOO_LONG` |
| `ca-modal-priority` | Required before confirm | "Select a priority to continue" | `ERR_PRIORITY_REQUIRED` |

---

## Open Questions

| # | Question | Context | Status |
|---|----------|---------|--------|
| 1 | Is the 7-day trend queried by service ID or route+time-slot? Train numbers on recurring services may change week to week. | Determines whether trend chart shows correct historical matches | 🔴 Open — Nomad Digital backend |
| 2 | Does the fleet planning queue exist as a system, or is "Add to capacity review queue" an export/notification? | Determines implementation of confirm action | 🔴 Open — ÖBB operations |
| 3 | Confirmed data retention period for historical occupancy data? (90 days assumed) | Determines date picker range and storage | 🔴 Open — Nomad Digital data governance |
| 4 | What is the configured exception threshold per operator deployment? | Default 85% assumed | 🔴 Open — ÖBB operations |
| 5 | Should the AI confidence and uptime KPIs in the strip reflect the selected date range or always show the latest 7-day window? | Currently range-aware for events + FP rate; uptime drifts by range | 🔴 Open |

---

## Checklist

- [x] Page purpose clear
- [x] All 4 sub-tabs specified
- [x] All Object IDs assigned
- [x] Components reference design system tokens
- [x] Content specified in English
- [x] Page states documented
- [x] Component states documented (cards, cells, bars, tooltips)
- [x] Validation rules defined
- [x] Conditional sections documented
- [x] Technical dependencies and open questions captured
- [x] SVG chart approach documented (real pixel viewBox, no distortion)
- [x] Accessibility documented (keyboard nav, aria-labels, focus rings)

---

**Previous Step:** ← [cc-system-health](../scenario-11-specs/01-cc-system-health.md)
**Next Step:** → [cc-train-detail](../scenario-12-specs/02-cc-train-detail.md)

---

_Last updated: 2026-05-16 — reflects locked prototype after all Freya review iterations_
