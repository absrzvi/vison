---
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
date: '2026-05-17'
project: ÖBB Smart Rail — Passenger Intelligence Service
---

# Implementation Readiness Report
## ÖBB Smart Rail — Passenger Intelligence Service

**Date:** 2026-05-17
**Prepared by:** Implementation Readiness Check workflow

---

## Document Inventory

| Document | Status | Path |
|---|---|---|
| PRD | ✅ Found | `_bmad-output/planning-artifacts/prd.md` |
| Architecture | ✅ Found | `_bmad-output/planning-artifacts/architecture.md` |
| Epics & Stories | ✅ Found | `_bmad-output/planning-artifacts/epics.md` |
| UX Design Spec (Analytics) | ✅ Found | `_bmad-output/design-artifacts/D-UX-Design/scenario-04-specs/01-control-centre-analytics-panel.md` |
| Design Document DD-001 | ✅ Found | `_bmad-output/design-artifacts/DD-001-cc-dashboard.md` |
| Design Log | ✅ Found | `_bmad-output/_progress/00-design-log.md` |

---

## PRD Analysis

### Functional Requirements

**In-Scope PoC FRs:**

FR1: Live per-coach headcount displayed in real time to Conductor App, PIS, Control Centre Dashboard, and Driver Display

FR2: Luggage item count per coach surfaced to Conductor App and Control Centre

FR3: Colour-coded train diagram (coach-level congestion map) shown to conductor and passengers

FR4: Alert raised to conductor when a bag has been left unattended beyond a configurable duration threshold

FR5: Alert raised to conductor and driver when a passenger or bag is blocking a door

FR6: Active Stadler/TCMS alarms ingested via SNMP and shown in plain language to conductor, technician, and driver (critical only for driver)

FR7: High-priority correlated door alert raised when camera and door fault sensor both agree a door problem exists

FR8: Conductor and passengers alerted when accessibility-dependent passenger (wheelchair/pushchair) is detected, with coach and door number

FR9: Speed-correlated door fault escalation — door fault alerts at speed carry higher severity

FR10: AI alerts suppressed during depot maintenance mode

FR11: Alert when accessibility door is released and a wheelchair user is nearby

FR12: Alert to conductor and platform staff when wheelchair ramp is deployed

FR20: Control Centre dashboard — live fleet view with occupancy, active incidents, and fault alerts across all trains

FR21: Unified prioritised incident feed for control centre operator, sorted by severity

FR22: Real-time dwell time shown per stop to control centre operator and capacity planner

FR23: Predictive overcrowding warning — forecast capacity breach at an upcoming stop

FR24: Slip/fall detection alert to control centre operator

FR25: Prohibited zone detection alert to control centre operator

FR26: Degraded operation alert to control centre operator, technician, and maintenance manager

FR27: All incidents tagged with trip ID and route for post-incident review

FR32: No-show seat detection data by route, day type, and class for capacity planner

FR33: Anonymised ridership analytics — monthly boardings, peak loads, coach class occupancy

FR34: Occupancy-normalised energy KPIs per journey for ESG reporting

FR35: Advertising audience metadata — aggregate audience profiles per route

**Total in-scope FRs: 27** (FR1–FR12, FR20–FR27, FR32–FR35)

**Deferred/Out-of-Scope FRs (not subject to coverage check):**

FR13–FR19, FR28–FR31, FR36–FR37 — deferred Phase 2 or descoped PoC.

---

### Non-Functional Requirements

NFR1: System uptime ≥99.5% — Docker restart policies; graceful degradation on SYS1 loss

NFR2: Occupancy accuracy ≥95% — APC fusion for ground-truth calibration

NFR3: False-positive alert rate <5% — formal suppression state machine

NFR4: Alert latency within station dwell window (~30–90s) — local inference, no cloud round-trip for alerts

NFR5: Privacy — raw video must never leave the train — edge-only inference; anonymised events to cloud only

NFR6: GDPR compliance — anonymised aggregate only to cloud; events tagged for deletion scope

NFR7: Rail environment — hardware rated -40°C to +85°C (Hailo-8 M.2 confirmed)

NFR8: Connectivity resilience — all 4 onboard interfaces fully functional when SYS1 is down; Control Centre Dashboard degrades gracefully

NFR9: Event metadata — all events carry trip_id, vehicle_id, ISO-8601 UTC timestamp for post-hoc metric analysis

NFR10: API format — all API responses use snake_case JSON; React frontend converts to camelCase at API client layer only

NFR11: API versioning — all REST routes prefixed `/api/v1/` from day one

NFR12: Test coverage ≥80% enforced via `pytest-cov --cov-fail-under=80`

NFR13: CI/CD — GitLab CI/CD (`.gitlab-ci.yml`); stages: ruff, mypy --strict, bandit, detect-secrets, pytest

NFR14: Logging — structured JSON logging (timestamp, container_name, level, event_type, trip_id, message) to local file with logrotate

NFR15: Secrets — API keys must never appear in source control — managed via `.env` (PoC) or Docker secrets (fleet)

**Total NFRs: 15**

---

### UX Design Requirements

UX-DR1: Control Centre Dashboard app shell — top nav bar, critical alert hook (pulsing red pill when Critical escalation unacknowledged >60s), tab bar (Live · Analytics · System Health)

UX-DR2: Live Monitoring — KPI strip (Active Trains, Open Escalations, Active Incidents, Capacity Alerts, Luggage Alerts) with tap-to-filter behaviour wired to unified feed

UX-DR3: Fleet List — sorted by severity (red → amber → green); normal trains collapsed by default; per-train card shows severity dot, route, dwell status pill, coach occupancy bars, avg%

UX-DR4: Unified Feed — severity-sorted stream; filter pills (Type · Status · Severity) combinable; unacknowledged count badge; clear filters control

UX-DR5: Escalation Detail — portal panel; severity accent bar; meta strip (Train · Coach · Time · Elapsed); still frame with camera/timestamp/confidence chips; Acknowledge / Resolve / "View on Live tab" actions

UX-DR6: Train Detail Panel — right panel within Live Monitoring; per-coach occupancy breakdown; AI inference status per coach; recent events list; escalation list with EscalationDetail link

UX-DR7: System Health view — inline 340px detail panel; per-row severity left-border; live elapsed in Since column; two-step ticket confirmation; Train Link row always rendered; container drill-down on amber/red app status

UX-DR8: Analytics Panel — four sub-tabs: Capacity Exceptions · Occupancy Heatmap · Dwell Time · AI Detection Quality; shared date range selector (7d / 14d / 30d); Export CSV per sub-tab

UX-DR9: Analytics / Capacity Exceptions — exception cards grouped by route; coach occupancy chart (horizontal bars, 85% threshold line, ▲ flag); 7-day trend bars; dismissed toggle + reopen; review modal with priority + note + queued-at timestamp

UX-DR10: Analytics / Occupancy Heatmap — route × hour grid (05:00–23:00); 5-band colour scale; null cells; hover + keyboard tooltip; peak hour table with 85% threshold line

UX-DR11: Analytics / Dwell Time — per-station bar chart (values in grid-row 2); scheduled tick with tooltip; under-schedule in green; scatter plot with absolute-positioned axes, station colour palette, R²-derived correlation label

UX-DR12: Analytics / AI Detection Quality — KPI strip (FP null state); stacked bar chart (deterministic weekly aggregation, maxBar ≥1, empty column handling); per-train uptime mapped 70–100% range with axis labels

UX-DR13: Design token system — all colours via CSS custom properties (`--obb-sev-*`, `--obb-surface-*`, `--obb-text-on-dark-*`, `--obb-blue-accent`, `--obb-border-dark`, `--font-mono`)

UX-DR14: Responsive layout — designed for 1440px+ desktop; no mobile breakpoints in PoC scope

UX-DR15: Luggage Monitoring — events grouped by train (collapsible); KPI strip with "Longest Unattended" (red) + "Longest Active" (amber); confidence chips colour-coded; unattended cards with pulsing border; resolved events in disclosure row

**Total UX-DRs: 15**

---

### Additional Requirements / Architecture Constraints

- Edge hardware: Single Hailo-8 M.2 on ADLINK cPCI-A3H20 blade
- Host OS: Debian 12 + Docker (SYS2); HailoRT runtime
- Container base: `python:3.11-slim-bookworm`, FastAPI+Uvicorn, asyncio, httpx
- Event envelope: `{uuid, journey_id, vehicle_id, timestamp, event_type, severity, source, payload}`
- journey_id scheme: `{vehicle_id}_{trip_number}_{YYYYMMDD}`
- Auth: VLAN isolation onboard (PoC); API key cloud (PoC)
- WebSocket: Client-driven subscriptions with `event_type` filter, `min_severity`, `coach_id`, `reconnect_replay_depth=50`
- Implementation sequence: event types → DB DDL → WS spec → CC Dashboard → inference pipeline → CI/CD

### PRD Completeness Assessment

The PRD is well-structured and covers vision, problem, solution, users, FRs, NFRs, UX-DRs, scope, architecture constraints, success criteria, implementation sequence, and open questions. 

Notable observations:
- **FR numbering gaps**: FR13–FR19 and FR28–FR31 are explicitly deferred — intentional, not a gap
- **FR32–FR35** (analytics) are in-scope but relatively thin on detail — epics coverage check will reveal whether stories cover them adequately
- **12 open questions** remain unresolved — several are blocking (e.g. Q3 confidence threshold, Q6 fleet planning queue) and may affect story completeness
- **UX-DRs** are detailed and tied directly to the locked prototype — high confidence in their implementability

---

## Epic Coverage Validation

### Coverage Matrix

| FR | PRD Requirement (summary) | Epic Coverage | Status |
|----|--------------------------|---------------|--------|
| FR1 | Live per-coach headcount — CC Dashboard, Conductor App, PIS, Driver | Epic 4 (pipeline), Epic 2 (CC Live) | ✅ Covered |
| FR2 | Luggage item count per coach — Conductor App & CC | Epic 4, Epic 2 | ✅ Covered |
| FR3 | Colour-coded train diagram / congestion map | Epic 4, Epic 2 | ✅ Covered |
| FR4 | Unattended bag alert beyond configurable threshold | Epic 4, Epic 2 | ✅ Covered |
| FR5 | Door obstruction alert to conductor & driver | Epic 4 | ✅ Covered |
| FR6 | TCMS alarm ingestion — plain language to conductor/driver | Epic 4 | ✅ Covered |
| FR7 | Correlated door alert (camera + door fault sensor) | Epic 4 | ✅ Covered |
| FR8 | Accessibility passenger detection (wheelchair/pushchair) | Epic 4 | ✅ Covered |
| FR9 | Speed-correlated door fault escalation | Epic 4 | ✅ Covered |
| FR10 | AI alerts suppressed in depot maintenance mode | Epic 4 | ✅ Covered |
| FR11 | Alert when accessibility door released near wheelchair user | Epic 4 | ✅ Covered |
| FR12 | Alert when wheelchair ramp deployed | Epic 4 | ✅ Covered |
| FR20 | CC dashboard — live fleet view | Epic 2 | ✅ Covered |
| FR21 | Unified prioritised incident feed | Epic 2 | ✅ Covered |
| FR22 | Real-time dwell time — CC operator & capacity planner | Epic 3 | ✅ Covered |
| FR23 | Predictive overcrowding warning | Epic 3 | ✅ Covered |
| FR24 | Slip/fall detection alert to CC | Epic 2 | ✅ Covered |
| FR25 | Prohibited zone detection alert to CC | Epic 2 | ✅ Covered |
| FR26 | Degraded operation alert | Epic 3 (System Health) | ✅ Covered |
| FR27 | Incidents tagged with trip ID + route | Epic 1 (event envelope ADR-1/ADR-2) | ✅ Covered |
| FR32 | No-show seat detection by route/day type/class | Epic 3 (analytics) | ⚠️ Partial — no pipeline story |
| FR33 | Anonymised ridership analytics | Epic 3 (analytics) | ⚠️ Partial — aggregation pipeline missing |
| FR34 | Occupancy-normalised energy KPIs (ESG) | Epic 3 (analytics) | ⚠️ Partial — energy data source unspecified |
| FR35 | Advertising audience metadata per route | Epic 3 (analytics) | ⚠️ Partial — no implementation path |

### Coverage Statistics

- **Total in-scope PoC FRs:** 27
- **FRs fully covered:** 23
- **FRs partially covered (thin story detail):** 4 (FR32–FR35)
- **FRs not covered:** 0
- **Coverage percentage:** 100% mapped, ~85% with full story-level detail

### Missing / Thin Coverage

#### ⚠️ FR32 — No-show seat detection
- **Gap:** Epic 3 covers the analytics UI/endpoint but no story addresses the inference logic for detecting unoccupied-reserved seats or the data schema for storing seat state by route/day type/class.
- **Recommendation:** Epic 4 needs a sub-story for seat occupancy classification event type; Epic 3 analytics endpoint story should reference it explicitly.

#### ⚠️ FR33 — Anonymised ridership analytics
- **Gap:** Monthly boardings/peak loads/coach class occupancy require a daily aggregation job not in any story. The analytics REST endpoint is mentioned but the rollup pipeline, retention window, and `occupancy_summaries` table are unspecified.
- **Recommendation:** Add a story in Epic 1 or Epic 3 for the occupancy aggregation job.

#### ⚠️ FR34 — Occupancy-normalised energy KPIs (ESG)
- **Gap:** Energy data source is unspecified. Neither the architecture nor the epics identify a VLAN or data feed for energy consumption figures.
- **Recommendation:** Flag as **blocking** — energy data source must be confirmed before a story can be written. Recommend escalating to open question list.

#### ⚠️ FR35 — Advertising audience metadata
- **Gap:** No story, no data model, no API endpoint. Mapped to Epic 1/analytics in the coverage map but has no concrete implementation path.
- **Recommendation:** Confirm whether this is still in PoC scope or should be formally deferred to Phase 2.

---

## UX Alignment Assessment

### UX Document Status

✅ **Found — multiple UX documents present:**
- `_bmad-output/design-artifacts/DD-001-cc-dashboard.md` — full design document, approved 2026-05-16
- `_bmad-output/design-artifacts/D-UX-Design/scenario-04-specs/01-control-centre-analytics-panel.md` — analytics panel spec (all 4 sub-tabs), approved 2026-05-16
- Prototype: `control-centre/` (React + Vite SPA) — locked and approved 2026-05-16

### UX ↔ PRD Alignment

| UX-DR | PRD Coverage | Status |
|--------|-------------|--------|
| UX-DR1 (App shell, nav, critical alert hook) | FR20, FR21 | ✅ Aligned |
| UX-DR2 (KPI strip, tap-to-filter) | FR20, FR21 | ✅ Aligned |
| UX-DR3 (Fleet list, severity sort) | FR20 | ✅ Aligned |
| UX-DR4 (Unified feed, filter pills) | FR21, FR27 | ✅ Aligned |
| UX-DR5 (Escalation Detail panel) | FR20, FR21, FR27 | ✅ Aligned |
| UX-DR6 (Train Detail panel) | FR1, FR2, FR20 | ✅ Aligned |
| UX-DR7 (System Health view) | FR26 | ✅ Aligned |
| UX-DR8 (Analytics 4 sub-tabs + date range) | FR22, FR23, FR32–FR35 | ✅ Aligned |
| UX-DR9 (Capacity Exceptions) | FR23, FR32 | ✅ Aligned |
| UX-DR10 (Occupancy Heatmap) | FR33 | ✅ Aligned |
| UX-DR11 (Dwell Time) | FR22 | ✅ Aligned |
| UX-DR12 (AI Detection Quality) | NFR2, NFR3 | ✅ Aligned |
| UX-DR13 (Design token system) | NFR10 (consistency req.) | ✅ Aligned |
| UX-DR14 (1440px+ desktop, no mobile) | Architecture constraint | ✅ Aligned |
| UX-DR15 (Luggage monitoring) | FR2, FR4 | ✅ Aligned |

### UX ↔ Architecture Alignment

| UX requirement | Architecture support | Status |
|----------------|---------------------|--------|
| Real-time occupancy on fleet list (UX-DR3) | WebSocket ADR-9 with `coach_id` filter + `reconnect_replay_depth=50` | ✅ Supported |
| Escalation Detail acknowledge/resolve (UX-DR5) | REST `/api/v1/` routes (NFR11); action endpoints implied | ⚠️ Endpoint not explicitly specified in epics |
| Analytics date-range queries (UX-DR8) | `?range=7d|14d|30d` param on analytics endpoints (Epic 3) | ✅ Supported |
| Export CSV per sub-tab (UX-DR8) | Not addressed in architecture or stories | ⚠️ Missing — no story or API design for CSV export |
| System Health live-tick elapsed (UX-DR7) | Health poll interval unspecified (PRD Open Q9) | ⚠️ Blocking open question |
| Critical alert hook >60s (UX-DR1) | WebSocket subscription — requires server-side elapsed tracking | ⚠️ No story for server-side escalation age tracking |
| Capacity review queue (UX-DR9 review modal) | PRD Open Q6 — internal PostgreSQL or ÖBB external? | ⚠️ Blocking open question |

### Alignment Issues

1. **Acknowledge/Resolve API endpoints** — UX-DR5 requires Acknowledge and Resolve actions wired to the API, but no REST endpoint is defined for escalation state transitions in architecture or epics. Epic 2 mentions this in the 9-item delta list but no story exists.

2. **CSV Export** — UX-DR8 specifies Export CSV per sub-tab on every analytics view. No story, no API endpoint, no architecture decision covers this. Must be added to Epic 3.

3. **Escalation age tracking** — The critical alert hook (>60s unacknowledged pulsing red pill, UX-DR1) requires the server to track escalation creation time and current state. WebSocket subscription model supports filtering but no story covers escalation TTL/age push.

4. **UX-DR versions diverge from epics.md UX-DRs** — The epics.md was written before the final Freya review sessions. The UX-DRs in epics.md (e.g. UX-DR9 describes "escalation table with status badges, route/train column, timestamps, resolution time; trend sparklines") no longer match the locked prototype (route-grouped exception cards, coach occupancy chart, dismissed toggle). **Risk:** Developers reading epics.md may implement outdated UX.

### Warnings

- ⚠️ **UX-DRs in epics.md are stale** — The epics document contains an older version of UX-DRs that diverges significantly from the locked prototype. Developers must be directed to DD-001 and `01-control-centre-analytics-panel.md` as the authoritative UX reference, not the UX-DRs embedded in epics.md.
- ⚠️ **CSV export unplanned** — Confirm whether Export CSV is required in PoC or Phase 2.
- ⚠️ **19 prototype approximations** (DD-001 §6) must all be replaced in production — none have been assigned to specific stories yet.

---

## Epic Quality Review

### Overview

| Epic | Title | User-centric? | Has Stories? | Story ACs? |
|------|-------|--------------|-------------|------------|
| Epic 1 | Foundation & Shared Infrastructure | ⚠️ Borderline | ❌ No | ❌ No |
| Epic 2 | Control Centre Dashboard — Live Operations | ✅ Yes | ❌ No | ❌ No |
| Epic 3 | Control Centre Dashboard — Analytics & System Health | ✅ Yes | ❌ No | ❌ No |
| Epic 4 | Onboard Edge Pipeline | ⚠️ Borderline | ❌ No | ❌ No |

### 🔴 Critical Violations

#### CRIT-1: No individual stories exist in any epic

**Severity:** 🔴 Critical  
**Location:** All epics (epics.md lines 156–194)  
**Detail:** Every epic in epics.md is an epic-level description only. There are no individual numbered stories (e.g., Story 2.1, 2.2...) with:
- User story format ("As a [user], I want... so that...")
- Acceptance criteria (Given/When/Then)
- Story-level scope boundaries
- Dependencies called out

The epics document contains deliverables lists and FR coverage maps but is missing the story decomposition layer entirely. This means developers have no actionable unit of work and testers have no acceptance criteria to validate against.

**Impact:** Blocks implementation — developers cannot begin without stories to implement.  
**Recommendation:** Run `bmad-create-epics-and-stories` workflow to decompose each epic into stories before implementation begins.

---

#### CRIT-2: Epic 1 ("Foundation & Shared Infrastructure") is a technical epic

**Severity:** 🔴 Critical  
**Location:** epics.md line 156  
**Detail:** Epic 1 is framed as a technical prerequisite — "developers can deploy a working skeleton". This delivers zero user value in isolation. It is a classic infrastructure/setup epic that no end user (Claudia, Conrad, Roland) benefits from directly.

**However:** The epics document itself acknowledges this as Story 1 must be the E2E skeleton MVP — recognising the sequencing need. For a PoC with tight dependencies, this is defensible as a "foundation sprint" but must be minimised in scope.

**Recommendation:** Keep Epic 1 as a technical enabler but:
- Scope it to the absolute minimum (skeleton only)
- Frame Story 1.1 as the E2E smoke test story
- Ensure Epic 2 can begin with mock data immediately after Story 1.1

---

#### CRIT-3: Epic 4 ("Onboard Edge Pipeline") claims FR13–FR14 coverage but they are deferred

**Severity:** 🔴 Critical  
**Location:** epics.md line 189: "FRs covered: FR1–FR14, FR26, FR29–FR31"  
**Detail:** FR13 (AI fault pattern detection) and FR14 (predictive fault alerting) are explicitly marked as "Deferred Phase 2" in both the PRD and the epics.md FR coverage map (line 125). Including them in Epic 4's "FRs covered" creates a contradiction — stories may be written to implement deferred requirements.  
**Recommendation:** Remove FR13–FR14 from Epic 4's coverage claim. Update to FR1–FR12, FR26.

---

### 🟠 Major Issues

#### MAJOR-1: 19 prototype approximations not assigned to any story

**Severity:** 🟠 Major  
**Detail:** DD-001 §6 lists 19 production delta items that must replace prototype approximations (e.g., replace MockWebSocketClient, wire Acknowledge/Resolve to API, real fleet sort, etc.). Epic 2 references the "9-item production delta" but these are not decomposed into stories. The remaining 10 delta items (approximations #10–19) from the Freya review session are not mentioned in any epic.  
**Recommendation:** All 19 delta items must be assigned to specific stories in Epic 2 or Epic 3.

---

#### MAJOR-2: No story covers the Acknowledge/Resolve REST endpoint

**Severity:** 🟠 Major  
**Detail:** Epic 2 mentions "wire Escalation Detail acknowledge/resolve to API" in the 9-item delta but no architecture decision defines the endpoint shape, state machine, or data model for escalation state transitions. Without this, developers face an ambiguous implementation task.  
**Recommendation:** Add a story to Epic 1 or Epic 2: "Define and implement escalation state machine (OPEN → ACKNOWLEDGED → RESOLVED) with REST endpoint."

---

#### MAJOR-3: Epic 2 references the 9-item delta from DD-001 but does not include the Luggage Monitoring tab

**Severity:** 🟠 Major  
**Detail:** Epic 2's FRs covered list (FR20, FR21, FR24, FR25, FR27) omits FR2 (luggage item count) and FR4 (unattended bag alert), which are implemented in the Luggage Monitoring tab (UX-DR15). The Luggage tab was designed and is part of the locked prototype but has no epic home in the Control Centre epics.  
**Recommendation:** Either add a Luggage Monitoring story to Epic 2 (FR2, FR4 as Control Centre view) or explicitly call it out as delivered via Epic 4's event pipeline + Epic 2's UI.

---

#### MAJOR-4: Epic 3 REST endpoints not connected to any data model or story

**Severity:** 🟠 Major  
**Detail:** Epic 3 lists 5 required REST endpoints but provides no guidance on:
- Response schema / data shape
- Which PostgreSQL table backs each endpoint
- Whether aggregation is real-time or pre-computed
- Query performance at 90-day data retention  

Without stories that define these, a developer must make all architectural decisions unilaterally.  
**Recommendation:** Write stories with explicit API contract (request params, response schema) for each of the 5 endpoints.

---

### 🟡 Minor Concerns

#### MINOR-1: Epic numbering diverges between epic list and implementation sequence

The Epic List table (lines 135–146) shows:
- Epic 1: Foundation
- Epic 2: CC Dashboard  
- Epic 3: Onboard Pipeline  
- Epic 4: Conductor App

But the Approved Epic List section (lines 149+) renumbers them:
- Epic 1: Foundation
- Epic 2: CC Dashboard — Live Operations
- Epic 3: CC Dashboard — Analytics & System Health
- Epic 4: Onboard Edge Pipeline

This creates confusion — "Epic 3" means two different things. The approved list reflects the correct PoC scope but the top-level list is stale.  
**Recommendation:** Remove or clearly mark the top-level Epic List table as superseded.

---

#### MINOR-2: "Story 1 must be" phrasing is not a story

The note "Story 1 must be: E2E skeleton MVP..." is guidance text but not an actual story. A developer reading this would have to interpret scope themselves.  
**Recommendation:** Convert to a formal story when the story decomposition is done.

---

#### MINOR-3: Epic 4 can run in parallel with Epics 2–3 "against MockAPCAdapter"

This is correct sequencing but implies that Epic 2 stories must work with mock data first. This dependency (Epic 2 needs `MockAPCAdapter` from Epic 1 to proceed) is valid and well-noted, but must be explicit in the Epic 2 story dependency chain when stories are written.

---

### Best Practices Compliance Checklist

| Check | Epic 1 | Epic 2 | Epic 3 | Epic 4 |
|-------|--------|--------|--------|--------|
| Epic delivers user value | ⚠️ Technical | ✅ Yes | ✅ Yes | ⚠️ Technical |
| Epic can function independently | ✅ Yes | ✅ Yes (with mocks) | ✅ Yes (with Epic 2) | ✅ Yes (with mocks) |
| Stories exist | ❌ No | ❌ No | ❌ No | ❌ No |
| Stories appropriately sized | — | — | — | — |
| No forward dependencies | — | — | — | — |
| Clear acceptance criteria | ❌ None | ❌ None | ❌ None | ❌ None |
| Traceability to FRs maintained | ✅ Yes | ✅ Yes | ✅ Yes | ⚠️ Includes deferred FRs |

---

## Summary and Recommendations

### Overall Readiness Status

**🔴 NOT READY — Story decomposition required before implementation can begin.**

The project has strong foundations: a coherent PRD, approved architecture, locked and approved Control Centre prototype (DD-001), and a well-structured FR/NFR inventory. The critical blocker is the absence of individual stories with acceptance criteria across all four epics.

---

### Issues Summary

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 Critical | 3 | No stories written; Epic 4 claims deferred FRs; Epic 1 is technical-only |
| 🟠 Major | 4 | 19 prototype delta items unassigned; no Acknowledge/Resolve endpoint story; Luggage tab has no epic home; Epic 3 endpoints have no schema |
| 🟡 Minor | 3 | Epic numbering inconsistency; "Story 1 must be" is not a story; mock dependency not explicit in story chain |
| ⚠️ UX | 4 | Stale UX-DRs in epics.md; CSV export unplanned; escalation age tracking missing; critical alert >60s has no server story |
| ⚠️ Coverage | 4 | FR32–FR35 mapped but pipeline stories missing; FR34 (energy) data source unknown |

**Total: 18 issues**

---

### Critical Issues Requiring Immediate Action

1. **Write stories for all 4 epics** — No implementation can begin without story-level decomposition with acceptance criteria. Run `bmad-create-epics-and-stories` to decompose epics into stories immediately.

2. **Remove FR13–FR14 from Epic 4 coverage** — These are deferred Phase 2 requirements. Including them risks developers implementing out-of-scope work.

3. **Resolve FR34 (energy data source)** — This is a blocking unknown. Until the energy VLAN or data feed is identified, FR34 cannot be implemented. Add to PRD open questions and escalate to ÖBB/Nomad Digital.

4. **Update UX-DRs in epics.md** — The UX-DRs embedded in epics.md are the pre-Freya-review version and no longer match the locked prototype. Stories built against these UX-DRs will implement the wrong design. Direct developers to DD-001 and `01-control-centre-analytics-panel.md` as authoritative references.

5. **Assign all 19 prototype approximations (DD-001 §6) to stories** — These production delta items are currently floating. Each must become an acceptance criterion in a specific story.

---

### Recommended Next Steps (ordered)

1. **[Immediate]** Run `bmad-create-epics-and-stories` skill to decompose Epics 1–4 into individual stories with Given/When/Then acceptance criteria
2. **[Immediate]** Correct Epic 4 FR coverage — remove FR13, FR14
3. **[Before stories are written]** Decide FR35 (advertising audience metadata) scope — PoC or Phase 2 deferral
4. **[Before Epic 3 stories]** Define API response schemas for all 5 analytics endpoints
5. **[Before Epic 2 stories]** Define escalation state machine (OPEN → ACKNOWLEDGED → RESOLVED) and REST endpoint shape
6. **[Before Epic 3 stories]** Clarify CSV export scope — PoC or Phase 2
7. **[Open question]** Escalate FR34 energy data source question to ÖBB/Nomad Digital as a blocking unknown
8. **[When stories are written]** Assign each of the 19 DD-001 prototype approximations to a specific story AC
9. **[When stories are written]** Add an occupancy aggregation pipeline story (for FR33 daily rollup)
10. **[Before Epic 2 stories]** Determine Luggage Monitoring tab's epic home (Epic 2 or new Epic 2.5)

---

### Final Note

This assessment identified **18 issues** across **5 categories**. The most significant finding is structural: **all four epics lack story decomposition**, which is the primary blocker to implementation. The underlying planning quality — architecture, prototype, FR inventory, event schemas — is strong and implementation-ready once stories are written. The recommendation is to proceed directly to the `bmad-create-epics-and-stories` workflow before any development begins.

**Report generated:** `_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-17.md`  
**Assessed:** 2026-05-17  
**Documents reviewed:** PRD v1.0, Architecture, epics.md, DD-001, 01-control-centre-analytics-panel.md, design log








