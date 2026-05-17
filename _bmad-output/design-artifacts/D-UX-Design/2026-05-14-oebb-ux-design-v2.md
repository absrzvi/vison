# OEBB Smart Rail — UX Design Spec v2
**Date:** 2026-05-14
**Status:** Updated — v2 adds escalations screen, expected vs actual occupancy, luggage/congestion surfacing, and three new Tier 1 use cases
**Supersedes:** `2026-05-13-oebb-ux-design.md`
**Related spec:** `2026-05-13-oebb-hailo8-ai-service-design.md`

---

## Overview

A single Hailo-8 M.2 on SYS2 of the R5001C powers the Passenger AI service. The Diagnostics AI service runs on SYS2 CPU using structured SNMP data from the Stadler system, with ML models and the LLM natural language agent running landside in the cloud. Both services are surfaced through role-specific UX across 7 interfaces plus an escalations system connecting onboard staff to landside operators.

Seven interfaces in total — 4 onboard (handheld/cab), 3 landside (web). All interfaces share an escalations channel.

### Mockup files (v1 — from 2026-05-13)
All mockups are HTML files saved in `.superpowers/brainstorm/1131-1778699015/content/`:
- `conductor-app-v1.html`
- `technician-app-v1.html`
- `bistro-app-v1.html`
- `driver-display-v1.html`
- `control-centre-v1.html`
- `maintenance-dashboard-v1.html`
- `analytics-station-v1.html`

v2 changes (this document) require mockup updates — see §Changes from v1.

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
| Control Centre Operator (Claudia) | Web dashboard | Both |
| Fleet Maintenance Manager (Roland) | Web dashboard | Diagnostics AI + occupancy |
| Capacity Planner | Web reports | Passenger AI analytics |
| Platform Staff / Station Manager | Tablet or display | Passenger AI |

---

## Interface 1: Conductor App

**Device:** Mobile handheld · **Services:** Both AI services

### Home screen sections (top to bottom)
1. **App header** — Train ID, route, current time, conductor name
2. **Active alert banner** — Highest priority alert pinned at top, pulsing animation. Tap to navigate to location. Shows alert type, coach, duration. Long-press → "Escalate this" shortcut.
3. **Coach occupancy bar** — Visual train diagram with all coaches. Green/amber/red at configurable thresholds. Tap any coach to expand detail panel showing: passenger count (actual), reservation count (expected), delta (±), luggage count, congestion score, accessibility flags, occupancy trend.
4. **Unified alert feed** — Both AI services feed one prioritised list. Passenger AI alerts (unattended luggage, accessibility, overcrowding, door obstruction, fire/smoke, vandalism, bicycle hazard) and Diagnostics AI alerts (subsystem faults) sorted by severity. Each item shows: icon, title, coach/location, sub-detail, timestamp.
5. **Diagnostics chat** — Single-turn or multi-turn natural language query to Diagnostics AI agent.

### Bottom navigation
- Home · Train · Alerts (badged) · Escalations (badged) · Chat

### Escalate flow
Three entry points:
1. Tap **Escalations** tab → blank form
2. Tap **Escalate** in active alert banner → form pre-filled from alert context
3. Long-press any alert in unified feed → "Escalate this"

**Raise escalation form (full-screen modal):**
1. **Category selector** — 2 columns, large tap targets:
   - **Operational → Claudia:** Medical emergency · Disruptive passenger · Overcrowding/boarding refusal · Accessibility assistance · Suspected security threat · Service disruption · Other operational
   - **Technical → Roland:** Door fault · HVAC/temperature · Power/lighting · Wheelchair ramp · Unusual noise/vibration · Equipment fault · Other technical
2. **AI pre-selection** — if raised from an alert, category pre-selected with "AI suggested" label. Conrad can override.
3. **Location** — coach auto-filled from alert context; editable dropdown if blank
4. **Severity** — Urgent (needs action now) · Advisory (FYI, non-blocking)
5. **Details** — optional text (200 char max) OR voice note (tap mic, record up to 60s)
6. **Photo** — optional camera attachment
7. **Routing preview** — shown before submit: "This will go to Claudia / Roland" with rationale
8. **Submit** → confirmation toast: "Escalated to Claudia · Ref #4821"

**Escalations tab view:**
- List of Conrad's raised escalations, sorted newest first
- Each item: category icon, title, routed-to badge (Claudia / Roland), status pill (New → Acknowledged → Resolved), timestamp
- Tap → detail view: full thread showing original submission, acknowledgement, resolution message
- Push notification on status change: "Claudia acknowledged · Medical team alerted at Salzburg Hbf" or "Roland resolved · Door sensor reset, safe to continue"

### Design principles
- Unified alert feed is the key differentiator — conductor doesn't need two apps
- Escalations tab gives Conrad full visibility of open issues without hunting through messages
- Coach detail panel (tap from occupancy bar) now shows the full operational picture: actual vs expected, luggage, congestion score
- Fire/smoke alerts shown at maximum severity — pulsing red banner, simultaneous alert to all parties

---

## Interface 2: Technician App

**Device:** Mobile handheld · **Service:** Diagnostics AI primary

### Home screen sections (top to bottom)
1. **App header** — Train ID, technician name, overall **Health Score (0–100)**. Colour: green >85, amber 70–85, red <70.
2. **Subsystem status grid** — 2-column grid of all Stadler subsystems polled via SNMP. Each card: subsystem name, status (Normal / Watch / Fault), active alarm count. Tap to drill into alarm history.
3. **Fault timeline** — Chronological alarm log with AI annotations. Each entry: severity dot, alarm title, coach/component, AI interpretation, alarm code + recurrence count, timestamp. Filterable by severity and time window.
4. **AI Prediction banner** — When a pattern matching a predicted failure is detected: predicted failure description, evidence rationale, fleet precedent, time window, recommended action.
5. **Diagnostics chat** — Multi-turn conversation with Diagnostics AI agent. Agent cites sources on each response.

### Escalations
Technician can raise technical escalations to Roland using the same form as Conrad. Technician also receives Roland's resolution responses.

### Bottom navigation
- Overview · Alarms (badged) · Trends · Predict · Chat

---

## Interface 3: Bistro Staff App

**Device:** Tablet or handheld · **Service:** Passenger AI

### Screen sections
1. **Header** — Train ID, next stop, current time, HIGH/MEDIUM/LOW demand pill
2. **Footfall — last 30 min** — large passenger count, % vs hour average, 10-bar sparkline
3. **Queue at counter** — person icon count + estimated wait time, trending up/down indicator
4. **Coach load strip** — all coaches with directional arrows showing flow toward bistro car
5. **Expected boarding — next stops** — per-stop passenger volume predictions fused from APC + reservation data
6. **Stock alert** — AI recommendation to restock specific items at next stop

### Design principles
- Extremely simple — bistro staff are busy, not tech-focused
- No alerts or fault data — single-purpose demand planning tool
- Large text, high contrast, glanceable at a distance

---

## Interface 4: Driver Display

**Device:** Cab-mounted display (fixed) · **Services:** Both (display only, no interaction)

### Screen sections
1. **Door status strip** — Per-door clear/obstructed status. Green = clear, red = obstructed.
2. **Critical fault indicator** — Single line showing any active critical-severity Diagnostics AI fault. Only shown above severity threshold.
3. **Platform overcrowding flag** — Advisory if platform at next stop is predicted heavily congested.
4. **Fire/smoke alert** — Full-screen red takeover if fire or smoke detected anywhere on train. Overrides all other states.

### Design principles
- Display only — zero interaction required
- Maximum 3 data points shown simultaneously in normal state
- Fire/smoke is the only case that takes over the full display
- Everything else only appears when actionable

---

## Interface 5: Control Centre Dashboard

**Device:** Web browser · 1920×1080 · **Services:** Both AI services · **Primary user: Claudia**

### Layout: 3-column grid

**KPI strip (full width, top)**
- Active trains · Avg fleet occupancy · Active incidents · Overcrowded coaches (>85%) · Fleet health score · **Congested coaches** (new) · **Luggage alerts** (new) · **Open escalations** (new)

**Left: Fleet train list**
- One card per active train: train ID, route + next stop, mini coach occupancy bar (colour-coded), status badge (Normal / Watch / Alert), top 1–2 alerts
- Trains sorted by severity — alert trains at top
- **Expected vs Actual overlay (new):** In normal state, train cards show occupancy % only. When actual headcount exceeds reservation count by configurable threshold (default +15%), the train card flags the delta in amber/red: "63 aboard / 48 reserved · +15". Overboarding trains surface toward the top of the fleet list.
- **Luggage + congestion icons (new):** Mini coach bar gains icon overlays when thresholds crossed — luggage icon on coaches with high luggage density, congestion pulse on coaches with high congestion score. No numbers at this level — icons only.
- Tap card → full train detail view

**Train detail view (drill-in)**
- **Coach grid** — one row per coach showing: passenger count (actual), reservation count (expected), delta (±), luggage count, congestion score, accessibility flags. All in one scannable table.
- Full alert list for that train
- Active escalations for that train

**Right column: Two panels stacked**
- **Escalations inbox (new)** — Incoming operational escalations from Conrad/onboard staff, sorted by severity then time. Each item: severity dot, type icon, free-text preview, train + coach, staff name, time raised, voice note indicator. Status: New (pulsing) · Acknowledged · Resolved. Tap → detail panel with full submission, photo, voice note player, reply/resolve actions. Read-only view of Roland's technical escalations shown below in muted style. AI-direct escalations (fall, fire, high-confidence door at speed) shown at top with AI badge.
- **Live incident feed** — Unified stream from both AI services across entire fleet. Each entry: severity dot, description, train + coach, AI source label, timestamp.

### Escalation resolution flow (Claudia)
1. Tap escalation → detail panel opens
2. **Acknowledge** → Conrad receives push: "Claudia acknowledged"
3. **Resolve** → resolution form: outcome text (required, 200 char) + action tags (Police alerted / Station notified / Passenger assisted / etc.) → Conrad receives push with outcome

### Design principles
- Operator sees whole fleet at a glance; drills into problem trains
- Expected vs actual surfaced only when anomalous — clean by default
- Luggage/congestion visible as icons without reading numbers
- Escalations inbox is Claudia's primary action surface alongside the incident feed
- AI-direct escalations (fire, fall, door at speed) appear at top of escalations inbox, above staff-raised items

---

## Interface 6: Maintenance Dashboard

**Device:** Web browser · **Services:** Diagnostics AI primary + Passenger AI occupancy · **Primary user: Roland**

### Layout: 3-column grid

**KPI strip (full width, top)**
- Open work orders · Active faults · Predicted failures (7-day) · Fleet health avg · AI-triggered cleaning jobs

**Left: Work orders panel**
- One card per open work order, sorted by priority (Critical → High → Medium → Scheduled)
- Each card: title, depot + timing + estimated duration, AI-generated rationale, action buttons (Assign Technician / View Fault History / Dismiss)

**Middle: Two panels stacked**
- **Fault trend chart** — 7-day bar chart of daily fault counts by subsystem
- **AI predictions** — Predicted failures with evidence rationale, fleet precedent, time window
- **Fleet health table** — All trains ranked by health score with visual bar, fault count, last depot visit

**Right: Two panels stacked**
- **Escalations inbox (new)** — Incoming technical escalations from Conrad/technicians, sorted by severity. Same structure as Claudia's inbox but filtered to Technical category. Read-only view of Claudia's operational escalations shown below in muted style for situational awareness. Resolution flow identical — Roland closes with outcome text + action tags (Depot notified / Safe to continue / Emergency procedure initiated) → push to Conrad.
- **AI-triggered cleaning schedule** — Cleaning jobs triggered by occupancy AI
- **Tonight's depot plan** — Work orders grouped by depot with estimated completion times

### Design principles
- Roland's escalations inbox surfaces technical issues from onboard staff directly — no routing via Claudia
- Both Roland and Claudia see each other's escalations in read-only for full situational awareness
- AI-generated work orders clearly labelled as AI-generated so Roland can audit and override

---

## Interface 7: Analytics & Station View

**Device:** Web (analytics) + tablet/display (station view) · **Service:** Passenger AI

### Analytics sub-view
1. **KPI strip** — monthly boardings, avg occupancy, avg dwell time, no-show rate, energy per passenger-km
2. **Daily boardings chart** — bar chart with CSV export
3. **Occupancy heatmap** — hour × day grid, 5 intensity levels
4. **Dwell time by stop** — horizontal bar chart, bottlenecks flagged in red
5. **Route occupancy comparison** — all routes ranked by occupancy with month-on-month trend
6. **Energy efficiency trend** — monthly kWh/pax-km
7. **No-show analysis** — by class and day type, AI recommendation to release unoccupied seats after 10 min
8. **Vandalism log (new)** — incidents by train, route, time of day. Pattern analysis for scheduling and security planning.
9. **Bicycle/luggage density trends (new)** — vestibule and aisle congestion patterns by route and time, useful for capacity planning and timetable design

### Station view sub-view
1. **Incoming train card** — train ID, route, ETA, platform, large coach occupancy bar with "Board here / Avoid" per coach
2. **Guidance banner** — plain language instruction for platform staff
3. **Accessibility panel** — wheelchair and pushchair users flagged with coach and door number
4. **Boarding prediction panel** — total expected boarders broken down by reservations vs walk-up vs alighting

---

## New Tier 1 Use Cases (v2 additions)

These additions extend the Tier 1 module table in `2026-05-13-oebb-hailo8-ai-service-design.md`:

| Module | Data sources | Description | Alert routing |
|---|---|---|---|
| Bicycle detection | CCTV (VLAN 5) | Bundled with luggage counting module — same YOLO pipeline, additional object class. Detects bicycles in aisles, vestibules, and doorways. Flags congestion risk and door obstruction risk. | Conrad (immediate) |
| Fire and smoke detection | CCTV (VLAN 5) | Smoke and flame detection via dedicated model running on Hailo-8. Highest priority alert class. | All simultaneously: Conrad (banner), Claudia (AI-direct escalation), Roland (AI-direct), Driver display (full-screen takeover) |
| Vandalism detection | CCTV (VLAN 5) | Detects acts of vandalism in real time (graffiti, damage to fittings, aggressive property interaction). Immediate alert to Conrad. Logged to analytics for pattern analysis. | Conrad (immediate), logged to analytics |

---

## Escalations System Summary

### Routing logic
- Conrad/technicians pick category at source: Operational → Claudia, Technical → Roland
- AI pre-suggests category when escalation is raised from an alert
- Both Claudia and Roland see each other's escalations in read-only at all times

### Alert classes that bypass staff and go AI-direct to Claudia + Roland
- Fall/slip detection (person down, not moving)
- Fire and smoke detected
- High-confidence door obstruction at speed > 0 (CCTV + TCMS combined)
- Train health score below critical threshold

### Push notification flow
1. Conrad submits escalation → routed to Claudia or Roland
2. Claudia/Roland acknowledges → Conrad receives push: "[Name] acknowledged"
3. Claudia/Roland resolves → Conrad receives push: "[Name] resolved · [outcome text]"

---

## Changes from v1

| Area | Change |
|---|---|
| Conductor App | Added escalate flow (form, tab, 3 entry points). Coach detail panel now shows expected vs actual, luggage count, congestion score. Added bicycle hazard and vandalism to alert types. Fire/smoke at maximum severity. |
| Control Centre | KPI strip: added Congested coaches, Luggage alerts, Open escalations. Train cards: expected vs actual delta overlay (alert-driven). Mini coach bar: luggage + congestion icon overlays. Train detail: full coach grid with all metrics. Right column: escalations inbox replaces/supplements fleet fault summary. |
| Maintenance Dashboard | Right column: escalations inbox added for Roland. |
| Driver Display | Added fire/smoke full-screen takeover state. |
| Tier 1 modules | Added: bicycle detection (bundled with luggage), fire/smoke detection, vandalism detection. |
| Analytics | Added vandalism log and bicycle/luggage density trend panels. |

---

## Summary: Interface status

| Interface | Status | Notes |
|---|---|---|
| Conductor App | Mockup v1 done · v2 updates needed | Add escalations tab, coach detail updates, new alert types |
| Technician App | Mockup v1 done · minor update | Add escalation entry point |
| Control Centre Dashboard | Mockup v1 done · v2 updates needed | KPI strip, coach bar icons, expected vs actual, escalations inbox |
| Maintenance Dashboard | Mockup v1 done · v2 update needed | Add escalations inbox for Roland |
| Bistro Staff App | Mockup v1 done · no changes | Unchanged |
| Driver Display | Mockup v1 done · minor update | Add fire/smoke full-screen state |
| Analytics & Station View | Mockup v1 done · minor update | Add vandalism log and bicycle/luggage trends |
