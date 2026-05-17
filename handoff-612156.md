# Session Handoff — OEBB Smart Rail Passenger Intelligence

**Date:** 2026-05-14 (updated end of session 4)
**Project dir:** `C:\Users\AbbasRizvi\Documents\oebb-agent`
**Next session focus:** Build light theme of AI dashboard, then Stadler Diagnostic Web UI (two separate products)

---

## What Was Done This Session (Session 4)

### Course correction — two separate products
The previous Control Centre Dashboard was pulling toward network/SNMP diagnostics instead of the AI value proposition. This session split the work into two distinct products:

1. **Passenger Intelligence AI Dashboard** — what Hailo-8 sees (occupancy, congestion, accessibility, device health). This is the hero product.
2. **Stadler Diagnostic Web UI** — Nomad-built web interface for Stadler's diagnostic system (on-train tablet + landside browser). This is where the L1 cable / SNMP / Roland network fault workflow lives. Not yet built.

### Control Centre Dashboard — rebuilt (dark theme complete)
File: `mockups/control-centre-dashboard-dark.html`

**4 screens:**
1. **Fleet overview** — fleet grid of 31 trains, Hailo-8 occupancy per coach colour-coded (green/amber/red), worst-first sorting, KPI row (fleet avg, over capacity, approaching cap, congestion alerts)
2. **Per-train drill-down** — coach detail strip with bar charts per coach, congestion zone breakdown (vestibule / luggage rack), Hailo-8 insights panel with interpretations + actions (e.g. "→ Suggest action to Conrad on train")
3. **Analytics / morning review** — Claudia's exception report, Conrad escalation card with 7-day trend attached, fleet occupancy bar chart (peak vs. off-peak, fixed baseline alignment)
4. **Hailo-8 Health — fleet overview (4A)** — device status grid per train (healthy/degraded/offline), Claudia data trust banner ("coach C3 occupancy unreliable — camera feed lost"), KPI row
5. **Hailo-8 Health — device drill-down (4B)** — per-camera feed status (6 cameras per train, live/lost/standby), fault detail card with likely cause and plain-language explanation, action buttons (log for depot, remote camera restart, notify maintenance), 7-day uptime sparkline

### Key design decisions this session
- "AI" replaced throughout with "Hailo-8" — Roland knows it as the product name
- "AI occupancy by coach" → **"Live occupancy by coach"** (technology-neutral label)
- "AI Health" nav item → **"Hailo-8 Health"**
- Hailo-8 Health has **two layers**: Claudia sees a trust indicator (is the data reliable?); Roland sees full technical depth (which camera, what fault, what action)
- Two distinct failure modes modelled: **device offline** (no heartbeat) vs. **camera feed lost** (device running but blind) — these look the same from the occupancy data but require different responses
- Operations/maintenance features explicit: model version tracking (fleet-wide), per-camera live status, inference latency + confidence per device, fault logging to depot queue, remote camera restart — none of these come from Hailo-8 out of the box, this is Nomad's platform layer

---

## Current Artifact State

### Phase 3 — UX Scenarios (12 scenarios, COMPLETE)

| # | Scenario | Persona | Status |
|---|---|---|---|
| 00 | Scenarios index | — | ✅ |
| 01 | Conrad boarding overview | Conrad | ✅ |
| 02 | Conrad vestibule congestion | Conrad | ✅ |
| 02b | Conrad occupancy imbalance | Conrad | ✅ |
| 02c | Conrad luggage rack saturation | Conrad | ✅ |
| 02d | Conrad unattended bag | Conrad | ✅ |
| 03 | Conrad escalates to Roland/Claudia | Conrad → Roland | ✅ |
| 04 | Claudia morning fleet review | Claudia | ✅ |
| 05 | Passenger guided to free seat | Passenger | ✅ |
| 06 | Passenger accessibility boarding | Passenger | ✅ |
| 07 | Brigitte pre-departure prep | Brigitte | ✅ |
| 08 | Brigitte trolley routing | Brigitte | ✅ |
| 09 | Roland spots failing L1 cable — Stadler notification | Roland | ✅ (needs re-scoping — belongs in Stadler Diagnostic UI product, not AI dashboard) |

### Phase 4 — Mockups

| Interface | Dark | Light | Status |
|---|---|---|---|
| Conductor App | `conductor-app-v1.html` | `conductor-app-light.html` | ✅ Complete |
| **AI Dashboard (Control Centre)** | `control-centre-dashboard-dark.html` | — | ✅ Dark done · ❌ Light needed |
| **Stadler Diagnostic Web UI** | — | — | ❌ Not started · next priority after light theme |
| Bistro App | — | — | ❌ Pending |
| Analytics & Station View | — | — | ❌ Pending (partially covered in dashboard screen 3) |
| Maintenance Dashboard | — | — | ❌ Pending |
| Technician App | — | — | ❌ Pending |

---

## Recommended Next Session Steps

1. Activate Freya: read `.claude/skills/freya.activation.md` and follow activation sequence
2. Build **light theme** of `control-centre-dashboard-dark.html` → `control-centre-dashboard-light.html`
   - Same 5 screens, light design system (ÖBB red header, white surfaces, `#ECEEF2` body)
   - Logo as-is (no invert filter)
3. Build **Stadler Diagnostic Web UI** — two versions:
   - **Landside browser** (`stadler-diagnostic-landside.html`) — Roland's fleet-wide view:
     - L1/L2 inter-coach link map per train (the spatial coach chain from the old dashboard)
     - All onboard systems: TCMS, PIS, WiFi, CCTV — status per system per train
     - SNMP data in plain language (not raw OIDs)
     - One-tap Stadler fault notification (Scenario 09 flow)
     - Fault log with Stadler ticket references
   - **On-train tablet** (`stadler-diagnostic-ontrain.html`) — technician walks the train:
     - Per-coach system status live
     - Tap a coach to see its switch/VLAN detail
     - Log a physical fault observation
4. Build **Bistro App** — Brigitte · Scenarios 07 + 08

---

## Design System (use for all remaining mockups)

### Dark theme
- `--surface-0: #0E1117` through `--surface-5: #2A3242`
- Body bg: `radial-gradient(ellipse at 30% 0%, #0D1628 0%, #0E1117 55%)`
- Text primary: `#D8DCE8` · secondary: `#7A8499` · muted: `#485060`
- Top bar: ÖBB Blue `#073D6E`
- Logo: `../current-portal-design/Logos & Symbole/Logos railnet/OeBB_railnet.png` with `filter: brightness(0) invert(1)`

### Light theme
- `--surface-0: #F4F5F8` · `--surface-1: #FFFFFF` · body bg: `#ECEEF2`
- Text primary: `#14202E` · secondary: `#4A5568` · muted: `#8A94A8`
- Top bar: ÖBB Red `#E2002A`
- Logo: PNG as-is (no filter)
- Amber/green/red darkened for contrast on white: green `#007A55` · amber `#B57300` · red `#C8001F`

### Shared
- ÖBB Red: `#E2002A` · ÖBB Blue: `#073D6E`
- Border radius: cards `10px` · buttons `8px` · dashboard frame `16px`
- Font: `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif`
- Status colours: green `#00A876` · amber `#E09900` · red `#E2002A` (dark theme)

---

## Two-Product Architecture (established this session)

### Product 1 — Passenger Intelligence AI Dashboard
**What it is:** What the Hailo-8 cameras see across the fleet.
**Users:** Claudia (occupancy, trust), Roland (Hailo-8 health, device ops)
**Key screens:** Live fleet occupancy · per-train drill-down · analytics / trends · Hailo-8 Health (device status, camera feeds, model version, uptime)
**File:** `mockups/control-centre-dashboard-dark.html` (dark) · `control-centre-dashboard-light.html` (light, TBD)

### Product 2 — Stadler Diagnostic Web UI
**What it is:** Nomad-built web interface for Stadler's onboard diagnostic system — replaces Roland's SSH + scripts + manual email workflow.
**Users:** Roland (landside) · Maintenance technician (on-train tablet)
**Key screens:** Fleet network health · per-train L1/L2 link map · all onboard systems (TCMS, PIS, WiFi, CCTV) · SNMP in plain language · one-tap Stadler fault notification · fault log
**Scenario:** Scenario 09 (L1 cable failure → Stadler notification) belongs here, not in Product 1
**Files:** `mockups/stadler-diagnostic-landside.html` · `mockups/stadler-diagnostic-ontrain.html` (both TBD)

---

## Technical Flags

| Flag | Context |
|---|---|
| PIS exterior screen L2 write access | Scenarios 01, 05 |
| PIS interior screen L2 write access | Scenarios 02b, 02c |
| Hailo-8 camera feed — RTSP connection per coach | Session 4 — camera C3 fault modelled as cable/connector |
| Hailo-8 model version management | Session 4 — fleet-wide model version tracking needed, not out of box |
| Remote camera restart capability | Session 4 — action modelled in UI, needs platform implementation scoping |
| Coral vs Hailo-8 deployment decision | Both tested on R5001C — production decision pending |
| SNMP OID list from Stadler | Required for Stadler Diagnostic UI — confirm with Stadler |
| Stadler notification API endpoint | Required for one-tap fault report — confirm integration format |
| Historical SNMP link quality retention | Required for 7-day trend in Stadler UI |
| Camera still-frame privacy scoping | Scenario 02d — ÖBB + Nomad access control decision needed |

---

## WDS Agent State

- **Freya** active (Phases 3–4). Activation: `.claude/skills/freya.activation.md`
- **Saga** complete (Phases 1–2). Activation: `.claude/skills/saga.activation.md`
- WDS config: `_bmad/wds/config.yaml` — output: `_bmad-output/design-artifacts`
