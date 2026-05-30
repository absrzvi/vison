---
stepsCompleted: [step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review, step-06-final-assessment]
filesIncluded:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md
  - _bmad-output/planning-artifacts/event-payload-schemas.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-05-30
**Project:** oebb-agent

## Document Inventory

| Type | File | Size | Modified |
|---|---|---|---|
| PRD | `_bmad-output/planning-artifacts/prd.md` | 18 KB | 2026-05-17 |
| Architecture | `_bmad-output/planning-artifacts/architecture.md` | 99 KB | 2026-05-21 |
| Epics & Stories | `_bmad-output/planning-artifacts/epics.md` | 150 KB | 2026-05-30 |
| UX Design | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md` | — | 2026-05-13 |
| Event schemas (supporting) | `_bmad-output/planning-artifacts/event-payload-schemas.md` | 10 KB | 2026-05-17 |

**Historical (not assessed):** `2026-05-13-oebb-user-stories.md` superseded by `epics.md`; `ux-design-specification.md` is a stub pointing to design-artifacts spec.

---

## PRD Analysis

**Source:** `_bmad-output/planning-artifacts/prd.md` v1.0 (Approved 2026-05-16)

### Functional Requirements (In-Scope PoC)

**Onboard Intelligence (Edge) — §5.1**

- **FR1** — Live per-coach headcount displayed in real time to Conductor App, PIS, Control Centre Dashboard, and Driver Display
- **FR2** — Luggage item count per coach surfaced to Conductor App and Control Centre
- **FR3** — Colour-coded train diagram (coach-level congestion map) shown to conductor and passengers
- **FR4** — Alert raised to conductor when a bag has been left unattended beyond a configurable duration threshold
- **FR5** — Alert raised to conductor and driver when a passenger or bag is blocking a door
- **FR6** — Active Stadler/TCMS alarms ingested via SNMP and shown in plain language to conductor, technician, and driver (critical only for driver)
- **FR7** — High-priority correlated door alert raised when camera and door fault sensor both agree a door problem exists
- **FR8** — Conductor and passengers alerted when accessibility-dependent passenger (wheelchair/pushchair) is detected, with coach and door number
- **FR9** — Speed-correlated door fault escalation — door fault alerts at speed carry higher severity
- **FR10** — AI alerts suppressed during depot maintenance mode
- **FR11** — Alert when accessibility door is released and a wheelchair user is nearby
- **FR12** — Alert to conductor and platform staff when wheelchair ramp is deployed

**Control Centre — Live Operations — §5.2**

- **FR20** — Control Centre dashboard — live fleet view with occupancy, active incidents, and fault alerts across all trains
- **FR21** — Unified prioritised incident feed for control centre operator, sorted by severity
- **FR22** — Real-time dwell time shown per stop to control centre operator and capacity planner
- **FR23** — Predictive overcrowding warning — forecast capacity breach at an upcoming stop
- **FR24** — Slip/fall detection alert to control centre operator
- **FR25** — Prohibited zone detection alert to control centre operator
- **FR26** — Degraded operation alert to control centre operator, technician, and maintenance manager
- **FR27** — All incidents tagged with trip ID and route for post-incident review

**Analytics & Reporting — §5.3**

- **FR32** — No-show seat detection data by route, day type, and class for capacity planner
- **FR33** — Anonymised ridership analytics — monthly boardings, peak loads, coach class occupancy
- **FR34** — Occupancy-normalised energy KPIs per journey for ESG reporting
- **FR35** — Advertising audience metadata — aggregate audience profiles per route

**Total in-scope FRs:** 24 (FR1–FR12, FR20–FR27, FR32–FR35)

### Deferred / Out-of-Scope (Tracked but not assessed for coverage)

- **Deferred Phase 2:** FR13, FR14, FR15, FR16, FR17, FR36, FR37
- **Descoped PoC:** FR18, FR19, FR28, FR29, FR30, FR31

### Non-Functional Requirements

- **NFR1** — Uptime ≥99.5%
- **NFR2** — Occupancy accuracy ≥95% (APC fusion calibration)
- **NFR3** — False-positive alert rate <5%
- **NFR4** — Alert latency within station dwell window (~30–90s); local inference, no cloud round-trip
- **NFR5** — Raw video must never leave the train
- **NFR6** — GDPR-compliant; anonymised aggregates only to cloud
- **NFR7** — Hardware rated -40°C to +85°C (rail environment)
- **NFR8** — Connectivity resilience — all 4 onboard interfaces functional when SYS1 down; CC degrades gracefully
- **NFR9** — All events carry trip_id, vehicle_id, ISO-8601 UTC timestamp
- **NFR10** — API responses use snake_case JSON; React converts to camelCase at API client layer
- **NFR11** — All REST routes prefixed `/api/v1/`
- **NFR12** — Test coverage ≥80% via `pytest-cov --cov-fail-under=80`
- **NFR13** — GitLab CI/CD; stages: ruff, mypy --strict, bandit, detect-secrets, pytest
- **NFR14** — Structured JSON logging to local file with logrotate
- **NFR15** — Secrets via `.env` (PoC) or Docker secrets (fleet); never in source

**Total NFRs:** 15

### UX Design Requirements

UX-DR1–UX-DR15 (Control Centre Dashboard — locked prototype DD-001). Total: **15**.

### Architecture Constraints (§9)

Edge hardware (Hailo-8 M.2 on ADLINK cPCI-A3H20), Debian 12 + Docker, HailoRT, privacy-by-design, structured cloud sync via SYS1, container base `python:3.11-slim-bookworm`, FastAPI+Uvicorn, asyncio, httpx; event envelope `{uuid, journey_id, vehicle_id, timestamp, event_type, severity, source, payload}`; `journey_id = {vehicle_id}_{trip_number}_{YYYYMMDD}`; VLAN isolation (PoC) → OAuth2/OIDC (fleet); WebSocket subscription model with `event_type`, `min_severity`, `coach_id`, `reconnect_replay_depth=50`.

### Open Questions Carried Forward

12 open questions (Q1–Q12) — none flagged as blocking PoC start, but several affect specific FR/UX implementations (e.g., Q2 staleness threshold → SSE banner; Q5 trend query key → FR23/analytics; Q7–Q9 health thresholds → UX-DR7 System Health).

### PRD Completeness Assessment

**Strengths:**
- Clear in-scope vs. deferred separation (FR table 5.4 explicitly enumerates everything excluded)
- NFRs are measurable (numeric targets on every quality attribute)
- UX-DRs trace directly to a locked prototype (DD-001) rather than abstract user stories
- Architecture constraints anchored to specific hardware and ADRs (e.g., journey_id scheme = ADR-2)

**Concerns:**
- **Discontinuous numbering** (FR1–12 jumps to FR20; FR27 to FR32) is intentional but easy to misread as missing requirements during traceability — must be flagged explicitly during epic mapping
- 12 open questions remain — none blocking but several touch implementation details (staleness threshold, escalation confidence, health poll intervals). Step 3 must check whether epics defer or resolve each
- §5.1 includes onboard requirements (FR1–FR12) but the in-scope component list (§8.1) defers Conductor App, Driver Display, PIS, Bistro to Phase 2 — apparent mismatch between FR audience ("displayed to Conductor App / Driver Display") and component scope. Coverage validation must confirm whether FR1, FR3, FR5, FR6, FR8 are met via Control Centre Dashboard alone for PoC, with onboard surfaces deferred
- WebSocket is specified in PRD (§9) but the PRD ix-summary (recorded in project-context) and CLAUDE.md container map call out "REST+SSE for Control Centre". Need to confirm transport choice in architecture step

---

## Epic Coverage Validation

**Source:** `_bmad-output/planning-artifacts/epics.md` (last updated 2026-05-21; Epic 10/11 added 2026-05-30)

### Epic List

| # | Epic | Priority | PoC scope | Defined in epics.md |
|---|---|---|---|---|
| 1 | Foundation & Shared Infrastructure | P0 | ✅ Done | ✅ Full (7 stories + L1) |
| 1.5 | Onboard Containerised Infrastructure | P0 | ✅ Done | ⚠️ Listed but no detailed stories (artifacts exist in implementation-artifacts/) |
| 2 | Control Centre Dashboard — Live Operations | P0 | ✅ Done | ✅ Full (9 stories) |
| 3 | CC Dashboard — Analytics & System Health | P0 | ✅ Done | ✅ Full (7 stories) |
| 4 | Onboard Edge Pipeline | P0 | ✅ Done | ✅ Full (S1–S10 + CS1) |
| 5 | Luggage Monitoring — Live Data | P0 | ✅ Done | ⚠️ Listed but no detailed stories (4 artifacts exist) |
| 6 | Fusion Hardening | P1 | ✅ Sprint 1 | ✅ Full (3 stories) |
| 7 | Retry & Idempotency Hardening | P1 | ✅ Sprint 1 | ✅ Full (2 stories) |
| 8 | Analytics UI Hardening | P2 | ✅ Sprint 1 | ✅ Full (2 stories) |
| 9 | Container & Infrastructure Hardening | P2 | ✅ Sprint 1 | ✅ Full (3 stories) |
| 10 | Operator Adoption & Trust (AI PM gap) | P1 | 🆕 Pre-pilot | ✅ Full (5 stories) |
| 11 | Control Centre Admin & Identity | P1 | 🆕 Backlog | ⚠️ Placeholder (5 stories named, no ACs) |

### FR Coverage Matrix (In-Scope PoC FRs)

| FR | PRD Requirement | Epic Coverage | Status |
|---|---|---|---|
| FR1 | Live per-coach headcount | Epic 4 (E4-S4 inference occupancy events) + Epic 2 (E2-S1 WS → CC) | ✓ Covered (CC surface; Conductor/PIS/Driver deferred) |
| FR2 | Luggage item count per coach | Epic 5 (luggage live feed) + Epic 2 (CC routing) | ✓ Covered (CC surface only; Conductor deferred) |
| FR3 | Colour-coded train diagram | Epic 2 (E2-S3 fleet list / coach occupancy bars; UX-DR3) | ✓ Covered (CC); Passenger Portal deferred |
| FR4 | Unattended bag alert | Epic 4 (E4-S6 fusion suppression + unattended_bag.py) + Epic 5 (UI) | ✓ Covered |
| FR5 | Door obstruction alert | Epic 4 (E4-S5 inference + E4-S6 fusion door_obstruction.py) | ✓ Covered (CC surface; Driver deferred) |
| FR6 | TCMS alarms plain language | Epic 4 (E4-S1 vlan-pollers SNMP, ALARM_ACTIVE/CLEARED) + Epic 2 (CC unified feed) | ✓ Covered (CC; Conductor/Driver/Technician deferred) |
| FR7 | Correlated door alert | Epic 4 (E4-S6 fusion door_obstruction cross-reference with ZFR) | ✓ Covered |
| FR8 | Accessibility detection alert | Epic 4 (E4-S5 inference ACCESSIBILITY_DETECTED) | ✓ Covered (CC; passenger PIS deferred) |
| FR9 | Speed-correlated door fault | Epic 4 (E4-S6 fusion speed escalation) | ✓ Covered |
| FR10 | AI alerts suppressed in depot | Epic 4 (E4-S6 fusion suppression.py DEPOT state) | ✓ Covered |
| FR11 | Wheelchair-door release alert | Epic 4 (E4-S1 context state door_release + E4-S5 accessibility detection) | ⚠️ Partial — correlation logic referenced but no dedicated story explicitly emits this combined alert |
| FR12 | Wheelchair ramp deployed alert | Epic 4 (E4-S5 RAMP_DEPLOYED event) | ✓ Covered (CC surface; platform-staff app out of scope) |
| FR20 | CC live fleet view | Epic 2 (E2-S1, E2-S2, E2-S3) | ✓ Covered |
| FR21 | Unified prioritised incident feed | Epic 2 (E2-S4 new-items chip, E2-S2 filter wiring) | ✓ Covered |
| FR22 | Real-time dwell time per stop | Epic 3 (E3-S4 dwell time tab) | ⚠️ Covered for historical analytics; **real-time** dwell per stop is not surfaced as an in-flight live indicator |
| FR23 | Predictive overcrowding warning | Epic 2/3 | ❌ **GAP** — no story explicitly forecasts a capacity breach at an upcoming stop; only historical exceptions exist (E3-S2). Open Question Q5 (trend query key) is unresolved |
| FR24 | Slip/fall detection alert | Epic 4 (E4-S5 slip_fall via hailotracker) | ✓ Covered |
| FR25 | Prohibited zone detection alert | Epic 4 | ❌ **GAP** — no story implements prohibited-zone detection; not in E4-S4 or E4-S5 acceptance criteria |
| FR26 | Degraded operation alert | Epic 3 (E3-S6 system health staleness, CAMERA_DEGRADED) + Epic 4 (E4-S3 emits CAMERA_DEGRADED) | ✓ Covered for CC; maintenance manager / technician routing deferred |
| FR27 | Incidents tagged with trip ID + route | Epic 1 (E1-S2 envelope with journey_id) + Epic 4 (vlan-pollers route_name in journey) | ✓ Covered |
| FR32 | No-show seat detection | Epic 3 (analytics) | ❌ **GAP** — no story emits or queries no-show seat data; no payload schema for it; E3-S2 covers capacity exceptions but not seat-level no-show |
| FR33 | Anonymised ridership analytics | Epic 3 (E3-S3 occupancy heatmap, E3-S2 capacity exceptions) | ✓ Covered for monthly boardings and peak loads via heatmap; coach class breakdown not explicit |
| FR34 | Occupancy-normalised energy KPIs | Epic 3 | ❌ **GAP** — no story produces ESG energy KPI; no VLAN 12 energy poller (E4-S1/S2 cover VLAN 7/8/3/6 only) |
| FR35 | Advertising audience metadata | Epic 3 | ❌ **GAP** — no story produces audience profile aggregates |

### NFR Coverage Matrix

| NFR | Requirement | Epic Coverage | Status |
|---|---|---|---|
| NFR1 | Uptime ≥99.5% | Epic 1 (docker restart policy), Epic 6 (handler robustness), Epic 9 (HEALTHCHECK directives) | ✓ Covered |
| NFR2 | Occupancy accuracy ≥95% | Epic 4 (E4-S6 APC fusion calibration) — **but ADR-15 explicitly says camera count is authoritative and `weight_apc` is removed.** | ⚠️ **Tension** — NFR2 says APC calibrates ground truth; ADR-15 / E4-S6 say APC is NOT blended. Calibration mechanism unclear |
| NFR3 | False-positive rate <5% | Epic 4 (E4-S6 suppression state machine); Epic 10 (E10-S5 redefines NFR3 as `explicit_fp_rate < 5% per alert class over 7d`) | ✓ Covered (definition closed by E10-S5) |
| NFR4 | Alert latency within dwell window | Epic 4 (edge inference, no cloud round-trip) | ✓ Covered (design); no story explicitly measures end-to-end latency |
| NFR5 | Raw video never leaves train | Epic 4 (architecture invariant); Epic 1.5 (onboard containers) | ✓ Covered (architectural); no story includes an explicit assertion test |
| NFR6 | GDPR compliance | Epic 4 (anonymised events); Epic 10 (E10-S2 PII boundary noted) | ✓ Covered |
| NFR7 | Rail temp -40°C to +85°C | Hardware constraint (Hailo-8 confirmed in PRD) | ✓ Covered (HW spec) |
| NFR8 | Connectivity resilience | Epic 4 (E4-CS1 cloud-sync 72h buffer); Epic 7 (retry policy) | ✓ Covered |
| NFR9 | trip_id, vehicle_id, ISO-8601 UTC on all events | Epic 1 (E1-S2 envelope validation) | ✓ Covered |
| NFR10 | snake_case JSON + camelCase at client | Epic 1 (E1-S2 Pydantic) + Epic 2 (FleetContext mapping) | ✓ Covered |
| NFR11 | /api/v1/ prefix | Epic 1 (E1-S7) | ✓ Covered |
| NFR12 | ≥80% test coverage | Epic 1 (E1-S1 pytest-cov gate) | ✓ Covered |
| NFR13 | GitLab CI ruff/mypy/bandit/detect-secrets/pytest | Epic 1 (E1-S1, E1-S7) | ✓ Covered |
| NFR14 | Structured JSON logging | Every Epic 4 story specifies structlog usage | ✓ Covered |
| NFR15 | Secrets via .env / Docker secrets | Epic 1 (E1-S7) | ✓ Covered |

### UX-DR Coverage Matrix

| UX-DR | Requirement | Epic Coverage | Status |
|---|---|---|---|
| UX-DR1 | App shell + critical alert hook | Epic 2 (E2-S8 threshold) | ✓ Covered |
| UX-DR2 | KPI strip + tap-to-filter | Epic 2 (E2-S2) | ✓ Covered |
| UX-DR3 | Fleet list sorted by severity | Epic 2 (E2-S3) | ✓ Covered |
| UX-DR4 | Unified feed with filter pills | Epic 2 (E2-S2, E2-S4) | ✓ Covered |
| UX-DR5 | Escalation Detail panel | Epic 2 (E2-S5) | ✓ Covered |
| UX-DR6 | Train Detail panel | Epic 2 (E2-S6) | ✓ Covered |
| UX-DR7 | System Health view | Epic 2 (E2-S9) + Epic 3 (E3-S6, E3-S7) | ✓ Covered |
| UX-DR8 | Analytics 4-tab structure | Epic 3 (E3-S2 to E3-S5) | ✓ Covered |
| UX-DR9 | Capacity Exceptions | Epic 3 (E3-S2) | ✓ Covered |
| UX-DR10 | Occupancy Heatmap | Epic 3 (E3-S3) | ✓ Covered |
| UX-DR11 | Dwell Time | Epic 3 (E3-S4) | ✓ Covered |
| UX-DR12 | AI Detection Quality | Epic 3 (E3-S5) + Epic 10 (E10-S5 rates redefinition) | ✓ Covered |
| UX-DR13 | Design tokens (CSS vars) | Cross-cutting (referenced in every Epic 2/3 story) | ✓ Covered |
| UX-DR14 | 1440px+ desktop, no mobile | Cross-cutting (referenced in DD-001) | ✓ Covered |
| UX-DR15 | Luggage Monitoring view | Epic 5 (4 stories in implementation-artifacts) | ⚠️ Covered by implementation artifacts but not formally captured in epics.md |

### Missing FR Coverage (Critical Gaps)

**❌ FR23 — Predictive overcrowding warning**
- Impact: Listed as in-scope PoC functionality in PRD §5.2; no story implements forecasting; Open Question Q5 (trend query key — train number vs. route+timeslot) blocks design
- Recommendation: Either (a) add an explicit story (E3-S8 or E10-S6) for forecasting that closes Q5, or (b) move FR23 to deferred Phase 2 in PRD §5.4

**❌ FR25 — Prohibited zone detection**
- Impact: Listed as in-scope PoC functionality; no detection logic in E4-S4/E4-S5 acceptance criteria
- Recommendation: Add a story to Epic 4 (or descope to Phase 2)

**❌ FR32 — No-show seat detection**
- Impact: In-scope PoC capacity-planner analytics; no payload schema, no analytics endpoint
- Recommendation: Either define an `OCCUPIED_RESERVATION_GAP` event type + analytics aggregation story, or descope to Phase 2

**❌ FR34 — Occupancy-normalised energy KPIs**
- Impact: In-scope PoC ESG analytics; requires VLAN 12 energy poller (not in E4-S1/S2); no analytics endpoint
- Recommendation: Either add a `vlan-pollers` energy story + analytics aggregation, or descope to Phase 2 (recommended — ESG reporting is a Phase 2 fit)

**❌ FR35 — Advertising audience metadata**
- Impact: In-scope PoC monetisation analytics; no story exists
- Recommendation: Descope to Phase 2 — outside the safety/operations focus of PoC

### Partial / At-Risk Coverage

**⚠️ FR11 — Wheelchair-door release combined alert**
- E4-S1 sets `ContextState.door_release` and E4-S5 emits `ACCESSIBILITY_DETECTED`, but no story explicitly implements the combined "accessibility door released AND wheelchair user nearby" alert. Likely an emergent fusion behaviour, but no AC verifies it.
- Recommendation: Add an AC to E4-S6 (fusion) explicitly testing this correlation, OR add a new fusion handler story.

**⚠️ FR22 — Real-time dwell time**
- E3-S4 covers historical dwell analytics; no story surfaces real-time per-stop dwell to the CC during a stop.
- Recommendation: Confirm "real-time" intent. If live-during-dwell is required, add a story; if historical analytics satisfies, mark closed.

**⚠️ NFR2 — Occupancy accuracy via APC fusion vs. ADR-15**
- ADR-15 removes APC blending (`weight_camera`/`weight_apc` parameters dropped). NFR2 still claims APC ground-truth calibration. These are inconsistent.
- Recommendation: Update PRD NFR2 to reflect that APC is used for **post-hoc calibration / accuracy reporting**, not real-time blending. Add an analytics story comparing camera vs. APC counts per coach for accuracy measurement.

**⚠️ Epic 1.5 and Epic 5 — Story details missing from epics.md**
- Both are listed as ✅ Done in the epic table but their detailed stories live only in `implementation-artifacts/`. This breaks traceability — a fresh reader of epics.md cannot find acceptance criteria for E1-5-1..4 or E5-1..4.
- Recommendation: Backfill epics.md with the four luggage stories and four onboard infra stories so the planning artifact is complete (low cost — copy from implementation-artifacts).

### Coverage Statistics

| Metric | Count |
|---|---|
| Total in-scope PRD FRs | 24 |
| FRs fully covered | 16 |
| FRs partially covered (⚠️) | 3 (FR11, FR22, FR33) |
| FRs missing (❌) | 5 (FR23, FR25, FR32, FR34, FR35) |
| **FR coverage** | **67% full + 12% partial = 79% acceptable** |
| Total NFRs | 15 |
| NFRs covered | 14 |
| NFRs at risk | 1 (NFR2 — PRD/ADR conflict) |
| **NFR coverage** | **93%** |
| Total UX-DRs | 15 |
| UX-DRs covered | 15 (1 via implementation-artifacts only) |
| **UX-DR coverage** | **100%** (with note on Epic 5 traceability) |

---

## UX Alignment Assessment

### UX Document Status

**Found — extensive.**

| Artifact | Purpose | Status |
|---|---|---|
| `DD-001-cc-dashboard.md` | Design Delivery contract — 5 views, prototype-to-production deltas | ✅ Approved 2026-05-16 |
| `D-UX-Design/2026-05-13-oebb-ux-design.md` (v1) | Pre-PoC broad vision (7 interfaces) | Reference only |
| `D-UX-Design/2026-05-14-oebb-ux-design-v2.md` (v2) | Refined vision incl. analytics ideation | Reference only — exceeds PoC scope |
| `D-UX-Design/scenario-{XX}-specs/` | Per-scenario specs (12 scenario folders) | Some implemented, some Phase 2 |
| `control-centre/` prototype | React + Vite implementation reference | DD-001 approved against this |

### UX ↔ PRD Alignment

| Dimension | Finding |
|---|---|
| Views in DD-001 vs. UX-DRs | DD-001 §1 lists 5 views (Live Monitoring, Train Detail, System Health, Analytics, Luggage Monitoring) — fully traceable to UX-DR1–UX-DR15 |
| Routes documented | DD-001 §2 enumerates 5 production routes; matches Epic 2/3 component file paths |
| Prototype-to-production delta list | DD-001 §6 lists 19 specific items to replace with real implementations — these map 1:1 to Epic 2/3 story acceptance criteria (E2-S1 through E2-S9; E3-S1 through E3-S7) |
| Analytics scope | DD-001 covers 4 analytics sub-tabs (Capacity Exceptions, Occupancy Heatmap, Dwell Time, AI Detection Quality). UX v2 vision mentions additional analytics (no-show, energy KPI, vandalism log, bicycle/luggage density) that are **NOT** in DD-001 — consistent with FR32/FR34/FR35 being out of approved PoC UX scope |
| Luggage Monitoring view | DD-001 §1 includes it; Epic 5 has 4 implementation artifacts; **UX-DR15 in PRD maps cleanly to scenario-02d** |

**Conclusion:** PRD UX-DRs are derived directly from DD-001 (PRD inputDocuments confirms this). Alignment is tight — no UX-DR is missing a PRD or epic counterpart.

### UX ↔ Architecture Alignment

| Architecture decision | UX dependency | Status |
|---|---|---|
| WebSocket transport (ADR-9 / PRD §9) | DD-001 specifies real-time fleet updates, escalation arrivals, train state, KPI counts | ⚠️ **Conflict** — PRD says WebSocket, but project-context memory + CLAUDE.md container map specify **REST + SSE** for Control Centre. Architecture decision needs to be confirmed in Step 5. Epic 2 stories (E2-S1) reference "WebSocket" — if architecture changes to SSE, all "WS" references need a sweep |
| `/api/v1/` prefix (NFR11) | DD-001 implies REST endpoints via the analytics tab data flows | ✅ Aligned |
| Design tokens (UX-DR13) | Architecture does not constrain CSS — handled at component layer | ✅ Aligned (control-centre/src/styles/colors_and_type.css exists per CLAUDE.md) |
| Per-operator preferences (E2-S8) | DD-001 calls out per-operator configurable alert threshold; UX-DR1 specifies critical-alert hook | ✅ Aligned (E2-S8 defines `operator_preferences` table) |
| Server-generated maintenance ticket IDs (E3-S7) | DD-001 prototype-approximation list flags `Math.random()` ticket refs as items to replace | ✅ Aligned (E3-S7 defines `POST /api/v1/maintenance/tickets`) |

### Misalignments & Warnings

**⚠️ Transport conflict — WebSocket vs SSE**
- PRD §9 says WebSocket with `SubscriptionRequest`, `reconnect_replay_depth=50`
- CLAUDE.md container map: "REST+SSE for Control Centre"
- Project-context memory: container map confirms "no ws-gateway, REST+SSE for Control Centre"
- Epic 1 (E1-S6) and Epic 2 (E2-S1) story acceptance criteria are written assuming WebSocket
- **Recommendation:** Resolve before Epic 2 implementation. If SSE is the chosen transport, Epic 1 and Epic 2 stories need their ACs updated; PRD §9 needs amendment. This is a **HARD BLOCKER for Epic 2 dev start.**

**⚠️ Out-of-scope UX bleed**
- UX v2 spec (2026-05-14) lists no-show analysis, energy KPI, vandalism log, bicycle/luggage density. None are in PRD §5 in-scope FRs. Risk: stakeholders viewing UX v2 may expect these in PoC.
- **Recommendation:** Mark v2 doc with "Phase 2 vision — not PoC scope" header, OR move the section into a separate `Phase 2 Vision` doc to prevent confusion.

**⚠️ Conductor App / Driver Display / PIS UX exists but is deferred**
- Scenario specs exist for Conductor App (`scenario-02b`, `scenario-02c`, `scenario-02d`, `scenario-10`), but those are Phase 2 per PRD §8.3
- E10-S4 ships only an event-payload field + a Conductor App spec stub — actual UI is gated
- **No blocker** but make sure pilot stakeholders understand that PRD §5.1 references to Conductor/Driver/PIS apps are *event-payload routing* targets, not deliverable UIs for PoC

**⚠️ FR23 / FR32 / FR34 / FR35 — UX exists in v2 but no PoC UX commitment**
- These FRs are flagged as MISSING in epic coverage. UX v2 mentions them, but DD-001 (the contract) does not commit to them. So architecturally they have no UX deliverable to build against either. Compounds the recommendation to descope or defer.

---

## Epic Quality Review

Reviewed against BMAD `create-epics-and-stories` best practices: user value, independence, story sizing, no forward dependencies, AC quality, traceability.

### A. Epic User-Value Check

| Epic | User-Value Check | Verdict |
|---|---|---|
| 1 — Foundation & Shared Infrastructure | Goal stated: "Developers can deploy a working system skeleton… so all subsequent epics build on a consistent, tested foundation" | 🟡 **Borderline technical epic.** Epic 1 is genuinely infrastructure-only. BMAD purists would flag this; the OEBB epic acknowledges it explicitly. Accepted because PoC needs MQTT broker, event envelope, DB schema and CI before any UI works; deferring would be worse than admitting it |
| 1.5 — Onboard Containerised Infrastructure | Bridge between Epic 1 (landside) and Epic 4 (onboard) | 🟡 **Technical bridge epic.** Same caveat. Listed as Done so this is post-hoc; accepted |
| 2 — CC Dashboard Live Operations | "Control Centre operators can monitor the full fleet in real time" | 🟢 Clear user value (Claudia) |
| 3 — CC Dashboard Analytics & System Health | "Operators and capacity planners can analyse historical exceptions…" | 🟢 Clear user value |
| 4 — Onboard Edge Pipeline | "The system detects occupancy, congestion, luggage… producing structured events" | 🟡 Stated as system-centric. Should be reframed: "Conrad receives real-time onboard occupancy and safety alerts in the Control Centre" — same outcome, user-centric framing |
| 5 — Luggage Monitoring | Not defined in epics.md (only listed in table) | 🔴 **Quality gap** — missing epic statement |
| 6 — Fusion Hardening | "Long-running PoC sessions do not accumulate incorrect state or drop events silently" | 🟡 Hardening epic — acceptable post-PoC sprint scope; cleanly scoped |
| 7 — Retry & Idempotency Hardening | Cross-container correctness fix | 🟡 Hardening — acceptable |
| 8 — Analytics UI Hardening | Stale-fetch / re-render fix | 🟡 Hardening — acceptable |
| 9 — Container & Infrastructure Hardening | Index, HEALTHCHECK, batching | 🟡 Hardening — acceptable |
| 10 — Operator Adoption & Trust | "Operator changes how they run trains because of it" | 🟢 Strong user-outcome framing — best epic in the set |
| 11 — CC Admin & Identity | Placeholder; "Introduce auth, user management, admin/configuration surface" | 🟡 Acceptable placeholder, but no detailed stories yet — explicit `backlog` status correctly flagged |

### B. Epic Independence Check

| Pair | Tested independence | Verdict |
|---|---|---|
| Epic 1 → standalone | Yes — E1-S1 to E1-S7 deliver foundational substrate without UI | 🟢 |
| Epic 2 → needs Epic 1 only? | Epic 2 stories depend on E1-S1 (skeleton), E1-S6 (WS), E1-S7 (auth). No forward refs to Epics 3+ | 🟢 |
| Epic 3 → needs Epic 1+2? | Epic 3 stories depend on E1-S3, E1-S7, E1-L1, plus E2-S1 (FleetContext). E3-S7 mentions E2-S1 (acceptable). **E2-S9 depends on E3-S1** — a forward dep from Epic 2 to Epic 3 | 🔴 **Forward dependency** |
| Epic 4 → independent of Epic 2/3? | Stated as "Can run in parallel with Epics 2–3 against MockAPCAdapter". Stories depend on Epic 1 only. E4-S10 (`COACH_COMFORT_INDEX`) targets CC analytics consumption — that's a forward consumer, not a forward dep | 🟢 |
| Epic 5 → ? | No epic-level dependency declared (epic body missing) | 🔴 Cannot evaluate |
| Epics 6–9 → hardening epics | Each cites the original story it hardens (E4-S6 → E6-S1 etc.). Dependencies flow correctly | 🟢 |
| Epic 10 → ? | E10-S1 depends on E4-S5, E4-S6, E2-S5, E2-S9, E3-S6. E10-S2 depends on E10-S1, E2-S5, E3-S1. E10-S5 depends on E10-S1, E10-S2, E2-S5. All upstream | 🟢 |
| Epic 11 → ? | Placeholder; no stories yet. Marked as `backlog` and "does NOT block E10" — clean | 🟢 |

**Critical finding — E2-S9 ↔ E3-S1 ordering:**
- E2-S9 (System Health Data Feed) is in Epic 2 but its `Backend required:` is `GET /api/v1/analytics/system-health` covered by E3-S1
- E3-S1 (Analytics REST Endpoints) is in Epic 3
- This violates the "Epic N cannot require Epic N+1" rule
- **Remediation:** Either (a) move E2-S9 to Epic 3 (better — it's a SystemHealth view, which is conceptually Epic 3 territory), or (b) move the `/system-health` endpoint definition out of E3-S1 into Epic 2 (worse — splits analytics endpoints across epics)
- **Recommendation: move E2-S9 to Epic 3 and renumber as E3-S0 or E3-S8.**

### C. Story Sizing & Independence

| Story | Concern | Severity |
|---|---|---|
| E1-S1 (E2E Skeleton MVP) | Covers FastAPI startup + WebSocket stub + DB migrations + ruff + mypy + pytest coverage gate + docker-compose + Dockerfile base image. This is 5–7 concerns in one story | 🟠 **Oversized.** Justifiable as "root story that nothing parallels", but could be split into E1-S1a (compose + Dockerfiles), E1-S1b (FastAPI + WS stub), E1-S1c (CI/lint/coverage) for cleaner reviews |
| E2-S8 (Per-Operator Threshold) | Adds Alembic migration + 2 API endpoints + new component + localStorage + keyboard handling. Touches 4 files. Dependencies span E1-S3, E1-S7, E2-S1, E2-S5 | 🟡 Large but coherent |
| E3-S1 (Analytics REST Endpoints) | Defines 5 endpoints in one story. Each has its own response shape, error handling, integration tests | 🟠 **Oversized — recommend split** into 5 stories (one per endpoint). Otherwise reviewing or rolling back one endpoint becomes risky |
| E4-S6 (Fusion Correlation & Suppression) | One epic story for: suppression state machine, door obstruction, occupancy fusion (with ADR-15 change), enrichment, depot handling, speed escalation. 6 modules touched | 🟠 **Oversized.** Suppression vs. door obstruction vs. occupancy fusion are distinct verifiable behaviours |
| E4-S7 (event-store API + WS) | POST events, GET events, GET journeys, WS handler, WS replay all in one. Concurrency test required | 🟠 **Oversized** |
| E10-S1 (Confidence Metadata + Kill-Switch + AI Pipeline Health) | Refined to "code-only with three discrete UI surfaces" but still: shared schema change + new event type + cloud-backend table + admin endpoint + 3 UI components | 🟠 **Oversized — already partially refined.** Full 24-AC story file referenced separately. Recommend a final split into E10-S1a (shared schema + inference heartbeat), E10-S1b (kill-switch backend), E10-S1c (CC UI surfaces) |

### D. Acceptance Criteria Quality

Sample-reviewed E1-S1, E2-S1, E4-S6, E10-S1.

| Criterion | Finding |
|---|---|
| BDD Given/When/Then format | ✅ Followed consistently across Epic 1, 2, 3, 4, 6, 7, 9, 10. Hardening epics use the same structure |
| Testable | ✅ Most ACs name explicit assertions (`HTTP 201`, `exit 0`, ``(`status_code: 422`)) |
| Error paths covered | ✅ Each story has at least one failure path (API 4xx/5xx, timeout, disconnect, invalid input) |
| Specific verifiable outcomes | ✅ Strong (e.g. E4-S6 occupancy.py "weight_camera and weight_apc config parameters are removed") |
| OEBB-domain-specific | ✅ FR-traceable (journey_id midnight crossing test, ADR-18 trigger logic, NFR3 suppression state machine) |

**Minor concerns:**
- E1-S1 AC about coverage: "≥80% coverage of the lines that exist". For a skeleton that's <100 LOC of real code, this is trivially met; an attacker could meet the gate without meaningful tests. Add: at least 1 integration test must exist
- E2-S8 (preferences) does not cover the case where the operator changes the threshold mid-pulse — does the pulsing red pill restart its 60s timer from the new threshold, or carry over? Edge case worth specifying

### E. Forward Dependency Audit

| Story | Stated dep | Type | Verdict |
|---|---|---|---|
| E2-S9 | E3-S1 backend endpoint | **Forward** (Epic 2 → Epic 3) | 🔴 Violation (already flagged in §B) |
| E2-S5 | E1-S7 backend auth | Upstream | ✅ |
| E2-S6 | E1-S7 | Upstream | ✅ |
| E2-S8 | E1-S3 migration | Upstream | ✅ |
| E3-S2..S5 | E3-S1 | Same epic, upstream | ✅ |
| E3-S7 | E2-S1 (operator session context) | **Forward** (Epic 3 → Epic 2) | 🟢 Acceptable — E2-S1 lands before Epic 3 |
| E4-S6 | E4-S5 (developed together; "interface contract is defined here") | Same epic, parallel | 🟡 Concurrent — non-blocking but introduces story-interleave risk |
| E10-S1 | E2-S5, E2-S9, E3-S6 | Upstream (earlier epics) | ✅ |
| E10-S4 | Conductor App epic (deferred Phase 2) | **Cross-phase forward dep** | 🟡 Acceptable — story explicitly ships only payload + CC tile + Conductor stub; UI gated |

### F. AC OEBB Domain-Specificity (per CLAUDE.md story standards)

Every reviewed story carries at least one OEBB-domain test scenario:
- E1-S2: journey_id midnight crossing test
- E4-S1: trip 23:45 → event 00:05 same journey_id assertion
- E4-S6: maintenance→normal suppression transition with simultaneous conditions
- E4-CS1: 72h offline buffer + 100-event drop test
- E1-S4: SIGKILL before truncate, restart, assert events 1–50 still present

This is **above-average rigour**. Story templates clearly demand OEBB-specific failure scenarios.

### G. Findings Summary

#### 🔴 Critical (must fix before any Tier-3 dev action)

1. **WebSocket vs SSE transport conflict** (already flagged in UX Alignment — repeated for emphasis). Until resolved, every "WS" story in Epic 1 and Epic 2 is built on a contested assumption. Blocking.
2. **E2-S9 forward dependency on E3-S1.** Move E2-S9 to Epic 3.
3. **Epic 5 (Luggage) and Epic 1.5 lack epic-level definition in epics.md.** Backfill from `_bmad-output/implementation-artifacts/` for traceability.

#### 🟠 Major (should fix before pilot start)

4. **5 missing FRs** (FR23, FR25, FR32, FR34, FR35) — either descope to Phase 2 in PRD §5.4 or add stories. Recommendation: descope all five (Phase 2).
5. **3 oversized stories** (E3-S1, E4-S6, E4-S7) — recommend splits for safer reviews and incremental ship.
6. **NFR2/ADR-15 conflict** — update NFR2 wording so APC is the post-hoc calibration mechanism, not real-time blender.

#### 🟡 Minor (cosmetic / improvement)

7. **Epic 4 framing** could be user-centric instead of system-centric.
8. **E1-S1 coverage gate** is trivially passable; add a minimum-integration-test count.
9. **UX v2 doc** should carry a "Phase 2 Vision — not PoC scope" header to prevent stakeholder confusion.
10. **FR11 and FR22** need explicit ACs (combined wheelchair-door-release; live dwell vs. historical dwell intent).

---

## Summary and Recommendations

### Overall Readiness Status

**🟡 NEEDS WORK — Conditionally Ready**

Phase 1 PoC implementation is substantially in motion (Epics 1–5 marked Done; hardening Sprint 1 active). The four planning artifacts (PRD, Architecture, Epics, UX) exist, are mutually consistent in 79% of FRs and 100% of UX-DRs, and are anchored to ADRs and a locked prototype (DD-001). However, **three critical gaps remain that should be resolved before more Epic 2/3 backend stories ship or before any pilot signoff:**

1. **Transport conflict (WebSocket vs SSE)** — must be resolved this week.
2. **5 in-scope FRs are not covered by any story** — descope or commit.
3. **Epic 5 and Epic 1.5 are listed as Done but lack detailed epic specs in `epics.md`** — traceability is broken.

The work itself is high quality: BDD-format ACs, OEBB-domain failure scenarios in every story, ADR-anchored architectural decisions, and a tested prototype. The gaps are largely **planning-artifact hygiene** rather than design holes.

### Critical Issues Requiring Immediate Action

| # | Issue | Owner | Action |
|---|---|---|---|
| 1 | WebSocket vs SSE transport conflict (PRD §9 vs CLAUDE.md container map) | Winston (Architect) + John (PM) | Hold a 30-minute decision meeting; update PRD §9 OR update CLAUDE.md and Epic 1/2 stories. **Decision blocks Epic 2 hardening progress and Epic 11.** |
| 2 | Forward dependency E2-S9 → E3-S1 | John (PM) | Move E2-S9 into Epic 3 (renumber as E3-S8). Update epics.md table. |
| 3 | Epic 5 and Epic 1.5 missing epic-level definitions | Paige (Tech Writer) | Backfill epic body + per-story ACs in epics.md from `_bmad-output/implementation-artifacts/5-*` and `1-5-*`. Low effort — content already exists. |
| 4 | 5 FRs without coverage (FR23, FR25, FR32, FR34, FR35) | John (PM) | Default recommendation: descope all five to Phase 2 in PRD §5.4 with a one-line rationale per FR. Each remains achievable post-PoC. |
| 5 | NFR2 / ADR-15 conflict (APC blending) | Winston | Update NFR2 wording: "Occupancy accuracy ≥95% measured post-hoc against APC ground truth (calibration-only; not real-time blending)". Add an analytics story measuring camera-vs-APC delta. |

### Major Issues — Address Before Pilot Start

6. **E3-S1, E4-S6, E4-S7 oversized stories** — split each into 2–3 stories for safer reviews and cleaner rollback boundaries.
7. **E10-S1 oversized** — already noted in the story header; commit to the three-way split (E10-S1a/b/c).
8. **FR11 partial coverage** — add an explicit fusion AC for the wheelchair-door-release combined alert.
9. **FR22 ambiguity** — clarify whether "real-time dwell time" means live during dwell or historical post-stop; update story accordingly.

### Minor Issues — Cleanup Pass

10. Epic 4 framing — reword as user-outcome statement.
11. E1-S1 coverage gate — add minimum integration test count.
12. UX v2 doc — add "Phase 2 Vision — not PoC scope" header.
13. Open Questions Q5, Q7–Q9, Q11, Q12 — close before pilot; some are referenced as gating for FR23 and System Health badge logic.

### Recommended Next Steps (Sequence)

1. **Convene transport decision meeting** (Winston + John, 30 min). Document decision in an ADR-19, update PRD §9 if SSE is chosen, update CLAUDE.md if WebSocket is chosen. *Blocking — this week.*
2. **PRD revision pass** — descope FR23/FR25/FR32/FR34/FR35 to §5.4 (Phase 2); fix NFR2 wording; close decision Q5/Q7/Q8/Q9 inline. *Within 1 week of #1.*
3. **Epic backfill** — Paige adds Epic 5 and Epic 1.5 to epics.md; John moves E2-S9 to Epic 3 and renumbers. *Concurrent with #2.*
4. **Story split pass** — split E3-S1, E4-S6, E4-S7, E10-S1 before any further code review on those scopes. *Within 1 week.*
5. **Re-run `bmad-check-implementation-readiness`** after #1–#4 — readiness should hit 🟢 READY.
6. **Pilot pre-flight** — once Epic 10 lands, run E10-S3 SOP drills before any ÖBB signed pilot date.

### Coverage Headline

| Dimension | Coverage |
|---|---|
| In-scope PRD FRs | 79% (67% full + 12% partial) |
| NFRs | 93% (1 conflict to fix) |
| UX-DRs (against DD-001 contract) | 100% |
| Epic story-level traceability | 75% (Epic 5 + Epic 1.5 gap) |
| Forward dependencies | 1 violation (E2-S9 → E3-S1) |
| AC quality (BDD + OEBB domain) | Above-average rigour |
| Open Questions resolved | 0 of 12 — none individually blocking, but Q5 is needed for FR23 if FR23 stays in scope |

### Final Note

This assessment identified **3 critical**, **6 major**, and **4 minor** issues across requirement coverage, architectural alignment, and planning-artifact hygiene. The PRD, Architecture, Epics, and UX are in genuinely good shape — the work flagged here is artifact maintenance and resolving a small number of contested decisions, not a redesign. Address items #1–#5 before further Epic 2/3 backend work, and the project will be **ready for production-track implementation** under the current PoC scope.

Address the critical issues before proceeding to implementation. These findings can be used to improve the artifacts or you may choose to proceed as-is.

---

**Assessment date:** 2026-05-30
**Assessor:** John (Product Manager) via bmad-check-implementation-readiness
**Prior assessment:** 2026-05-17 (this report supersedes)
