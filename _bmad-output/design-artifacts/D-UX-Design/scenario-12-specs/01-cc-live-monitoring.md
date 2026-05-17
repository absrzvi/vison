### 12.1-cc-live-monitoring

**Previous Step:** ← [Scenario 11 — System Health](../../scenario-11-specs/)
**Next Step:** → [12.2 — Train Detail Drill-In](./02-cc-train-detail.md)

![Passenger Intelligence Dashboard — Live Monitoring](Sketches/cc-live-monitoring-wireframe.png)

**Previous Step:** ← [Scenario 11 — System Health](../../scenario-11-specs/)
**Next Step:** → [12.2 — Train Detail Drill-In](./02-cc-train-detail.md)

---

# 12.1 — Passenger Intelligence Dashboard: Live Monitoring

## Page Metadata

| Property | Value |
|----------|-------|
| **Scenario** | 12 — Claudia Monitors the Live Fleet and Resolves an Escalation |
| **Page Number** | 12.1 |
| **Platform** | Desktop web |
| **Page Type** | Full Page |
| **Viewport** | Desktop-first (1920×1080) |
| **Interaction** | Mouse + keyboard |
| **Visibility** | Authenticated — Control Centre operators (Claudia, Roland) |

---

## Overview

**Page Purpose:** Maintain situational awareness across the active fleet in real time. Surface capacity, safety, and escalation signals without requiring active scanning. Enable inline resolution of escalations without leaving the view.

**User Situation:** Claudia opens this view at the start of shift — or returns to it after navigating away. She needs to re-establish fleet awareness within 60 seconds. This is her default, ambient-monitoring surface for the entire shift.

**Success Criteria:**
- Claudia can identify which trains need attention within 60 seconds of opening the view
- Critical escalations surface to her without requiring active scanning
- She can acknowledge and resolve an escalation inline, without navigating away
- She never sees occupancy data without knowing whether the underlying inference is live

**Entry Points:**
- Direct URL `/dashboard/live` on shift start
- Tab navigation from Analytics or System Health views
- App shell critical alert hook (tap → scrolls feed to the critical item)

**Exit Points:**
- Analytics tab → `/dashboard/analytics`
- System Health tab → `/dashboard/health`
- Maintenance App deep link (from staleness banner or System Health tab)

---

## Reference Materials

**Strategic Foundation:**
- [Product Brief](_bmad-output/design-artifacts/A-Product-Brief/product-brief.md)
- [Scenario 12](_bmad-output/design-artifacts/C-UX-Scenarios/12-claudia-live-fleet-monitoring.md) — full scenario with trigger map connections
- [Architecture](_bmad-output/planning-artifacts/architecture.md) — ADR-9 (WebSocket subscription), ADR-4 (event-store sync cursor)

**Related Pages:**
- [Scenario 04 — Analytics Panel](../scenario-04-specs/01-control-centre-analytics-panel.md)
- [Scenario 11 — System Health](../scenario-11-specs/)
- [Scenario 02d — Unattended Item Escalation](../scenario-02d-specs/03-control-centre-unattended-item-escalation.md)

---

## Layout Structure

Desktop only — 1920×1080. No responsive breakpoints for PoC/MVP.

```
+─────────────────────────────────────────────────────────────────────+
│ APP SHELL NAV (64px) — logo · app name · critical alert hook        │
+─────────────────────────────────────────────────────────────────────+
│ TAB BAR (44px) — Live ● | Analytics | System Health                 │
+─────────────────────────────────────────────────────────────────────+
│ KPI STRIP (64px) — Active Trains · Escalations · Incidents · Capacity · Luggage │
+──────────────────────┬──────────────────────────────────────────────+
│ FLEET LIST (480px)   │ UNIFIED FEED (1440px)                        │
│                      │ ┌─ Filter bar ────────────────────────────┐  │
│ Train cards          │ │ All · AI · Staff · Unacknowledged · ... │  │
│ sorted by            │ └─────────────────────────────────────────┘  │
│ passenger count ↓    │                                              │
│                      │ Feed items — severity sorted                 │
│ [Coach drill-in      │ · AI Critical (red stripe, pulsing)         │
│  expands inline]     │ · Staff escalation (amber stripe)           │
│                      │ · AI Info (blue/no stripe, muted)           │
│                      │                                              │
│                      │ [Inline resolve form — expands on RESOLVE ▾] │
│                      │                                              │
│                      │ [Staleness banner — amber, when applicable]  │
+──────────────────────┴──────────────────────────────────────────────+
```

---

## Spacing

**Scale:** ÖBB Smart Rail ops token scale (8pt base grid, from `claude-design-mockups/colors_and_type.css`)

| Spacing Object ID | Between | Token | Rationale |
|---|---|---|---|
| `pid-v-space-zero` | App Shell Nav → Tab Bar | `zero` | One continuous chrome unit |
| `pid-v-space-zero` | Tab Bar → KPI Strip | `zero` | KPI strip is part of the chrome |
| `pid-v-space-zero` | KPI Strip → Fleet List / Feed | `zero` | Columns start immediately — full height |
| `pid-v-space-sm` | Train card → Train card | `sm` | Related list items — tight, readable |
| `pid-v-space-sm` | Feed item → Feed item | `sm` | Dense ops feed |
| `pid-v-space-zero` | Feed item → Inline resolve form | `zero` | Form is direct expansion of item — one unit |
| `pid-v-space-md` | Staleness banner → feed items below | `md` | Warning layer separation |

**Grid gaps:**
- Fleet list card gap: `v-space-sm` (8px)
- Feed item gap: `v-space-sm` (8px)
- Coach drill-in row gap: `v-space-xs` (4px) — dense data table

---

## Typography

**Scale:** ÖBB ops dark palette — `class="obb-dark"` on `<body>`. Font: Open Sans (Verdana fallback).

| Element | Semantic | Size token | Weight | Notes |
|---|---|---|---|---|
| App name | `h1` | `heading-sm` (18px) | semibold | Chrome label — not a page hero |
| Tab labels | `span` | `heading-xxs` (14px) | bold caps | Nav labels, uppercase |
| KPI numbers | `h2` | `heading-2xl` (36px) | bold | Glanceable from distance |
| KPI labels | `span` | `heading-xxs` (14px) | bold caps | Uppercase label below number |
| Fleet header "FLEET" | `h2` | `heading-xxs` (14px) | bold caps | Section label |
| Train ID | `h3` | `heading-xs` (16px) | semibold | Primary card identifier |
| Route + stop | `span` | `heading-xxs` (14px) | regular | Secondary card info |
| Coach drill-in headers | `span` | `heading-xxs` (14px) | bold caps | Table column labels |
| Feed header "Live Feed" | `h2` | `heading-xxs` (14px) | bold caps | Section label |
| Feed item description | `h3` | `heading-xs` (16px) | semibold | Primary event text |
| Feed item metadata | `span` | `heading-xxs` (14px) | regular | Train · coach · time |
| Resolve form heading | `h3` | `heading-xs` (16px) | semibold | Inline form label |
| Staleness banner | `span` | `heading-xxs` (14px) | regular | Warning message |

---

## Page Sections

### Section: App Shell

**OBJECT ID:** `pid-app-shell-nav`

| Property | Value |
|----------|-------|
| Purpose | Persistent dark ops chrome — ÖBB logo, app name, critical alert hook |
| Component | Navigation — custom ops bar |
| Height | 64px |
| Padding | `space-md` horizontal |
| Element gap | `space-md` |

#### App name

**OBJECT ID:** `pid-app-shell-title`

| Property | Value |
|----------|-------|
| Component | Text label |
| EN | "Passenger Intelligence Dashboard" |
| Behavior | Static — no interaction |

#### Critical alert hook

**OBJECT ID:** `pid-app-shell-alert-hook`

| Property | Value |
|----------|-------|
| Component | Badge — pulsing red |
| EN | "[N] critical" |
| Behavior | Hidden by default. Appears when a Critical feed item has been unacknowledged for >60s. Tap → scrolls unified feed to that item. Clears when item acknowledged. |
| State — default | Hidden |
| State — active | Pulsing red badge, right of app name |

#### ↕ `pid-v-space-zero` — app shell and tab bar form one continuous chrome unit

---

### Section: Tab Bar

**OBJECT ID:** `pid-tab-bar`

| Property | Value |
|----------|-------|
| Purpose | Switch views within the Passenger Intelligence Dashboard |
| Component | Navigation — tab bar |
| Height | 44px |
| Padding | `space-zero` |

#### Tab — Live (active)

**OBJECT ID:** `pid-tab-live`

| Property | Value |
|----------|-------|
| EN | "Live" |
| Active indicator | Red underline + live pulse dot |
| Badge | "[N] unacknowledged" — amber badge when unacknowledged items exist. Clears as items acknowledged. |
| Behavior | Active by default on `/dashboard/live`. No navigation (already here). |

#### Tab — Analytics

**OBJECT ID:** `pid-tab-analytics`

| Property | Value |
|----------|-------|
| EN | "Analytics" |
| Behavior | Tap → navigate to `/dashboard/analytics` |

#### Tab — System Health

**OBJECT ID:** `pid-tab-health`

| Property | Value |
|----------|-------|
| EN | "System Health" |
| Badge | "[N] alerts" — amber/red badge when trains have degraded VLAN 5 or container signals |
| Behavior | Tap → navigate to `/dashboard/health` |

#### ↕ `pid-v-space-zero` — tab bar and KPI strip form one continuous chrome unit

---

### Section: KPI Strip

**OBJECT ID:** `pid-kpi-strip`

| Property | Value |
|----------|-------|
| Purpose | 5 glanceable fleet-wide metrics — readable from across the room |
| Component | Custom — horizontal tile row |
| Height | 64px |
| Background | `--obb-surface-1` (slightly elevated from page bg) |
| Padding | `space-md` horizontal |

#### KPI tiles (5)

**OBJECT ID:** `pid-kpi-tile-{slug}` — one per metric

| Tile | Object ID | EN label | Zero state | Non-zero | Critical state |
|---|---|---|---|---|---|
| Active Trains | `pid-kpi-tile-trains` | "Active Trains" | "0" neutral | Number, neutral | — |
| Open Escalations | `pid-kpi-tile-escalations` | "Open Escalations" | "0" neutral | Number, amber tint | Number, red tint + pulse |
| Active Incidents | `pid-kpi-tile-incidents` | "Active Incidents" | "0" neutral | Number, amber tint | Number, red tint + pulse |
| Capacity Alerts | `pid-kpi-tile-capacity` | "Capacity Alerts" | "0" neutral | Number, amber tint | Number, red tint + pulse |
| Luggage Alerts | `pid-kpi-tile-luggage` | "Luggage Alerts" | "0" neutral | Number, amber tint | Number, red tint + pulse |

**Behavior — all tiles:**
- Live update via WebSocket — numbers change without page refresh
- Tap tile → applies matching filter to `pid-unified-feed` + highlights corresponding pill in `pid-feed-filter-bar`
- Tap active tile again → clears filter, returns to All
- Active filter state: tile gains border highlight

#### ↕ `pid-v-space-zero` — KPI strip and column layout start flush

---

### Section: Fleet List

**OBJECT ID:** `pid-fleet-list`

| Property | Value |
|----------|-------|
| Purpose | All active trains — sorted by total passengers aboard descending |
| Component | List — scrollable, full column height |
| Width | 480px |
| Background | `--obb-surface-2` |
| Padding | `space-sm` |

#### Fleet list header

**OBJECT ID:** `pid-fleet-list-header`

| Property | Value |
|----------|-------|
| EN | "FLEET  ([N] active)" |
| Updates | Live — active count increments/decrements as trains go active/inactive |

#### Train card

**OBJECT ID:** `pid-train-card`

| Property | Value |
|----------|-------|
| Component | Card — custom, live-updating |
| Sorting | Descending by total passengers aboard. Live reorder — smooth position transition animation (not instant jump) |
| Left severity stripe | 4px — red (Alert) · amber (Watch) · green (Normal). Updates live. |
| Tap | Expands `pid-coach-drill-in` inline below card. Other open drill-ins collapse. Tap again → collapses. |
| Hover | Background lift (`--bg-elev`) |

**Train card content:**

| Element | Content | Live? |
|---|---|---|
| Train ID | "R5001C-031" | No |
| Status badge | "Alert" · "Watch" · "Normal" | Yes |
| Route | "Vienna → Salzburg" | No |
| Next stop + ETA | "Next: Linz 11:42" | Yes |
| Coach bar | See `pid-coach-bar` | Yes |
| Top alert(s) | Top 1–2 active alerts inline | Yes |
| Staleness indicator | "⚠ Inference offline" — shown when inference down | Yes |

**States:**

| State | Appearance |
|---|---|
| Normal | Green stripe · muted text · collapsed |
| Watch | Amber stripe · standard text · collapsed |
| Alert | Red stripe · bright text · top of list |
| Expanded | Coach drill-in visible · card slightly elevated |
| Stale | Amber staleness indicator inline · occupancy numbers dimmed |
| Hover | Subtle background lift |

#### Coach bar

**OBJECT ID:** `pid-coach-bar`

| Property | Value |
|----------|-------|
| Component | Custom — live visualisation |
| Purpose | Per-coach occupancy + passenger flow within each train card |
| Layout | Horizontal segments — one per coach, equal width |

**Coach segment colours:**

| Occupancy | Colour token |
|---|---|
| Normal (<75%) | `--obb-sev-normal` (green) |
| Watch (75–84%) | `--obb-sev-medium` (amber) |
| Alert (≥85%) | `--obb-sev-high` (red) |

**Colour transitions:** Smooth CSS transition (300ms ease) — no instant jump.

**Icon overlays:**
- Luggage icon: when rack approaching saturation threshold
- Accessibility icon: when wheelchair/pushchair detected in coach

**Flow indicators:**

| Context | Behaviour |
|---|---|
| At station — doors open | Sustained directional arrows between platform entry and coaches. Animate continuously while doors open. Boarding count "+[N]" and alighting count "−[N]" overlaid on relevant coach segments. Resets on departure. |
| In transit — crossing detected | Discrete pulse fires between coach segments when inter-coach crossing detected via BYTETracker. Fades after 3s. Cumulative inter-coach movement count incremented on `pid-coach-drill-in`. |

**Inference offline state:** Segment colours dimmed · diagonal hatch pattern overlay · "APC only" label on affected segments.

**Behavior:** Passive display — no tap on coach bar itself. Tap is on `pid-train-card`.

#### Coach drill-in panel

**OBJECT ID:** `pid-coach-drill-in`

| Property | Value |
|----------|-------|
| Component | Custom — inline expansion below train card |
| Trigger | Tap `pid-train-card` |
| Collapse | Tap train card again, or tap another train card |
| Live update | All numbers update in real time while expanded |

**Columns:**

| Column | Content | Notes |
|---|---|---|
| Coach | Coach ID (C1–C10) | Static |
| Aboard | Current headcount | Live |
| Reserved | Reservation count | From ÖBB reservation feed |
| Delta | Actual − Reserved (±) | Live — red when +15% over threshold |
| Luggage | Rack density indicator | Live |
| Access | Wheelchair/pushchair flag | Live |
| Seated ⚠️ | Seated count | **TBC — pose_estimation feasibility** |
| Standing ⚠️ | Standing count | **TBC — pose_estimation feasibility** |

**At station — additional rows:**
- "Boarding this stop: +[N]" — cumulative since doors opened, resets on departure
- "Alighting this stop: −[N]" — cumulative since doors opened, resets on departure

**In transit — additional row:**
- "Inter-coach since departure: [N] in · [N] out" — cumulative since last departure

**Staleness note (when applicable):**
- "⚠ Inference offline since [HH:MM] — APC data only. Seated/standing unavailable."

#### ↕ `pid-v-space-sm` — between train cards

#### Collapsed normal trains

**OBJECT ID:** `pid-fleet-list-collapsed`

| Property | Value |
|----------|-------|
| EN | "[N] trains — all normal" |
| Behavior | Tap → expands all normal trains into the list |
| Purpose | Reduces visual noise — Claudia rarely needs to see normal trains during active monitoring |

---

### Section: Unified Feed

**OBJECT ID:** `pid-unified-feed`

| Property | Value |
|----------|-------|
| Purpose | Single severity-sorted stream — all AI escalations, staff escalations, AI info alerts fleet-wide |
| Component | List — scrollable, full column height |
| Width | 1440px |
| Background | `--obb-surface-0` (deepest — feed recedes behind items) |
| Padding | `space-sm` |

#### Feed header

**OBJECT ID:** `pid-feed-header`

| Property | Value |
|----------|-------|
| EN | "Live Feed  ·  [N] unacknowledged" |
| Updates | Live — unacknowledged count decrements as items acknowledged |

#### New items chip

**OBJECT ID:** `pid-feed-new-chip`

| Property | Value |
|----------|-------|
| EN | "[N] new items ↑" |
| Behavior | Appears at top of feed when Claudia is scrolled down and new items arrive. Tap → scrolls to top. Hidden when Claudia is at top (new items slide in naturally). |
| Purpose | Prevents auto-scroll interrupting Claudia when she's reading older items |

#### Feed filter bar

**OBJECT ID:** `pid-feed-filter-bar`

| Property | Value |
|----------|-------|
| Component | Custom — horizontal pill row |
| Layout | Single row, left-aligned, scrollable if overflow |
| Default | All pills inactive (showing All) |
| Persistence | Filter state persists within session |

**Filter pills:**

| Pill | Object ID | EN | Type |
|---|---|---|---|
| All | `pid-filter-all` | "All" | Resets all filters |
| AI | `pid-filter-ai` | "AI" | Type filter |
| Staff | `pid-filter-staff` | "Staff" | Type filter |
| Unacknowledged | `pid-filter-unack` | "Unacknowledged" | Status filter |
| Acknowledged | `pid-filter-ack` | "Acknowledged" | Status filter |
| Critical | `pid-filter-critical` | "Critical" | Severity filter |
| Warning | `pid-filter-warning` | "Warning" | Severity filter |
| Info | `pid-filter-info` | "Info" | Severity filter |
| [Train ID] | `pid-filter-train-{id}` | "[Train ID]" | Train filter — single select |

**Behavior:**
- Tap pill → activates, pill highlighted, feed filters instantly
- Tap active pill → deactivates, returns to All
- Type + Status + Severity combinable. Train filter single-select.
- KPI tile tap → auto-activates matching pill

#### ↕ `pid-v-space-sm` — filter bar to first feed item

#### Feed item — AI escalation

**OBJECT ID:** `pid-feed-item-ai`

| Property | Value |
|----------|-------|
| Component | Card — custom, AI escalation |
| Left stripe | 4px — red (Critical) · amber (Warning) |
| Sort position | Top of feed — above staff escalations and info items |

**Content:**

| Element | Content |
|---|---|
| Source badge | "AI" — `--obb-blue` pill |
| Severity pill | "Critical" · "Warning" |
| Train + coach | Right-aligned — "R5001C-031 · Coach C4" |
| Timestamp | Right-aligned — "11:23" |
| Event description | Plain language — "Unattended item detected — 94% confidence · 8 min unattended" |
| Still frame | Single JPEG thumbnail from detection moment. Tap → expands full width inline. Tap again → collapses. |
| Conrad status | "Conrad notified [HH:MM] · Response: '[text]'" — shown if Conrad has responded |

**Actions:**

| Action | Object ID | EN | Behavior |
|---|---|---|---|
| Acknowledge | `pid-feed-item-ai-ack` | "Acknowledge" | POST acknowledgement to cloud backend → status → Acknowledged · Conrad push: "Claudia acknowledged" · button → "Acknowledged ✓" (disabled) |
| Resolve | `pid-feed-item-ai-resolve` | "Resolve" | Expands `pid-feed-resolve-form` inline below item · other open forms collapse |

**States:**

| State | Appearance |
|---|---|
| New | Stripe pulses 5s on arrival · "New" pill · full brightness |
| Acknowledged | Stripe steady · "Acknowledged ✓" pill · slightly dimmed |
| Resolve expanded | Form visible below · acknowledge button locked |
| Resolved | Grey stripe · grey text · "Resolved" pill · sorted toward bottom of feed |
| Hover | Background lift |

#### Feed item — Staff escalation

**OBJECT ID:** `pid-feed-item-staff`

| Property | Value |
|----------|-------|
| Component | Card — custom, staff escalation |
| Left stripe | 4px — amber · red depending on severity |
| Sort position | Below AI escalations, above AI info items |

**Content:**

| Element | Content |
|---|---|
| Source badge | Staff name — "[Conrad]" avatar + name pill |
| Severity pill | "Critical" · "Warning" |
| Train + coach | Right-aligned |
| Timestamp | Right-aligned |
| Escalation type | Category label — "Capacity flag" · "Safety concern" · "Accessibility" etc. |
| Free-text preview | First line of Conrad's note |
| 7-day trend indicator | Shown on capacity flags — "↑ 3 consecutive weeks" |
| Status pill | "New" (pulsing) · "Acknowledged" · "Resolved" |

**Actions:**

| Action | Object ID | EN | Behavior |
|---|---|---|---|
| Acknowledge | `pid-feed-item-staff-ack` | "Acknowledge" | POST → Acknowledged · Conrad push |
| View Details | `pid-feed-item-staff-detail` | "View Details" | Expands inline: full free text, photo (if attached), voice note player (if recorded), 7-day trend chart (if capacity flag) |
| Resolve | `pid-feed-item-staff-resolve` | "Resolve" | Expands `pid-feed-resolve-form` |

**States:** Same as `pid-feed-item-ai`.

#### Feed item — AI informational

**OBJECT ID:** `pid-feed-item-info`

| Property | Value |
|----------|-------|
| Component | Card — muted, read-only |
| Left stripe | 4px `--obb-blue` (info) · or none |
| Sort position | Below all escalations |
| Text colour | Muted — `--fg-3` |

**Content:** Event description + data source label + train/coach/time. No actions.

**Behavior:** Tap → expands full description inline. Tap again → collapses.

**States:** Default (muted) · Expanded · Hover (subtle lift).

#### Inline resolve form

**OBJECT ID:** `pid-feed-resolve-form`

| Property | Value |
|----------|-------|
| Component | Custom — inline expansion |
| Trigger | Tap "Resolve" on any escalation item |
| Position | Directly below the triggering feed item — zero spacing |
| Collapse | Tap Cancel · or tap Resolve on a different item (collapses this one) |

**Fields:**

| Field | Object ID | EN label | EN placeholder | Rules |
|---|---|---|---|---|
| Outcome text | `pid-resolve-outcome` | "Outcome" | "Describe what happened and what action was taken…" | Required · 1–200 chars · char count shown live "143 / 200" |
| Action tags | `pid-resolve-tags` | — | — | Multi-select pills · min 1 required |

**Action tag pills (EN):** "Passenger assisted" · "Police alerted" · "Station notified" · "Conrad instructed" · "No action required" · "Other"

**Buttons:**

| Button | Object ID | EN | Behavior |
|---|---|---|---|
| Cancel | `pid-resolve-cancel` | "Cancel" | Collapses form · item returns to Acknowledged state |
| Submit | `pid-resolve-submit` | "Submit Resolution" | Disabled until outcome + tag valid. On submit: spinner · POST resolution → feed item → Resolved · Conrad push with outcome text · success toast "Resolved — Conrad notified" |

**Validation:**

| Field | Rule | Error message | Error code |
|---|---|---|---|
| Outcome | Required, 1–200 chars | "Please describe the outcome before submitting." | `ERR_RESOLVE_OUTCOME_EMPTY` |
| Outcome | Max 200 chars | "Outcome must be 200 characters or less." | `ERR_RESOLVE_OUTCOME_TOO_LONG` |
| Action tags | Min 1 selected | "Please select at least one action tag." | `ERR_RESOLVE_TAG_REQUIRED` |

**Validation timing:** On submit attempt only. Errors shown inline below field.

**States:**

| State | Appearance |
|---|---|
| Default | Outcome empty · tags unselected · Submit disabled (greyed) |
| Filling | Text entered · Submit disabled until tag also selected |
| Ready | Outcome + tag valid · Submit enabled (red) |
| Submitting | Submit shows spinner · form locked |
| Success | Form collapses · feed item → Resolved · toast appears |

#### ↕ `pid-v-space-sm` — between feed items

---

### Section: Staleness Banner

**OBJECT ID:** `pid-staleness-banner`

| Property | Value |
|----------|-------|
| Component | Alert — contextual amber banner |
| Position | Pinned within the feed column — appears above feed items, below filter bar |
| Trigger | When inference is offline for one or more active trains |
| Stacking | One banner per affected train — stacked if multiple |
| Dismissible | No — persists until inference comes back online |
| Background | `--obb-sev-medium` tint (amber wash) |

**Content:**

| Element | EN |
|---|---|
| Icon | ⚠ warning icon |
| Message | "[Train ID] — Inference offline since [HH:MM]. Occupancy from APC only. Camera alerts suspended." |
| Link | "View in System Health →" — navigates to `/dashboard/health` |

#### ↕ `pid-v-space-md` — staleness banner to feed items below

---

## Page States

| State | When | Appearance | Actions available |
|---|---|---|---|
| **Default — live** | Normal operation, trains active, WebSocket connected | Full 2-column layout. KPI strip populated. Fleet list + feed live. | All interactions |
| **Quiet** | No escalations, no alerts, all trains normal | KPI strip zeros/green. Feed shows info items only. Fleet list all green. No banners. | Monitoring only |
| **Active incident** | Critical escalation unacknowledged | App shell alert hook pulsing. Feed item at top pulsing. KPI incremented. | Acknowledge / resolve inline |
| **Loading** | Initial page load or reconnect | Skeleton loaders in fleet list + feed. KPI strip shows dashes. Tab bar visible. | None — waiting |
| **No active trains** | Outside operating hours | Fleet list: "No active trains." Feed: empty. KPI all zeros. | Analytics and System Health tabs accessible |
| **Filtered** | Feed filter active | Feed shows filtered subset. Active filter pills highlighted. Feed header: "Showing [N] of [M] items." | Clear filters · adjust filters |

---

## Conditional Sections

| Condition | Status |
|---|---|
| Has forms/inputs | ✅ — `pid-feed-resolve-form` validation defined above |
| Needs API data | ✅ — WebSocket (ADR-9) for live events · REST GET for historical data |
| Authenticated page | ✅ — API key auth (PoC); OIDC upgrade path documented in architecture |
| Accessibility | See open questions |
| Multiple breakpoints | ❌ — desktop only for PoC/MVP. German language: post-PoC. |

---

## Technical Notes

- **WebSocket:** Cloud backend pushes events to dashboard via WebSocket `/ws` (ADR-9). Client reconnects with exponential backoff. On reconnect: 50-event replay to prevent missed events.
- **Live reorder:** Fleet list reorders by passenger count on every WebSocket event. Reorder uses CSS transition (300ms) to prevent disorienting jumps.
- **Staleness detection:** `fusion` container tags events with `last_inference_ts`. Dashboard shows staleness when `now − last_inference_ts > threshold` (configurable — default 2 minutes).
- **Still frames:** Single JPEG stored in event-store at detection time. Delivered as URL in escalation payload. Not live video.
- **Seated/standing (⚠️ TBC):** Depends on `pose_estimation` feasibility from hailo-apps. If not feasible for PoC, columns hidden from coach drill-in. APC headcount still shown.
- **Conrad push notifications:** Acknowledgement and resolution outcomes delivered via Conductor App WebSocket push. Out of scope for this spec — defined in Conductor App specs.
- **Languages:** English only (PoC/MVP). German planned post-PoC — all strings use translation keys for future i18n.

---

## Open Questions

| # | Question | Context | Status |
|---|----------|---------|--------|
| 1 | Is seated/standing split feasible from `pose_estimation` in hailo-apps for PoC? | Coach drill-in columns depend on this | 🔴 Open — flag to Nomad Digital / Hailo team |
| 2 | What is the staleness threshold? (Default assumed: 2 minutes) | Affects when staleness banner appears and occupancy dims | 🔴 Open — agree with ÖBB operations |
| 3 | What is the configurable AI escalation confidence threshold? | Prevents alert overload — must be agreed before go-live | 🔴 Open — agree with ÖBB |
| 4 | Accessibility requirements for ops dashboard? (WCAG AA target?) | Screen reader support for live-updating regions | 🔴 Open |
| 5 | Does the train filter pill in the feed auto-populate from the fleet list? | UX consistency — tapping a train card could auto-filter the feed | 🟡 In Discussion |
| 6 | What is the live reorder animation duration? (Default assumed: 300ms) | Needs to be long enough to track, short enough to feel live | 🟡 In Discussion |

---

## Checklist

- [x] Page purpose clear
- [x] All Object IDs assigned
- [x] Components reference design system (obb-dark palette, colors_and_type.css)
- [x] Content in English (PoC/MVP) — translation keys defined for German (post-PoC)
- [x] States documented (6 page states · 28 component states)
- [x] Validation rules defined (2 fields · 3 error messages)
- [x] Spacing objects defined (7)
- [x] Typography tokens defined (13)
- [x] Technical dependencies flagged (seated/standing TBC)
- [x] Open questions documented (6)

---

**Previous Step:** ← [Scenario 11 — System Health](../../scenario-11-specs/)
**Next Step:** → [12.2 — Train Detail Drill-In](./02-cc-train-detail.md)

---

_Created using Whiteport Design Studio (WDS) — Phase 4: UX Design_
_Scenario 12 · Page 12.1 · 2026-05-16_
