# OEBB Smart Rail — UX Design Spec
**Date:** 2026-05-13
**Status:** Complete — all 7 interface mockups done. Mockup HTML files saved in `.superpowers/brainstorm/`.
**Related spec:** `2026-05-13-oebb-hailo8-ai-service-design.md`

---

## Overview

A single Hailo-8 M.2 on SYS2 of the R5001C powers the Passenger AI service. The Diagnostics AI service runs on SYS2 CPU using structured SNMP data from the Stadler system, with ML models and the LLM natural language agent running landside in the cloud. Both services are surfaced through role-specific UX across 7 interfaces.

Seven interfaces in total — 4 onboard (handheld/cab), 3 landside (web).

### Mockup files
All mockups are HTML files saved in `.superpowers/brainstorm/1131-1778699015/content/`:
- `conductor-app-v1.html`
- `technician-app-v1.html`
- `bistro-app-v1.html`
- `driver-display-v1.html`
- `control-centre-v1.html`
- `maintenance-dashboard-v1.html`
- `analytics-station-v1.html`

---

## User Roles

### Onboard
| Role | Device | Primary AI service |
|---|---|---|
| Conductor / Train Manager | Mobile handheld | Both |
| Onboard Technician | Mobile handheld | Diagnostics AI |
| Bistro / Café Staff | Tablet or handheld | Passenger AI |
| Driver | Cab-mounted display | Both (display only) |

### Landside
| Role | Device | Primary AI service |
|---|---|---|
| Control Centre Operator | Web dashboard | Both |
| Fleet Maintenance Manager | Web dashboard | Diagnostics AI + occupancy |
| Capacity Planner | Web reports | Passenger AI analytics |
| Platform Staff / Station Manager | Tablet or display | Passenger AI |

---

## Interface 1: Conductor App ✅ Mockup complete

**Device:** Mobile handheld · **Services:** Both Hailo-8 modules

### Home screen sections (top to bottom)
1. **App header** — Train ID, route, current time, conductor name
2. **Active alert banner** — Highest priority alert pinned at top, pulsing animation. Tap to navigate to location. Shows alert type, coach, duration.
3. **Coach occupancy bar** — Visual train diagram with all coaches. Green/amber/red at configurable thresholds. Tap any coach to expand detail panel below showing: passenger count, luggage count, accessibility flags, occupancy trend.
4. **Unified alert feed** — Both AI services feed one prioritised list. Passenger AI alerts (unattended luggage, accessibility, overcrowding, door obstruction) and Diagnostics AI alerts (subsystem faults) sorted by severity. Each item shows: icon, title, coach/location, sub-detail, timestamp.
5. **Diagnostics chat** — Single-turn or multi-turn natural language query to Diagnostics AI agent. Conductor asks in plain language ("what's wrong with coach 3?"). Agent responds with fault context, history, severity, and recommended action.

### Bottom navigation
- Home · Train · Alerts (badged) · Diagnostics · Chat

### Design principles
- Unified alert feed is the key differentiator — conductor doesn't need two apps
- Diagnostics AI alerts shown at lower visual weight than passenger safety alerts unless severity is high
- Chat is quick-access for ad-hoc queries, not the primary interface

---

## Interface 2: Technician App ✅ Mockup complete

**Device:** Mobile handheld · **Service:** Diagnostics AI (Hailo-8 #2) primary

### Home screen sections (top to bottom)
1. **App header** — Train ID, technician name, overall **Health Score (0–100)** calculated from active alarm severity and frequency. Colour: green >85, amber 70–85, red <70.
2. **Subsystem status grid** — 2-column grid of all Stadler subsystems polled via SNMP. Each card: subsystem name, status (Normal / Watch / Fault), active alarm count. Colour-coded border. Tap to drill into full alarm history for that subsystem.
3. **Fault timeline** — Chronological alarm log with AI annotations. Each entry: severity dot, alarm title, coach/component, AI interpretation (not just raw alarm code), alarm code + recurrence count, timestamp. Filterable by severity and time window.
4. **AI Prediction banner** — When Hailo-8 #2 detects a pattern matching a predicted failure, this banner appears with: predicted failure description, evidence rationale, precedent from fleet history, time window, recommended action.
5. **Diagnostics chat** — Multi-turn conversation with Diagnostics AI agent. Agent cites sources (Stadler alarm log, fleet history, safety rulebook) on each response so technician can trust and verify. Example questions: "Is it safe to continue to Salzburg?", "Why does this alarm keep recurring?"

### Bottom navigation
- Overview · Alarms (badged) · Trends · Predict · Chat

### Design principles
- Health Score gives instant situational awareness without reading individual alarms
- AI annotations on alarm codes are the core value — translating 0x3A12 into "bearing wear pattern, replace at next depot visit"
- Agent always cites sources; technician is the decision-maker, AI is the advisor
- Subsystem drill-down (not shown in mockup) shows full alarm waveform history and cross-train comparison

---

## Interface 3: Bistro Staff App ✅ Mockup complete

**Device:** Tablet or handheld · **Service:** Passenger AI (Hailo-8 #1)

### Planned sections
1. **Header** — Train ID, next stop, current time
2. **Passenger load by coach** — Simplified coach bar showing which coaches are full/empty, directional flow toward bistro car
3. **Footfall trend** — Rolling 30-minute chart of passengers passing through bistro car area. Helps staff anticipate rush.
4. **Queue length at bistro** — Live count of people queuing at the bistro counter, derived from camera detection in bistro car
5. **Next stop expected boarding** — Estimated new passengers boarding at next stop (from historical data + current occupancy), so staff can prep
6. **Demand indicator** — Simple high/medium/low demand signal for the next 30 minutes

### Mockup screen sections (built)
1. **App header** — Train ID, route, HIGH/MEDIUM/LOW demand pill in top right
2. **Footfall — last 30 min** — large passenger count, % vs hour average, 10-bar sparkline showing trend direction
3. **Queue at counter** — person icon count + estimated wait time, trending up/down indicator
4. **Coach load strip** — all coaches with directional arrows showing which are sending passengers toward bistro car. Bistro car marked with star.
5. **Expected boarding — next stops** — per-stop passenger volume predictions (HIGH/MEDIUM/LOW badge) fused from APC + reservation data
6. **Stock alert** — AI recommendation to restock specific items at next stop, cross-referenced with bistro telemetry (VLAN 46) and demand pace

### Design principles
- Extremely simple — bistro staff are busy, not tech-focused
- No alerts or fault data — single-purpose demand planning tool
- Large text, high contrast, glanceable at a distance
- Stock alert is the highest-value feature — tells staff what to do, not just what's happening

---

## Interface 4: Driver Display ✅ Mockup complete

**Device:** Cab-mounted display (fixed) · **Services:** Both (display only, no interaction)

### Planned sections
1. **Door status strip** — Per-door clear/obstructed status. Green = clear, red = obstructed. Updates in real time from Passenger AI. Critical for departure safety.
2. **Critical fault indicator** — Single line showing any active critical-severity Diagnostics AI fault. Only shown when severity threshold exceeded — not every fault. Driver does not need to know about HVAC watch states.
3. **Platform overcrowding flag** — Incoming alert if platform at next stop is predicted to be heavily congested (from occupancy forecast). Allows driver to hold doors longer or notify conductor.

### Mockup states (built)
Two states shown side by side in mockup:
- **State A — Normal:** All 6 doors clear (green), no active faults, platform normal. Calm, minimal.
- **State B — Active alerts:** Door D2L blocked (pulsing red), HVAC fault shown with "continue service" guidance, platform congestion advisory at next stop.

### Design principles
- **Display only — zero interaction required.** Driver must not be distracted.
- Maximum 3 data points ever shown simultaneously
- Large, high-contrast, readable in daylight and low light
- Door status is the single most important element — always visible, always largest
- Faults only appear above a configurable severity threshold — minor warnings go to Conductor/Technician apps only
- Platform flag is advisory at lower visual weight than door status
- Everything else only appears when actionable

---

## Interface 5: Control Centre Dashboard ✅ Mockup complete

**Device:** Web browser · 1920×1080 · **Services:** Both Hailo-8 modules

### Layout: 3-column grid

**KPI strip (full width, top)**
- Active trains · Avg fleet occupancy · Active incidents · Overcrowded coaches (>85%) · Fleet health score

**Left: Fleet train list**
- One card per active train showing: train ID, route + next stop, mini coach occupancy bar (colour-coded), status badge (Normal / Watch / Alert), top 1–2 alerts for that train
- Trains sorted by severity — alert trains at top
- Tap card to open full train detail view

**Right: Two panels stacked**
- **Live incident feed** — Unified stream from both AI services across entire fleet. Each entry: severity dot, description, train + coach, AI source label, timestamp. Covers: unattended luggage, overcrowding, safety incidents, diagnostics faults, accessibility flags, predictive alerts.
- **Fleet fault summary** — Compact table of active faults by subsystem across all trains (HVAC, Brakes, Doors, Traction, Passenger Info)

### Design principles
- Operator needs to see the whole fleet at a glance and drill into problem trains
- Unified incident feed is the primary action surface — operator responds to items here
- Fleet fault summary gives maintenance a secondary view on the same screen
- Live indicator shows data freshness (last update timestamp, sync status)

---

## Interface 6: Maintenance Dashboard ✅ Mockup complete

**Device:** Web browser · **Services:** Diagnostics AI primary + Passenger AI occupancy data

### Layout: 3-column grid

**KPI strip (full width, top)**
- Open work orders · Active faults · Predicted failures (7-day) · Fleet health avg · AI-triggered cleaning jobs

**Left: Work orders panel**
- One card per open work order, sorted by priority (Critical → High → Medium → Scheduled)
- Each card: title, depot + timing + estimated duration, AI-generated rationale (fault pattern, prediction evidence), action buttons (Assign Technician / View Fault History / Dismiss)
- Work orders auto-generated by Diagnostics AI when fault patterns cross thresholds
- Cleaning work orders auto-generated by Passenger AI when occupancy data triggers intensity thresholds

**Middle: Two panels stacked**
- **Fault trend chart** — 7-day bar chart of daily fault counts by subsystem (HVAC, Brakes, etc.). Shows escalating patterns visually.
- **AI predictions** — List of predicted failures with: train/component, evidence rationale, fleet precedent citation, time window. Each links to relevant work order.
- **Fleet health table** — All trains ranked by health score with visual bar, active fault count, last depot visit date.

**Right: Two panels stacked**
- **AI-triggered cleaning schedule** — Cleaning jobs triggered by occupancy AI showing which coaches need priority vs routine clean, at which depot, and what triggered it (>90% occupancy duration, high luggage density, etc.)
- **Tonight's depot plan** — Summarised view of all work orders grouped by depot with estimated completion times

### Design principles
- Maintenance manager should be able to walk in and immediately understand what needs doing tonight
- AI-generated work orders are clearly labelled as AI-generated so manager can audit and override
- Fleet health scores give a single ranking to prioritise attention across trains
- Occupancy-driven cleaning triggers is a novel feature that saves manual scheduling effort

---

## Interface 7: Analytics & Station View ✅ Mockup complete

**Device:** Web (analytics reports) + tablet/display (station view) · **Service:** Passenger AI

### Analytics sub-view (Capacity Planner)
1. **Ridership reports** — Monthly and weekly reports: total boardings by route, peak load times by day/hour, avg occupancy by coach class, dwell time by stop. Exportable as PDF/CSV.
2. **Route heatmaps** — Visual map of occupancy intensity across the network by time of day
3. **Dwell time analysis** — Bar chart of boarding/alighting duration per stop, highlighting bottlenecks
4. **Trend comparison** — Month-on-month or route-on-route occupancy comparison
5. **Data export / API** — Raw data access for OEBB's own analytics tools (separate data subscription tier)

### Station view sub-view (Platform Staff / Station Manager)
1. **Incoming train card** — Next train to arrive: train ID, ETA, per-coach occupancy colour bar, total passenger count
2. **Accessibility flags** — Any wheelchair users, pushchair users, or mobility aid passengers flagged on incoming train with coach number — so platform staff can position correctly
3. **Overcrowding guidance** — If train is heavily loaded in specific coaches, platform display shows passengers where to wait for less crowded coaches
4. **Predictive boarding volume** — Estimated how many passengers will board at this station based on historical data + current train occupancy

### Mockup sections (built)

**Analytics tab:**
1. **KPI strip** — monthly boardings, avg occupancy, avg dwell time, no-show rate, energy per passenger-km
2. **Daily boardings chart** — bar chart with CSV export button
3. **Occupancy heatmap** — hour × day grid, 5 intensity levels, Friday 17:00 peaks immediately visible
4. **Dwell time by stop** — horizontal bar chart per stop, bottlenecks flagged in red (Linz Hbf at 3m 31s)
5. **Route occupancy comparison** — all routes ranked by occupancy with month-on-month trend
6. **Energy efficiency trend** — monthly kWh/pax-km chart, improves as occupancy rises, exportable for sustainability reports
7. **No-show analysis** — by class and day type, AI recommendation to release unoccupied 1st class seats after 10 min

**Station View tab:**
1. **Incoming train card** — train ID, route, ETA, platform, large 6-coach occupancy bar with "Board here / Avoid" guidance per coach
2. **Guidance banner** — plain language instruction for platform staff ("Guide passengers to Coaches 1, 2 and 6")
3. **Accessibility panel** — wheelchair and pushchair users flagged with coach and door number, action required
4. **Boarding prediction panel** — total expected boarders, broken down by reservations vs walk-up vs alighting, net change, post-boarding capacity warning with AI recommendation

### Design principles
- Analytics view is a data product — clean, exportable, designed for monthly review meetings
- Station view is a real-time operational tool — simple, large format, glanceable
- Station view could be rendered as a portal page on a platform display screen, not just a handheld
- Accessibility flagging gives OEBB a strong story around EU rail accessibility compliance
- No-show analysis + seat release recommendation is a novel insight not available from any existing OEBB system

---

## Summary: What's been designed vs pending

| Interface | Status | Notes |
|---|---|---|
| Conductor App | ✅ Mockup complete | Both AI services, unified alerts + diagnostics chat |
| Technician App | ✅ Mockup complete | Diagnostics AI, health score, fault timeline, AI predictions, chat |
| Control Centre Dashboard | ✅ Mockup complete | Fleet overview, unified incident feed, fault summary |
| Maintenance Dashboard | ✅ Mockup complete | Work orders, predictions, cleaning schedule, depot plan |
| Bistro Staff App | ✅ Mockup complete | Demand pill, footfall sparkline, queue count, coach load, boarding prediction, stock alert |
| Driver Display | ✅ Mockup complete | Display only, 2 states shown (normal + alerts), doors + critical faults + platform flag |
| Analytics & Station View | ✅ Mockup complete | Analytics tab (KPIs, heatmap, dwell, energy, no-show) + Station View tab (incoming train, accessibility, boarding prediction) |

---

## Next: Diagnostics AI Architecture (Hailo-8 #2)

See: `2026-05-13-oebb-diagnostics-ai-design.md` (to be written)

Key areas to design:
- SNMP ingestion pipeline from Stadler diagnosis system
- Time-series alarm pattern inference on Hailo-8 #2
- Natural language agent architecture (query → alarm log → response)
- Fleet history data model (cross-train pattern matching)
- Predictive failure model training and update cycle
- Cloud sync architecture for landside dashboards
