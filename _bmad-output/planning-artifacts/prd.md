---
status: APPROVED
date: '2026-05-30'
version: '1.2'
changelog:
  - '1.2 (2026-05-30): Ratify SSE as landside push transport per ADR-20 (supersedes ADR-9 for landside). Onboard event-store WS retained for intra-CCU fan-out. §9 split into Landside push and Onboard fan-out rows. OQ-13 added (multi-worker SSE fan-out at fleet scale).'
  - '1.1 (2026-05-30): Descope FR23, FR25, FR32, FR34, FR35 to Phase 2 per readiness review 2026-05-30. NFR2 reworded to reflect ADR-15 (APC is post-hoc calibration, not real-time blending).'
  - '1.0 (2026-05-16): Initial approval.'
inputDocuments:
  - _bmad-output/design-artifacts/A-Product-Brief/product-brief.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/event-payload-schemas.md
  - _bmad-output/design-artifacts/DD-001-cc-dashboard.md
  - project-context.md
---

# Product Requirements Document
## ÖBB Smart Rail — Passenger Intelligence Service

| Property | Value |
|----------|-------|
| **Project** | ÖBB Smart Rail — Passenger Intelligence Service |
| **Client** | ÖBB (Austrian Federal Railways) |
| **Vendor** | Nomad Digital |
| **Delivery model** | AI Insights-as-a-Service (managed SaaS, per-train subscription) |
| **Pilot scope** | Single vehicle (R5001C CCU), 3-month PoC |
| **PRD version** | 1.2 |
| **Date** | 2026-05-30 |
| **Status** | Approved |

---

## 1. Vision

Nomad Digital becomes the intelligence layer of European rail — transforming a connectivity hardware install into a continuously delivered AI service that makes every ÖBB train smarter, safer, and more commercially valuable with each journey.

The product is not the Hailo-8 M.2. The product is the *insight* it enables: real-time knowledge of what is happening in every coach, surfaced to the right person, at the right moment, on the right device. Nomad Digital's unique position — owning the VLAN routing on these trains — means no competitor can replicate this without replacing the network infrastructure first.

---

## 2. Problem Statement

ÖBB train staff currently manage passenger flow, congestion, and safety incidents through direct observation — walking the train, visual checks, radio communication. This is:

- **Slow** — a conductor walking a 10-coach train takes 3–5 minutes; overcrowding incidents resolve faster than that
- **Incomplete** — no single person has simultaneous visibility across all coaches
- **Reactive** — unattended luggage, door obstructions, and accessibility needs are discovered only after they become problems
- **Unscalable** — landside operations (control centre, fleet management) have no real-time data on individual train occupancy

---

## 3. Solution Overview

A single Hailo-8 M.2 AI accelerator on SYS2 of the Nomad Digital R5001C CCU, running the **Passenger Intelligence Service** — a fully managed, privacy-by-design AI service delivering:

| Capability | What it does |
|------------|--------------|
| **Live occupancy** | Real-time passenger headcount per coach |
| **Luggage detection** | Luggage item count + unattended bag alerts (configurable timer) |
| **Congestion mapping** | Colour-coded train diagram (green/amber/red per threshold) |
| **Door safety** | Obstruction detection alerts at doors |
| **Accessibility detection** | Wheelchair/pushchair detection, PRM door correlation |
| **TCMS alarm ingestion** | Plain-language Stadler/TCMS alarm surfacing |

All inference runs onboard. Raw video never leaves the train. Only structured, anonymised results are transmitted to the cloud.

---

## 4. Target Users

| User | Role | Priority |
|------|------|----------|
| **Conrad** — Conductor / Train Manager | Operational safety on train. Needs unified, prioritised alert view on mobile handheld. | Primary |
| **Claudia** — Control Centre Operator | Fleet-wide real-time visibility. Manages capacity decisions and escalations on web dashboard. | Secondary |
| **Roland** — Fleet Maintenance Manager | Occupancy trends and system health for fleet planning. Not real-time. | Secondary |
| **Brigitte** — Bistro Staff | Coach load for catering allocation. Lightweight, low-frequency. | Supporting |
| **Driver** | Read-only highest-severity summary on cab display. No interaction. | Supporting |
| **Capacity Planner** | Web reports for long-range network planning. Lowest urgency. | Supporting |

---

## 5. Functional Requirements

### 5.1 Onboard Intelligence (Edge)

| ID | Requirement |
|----|-------------|
| FR1 | Live per-coach headcount displayed in real time to Conductor App, PIS, Control Centre Dashboard, and Driver Display |
| FR2 | Luggage item count per coach surfaced to Conductor App and Control Centre |
| FR3 | Colour-coded train diagram (coach-level congestion map) shown to conductor and passengers |
| FR4 | Alert raised to conductor when a bag has been left unattended beyond a configurable duration threshold |
| FR5 | Alert raised to conductor and driver when a passenger or bag is blocking a door |
| FR6 | Active Stadler/TCMS alarms ingested via SNMP and shown in plain language to conductor, technician, and driver (critical only for driver) |
| FR7 | High-priority correlated door alert raised when camera and door fault sensor both agree a door problem exists |
| FR8 | Conductor and passengers alerted when accessibility-dependent passenger (wheelchair/pushchair) is detected, with coach and door number |
| FR9 | Speed-correlated door fault escalation — door fault alerts at speed carry higher severity |
| FR10 | AI alerts suppressed during depot maintenance mode |
| FR11 | Alert when accessibility door is released and a wheelchair user is nearby |
| FR12 | Alert to conductor and platform staff when wheelchair ramp is deployed |

### 5.2 Control Centre — Live Operations

| ID | Requirement |
|----|-------------|
| FR20 | Control Centre dashboard — live fleet view with occupancy, active incidents, and fault alerts across all trains |
| FR21 | Unified prioritised incident feed for control centre operator, sorted by severity |
| FR22 | Real-time dwell time shown per stop to control centre operator and capacity planner |
| FR24 | Slip/fall detection alert to control centre operator |
| FR26 | Degraded operation alert to control centre operator, technician, and maintenance manager |
| FR27 | All incidents tagged with trip ID and route for post-incident review |

### 5.3 Analytics & Reporting

| ID | Requirement |
|----|-------------|
| FR33 | Anonymised ridership analytics — monthly boardings, peak loads, coach class occupancy |

### 5.4 Deferred / Out of PoC Scope

| ID | Requirement | Status | Rationale |
|----|-------------|--------|-----------|
| FR13 | AI-generated fault pattern detection | Deferred Phase 2 | Diagnostics AI scope |
| FR14 | Predictive fault alerting | Deferred Phase 2 | Diagnostics AI scope |
| FR15 | Natural language diagnostics agent | Deferred Phase 2 | Diagnostics AI scope |
| FR16 | Automated cleaning work orders | Deferred Phase 2 | Maintenance integration outside PoC |
| FR17 | Energy anomaly flagging | Deferred Phase 2 | Requires VLAN 12 energy poller (not in PoC) |
| FR18 | Bistro demand intelligence | Descoped PoC | Bistro App is Phase 2 |
| FR19 | Boarding volume prediction | Descoped PoC | Platform Staff interface is Phase 2 |
| FR23 | Predictive overcrowding warning — forecast capacity breach at upcoming stop | Deferred Phase 2 (descoped 2026-05-30) | No forecasting story in PoC epics; depends on resolution of Open Question Q5 (trend query key). Historical capacity exceptions covered by E3-S2 satisfy operator needs for PoC |
| FR25 | Prohibited zone detection alert | Deferred Phase 2 (descoped 2026-05-30) | Not implemented in E4-S4/E4-S5; zone-definition workflow (operator-drawn polygons) is itself a feature requiring UX work. Out of PoC safety-critical scope |
| FR28–FR31 | Fleet maintenance manager features | Descoped PoC | Maintenance Dashboard is Phase 2 |
| FR32 | No-show seat detection by route, day type, class | Deferred Phase 2 (descoped 2026-05-30) | Requires reservation-vs-occupancy reconciliation event type not in schema; capacity planner is a Phase 2 secondary user |
| FR34 | Occupancy-normalised energy KPIs (ESG) | Deferred Phase 2 (descoped 2026-05-30) | Requires VLAN 12 energy poller (not in E4-S1/S2); ESG reporting is a Phase 2 commercial concern, not safety/ops |
| FR35 | Advertising audience metadata | Deferred Phase 2 (descoped 2026-05-30) | Commercial monetisation; outside safety/operations PoC focus |
| FR36–FR37 | Platform displays, PIS sync | Deferred Phase 2 | Platform Staff interface + PIS apps are Phase 2 |

---

## 6. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | System uptime | ≥99.5% — Docker restart policies; graceful degradation on SYS1 loss |
| NFR2 | Occupancy accuracy | ≥95% measured post-hoc against APC ground truth — camera count is the authoritative real-time figure (ADR-15); APC is the calibration/accuracy-reporting reference, not a real-time blending input |
| NFR3 | False-positive alert rate | <5% — formal suppression state machine |
| NFR4 | Alert latency | Within station dwell window (~30–90s) — local inference, no cloud round-trip for alerts |
| NFR5 | Privacy — video | Raw video must never leave the train — edge-only inference; anonymised events to cloud only |
| NFR6 | GDPR compliance | Anonymised aggregate only to cloud; events tagged for deletion scope |
| NFR7 | Rail environment | Hardware rated -40°C to +85°C (Hailo-8 M.2 confirmed) |
| NFR8 | Connectivity resilience | All 4 onboard interfaces fully functional when SYS1 is down; Control Centre Dashboard degrades gracefully |
| NFR9 | Event metadata | All events carry trip_id, vehicle_id, ISO-8601 UTC timestamp for post-hoc metric analysis |
| NFR10 | API format | All API responses use snake_case JSON; React frontend converts to camelCase at API client layer only |
| NFR11 | API versioning | All REST routes prefixed `/api/v1/` from day one |
| NFR12 | Test coverage | ≥80% enforced via `pytest-cov --cov-fail-under=80` |
| NFR13 | CI/CD | GitLab CI/CD (`.gitlab-ci.yml`); stages: ruff, mypy --strict, bandit, detect-secrets, pytest |
| NFR14 | Logging | Structured JSON logging (timestamp, container_name, level, event_type, trip_id, message) to local file with logrotate |
| NFR15 | Secrets | API keys must never appear in source control — managed via `.env` (PoC) or Docker secrets (fleet) |

---

## 7. UX Design Requirements

These requirements are derived from the locked prototype (DD-001) and `01-control-centre-analytics-panel.md`.

| ID | Requirement |
|----|-------------|
| UX-DR1 | Control Centre Dashboard — App shell with top nav bar, critical alert hook (pulsing red pill when Critical escalation unacknowledged >60s), and tab bar (Live · Analytics · System Health) |
| UX-DR2 | Live Monitoring — KPI strip (Active Trains, Open Escalations, Active Incidents, Capacity Alerts, Luggage Alerts) with tap-to-filter behaviour wired to unified feed |
| UX-DR3 | Fleet List — sorted by severity (red → amber → green); normal trains collapsed by default; per-train card shows severity dot, route, dwell status pill, coach occupancy bars, avg% |
| UX-DR4 | Unified Feed — severity-sorted stream; filter pills (Type · Status · Severity) combinable; unacknowledged count badge; clear filters control |
| UX-DR5 | Escalation Detail — portal panel; severity accent bar; meta strip (Train · Coach · Time · Elapsed); still frame with camera/timestamp/confidence chips; Acknowledge / Resolve / "View on Live tab" actions |
| UX-DR6 | Train Detail Panel — right panel within Live Monitoring; per-coach occupancy breakdown; AI inference status per coach; recent events list; escalation list with EscalationDetail link |
| UX-DR7 | System Health view — inline 340px detail panel (not modal); per-row severity left-border; live elapsed in Since column; two-step ticket confirmation; Train Link row always rendered; container drill-down on amber/red app status |
| UX-DR8 | Analytics Panel — four sub-tabs: Capacity Exceptions · Occupancy Heatmap · Dwell Time · AI Detection Quality; all respond to shared date range selector (7d / 14d / 30d); Export CSV per sub-tab |
| UX-DR9 | Analytics / Capacity Exceptions — exception cards grouped by route; coach occupancy chart (horizontal bars per coach, 85% threshold line, ▲ flag on exceeding coaches); 7-day trend bars (relative day labels); dismissed toggle + reopen; review modal with priority (required) + note (optional) + queued-at timestamp |
| UX-DR10 | Analytics / Occupancy Heatmap — route × hour grid (05:00–23:00, 19 columns); 5-band colour scale; null cells for out-of-range hours; hover + keyboard tooltip; scroll fade indicator; peak hour table with aligned CSS grid layout, 85% threshold line, days-over-threshold note |
| UX-DR11 | Analytics / Dwell Time — per-station bar chart (values in grid-row 2, not overlapping bar); scheduled tick with wide hover zone + tooltip; under-schedule shown in green; scatter plot with absolute-positioned axes, station colour palette, 9-station legend, R²-derived correlation label |
| UX-DR12 | Analytics / AI Detection Quality — KPI strip (FP null state distinguished from 0%); stacked bar chart (deterministic weekly aggregation, `maxBar` ≥1, empty column handling, per-column hover tooltip, FP note on own line); per-train uptime mapped to 70–100% range with axis labels |
| UX-DR13 | Design token system: all colours via CSS custom properties (`--obb-sev-*`, `--obb-surface-*`, `--obb-text-on-dark-*`, `--obb-blue-accent`, `--obb-border-dark`, `--font-mono`) |
| UX-DR14 | Responsive layout: dashboard designed for 1440px+ desktop; no mobile breakpoints in PoC scope |
| UX-DR15 | Luggage Monitoring — events grouped by train (collapsible); KPI strip with "Longest Unattended" (red) + "Longest Active" (amber) split; confidence chips colour-coded; unattended cards with pulsing border; resolved events in disclosure row |

---

## 8. Scope

### 8.1 PoC Phase 1 — In Scope

| Component | Description |
|-----------|-------------|
| Edge inference pipeline | `rtsp-ingest`, `vlan-pollers`, `inference`, `fusion`, `event-store` containers on SYS2 |
| Control Centre Dashboard | Live Monitoring, Train Detail, System Health, Analytics (all 4 sub-tabs), Luggage Monitoring |
| Onboard data sources | CCTV VLAN 5, APC VLAN 8, ZFR VLAN 2, TCMS VLAN 7 |
| Cloud sync | Structured events only via SYS1; PostgreSQL on cloud; REST + WebSocket APIs |
| Shared infrastructure | Event envelope, EventType taxonomy, PostgreSQL DDL, SQLite sync cursor, WebSocket subscription spec, CI/CD |

### 8.2 Deferred to Phase 1.1

- Passenger Portal (needs design delivery)

### 8.3 Deferred to Phase 2

- Conductor App (PWA)
- PIS exterior + interior screens
- Driver Display
- Bistro App
- Maintenance Dashboard

### 8.4 Out of Scope

- Diagnostics AI (SNMP/TCMS fault ingestion via Nomie) — separate engagement
- Natural language diagnostics chat — Nomie integration
- Platform Staff interface
- Technician app

---

## 9. Architecture Constraints

| Constraint | Detail |
|------------|--------|
| Edge hardware | Single Hailo-8 M.2 (M-key 2242/2280, PCIe Gen 3 x4) on ADLINK cPCI-A3H20 blade |
| Host OS | Debian 12 + Docker (SYS2) |
| Runtime | HailoRT — supported on Debian 12 |
| Privacy | Raw video never leaves train — inference only |
| Cloud sync | Structured results only via SYS1 connectivity |
| Operating temp | Hailo-8 rated -40°C to 85°C — rail-compliant |
| Container base | `python:3.11-slim-bookworm`, FastAPI+Uvicorn, asyncio, httpx, pyproject.toml + ruff + pytest |
| Event envelope | All events: `{uuid, journey_id, vehicle_id, timestamp, event_type, severity, source, payload}` |
| journey_id scheme | `{vehicle_id}_{trip_number}_{YYYYMMDD}` — stable across midnight crossings |
| Auth | VLAN isolation onboard (PoC); API key cloud (PoC); OAuth2/OIDC upgrade path at fleet rollout |
| Landside push transport | **Server-Sent Events (SSE)** on `GET /api/v1/alerts/stream` (cloud-backend → Control Centre). Server-side filter limited to `{ALARM_ACTIVE, ALERT_RAISED, ALERT_RESOLVED}`; client filters severity/coach in `FleetContext`. No reconnect replay on the wire — reconcile via REST. See ADR-20. |
| Onboard fan-out transport | WebSocket with ADR-9 `SubscriptionRequest` (+ `reconnect_replay_depth=50`) — used by the **onboard `event-store`** for intra-CCU consumers (Conductor App, Driver Display in Phase 2). **Not** used landside. See ADR-9. |

---

## 10. Success Criteria

### Operational (ÖBB)
- Conductors reduce time spent walking the train to manually assess occupancy
- Fewer delayed departures caused by undetected door obstructions
- Accessibility incidents handled proactively, not reactively
- Control Centre gains real-time occupancy visibility across pilot fleet

### Technical (Nomad Digital)
- Inference accuracy meets agreed threshold for occupancy count (target: ≥95%)
- Alert false-positive rate below agreed threshold (target: <5%)
- System uptime ≥99.5% across pilot period
- Raw video confirmed to never leave train (privacy compliance)

### Commercial (Nomad Digital)
- ÖBB signs renewal/expansion contract at end of 3-month pilot
- Pilot creates replicable blueprint for other European rail operators
- Per-train monthly subscription model validated as commercially viable

---

## 11. Implementation Sequence

Per architecture document, the confirmed build order is:

1. `events/types.py` → event envelope → PostgreSQL DDL → SQLite sync cursor
2. `APCAdapter` Protocol + `MockAPCAdapter`
3. WebSocket subscription spec → FastAPI routes skeleton
4. **Control Centre Dashboard** (first interface — drives WS API contract, early demo surface)
5. `rtsp-ingest` → `vlan-pollers` → `inference` → `fusion`
6. GitLab CI/CD
7. Conductor App (Phase 2)

---

## 12. Open Questions

| # | Question | Blocking | Owner |
|---|----------|----------|-------|
| 1 | Is `pose_estimation` feasible per coach for seated/standing split? | Coach drill-in seated/standing columns | Hailo-8 / Nomad Digital |
| 2 | WebSocket staleness threshold — default assumed 2 minutes | Staleness banner trigger | ÖBB operations |
| 3 | AI escalation confidence threshold | Alert overload risk | ÖBB operations |
| 4 | Maintenance App deep-link URL scheme + auth handoff | System Health CTA | Maintenance App team |
| 5 | 7-day trend query key — by train number or route+timeslot? | Analytics trend chart accuracy | Nomad Digital backend |
| 6 | Fleet planning queue — internal PostgreSQL or ÖBB external system? | Analytics "Add to review" action | ÖBB operations |
| 7 | CCTV stream amber vs red threshold definition | System Health badge logic | ÖBB / Nomad Digital |
| 8 | Applications amber vs red threshold (restarting vs exited) | System Health badge logic | ÖBB / Nomad Digital |
| 9 | Health poll interval for `rtsp-ingest` and `event-store` | "Updated Xs ago" freshness logic | Nomad Digital |
| 10 | Should dismissed exceptions stay visible (greyed) or be fully hidden? | Analytics exception list UX | ÖBB / Claudia |
| 11 | Confirmed data retention period for historical occupancy data? (90 days assumed) | Analytics date picker range | Nomad Digital data governance |
| 12 | Per-operator configurable alert threshold — stored in operator config or environment variable? | Alert threshold implementation | ÖBB operations |
| 13 | SSE multi-worker fan-out — in-process `_subscribers` set OK for PoC (single worker); fleet rollout needs Redis pub/sub or PG `LISTEN/NOTIFY`. Which? | SSE fan-out at fleet scale | Nomad Digital backend (non-blocking for PoC) |

---

## 13. Prototype Reference

The Control Centre Dashboard prototype is the primary visual reference for all UX-DRs.

**Location:** `control-centre/` (React + Vite SPA)

**Run locally:**
```bash
cd control-centre
npm install
npm run dev
```

**Design delivery:** `_bmad-output/design-artifacts/DD-001-cc-dashboard.md` — approved 2026-05-16

All 19 prototype approximations listed in DD-001 §6 must be replaced with production implementations during development.

---

_PRD v1.0 — ÖBB Smart Rail Passenger Intelligence Service_
_Created 2026-05-16 — sourced from Product Brief, Architecture Document, Epics, and DD-001_
