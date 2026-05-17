### 01-cc-system-health

**Previous Step:** ← [cc-live-monitoring](../scenario-12-specs/01-cc-live-monitoring.md)
**Next Step:** → [cc-analytics-panel](../scenario-04-specs/01-control-centre-analytics-panel.md)

---

# 01-cc-system-health

## Page Metadata

| Property | Value |
|----------|-------|
| **Scenario** | 11 — Claudia (and Roland) Check System Health Across the Fleet |
| **Page Number** | 11.1 |
| **Platform** | Desktop web |
| **Page Type** | Tab view (within Control Centre Dashboard) |
| **Viewport** | Desktop-first |
| **Interaction** | Mouse + keyboard |
| **Visibility** | Authenticated (Control Centre operators and fleet managers) |

---

## Overview

**Page Purpose:** Provide a fleet-wide, at-a-glance view of two AI service health signals per train — CCTV stream connectivity and application (Docker container) health — so Claudia can confirm the platform is working before operational decisions, and Roland can identify the degraded layer before opening the Maintenance App.

**User Situation:** Claudia opens this tab at the start of shift (or when she suspects stale data). Roland opens it after a tip from Claudia or when noticing absent alerts. Both need to reach a conclusion in under 60 seconds.

**Success Criteria:**
- Claudia: Closes tab in < 30s on a healthy fleet. On degradation, knows which train + which layer within 60s.
- Roland: Navigates directly to the correct diagnostic layer in the Maintenance App without guessing.
- Platform: Failures are visible before operators notice missing alerts — platform self-reports health.

**Entry Points:**
- Tab bar in the Control Centre Dashboard (from Live Monitoring or Analytics tab)
- Direct link from a staleness indicator badge on a Live Monitoring fleet card
- Roland deep-linking after a Claudia message

**Exit Points:**
- "Open in Maintenance App →" CTA (conditional — if Maintenance App integration is configured)
- Tab bar — back to Live Monitoring or Analytics tab

---

## Reference Materials

**Strategic Foundation:**
- [Scenario 11](../../C-UX-Scenarios/11-claudia-roland-system-health.md) — Full scenario with sunshine + exception paths
- [Scenario 09](../../C-UX-Scenarios/09-roland-l1-cable-failure.md) — Roland's entry point context

**Related Pages:**
- [cc-live-monitoring](../scenario-12-specs/01-cc-live-monitoring.md) — Live Monitoring tab (staleness indicator links here)
- [cc-analytics-panel](../scenario-04-specs/01-control-centre-analytics-panel.md) — Analytics tab

---

## Layout Structure

Desktop only. Two-column layout when train detail panel is open (inline — no modal/backdrop); single-column (full-width grid) when no panel is open.

```
+----------------------------------------------------------+
| APP SHELL — Top nav (shared, see cc-live-monitoring)      |
+----------------------------------------------------------+
| TAB BAR — Live Monitoring | System Health* | Analytics    |
+----------------------------------------------------------+
| TAB HEADER / SUMMARY STRIP                                |
| [14 trains monitored]  [2 trains with issues]  [Updated] |
+----------------------------------------------------------+
| FLEET HEALTH GRID (flex: 1)     | INLINE DETAIL PANEL    |
|                                 | (340px fixed, on tap)  |
| ● R5001C-031  [Streams:green] [Devices:red] [App:red] 41m | R5001C-031 ●    [×]|
| ● R5001C-008  [Streams:green] [Devices:red] [App:grn] 44m | Train Link ● Connected 11:35|
| ● R5001C-022  [Streams:amber] [Devices:amb] [App:amb] 2m  | CCTV Streams ● Healthy |
| R5001C-017  [Streams:green] [Devices:grn] [App:green]  —  | CCTV Devices [2 of 6 not found]|
| ...                             |  C3 · C5 — Not found  |
|                                 |  Applications [1 of 5 healthy]|
|                                 |  inference — exited·OOM|
|                                 |  Last fully healthy: 09:43 · 41m ago|
|                                 |  [Raise Maintenance Ticket]|
+----------------------------------------------------------+
```

`*` = active tab indicator. Coloured left border (4px) on each row reflects worst severity. Panel slides in from right; grid remains scrollable.

---

## Spacing

**Scale:** Inherits `--space-*` token scale from ÖBB dark ops design system (`colors_and_type.css`)

| Property | Token |
|----------|-------|
| Page horizontal padding | `space-lg` |
| Tab header strip → Fleet grid | `space-sm` |
| App shell → Tab header strip | `space-zero` |
| Grid row internal gap | `space-zero` (rows flush, separated by 1px divider) |
| Grid → Summary panel horizontal gap | `space-md` |

---

## Typography

**Scale:** ÖBB dark ops type scale (`colors_and_type.css`)

| Element | Semantic | Desktop size | Weight | Notes |
|---------|----------|-------------|--------|-------|
| Summary strip stats | `p` | `heading-lg` | 700 | Glanceable KPI figures |
| Train ID in grid row | `p` | `heading-xs` | 500 | Compact list context |
| Panel train ID heading | `h2` | `heading-xl` | 700 | Primary identity in panel |
| Panel detail labels | `p` | `heading-xs` | 400 | CCTV / App status descriptions |
| Container list rows | `p` | `heading-xs` | 400 | Per-container name + status |
| Last healthy timestamp | `p` | `heading-xxs` | 400 | Secondary metadata |
| Badge labels | `p` | `heading-xxs` | 600 | "CCTV Streams" / "Applications" |

---

## Page Sections

### Section: Tab Header / Summary Strip

**OBJECT ID:** `sh-summary-strip`

| Property | Value |
|----------|-------|
| Purpose | At-a-glance fleet health before scanning the grid. Two stat tiles + refresh timestamp. |
| Layout | Horizontal row, left-aligned tiles |
| Padding | `space-md` vertical, `space-lg` horizontal |
| Element gap | `space-lg` between tiles |

---

#### Total Trains Counter

**OBJECT ID:** `sh-summary-total`

| Property | Value |
|----------|-------|
| Component | Stat tile (read-only) |
| EN | "14 trains monitored" |
| Behavior | Display only — data-driven from WebSocket fleet roster |

---

#### Degraded Trains Counter

**OBJECT ID:** `sh-summary-degraded`

| Property | Value |
|----------|-------|
| Component | Stat tile (interactive when issues present) |
| EN (all healthy) | "All systems healthy" |
| EN (issues present) | "2 trains with issues" |
| Sub-label | Always rendered (prevents layout shift). "fleet status" when healthy; "click to jump" when issues present. |
| Behaviour | On tap (when issues present) → selects and smooth-scrolls to first issue row. |
| Colour | Issue tile colour matches worst fleet severity: red text when any train is red, amber when amber only. |
| States | **Healthy:** neutral colour · **Issues-red:** red accent text · **Issues-amber:** amber accent text |

---

#### Last Refresh Timestamp

**OBJECT ID:** `sh-summary-refresh`

| Property | Value |
|----------|-------|
| Component | Text label (read-only) |
| EN (fresh) | "12s ago" |
| EN (stale) | "1m 15s ago — reconnecting…" |
| Behavior | Live-ticking via `setInterval` every 1s — derived from real wall-clock `Date.now()`. Auto-updates on every WebSocket poll receipt (resets counter). No user trigger. |
| States | **Fresh:** neutral text · **Stale (> 60s):** amber text + pulse animation |

#### ↕ `sh-v-space-zero` — summary strip is continuous with tab bar above (no visual gap)

#### ↕ `sh-v-space-sm` — related sections: summary strip summarises the grid below

---

### Section: Fleet Health Grid

**OBJECT ID:** `sh-fleet-grid`

| Property | Value |
|----------|-------|
| Purpose | One row per active train — CCTV stream status + Application status. Exceptions sorted to top. |
| Layout | Vertical list |
| Padding | `space-md` |
| Row gap | `space-zero` (flush rows, 1px `--obb-surface-3` divider between each) |

---

#### Train Health Row

**OBJECT ID:** `sh-grid-row`

| Property | Value |
|----------|-------|
| Component | List row (repeating — one per active train) |
| Layout | Horizontal: severity dot · Train ID · CCTV Streams badge · CCTV Devices badge · Applications badge · Since column |
| Severity left border | 4px left border — red/amber/transparent. Immediate triage signal before reading badges. |
| Severity dot | 8px circle — red (with glow shadow), amber, or green (faded). |
| Behavior | On tap → toggles inline detail panel for this train. Tap selected row again to close. Panel stays open when scrolling grid. |
| "Ticket raised" chip | Blue chip shown on row when ticket has been raised via panel — visible without opening panel. No row-level opacity change. |
| Since column | Real wall-clock elapsed since `lastHealthy` (e.g. "41m ago"). "—" when no fault this session. |
| States | **Default:** unselected · **Selected:** surface-3 background · **Hover:** surface-2 background |

---

#### CCTV Stream Status Badge

**OBJECT ID:** `sh-badge-cctv-streams`

| Property | Value |
|----------|-------|
| Component | Status badge |
| States | **Green:** "● Healthy" · **Amber:** "● Degraded" · **Red:** "● Failed" |

---

#### CCTV Devices Status Badge

**OBJECT ID:** `sh-badge-cctv-devices`

| Property | Value |
|----------|-------|
| Component | Status badge |
| States | **Green:** "● All reachable" · **Amber:** "● Intermittent" · **Red:** "● Device not found" |

---

#### Application Status Badge

**OBJECT ID:** `sh-badge-containers`

| Property | Value |
|----------|-------|
| Component | Status badge |
| States | **Green:** "● Healthy" · **Amber:** "● Degraded" · **Red:** "● Unhealthy" |

---

### Section: Inline Detail Panel

**OBJECT ID:** `sh-panel`

| Property | Value |
|----------|-------|
| Purpose | Per-train detail — Train Link connectivity, CCTV streams, CCTV devices, application health breakdown, last-healthy timestamp, maintenance ticket action |
| Layout | Inline 340px fixed-width right column. No modal/backdrop — grid stays visible and scrollable. Slides in from right (180ms ease animation). |
| Visibility | Hidden until a grid row is tapped. One panel at a time. Toggled off by tapping the selected row again, or pressing ESC, or clicking the close button. |

---

#### Panel Header

**OBJECT ID:** `sh-panel-header`

| Property | Value |
|----------|-------|
| Component | Header bar — severity dot + train ID (mono font, 15px/700) + close button |
| Close button | 32×32px hit target. ESC also closes (ESC cancels pending confirm state first if active). |
| Accessible label | "Close detail panel" |

---

#### Train Link Row

**OBJECT ID:** `sh-panel-connectivity`

| Property | Value |
|----------|-------|
| Component | Status row — always rendered |
| EN (connected) | "● Connected · 11:35" (last seen timestamp) |
| EN (degraded) | "⚠ Degraded · 11:29" (amber text) |
| EN (no data) | "No data" (muted italic) |
| Behavior | Display only — driven by `connectivity` field on train object. Always rendered even if no data. |

---

#### CCTV Streams Row

**OBJECT ID:** `sh-panel-cctv-streams`

| Property | Value |
|----------|-------|
| Component | Status row |
| EN (healthy) | "All streams reachable" |
| EN (degraded) | "Degraded · packet loss" |
| EN (failed) | "Unreachable" |

---

#### CCTV Devices Row + Drill-down

**OBJECT ID:** `sh-panel-cctv-devices`

| Property | Value |
|----------|-------|
| Component | Status row + conditional per-coach drill-down list |
| EN (healthy) | "All devices reachable" |
| EN (degraded) | "1 of 8 intermittent" |
| EN (failed) | "2 of 6 not found" |
| Drill-down | Shown when `deviceStatus !== 'green'`. Per-coach rows with status badge. Reason note in muted italic below the list. |

---

#### Applications Row + Container Drill-down

**OBJECT ID:** `sh-panel-apps`

| Property | Value |
|----------|-------|
| Component | Status row + conditional container list |
| EN (healthy) | "5 of 5 healthy" |
| EN (degraded) | "Degraded · 1 container" |
| EN (failed) | "1 of 5 healthy" |
| Drill-down | Shown when `appStatus !== 'green'`. Per-container rows `{ name, status, note }`. Unhealthy containers have red-tinted background. Healthy containers show badge--green "healthy". |
| Count logic | Healthy count = containers where `status === 'green'` only (amber does not count as healthy). |
| Containers | `rtsp-ingest` · `vlan-pollers` · `inference` · `fusion` · `event-store` |

---

#### Last Healthy Timestamp

**OBJECT ID:** `sh-panel-last-healthy`

| Property | Value |
|----------|-------|
| Component | Text label in panel body footer |
| EN | "Last fully healthy: 09:43 today · 41m ago" |
| Behavior | Elapsed is real wall-clock (`Date.now()`) — live-ticking. Hidden when `lastHealthy` is null (no fault this session). |

---

#### Panel Footer — Ticket Actions

**OBJECT ID:** `sh-panel-footer`

| State | When | UI |
|-------|------|----|
| Default | Train has issues, no ticket raised | "Raise Maintenance Ticket" secondary button (full width) |
| Pending confirm | Button clicked | Label "Raise a maintenance ticket for {trainId}?" + Confirm (primary) + Cancel (ghost). ESC cancels. |
| Ticket raised | Confirmed | Green ✓ icon + "Ticket raised" + monospace ref (REF#XXXXX). Toast shown: "Ticket raised — REF#XXXXX · {trainId}" auto-dismisses 4s. Chip also appears on grid row. |
| No footer | Train is all-green | Footer not rendered |

---

#### Open in Maintenance App (Conditional)

**OBJECT ID:** `sh-panel-cta`

| Property | Value |
|----------|-------|
| Conditional render | Only rendered when `maintenance_app_enabled = true` in deployment config. Hidden entirely when not configured. |
| Behavior | Opens Maintenance App in new tab, deep-linking to per-train VLAN or container view. |

---

## Page States

| State | When | Appearance | Actions available |
|-------|------|------------|-------------------|
| **Loading** | Tab first opens, initial health poll in flight | Grid skeleton rows; badges show "—"; summary strip shows "Fetching…" | None — wait |
| **All healthy** | Poll received, all trains green | "All systems healthy" in summary strip; grid rows sorted alphabetically; all badges green | Tap row to open panel (all-green detail) |
| **Issues present** | One or more trains amber or red | "N trains with issues" in summary strip (amber); degraded rows sorted to top | Tap degraded rows; tap summary tile to jump to first issue |
| **Panel open** | User tapped a grid row | Right panel visible alongside grid; selected row highlighted | Tap CTA (if configured), tap close, tap different row |
| **WebSocket disconnected** | Cloud connection lost > 60s | Refresh label pulses amber: "Last update 75s ago — reconnecting…"; grid data visible but badge borders dim to indicate staleness | None — auto-reconnect in background |
| **No active trains** | Edge case — no trains registered | Grid empty state: "No trains currently active" | None |

---

## Component States Summary

| OID | States |
|---|---|
| `sh-summary-degraded` | Healthy (neutral) · Issues-amber (amber text) · Issues-red (red text) |
| `sh-summary-refresh` | Fresh (neutral, live-ticking) · Stale > 60s (amber + pulse) |
| `sh-badge-cctv-streams` | Green · Amber · Red |
| `sh-badge-cctv-devices` | Green · Amber · Red |
| `sh-badge-containers` | Green · Amber · Red |
| `sh-grid-row` | Default · Selected (surface-3) · Hover (surface-2) |
| `sh-panel-connectivity` | Connected · Degraded · No data |
| `sh-panel-footer` | Default (button) · Pending confirm · Ticket raised |
| `sh-panel-cta` | Default · Loading · Error (conditional render) |

---

## Conditional Sections

| Condition | Status |
|-----------|--------|
| Maintenance App integration | `sh-panel-cta` renders only when `maintenance_app_enabled = true` in deployment config |
| Staleness propagation | When CCTV streams degraded or `inference` container down → occupancy cards in Live Monitoring tab carry staleness indicator; not handled in this tab |
| Needs API data | → WebSocket push from cloud-backend; health poll from `event-store` health endpoint |
| Final review | → [accessibility.instructions.md](../../4-ux-design/templates/instructions/accessibility.instructions.md) |
| Always | → [open-questions.instructions.md](../../4-ux-design/templates/instructions/open-questions.instructions.md) |

---

## Technical Notes

- **Three health signals:** CCTV stream connectivity, CCTV device reachability, and Docker container health (5 containers). `worstOf(train)` derives row severity from the worst across all three.
- **Exceptions-first sort:** Grid rows sorted `red → amber → green` by worst severity. Within tier, order is stable (insertion order from WebSocket payload).
- **Real-time updates via WebSocket:** Same WebSocket channel as Live Monitoring (ADR-9). Health events update badge colours and trigger row re-sort without page refresh.
- **Inline panel — no modal:** Panel opens at 340px fixed right. Grid remains scrollable and interactive. No backdrop, no focus trap. One panel at a time — toggling another row replaces the panel.
- **Live elapsed clock:** `elapsedLabel(ts)` uses real `Date.now()` for the "now" baseline. `setInterval(1000)` drives updates. Mock `lastHealthy` timestamps are scenario-time anchored (~09:43, 10:51) — elapsed will appear large in demo vs. production.
- **Two-step ticket confirmation:** `ticketPending` state (trainId or null) shows inline confirm/cancel before firing. ESC cancels pending state before closing panel. Ticket ref is client-generated for prototype — production must use server-assigned IDs.
- **Connectivity row always rendered:** Shows "No data" when `connectivity` is absent — never omitted.
- **App healthy count:** Counts only `status === 'green'` containers. Amber containers are degraded, not healthy.
- **Maintenance App deep-link:** URL scheme TBC with Maintenance App team. Controlled by `MAINTENANCE_APP_ENABLED` flag (currently `false`).
- **No remediation actions here:** This view is read-only + ticket-raising only. No restart buttons, no SNMP detail, no config changes.
- **Health badge thresholds (resolved OQ7/OQ8):** Duration-based. `CCTV_AMBER_SEC = 120`, `CCTV_RED_SEC = 300`. Same constants apply to Applications (`APP_AMBER_SEC = 120`, `APP_RED_SEC = 300`). Degradation clock starts from the last healthy signal timestamp. Green = currently healthy or recovered within threshold. Amber = unhealthy 2–5 min. Red = unhealthy > 5 min.
- **Staleness propagation is outbound:** This tab reads health status. The Live Monitoring tab reads the staleness flag emitted by `fusion` container — the two tabs are independent consumers of the same event-store data.

---

## Open Questions

| # | Question | Context | Status |
|---|----------|---------|--------|
| 1 | What is the health poll interval for `rtsp-ingest` and `event-store` endpoints? | Determines how fresh the "Updated Xs ago" timestamp can be and when to trigger the stale state (currently: > 60s) | 🔴 Open |
| 2 | Should the panel show CCTV detail even when all streams are healthy (all-green train tapped)? | Claudia may tap a green row to verify — empty "all healthy" panel vs. no panel on green rows | 🔴 Open |
| 3 | Deep-link URL scheme for Maintenance App — format and auth handoff | `sh-panel-cta` cannot be implemented without this | 🔴 Open (Maintenance App team) |
| 4 | Amber vs red threshold for CCTV streams — is amber "some streams down" or "degraded quality"? | Determines badge colour logic in `sh-badge-vlan` | ✅ Resolved: **amber = degraded for ≥ 2 min, red = degraded for ≥ 5 min** (wall-clock duration since last healthy signal). Constants: `CCTV_AMBER_SEC = 120`, `CCTV_RED_SEC = 300`. |
| 5 | Amber vs red threshold for Applications — is amber "restarting" or "1–2 containers unhealthy"? | Determines badge colour logic in `sh-badge-containers` | ✅ Resolved: **amber = unhealthy for ≥ 2 min, red = unhealthy for ≥ 5 min** (duration-based, same constants as CCTV). Constants: `APP_AMBER_SEC = 120`, `APP_RED_SEC = 300`. |

---

## Checklist

- [x] Page purpose clear
- [x] All Object IDs assigned (12 components)
- [x] Components reference design system tokens
- [x] Content specified in English
- [x] Page states documented (6)
- [x] Component states documented (18)
- [x] Conditional section: Maintenance App CTA documented
- [x] Technical dependencies listed
- [x] Open questions captured

---

**Previous Step:** ← [cc-live-monitoring](../scenario-12-specs/01-cc-live-monitoring.md)
**Next Step:** → [cc-analytics-panel](../scenario-04-specs/01-control-centre-analytics-panel.md)

---

_Created using Whiteport Design Studio (WDS) methodology — Phase 4 UX Design_
