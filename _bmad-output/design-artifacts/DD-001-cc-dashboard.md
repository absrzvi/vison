# DD-001 — Control Centre Dashboard
## Design Delivery · Handover to Development

| Property | Value |
|----------|-------|
| **Document ID** | DD-001 |
| **Delivered by** | Sally (UX Designer) |
| **Delivered to** | Development team |
| **Date** | 2026-05-16 |
| **Status** | ✅ Approved — ready for development |
| **Prototype** | `control-centre/` (React + Vite) |
| **Spec files** | `_bmad-output/design-artifacts/D-UX-Design/` |

---

## 1. Scope

This delivery covers the **ÖBB Smart Rail Control Centre Dashboard** — a desktop web application for Control Centre operators (Claudia) and Fleet Maintenance Managers (Roland). It comprises five approved views:

| View | Spec | Page no. | Scenarios |
|------|------|----------|-----------|
| Live Monitoring | [01-cc-live-monitoring.md](D-UX-Design/scenario-12-specs/01-cc-live-monitoring.md) | 12.1 | 12, 02d, 03 |
| Train Detail Panel | [02-cc-train-detail.md](D-UX-Design/scenario-12-specs/02-cc-train-detail.md) | 12.2 | 12 |
| System Health | [01-cc-system-health.md](D-UX-Design/scenario-11-specs/01-cc-system-health.md) | 11.1 | 11, 09 |
| Analytics Panel | [01-control-centre-analytics-panel.md](D-UX-Design/scenario-04-specs/01-control-centre-analytics-panel.md) | 04.1 | 04, 03 |
| Luggage Monitoring | [01-cc-unattended-item-escalation.md](D-UX-Design/scenario-02d-specs/01-cc-unattended-item-escalation.md) | 02d.1 | 02d |

All five views were acceptance-tested against their specs on 2026-05-16 and passed. The prototype (`control-centre/`) is the primary visual reference.

---

## 2. Prototype Reference

**Location:** `control-centre/` — React + Vite SPA

**Run locally:**
```
cd control-centre
npm install
npm run dev
```

**Routes:**
| Route | View |
|-------|------|
| `/dashboard/live` | Live Monitoring (default) |
| `/dashboard/health` | System Health |
| `/dashboard/analytics` | Analytics Panel |
| `/dashboard/luggage` | Luggage Monitoring |
| `/dashboard/occupancy` | Occupancy tab (within Live) |

Train Detail opens as a right panel within `/dashboard/live` — it is not a separate route.

**Mock data:** All live data is simulated via `src/mock/MockWebSocketClient.js`. This file drives train/coach/escalation state and should be replaced by real WebSocket connections in development.

---

## 3. Component Inventory

### 3.1 App Shell
**File:** `src/components/shell/AppShell.jsx` + `AppShell.css`

| Component | OID | Notes |
|-----------|-----|-------|
| Top nav bar | `pid-app-shell-nav` | Logo, app title, critical alert hook |
| Critical alert hook | `pid-app-shell-alert-hook` | Pulsing red pill — appears when a Critical escalation is unacknowledged >60s. Navigates to `/dashboard/live`. |
| Tab bar | `pid-tab-bar` | Live · Analytics · System Health. Active tab has red underline. |

**Prototype approximation:** Alert hook triggers at 1 minute (mock). Production threshold should be configurable per operator.

---

### 3.2 Live Monitoring
**File:** `src/components/live/LiveMonitoring.jsx` (layout), `src/components/live/FleetList.jsx`, `src/components/live/UnifiedFeed.jsx`, `src/components/live/EscalationDetail.jsx`

#### KPI Strip
| OID | Label | Behaviour |
|-----|-------|-----------|
| `pid-kpi-tile-trains` | Active Trains | Display only |
| `pid-kpi-tile-escalations` | Open Escalations | Red/amber tint when > 0; tap → not wired in prototype |
| `pid-kpi-tile-incidents` | Active Incidents | As above |
| `pid-kpi-tile-capacity` | Capacity Alerts | As above |
| `pid-kpi-tile-luggage` | Luggage Alerts | As above |

**Dev note:** KPI tile taps filtering the unified feed are specced (`pid-feed-filter-bar`) but not implemented in the prototype. Wire in development.

#### Fleet List
| OID | Component | Notes |
|-----|-----------|-------|
| `pid-fleet-list` | `FleetList.jsx` | Sorted by severity (red → amber → green). Normal trains collapsed behind toggle. |
| `pid-train-card` | `TrainCard` sub-component | Severity dot, route, dwell status pill, coach occupancy bar, avg%. |
| Sort controls | `fleet-sort-toggle` | Occupancy / Severity toggle — wired. |
| Normal train collapse | `fleet-list__normal-toggle` | Green trains hidden by default; togglable. |

**Prototype approximation:** Fleet list is sorted by severity, not by passenger count descending as specced. Spec takes precedence — implement passenger count sort.

#### Unified Feed
| OID | Component | Notes |
|-----|-----------|-------|
| `pid-unified-feed` | `UnifiedFeed.jsx` | Severity-sorted stream of escalations. |
| `pid-feed-filter-bar` | Filter pills | Type (All · AI · Staff · Roland) + Status (Unacked · Acked · Resolved) + Severity (Red · Amber · Green) — combinable. Single horizontally scrollable row. |
| Unacknowledged count | `unified-feed__unacked-count` | Red badge in feed header — count of unacknowledged items. |
| Clear filters | `unified-feed__clear-filters` | Shown when any filter is active. |
| Feed item | `FeedItem` sub-component | Inline acknowledge + resolve form with outcome textarea + action tag pills. |

**Dev note:** "New items ↑" chip (`pid-feed-new-chip`) is specced but not in prototype. Implement for production — prevents auto-scroll interrupting Claudia.

#### Escalation Detail Modal
**File:** `src/components/live/EscalationDetail.jsx`

| Feature | Notes |
|---------|-------|
| Portal to `document.body` | Uses `createPortal` — renders above all other content. |
| Keyboard close | Escape key closes modal. |
| Severity accent bar | 3px top border in severity colour — visual severity signal at a glance. |
| Status pill | Shown next to source badge in header. |
| Meta bar | Train · Coach · Time · Elapsed — standardised context strip. |
| Description | Rendered in a left-border accent block for visual weight. |
| Still frame | Camera chip (top-left), timestamp chip (bottom-left), confidence chip (top-right). |
| Acknowledge | Available when status is `unacknowledged`. Sticky footer. |
| Resolve form | Available when status is `acknowledged` and type is not `roland`. Requires outcome text (200 char max) + at least one action tag. |
| Read-only pill | Shown in header when status is `resolved`. No actions available. |
| "View on Live tab" | Secondary button in sticky footer — calls `navigate('/dashboard/live')` + `onClose()`. |

---

### 3.3 Train Detail Panel
**File:** `src/components/train-detail/TrainDetail.jsx` + `TrainDetail.css`

| Section | OID | Notes |
|---------|-----|-------|
| Panel header | `td-panel-header` | Train ID, status badge, close button. Sticky. |
| Coach grid | `td-coach-grid` | One cell per coach. Occupancy bar height = occupancy %. Colour: green <75% · amber 75–89% · red ≥90%. |
| Coach cell tap | `td-coach-cell` | Tapping a coach filters the Active Alerts list to that coach. Tap same cell again to clear. `aria-label`, `role="button"`, keyboard accessible. |
| Active Alerts | `td-alerts-list` | Derived from `train.coaches.filter(c => c.hasAlert)`. Red trains also get a synthetic unattended item alert on C4. |
| Alert type labels | `ALERT_TYPE_LABEL` | unattended · overcrowded · oversized · obstruction |
| Open Escalations | `td-escalations-list` | Escalations for this train from the shared fleet context. Heading shows count when > 0: "Open Escalations (N)". Tapping an escalation row opens EscalationDetail modal. |

**Prototype approximation:** Active Alerts are derived inline from coach data — a prototype shortcut. In production, alerts should come from the event-store as a first-class data structure, not be derived from occupancy.

---

### 3.4 System Health
**File:** `src/components/health/SystemHealth.jsx` + `SystemHealth.css`

#### Summary Strip
| OID | Label | Behaviour |
|-----|-------|-----------|
| `sh-summary-tile-trains` | Trains Monitored | Display only |
| `sh-summary-tile-issues` | Issue count / "All systems healthy" | Colour reflects worst fleet severity (red/amber). Clickable — scrolls and selects first issue row. Label slot always rendered to prevent layout shift. |
| `sh-summary-tile-refresh` | Last Update | Live-ticking wall-clock elapsed (Xs ago / Xm Xs ago). Updates every second via `setInterval`. |

#### Fleet Health Grid
| OID | Component | Notes |
|-----|-----------|-------|
| `sh-grid__row` | Per-train row | 4px left border coloured by worst severity (red/amber/transparent for green). Sorted red → amber → green. |
| Severity dot | `sh-sev-dot` | 8px dot — red has glow shadow. |
| CCTV Streams badge | — | green/amber/red badge. |
| CCTV Devices badge | — | green/amber/red badge. |
| Applications badge | — | green/amber/red badge. |
| Since column | `sh-since` | Elapsed since last healthy — live wall-clock calculation via `elapsedLabel()`. Uses real `Date.now()`, not hardcoded mock time. |
| Ticket chip | `sh-ticket-chip` | Blue "Ticket raised" chip on row — visible without opening panel. No row opacity change. |

#### Inline Detail Panel
Panel opens inline (340px, right edge) when a row is clicked. Grid stays visible. No modal/backdrop.

| Section | Notes |
|---------|-------|
| Panel header | Train ID (mono) + severity dot + close button (32×32 hit target, ESC also closes). |
| Train Link row | Always rendered. Shows "● Connected / ⚠ Degraded" status + last-seen timestamp inline. Shows "No data" when `connectivity` is absent. |
| CCTV Streams row | Verbose status label (All streams reachable / Degraded · packet loss / Unreachable). |
| CCTV Devices row | Shows "X of Y not found / intermittent" when degraded. Per-coach drill-down list with reason note rendered below. |
| Applications row | Count summary ("X of Y healthy" or "Degraded · N containers"). Container drill-down list shown when `appStatus !== 'green'`. Per-container `{ name, status, note }` — unhealthy rows have red-tinted background. |
| Fault timestamp | "Last fully healthy: HH:MM today · Xm ago" — real wall-clock elapsed. |
| Panel footer — default | "Raise Maintenance Ticket" secondary button (only shown when train has issues). |
| Panel footer — pending | Two-step confirmation: label + Confirm (primary) + Cancel (ghost). ESC cancels pending state. |
| Panel footer — raised | Green ✓ icon + "Ticket raised" + monospace ref number (REF#XXXXX). |
| Toast | Fixed bottom-right — "Ticket raised — REF#XXXXX · train ID" — auto-dismisses after 4s. |

**Dev note:** WebSocket staleness state (stale > 60s → amber "reconnecting…" label) is specced but not in prototype. Implement for production.

**Dev note:** Maintenance App CTA (`sh-panel-cta`) is controlled by `MAINTENANCE_APP_ENABLED` flag (currently `false`). Enable when Maintenance App deep-link URL scheme confirmed.

---

### 3.5 Luggage Monitoring
**File:** `src/components/luggage/LuggageFeed.jsx` + `LuggageFeed.css`, `LuggageKpiStrip.jsx`

#### KPI Strip
| Tile | Colour | Notes |
|------|--------|-------|
| Longest Unattended | Red | Max elapsed across unattended-status events. "—" when none. |
| Longest Active | Amber | Max elapsed across active (non-unattended, non-resolved) events. |
| Unattended | Red count | Count of events at `unattended` status. |
| Overcrowded | — | Count of type `overcrowded`. |
| Oversized | — | Count of type `oversized`. |
| Cleared | Green | Count of `resolved` events. |

#### Luggage Feed
Events are grouped by train — one collapsible train header per train, events listed inside.

| Feature | Notes |
|---------|-------|
| Train group header | Train ID · event count · next station. Left border: red if group has unattended event, amber if active only, grey if all resolved. Collapsed/expanded via Set-based state. "Train detail ↗" button navigates to `/dashboard/live` with that train selected. |
| Filter pills | All · Unattended · Active · Resolved — each shows live event count. Combined with type filter. |
| Event card | Elapsed time on every card. Unattended cards: pulsing red border. "DOOR RISK" flag when `doorRisk: true`. Confidence chip colour-coded: green ≥85% / amber ≥70% / red <70%. |
| Resolved disclosure | Resolved events collapse to a single disclosure row per train group — not mixed into active feed. Expandable inline. |
| EscalationDetail | Opens via portal on card tap (same component as Live tab). "View on Live tab" secondary button navigates to `/dashboard/live`. |

**Phase 2 deferred:** Crew dispatch and operator ID — monitoring only for now. Acknowledgement assumes offline contact with on-train staff.

---

### 3.6 Analytics Panel
**File:** `src/components/analytics/Analytics.jsx` — tab router
Sub-views: `ExceptionWorkflow.jsx` · `OccupancyHeatmap.jsx` · `DwellTime.jsx` · `AIDetection.jsx`

#### Analytics Tab Bar + Shared Controls
Tabs: Capacity Exceptions (default) · Occupancy Heatmap · Dwell Time · AI Detection Quality

Date range selector (7d / 14d / 30d segmented button) and Export CSV button are persistent in the tab bar across all sub-tabs. Range state persists while navigating between sub-tabs; resets to 7d on tab close.

---

#### Capacity Exceptions
**File:** `src/components/analytics/ExceptionWorkflow.jsx`

| Feature | Notes |
|---------|-------|
| Summary strip | Date range label + from/to dates, services operated, exception counts (red/amber), Conrad flag count. |
| Exception list | Left column (~300px). Exceptions **grouped by route** — route group header (name + count badge) above each group's cards. Groups sort red-first. Cards keyboard-navigable (`tabIndex=0`, `role="button"`, `aria-pressed`, Enter/Space). |
| Card contents | Severity dot · train ID + departure · date (14d/30d only) · status pill (In review / Dismissed) · coaches + peak · trend badge · Conrad flag row (own line, conditional). |
| Dismissed toggle | "Show dismissed (N)" / "Hide dismissed (N)" at list bottom. Dismissed section label between active and dismissed blocks when visible. |
| Service detail | Right column. Scrolls to top on each card selection (`useRef` + `scrollTop = 0`). |
| Coach occupancy chart | **Replaces occupancy timeline.** Horizontal bar per coach showing peak occupancy. 85% threshold line on every row. Colour: ≥90% red · 85–89% amber · <85% green. ▲ flag on exceeding coaches. X-axis ticks at 0 / 50% / 85% / 100%. |
| 7-day trend chart | SVG bar chart (`viewBox="0 0 400 100"`, no `preserveAspectRatio="none"`). X-axis: relative labels −6…−1, Today. Y-axis: 0/50/85/100 gridlines. 85% dashed threshold. Bars: red ≥85% · amber <85%. |
| Conrad flag box | Blue-bordered info box — shown only when `conradFlag` is present. |
| Action strip — unreviewed | "Add to capacity review queue" (primary) + "No action required" (secondary) |
| Action strip — in_review | "Queued · Priority: {X}" + "Added at {HH:MM}" timestamp |
| Action strip — dismissed | "Marked no action required" + "Reopen" ghost button (undo dismiss) |
| Review modal | Note textarea (200 char max, optional) + priority pills (Low / Medium / High, required). Modal service line uses `exception.date ?? EXCEPTION_DATE`. `queuedAt` timestamp recorded on confirm. |
| Date range | `getExceptionsForRange(range)` returns distinct historical records per range window. Range change via `useEffect` — not render body. |

**Dev note:** "View Conrad's full flag →" link (`ca-action-flag-link`) is specced but not wired in prototype. Connect to Conrad's capacity flag record in production.

**Dev note:** The spec describes a full 90-day date picker. The prototype uses a 3-option range toggle (7d/14d/30d). Replace with full date picker in production.

---

#### Occupancy Heatmap
**File:** `src/components/analytics/OccupancyHeatmap.jsx`

| Feature | Notes |
|---------|-------|
| Grid | Routes (rows) × hours 05:00–23:00 (19 columns). 5-level colour scale. Cells show "{N}%". |
| Null cells | Hours outside date-range shift return `occupancy: null` → rendered as "—" with dim styling. Not silently clamped to edge values. |
| Hover tooltip | Fixed-position, viewport-clamped. Content: "{route} · {hour} · {N}% avg occupancy". |
| Keyboard | `tabIndex=0`, `role="gridcell"`, `aria-label`. `:focus-visible` ring in blue accent. Tooltip on `onFocus`. |
| Hover state | Scale 1.15×, white outline via `occ-heatmap__cell--hovered` class — set by `{ ri, ci }` state, not CSS `:hover`. |
| Scroll fade | Right-edge gradient only shown when content overflows (`useRef` + scroll listener → `--overflow` class toggle). |
| Legend | 5 swatches: <40% · 40–59% · 60–74% · 75–89% · ≥90%. |
| Peak hour table | CSS grid `160px 52px 1fr 44px auto` shared by axis row and all data rows. 85% threshold line extends ±2px beyond bar (`overflow: visible`, `z-index: 2`). Axis tick labels at 50% and 85% absolutely positioned within bar column. Days-over-85 note in amber when `daysOver85 > 0`. |
| Date range | `getOccupancyHeatmap(dateRange)` — per-range profile offsets (slight peak hour shift) + scale factors (7d: 1.0 · 14d: 0.97 · 30d: 0.93). |

---

#### Dwell Time
**File:** `src/components/analytics/DwellTime.jsx`

| Feature | Notes |
|---------|-------|
| Bar chart | Stations sorted descending by actual dwell. CSS grid: `160px 1fr` × 2 rows. Values row in grid-row 2 (below bar — not overlapping). |
| Scheduled tick | 12px-wide wrapper div at scheduled proportion. Hover → fixed-position tooltip "Scheduled: {Xs}". |
| Colour | Actual/scheduled ratio: ≥1.4 → critical · ≥1.15 → medium · <1.0 → normal · else → normal. |
| Under-schedule | "−{Xs} within schedule" in green when actual < scheduled. |
| Breach counts | Discrete accumulation: ×1/×2/×4 for 7d/14d/30d. Period label: "this week" / "last 14 days" / "last 30 days". |
| Empty state | "No dwell data available for this period." |
| `fmtSec` | `≥60s && rem===0` → "{M}m" (no trailing "0s"). |
| Scatter plot | 9-station colour palette. Dots coloured by station. Station legend below chart. |
| Axes | Y-axis: absolute ticks at `bottom: toPlotY(v)%`, `translateY(50%)`. X-axis: absolute ticks at `left: toPlotX(v)%`, `translateX(-50%)`. No flex space-between. |
| Correlation insight | `{correlationLabel}` derived from R²: ≥0.7 → Strong · 0.4–0.69 → Moderate · <0.4 → Weak. R² computed from linear regression at module level. |
| Date range | `getDwellData(dateRange)` — separate `actualScale` (smoothing) and `breachScale` (discrete accumulation). Array sort uses spread copy — no mutation. |

---

#### AI Detection Quality
**File:** `src/components/analytics/AIDetection.jsx`

| Feature | Notes |
|---------|-------|
| KPI strip | Events · FP rate · avg confidence · fleet uptime. FP rate null state: shows "—" + "(no data)" label when both totalEvents and totalFP are zero (distinct from 0% FP). |
| Detection chart | 7d: daily bars (Mon–Sun). 14d/30d: weekly aggregated bars (W1, W2…) from deterministic baked constants — no `Math.random()`. Memoised on `dateRange`. |
| `maxBar` | Floored at 1 — prevents divide-by-zero / NaN bar heights when all zero. |
| Empty bar columns | `detection-bar-col--empty` class: total label dimmed, stack hidden (no orphan min-height stub). |
| Chart height | `min-height: 180px` (not fixed) — labels can't clip above container. |
| FP legend note | On its own line below the type legend — not inside the flex legend row. |
| Bar hover tooltip | Fixed-position per column: day + total events + per-type breakdown rows. |
| Per-train uptime | Sorted ascending (lowest first). Data from `getInferenceUptime(dateRange)` — incidents scale ×1/×2/×4, uptime drifts −0/−0.5/−1.2pp. |
| Uptime bar range | Maps 70–100% to full bar width — 11pp differences visible. Axis labels at 70% / 85% / 100% above list. Warning threshold line at 85% position. |
| Date range | All data respects `dateRange` prop. Weekly trend and uptime memoised via `useMemo([dateRange])`. |

---

## 4. Data Contracts

### WebSocket Events (mock → production replacement)
**File:** `src/mock/MockWebSocketClient.js`

The mock emits on a 5-second tick. Production client should replace `MockWebSocketClient` with a real WebSocket connection to the cloud backend (`/ws`, per ADR-9).

**Train event shape:**
```js
{
  id: 'R5001C-031',
  severity: 'red' | 'amber' | 'green',
  route: 'Wien → Salzburg',
  avgOccupancy: 78,
  dwellStatus: { station: 'Linz', delayMin: 4, dwellingSince: 'HH:MM', scheduledDep: 'HH:MM', actualDep: 'HH:MM' | null, platformCrowding: 'high' | 'medium' | 'low' } | null,
  coaches: [
    {
      id: 'C1', occupancy: 45, hasAlert: false,
      headCount: 36, seated: 30, standing: 6,
      doorCongestion: 12, tempC: 21.4, rackUtil: 27,
      hasFall: false
    },
    // …
  ],
  // System health fields
  cctvStatus: 'green' | 'amber' | 'red',
  appStatus: 'green' | 'amber' | 'red',
  deviceStatus: 'green' | 'amber' | 'red',
  lastHealthy: 'HH:MM' | null,  // null = no fault this session
  appDetail: [
    { name: 'rtsp-ingest', status: 'green' | 'amber' | 'red', note: 'healthy' | 'exited · OOM at 09:43' | 'high latency · 420ms avg' }
    // 5 containers: rtsp-ingest, vlan-pollers, inference, fusion, event-store
  ] | null,  // null = all healthy (no drill-down needed)
  deviceDetail: {
    total: 6, unreachable: 2,
    coaches: ['C3', 'C5'],
    reason: 'No response — power or network failure suspected'
  } | null,
  connectivity: {
    status: 'ok' | 'degraded',
    transport: 'LTE' | 'WiFi',
    signalDbm: -72,
    lastSeen: 'HH:MM',
    latencyMs: 88,
    note: 'Intermittent LTE…' | null
  } | null
}
```

**Escalation event shape:**
```js
{
  id: 'esc-001',
  type: 'ai' | 'conductor' | 'roland' | 'occupancy',
  severity: 'red' | 'amber' | 'green',
  trainId: 'R5001C-031',
  coachId: 'C4' | null,
  title: 'Unattended item detected',
  detail: 'Detection confidence 94% …',
  timestamp: 'HH:MM',
  status: 'unacknowledged' | 'acknowledged' | 'resolved',
  stillFrame: {
    url: 'https://…',
    capturedAt: 'HH:MM:SS',
    camera: 'C3-door-L1',
    confidence: 96
  } | null
}
```

### Shared Context
**File:** `src/context/FleetContext.jsx`, `src/hooks/useFleetData.js`

Single `MockWebSocketClient` instance shared across all views via React context. In production, replace the client in `FleetContext` — all consumers update automatically.

---

## 5. Design Tokens

**Source:** `src/styles/` (CSS custom properties on `:root`)

| Token | Value | Usage |
|-------|-------|-------|
| `--obb-sev-critical` | `#FF3B3B` | Red severity |
| `--obb-sev-warning` | `#FF9800` | Amber severity |
| `--obb-sev-medium` | `#E8A020` | Medium/amber text |
| `--obb-sev-normal` | `#22C55E` | Green / healthy |
| `--obb-blue-accent` | `#4A9EFF` | Links, selected state, info |
| `--obb-surface-1..5` | `#0f1117` → `#2e3340` | Background elevation scale |
| `--obb-border-dark` | — | Subtle dividers |
| `--obb-border-bright` | — | Interactive borders |
| `--obb-text-on-dark-1..4` | — | Text contrast scale |
| `--font-mono` | `'JetBrains Mono', monospace` | Train IDs, timestamps, data |
| `--font-body` | `'Inter', sans-serif` | All UI text |

---

## 6. Prototype Approximations — Dev Must Know

These are intentional shortcuts in the prototype that development should replace with production implementations:

| # | View | Approximation | Production intent |
|---|------|---------------|-------------------|
| 1 | Fleet List | Sorted by severity, not passenger count descending | Sort by `total passengers aboard` from WebSocket event |
| 2 | Train Detail | Active Alerts derived from coach `hasAlert` flag inline | Alerts as first-class events from event-store |
| 3 | Analytics — Exceptions | Date picker is 3-option range toggle | Full calendar date picker, 90-day lookback |
| 4 | Analytics — Exceptions | "View Conrad's full flag →" is a placeholder | Deep-link to Conrad's capacity flag record |
| 5 | Analytics — All tabs | Range scaling uses simple multipliers on mock data | Real historical query per selected range |
| 6 | System Health | Maintenance App CTA behind `MAINTENANCE_APP_ENABLED = false` flag | Enable when deep-link URL scheme confirmed |
| 7 | All views | No loading skeletons | Implement skeleton states for all data-driven sections |
| 8 | Live Feed | No "N new items ↑" chip | Implement to prevent auto-scroll interrupting Claudia |
| 9 | KPI tiles | Taps do not filter the feed | Wire to auto-activate matching filter pill |
| 10 | System Health | Ticket refs generated client-side (Math.random) | Server-generated ticket IDs from maintenance system integration |
| 11 | System Health | `lastHealthy` timestamps are mock scenario time (~11:35); elapsed uses real wall clock | Both timestamps and elapsed will be server-sourced in production |
| 12 | Luggage Feed | Next station shown as static mock data | Derived from live schedule feed per train |
| 13 | Luggage Feed | "Longest Unattended / Longest Active" computed from mock elapsed values | Server-computed elapsed from event ingestion timestamp |
| 14 | Analytics — Exceptions | Exception list uses 3 range windows (7d/14d/30d) with distinct mock record sets | Real historical query against occupancy store per selected range |
| 15 | Analytics — Exceptions | Coach occupancy chart derives peak per coach from timeline array client-side | Server should pre-compute peak-per-coach and return as `coachPeaks` in exception record |
| 16 | Analytics — Heatmap | Range variation is a simple scale factor + hour offset on a base array | Real per-range aggregation query from occupancy timeseries |
| 17 | Analytics — Dwell | Breach counts use ×1/×2/×4 multipliers on 7d base | Cumulative breach count queried directly per range window from event-store |
| 18 | Analytics — AI | Weekly trend uses deterministic baked constants per week | Real per-week aggregation from inference event log |
| 19 | Analytics — AI | Uptime % drifts by range via fixed adjustments | Real uptime computed per range window from inference gap events |

---

## 7. Open Questions Inherited from Specs

These were open at spec time and remain unresolved. Development cannot proceed on the affected areas without answers.

| # | Question | Blocking | Owner |
|---|----------|----------|-------|
| 1 | Is `pose_estimation` feasible per coach for seated/standing split? | Coach drill-in seated/standing columns | Hailo-8 / Nomad Digital |
| 2 | ~~WebSocket staleness threshold~~ | ~~Staleness banner trigger~~ | **Resolved 2026-05-17** — 120s default, configurable per operator via `operator_preferences.staleness_threshold_sec` (options: 60/120/180/300s) |
| 3 | ~~AI escalation confidence threshold~~ | ~~Alert overload risk~~ | **Resolved 2026-05-17** — 80% minimum confidence to emit an alert (OQ3). Start conservative; tune down post-PoC if incidents are missed. Named constant `ALERT_CONFIDENCE_THRESHOLD = 0.80` in `inference/src/inference/detector.py`. |
| 4 | Maintenance App deep-link URL scheme + auth handoff | System Health CTA | Maintenance App team |
| 5 | 7-day trend query key — by train number or route+timeslot? | Analytics trend chart accuracy | Nomad Digital backend |
| 6 | ~~Fleet planning queue — internal PostgreSQL or ÖBB external system?~~ | ~~Analytics "Add to review" action~~ | **Resolved 2026-05-17** — Internal PostgreSQL `capacity_review_queue` table for PoC. Claudia can export as CSV (`GET /api/v1/capacity-review-queue/export`) to share with Passenger Experience / Fleet Management teams. External system integration is out of PoC scope. |
| 7 | CCTV stream amber vs red threshold definition | System Health badge logic | ÖBB / Nomad Digital |
| 8 | Applications amber vs red threshold (restarting vs exited) | System Health badge logic | ÖBB / Nomad Digital |
| 9 | Health poll interval for `rtsp-ingest` and `event-store` | "Updated Xs ago" freshness logic | Nomad Digital |
| 10 | Should dismissed exceptions stay visible (greyed) or be fully hidden? | Analytics exception list UX | ÖBB operations / Claudia |

---

## 8. Out of Scope for This Delivery

The following were explicitly excluded and remain in the design backlog:

- Read-only alert detail panel for non-escalated AI informational alerts (`td-alert-row` tap when no escalation linked)
- "New items ↑" chip in unified feed
- Responsive breakpoints (desktop only for PoC/MVP)
- German language localisation (post-PoC — all strings use translation keys)
- WCAG AA accessibility audit (post-PoC — open question #3 in cc-live-monitoring spec)
- Conductor App, Driver Display, Bistro App, PIS, Passenger Portal, Maintenance Dashboard (separate design deliveries)

---

## 9. Acceptance Evidence

| View | Accepted | Notes |
|------|----------|-------|
| cc-live-monitoring | ✅ 2026-05-16 | All spec gaps resolved in acceptance pass |
| cc-train-detail | ✅ 2026-05-16 | All spec gaps resolved |
| cc-system-health | ✅ 2026-05-16 | All spec gaps resolved; two Freya review rounds applied (inline panel, connectivity, ticket confirmation, amber drill-down, live elapsed, appDetail) |
| cc-analytics-panel | ✅ 2026-05-16 | All spec gaps resolved; four Freya review rounds applied across all sub-tabs. Final locked design: route grouping, coach occupancy chart, deterministic AI chart, uptime range scaling, accessible heatmap cells, absolute axis ticks, scatter station legend, R²-derived correlation label. |
| cc-luggage-monitoring | ✅ 2026-05-16 | Freya review round applied (train grouping, KPI split, confidence chips, resolved disclosure, EscalationDetail integration) |

---

## 10. Contacts

| Role | Name | Note |
|------|------|------|
| UX Design | Sally (BMad UX Designer) | This document |
| Product Owner | Abbas Rizvi | abbas.rizvi@nomadrail.com |
| Architecture | Winston (BMad Architect) | Next phase — architecture spec |

---

_Design Delivery DD-001 · ÖBB Smart Rail Control Centre Dashboard_
_Created using Whiteport Design Studio (WDS) methodology — Phase 4 [H] Handover_
_2026-05-16_
