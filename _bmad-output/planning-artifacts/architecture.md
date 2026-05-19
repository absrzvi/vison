---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: COMPLETE
lastUpdated: '2026-05-16'
updateReason: 'Control Centre Dashboard component structure updated to match DD-001 (post-prototype acceptance)'
inputDocuments:
  - project-context.md
  - _bmad-output/design-artifacts/A-Product-Brief/product-brief.md
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md
  - _bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md
  - _bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md
  - docs/handoff/2026-05-14-oebb-smart-rail-v3-handoff.md
  - docs/superpowers/specs/2026-05-14-onboard-inference-pipeline-design.md
workflowType: 'architecture'
project_name: 'oebb-agent'
user_name: 'AbbasRizvi'
date: '2026-05-14'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Pilot Scope (PoC Boundaries)

**Deployment:** Single vehicle only. Multi-CCU coupled-train topology is explicitly out of scope for the PoC. Design for it, but do not implement it.

**Interfaces in scope (5):**
| Interface | Primary user | PoC purpose |
|---|---|---|
| Conductor App | Conrad (Train Manager) | Core operational use — real user, real workflow |
| Passenger Portal | — | Client presentation / demo screen (not live passenger use in PoC) |
| PIS exterior + interior screens | Passengers | Real display output — table-stakes for "smart train" demo |
| Control Centre Dashboard | Claudia (Control Centre) | Operational use + ÖBB stakeholder demo |
| Driver Display | Driver | Read-only passthrough — safety requirement |

**Interfaces descoped from PoC:** Bistro App, Maintenance Dashboard.

---

### Pilot Success Criteria

| Criterion | Measurement approach |
|---|---|
| Reduced dwell time | Compare pre/post station stop duration using APC door-open/close timestamps per stop. Baseline to be established in PoC weeks 1–2. |
| Reduced passenger congestion | Occupancy delta per coach per stop; vestibule congestion alert frequency; conductor response time to congestion alerts |
| Reduced luggage congestion | Luggage rack saturation alert frequency; unattended bag alert false-positive rate |

> **Note:** Specific reduction thresholds (% dwell time saved, congestion incidents per journey) are a commercial agreement between Nomad Digital and ÖBB — not architecture inputs. The architecture must ensure these metrics are *measurable* from day one. All events must carry sufficient timestamp and location metadata to support post-hoc analysis.

---

### Requirements Overview

**Functional Requirements (PoC scope):**

The Passenger Intelligence Service delivers six capabilities, all running on the single Hailo-8 M.2 on SYS2:

| Capability | Data sources | Interface consumers |
|---|---|---|
| Live occupancy (per-coach headcount) | CCTV VLAN 5 + APC VLAN 8 | Conductor App, PIS, Control Centre, Driver Display |
| Luggage detection + unattended bag alert | CCTV VLAN 5 | Conductor App, Control Centre |
| Congestion mapping (vestibule + coach) | CCTV + APC fusion | Conductor App, PIS, Passenger Portal, Control Centre |
| Door obstruction detection | CCTV VLAN 5 + ZFR VLAN 2 | Conductor App, Control Centre |
| Accessibility detection (wheelchair/pushchair + ramp) | CCTV VLAN 5 + TCMS VLAN 7 | Conductor App, Passenger Portal |
| Stadler/TCMS alarm ingestion | SNMP VLAN 7 | Conductor App, Control Centre |

**Non-Functional Requirements:**

| NFR | Target | Architectural implication |
|---|---|---|
| Uptime | ≥99.5% | Docker restart policies; graceful degradation on SYS1 loss |
| Occupancy accuracy | ≥95% | APC fusion for ground truth calibration; `APCAdapter` interface |
| False-positive rate | <5% | Formal suppression state machine (see §Cross-Cutting Concerns) |
| Alert latency | Within station dwell window (~30–90s) | Local inference + local API serving; no cloud round-trip for alerts |
| Privacy | Raw video never leaves train | Edge-only inference; structured anonymised events to cloud only |
| GDPR | Anonymised aggregate only to cloud | Events tagged with metadata now; deletion/anonymisation policy applied when legal signs off — do not block architecture |
| Rail environment | -40°C to +85°C | Hailo-8 M.2 confirmed rail-compliant |
| Connectivity resilience | Onboard UX fully functional when SYS1 is down | Offline-first for all 4 onboard interfaces; cloud-dependent interfaces (Control Centre Dashboard) degrade gracefully |

---

### Technical Constraints

| Constraint | Detail |
|---|---|
| Edge hardware | Single Hailo-8 M.2 (26 TOPS, PCIe Gen 3 x4) on ADLINK cPCI-A3H20 blade, SYS2 |
| Host OS | Debian 12 + Docker |
| Runtime | HailoRT + TAPPAS |
| Container architecture | 5 containers: `rtsp-ingest`, `vlan-pollers`, `inference`, `fusion`, `event-store` |
| Local data store | SQLite, journey-scoped |
| API | REST + WebSocket, served from `event-store` container |
| Cloud sync | Via SYS1, structured events only |
| Model quantization | INT4 vs INT8 — TBD (requires camera count + TOPS budget analysis before inference ADR) |
| PoC topology | Single vehicle; multi-CCU deferred |

---

### Open Dependencies (tracked, not blocking architecture)

| Dependency | Impact | Resolution path |
|---|---|---|
| APC data format (VLAN 8) | Fusion container ground-truth reconciliation | Stub via `APCAdapter` interface + `MockAPCAdapter`; swap real adapter when format confirmed from AFZ supplier |
| TCMS alarm name list (project-specific STADLER-IM-MIB_Configuration.xlsm) | `vlan-pollers` schema completeness | vlan-pollers uses placeholder schema; finalize when Stadler supplies the OEB fleet alarm list |
| L2 write access to PIS exterior/interior screens | All PIS scenario outputs | Confirm with Stadler/ÖBB network team during PoC |
| Camera count per tier per train | Hailo-8 TOPS budget allocation | Confirm from R5001C hardware spec; required before inference container ADR is finalized |
| Cloud backend hosting (Nomad-owned vs Azure/AWS) | Cloud sync retry logic, event schema versioning | Event envelope format must be locked independently of hosting decision |
| GDPR sign-off from ÖBB legal | Anonymised data sync to cloud | Tag events correctly now; do not block on legal sign-off |
| ÖBB pilot baseline metrics | Dwell time / congestion reduction measurement | Establish empirically in PoC weeks 1–2; architecture must instrument events to support it |

---

### Cross-Cutting Concerns

1. **Suppression state machine** — Not a shared library concern; a *correctness* requirement. Maintenance mode, coupling-in-progress (PoC: N/A), GPS invalid, `im0vstDegradedOperation`, `im0vstShutdownAll` — all affect multiple alert types. Must be a formal state machine with explicit transitions, documented in the architecture. ÖBB operational sign-off required on transitions before implementation.

2. **Journey scoping** — `im0triTripNumber` is the primary event key. All events keyed to trip ID. Affects event store schema, cloud sync batching, GDPR deletion scope, UI filtering, and analytics. Journey scope must be defined before event-store schema ADR.

3. **Connectivity resilience** — SYS1 may be unavailable (tunnels). Onboard interfaces (Conductor App, PIS, Passenger Portal, Driver Display) must work fully offline. Control Centre Dashboard is cloud-dependent and degrades gracefully. The staleness boundary (acceptable stale data window for onboard alerts) is an operational question for ÖBB — must be agreed before Conductor App offline design is finalized.

4. **Event envelope and cloud sync semantics** — Cloud hosting decision is deferred; event envelope format is not. Trains reconnect after tunnels; the cloud backend must handle idempotent writes and out-of-order delivery. Event envelope format and delivery semantics must be locked before event-store schema ADR, independently of hosting choice.

5. **Authentication and access control** — 5 roles with different trust levels. Onboard interfaces run on VLAN 30 (staff network) and VLAN 10 (passenger WiFi / portal). Auth boundary: VLAN isolation vs. token-based — must be decided before API/WebSocket ADR. In offline mode (SYS1 down), Conductor App must still be able to authenticate locally.

6. **Camera priority scheduling and Hailo-8 budget** — P1 (door/vestibule, 10fps always), P2 (interior, 5fps always), P3 (exterior/platform, 8fps station-window only). Camera count per tier is unconfirmed. Budget management signal must flow from `vlan-pollers` → `inference` or be internal to `inference` — this inter-container decision affects the container interface design and must be resolved before the inference ADR.

7. **SQLite write contention** — `fusion` and `event-store` containers share the SQLite DB. WAL mode handles one writer at a time. At 10fps door events + concurrent APC/TCMS writes, lock contention is a real risk. Inter-container write protocol (direct write vs. queue) must be decided before the data layer ADR.

8. **Passenger Portal as demo surface** — Portal is a client presentation screen in the PoC, not live passenger use. This changes its technical requirements: optimised for visual clarity and demo reliability, not 24/7 passenger resilience. Design accordingly; do not over-engineer for production passenger load during pilot.

---

## Starter Template & Technology Foundations

### Primary Technology Domain

Edge AI pipeline (Python + Docker on Debian 12) + cloud hybrid backend + 5 web UI surfaces. Not a standard web app scaffolding problem — each layer addressed separately.

---

### Onboard Container Scaffold

| Decision | Choice | Rationale |
|---|---|---|
| Base image (all 5 containers) | `python:3.11-slim-bookworm` | Debian 12-aligned, minimal footprint, HailoRT-compatible |
| API framework | FastAPI + Uvicorn (`event-store` only) | One HTTP surface onboard — no other container exposes an HTTP port |
| Inter-container HTTP client | `httpx>=0.27` (async) — **mandatory** | Prevents `requests` (sync/GIL-blocking) or `aiohttp` drift across containers |
| Event loop model | `asyncio` — **all containers** | Explicit standard; Trio/Twisted banned without ADR |
| Container orchestration | `docker-compose` | Appropriate for single-vehicle PoC on constrained CCU hardware |
| Tooling | `pyproject.toml` + `pytest` + `ruff` | Shared template across all 5 containers |
| `ruff` config | `select = ["E", "F", "I", "UP"]`, `line-length = 100` | `UP` catches Python 3.11 upgrade opportunities automatically |
| `pytest` config | `--tb=short --strict-markers` | Strict markers prevent silent test skips |
| Coverage gate | `pytest-cov --cov-fail-under=80` | 80% enforceable on PoC; 100% creates fixture bloat |

**No framework** for `rtsp-ingest`, `vlan-pollers`, `inference`, `fusion` — pure Python pipeline stages. Framework surface area is not warranted for non-HTTP services.

**Python GIL note:** Hailo-8 offloads inference from CPU, significantly reducing GIL contention between `rtsp-ingest` and `inference`. Docker CPU affinity is part of the deployment spec if profiling reveals contention. Multiprocessing is off-limits for PoC — document and revisit if fusion latency becomes a production concern.

**Container startup race:** Containers start in parallel; `inference` and `fusion` may POST to `event-store` before it is ready. All outbound HTTP clients must implement exponential backoff with health-check loop. This is a P1 implementation requirement.

---

### SQLite Single-Writer Pattern (P0 ADR)

**Decision:** `event-store` container is the **sole write authority** for SQLite. All other containers write via HTTP POST to `/events` — never via direct file access.

**Rationale:** WAL mode serialises writes; concurrent file access from multiple containers will produce `SQLITE_BUSY` under burst conditions (inference at 10fps + APC + TCMS writes). Option A (single-writer via HTTP) is cleaner than connection pooling or introducing a broker for PoC scope.

**pytest fixture note:** `sqlite3` WAL mode does not work with `:memory:`. All fixtures must use `tmp_path`-scoped DB files. Broken `:memory:` fixtures will silently pass without WAL semantics — document in contributing guide.

---

### APC Adapter Protocol (P1 ADR)

**Decision:** All APC data access goes through a typed `APCAdapter` Protocol. No production code calls APC directly.

```python
# apc/adapter.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class OccupancyReading:
    car_id: str
    count: int
    timestamp: str

class APCAdapter(Protocol):
    async def get_occupancy(self, car_id: str) -> OccupancyReading: ...
    async def get_door_state(self, car_id: str) -> DoorState: ...
```

A `MockAPCAdapter` ships with deterministic synthetic data. When APC format is confirmed, the real adapter is a single-file swap. All downstream tests use `MockAPCAdapter` — zero integration tests blocked on hardware.

---

### UI Surface Approach

| Interface | Serving context | Technology | Notes |
|---|---|---|---|
| Passenger Portal | SYS2 media server | Static HTML/CSS/JS | Demo screen for PoC — not live passenger use. Shared CSS single-file policy — no per-surface stylesheets |
| Conductor App | VLAN 30 (staff network), mobile browser | PWA served from SYS2 | Offline capable in principle. **PWA offline not validated in PoC — deferred to Phase 2.** SYS2 must emit correct `Cache-Control` headers; service worker cache version string must be tied to deploy |
| PIS exterior + interior | L2 display write | Static HTML templates | Pushed via L2 write API (pending network access confirmation) |
| Control Centre Dashboard | Cloud-hosted | React + Vite | **Only surface not offline-capable by design** — cloud WebSocket dependency is intentional and documented |
| Driver Display | SYS2 | Static HTML (read-only) | Zero interaction, minimal JS, safety requirement |

**Static file update path (PoC):** Static files are baked into Docker images and updated via redeployment. No CDN or live file-sync in PoC scope — document and revisit for fleet rollout.

---

### Cloud Backend Foundations

| Decision | Choice | Rationale |
|---|---|---|
| API framework | FastAPI + Uvicorn | Consistent with onboard; async WebSocket native |
| Database | PostgreSQL | Journey-scoped event store; idempotent ingestion |
| Schema strategy | Single `events` table with JSONB payload | Intentionally minimal — not migration-hardened for v1 |
| Idempotency | DB unique constraint on `(journey_id, event_type, source_timestamp)` | Application-level dedup is defence-in-depth only; DB constraint is authoritative |
| WebSocket reconnect | Client-side exponential backoff (Control Centre dashboard) | PoC default; server-side session management deferred to Phase 2 |
| PostgreSQL in CI | `testcontainers-python` | Do not mock the DB for integration tests |
| Hosting | **TBD** — Nomad-owned vs Azure/AWS | Event envelope format locked independently of hosting decision |

**Cloud backend is the only layer where hosting is deferred.** Event envelope format (idempotency key, journey scope, event type taxonomy) must be defined before event-store schema ADR regardless of hosting choice.

---

### Observability & Logging

**Decision:** Structured JSON logging to local file with `logrotate`, all 5 onboard containers. Explicit choice — not an oversight.

**Rationale:** Vehicles cannot always be SSH'd into during a tunnel. Structured logs enable post-hoc debugging from log files retrieved via SYS1 remote management. No log aggregation service in PoC scope.

**Minimum fields per log line:** `timestamp`, `container_name`, `level`, `event_type`, `trip_id` (if available), `message`.

---

### ADR Pre-Requisites (must be resolved before implementation ADRs)

| Item | Priority | Blocked on |
|---|---|---|
| Hailo-8 TOPS budget allocation per camera stream | P1 | **Resolved 2026-05-16: 25–30 cameras per train** — budget.py TOPS allocation can now be implemented |
| APC data format | P1 | AFZ supplier confirmation (stub unblocks ADR) |
| TCMS alarm name list | P1 | Stadler STADLER-IM-MIB_Configuration.xlsm for ÖBB fleet |
| Camera count per tier per train | P1 | **Resolved 2026-05-16: 25–30 cameras per train** — TOPS budget analysis can now proceed |
| Cloud backend hosting decision | P2 | Nomad Digital commercial decision |
| Source control platform (GitHub vs GitLab) | P1 | **Resolved 2026-05-16: GitLab** — CI/CD pipeline config will use GitLab CI/CD (.gitlab-ci.yml) |

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Event envelope schema and journey_id key scheme
- SQLite sync cursor pattern (atomicity of sync-then-truncate)
- WebSocket subscription contract and replay semantics
- Event type taxonomy (`events/types.py`)
- Onboard auth boundary

**Important Decisions (Shape Architecture):**
- Separate `journeys` table in PostgreSQL
- API versioning prefix
- Error envelope standard
- CI/CD platform
- Environment secret management
- Horizontal scale-out model

**Deferred Decisions (Post-PoC):**
- JWT / token-based onboard auth (Phase 2 trigger: first multi-conductor deployment or contractual security requirement from ÖBB)
- PWA offline validation (Phase 2)
- PostgreSQL HA / read replica for fleet scale (fleet rollout gate)
- Server-side WebSocket session management (Phase 2)

---

### Data Architecture

#### ADR-1: Event Envelope Schema

**Decision:** Canonical event envelope for all events written to SQLite and synced to cloud:

```json
{
  "event_id": "<uuid-v4>",
  "journey_id": "<vehicle_id>_<trip_number>_<journey_start_date_YYYYMMDD>",
  "vehicle_id": "<string>",
  "timestamp": "<ISO-8601 UTC>",
  "event_type": "<see Event Type Taxonomy>",
  "severity": "critical | warning | info",
  "source": "inference | fusion | vlan-pollers",
  "payload": { }
}
```

**Affects:** event-store schema, cloud sync buffer, PostgreSQL ingestion, all UI consumers.

#### ADR-2: journey_id Key Scheme

**Decision:** `{vehicle_id}_{trip_number}_{journey_start_date_YYYYMMDD}`

**Rationale:** Trip numbers reuse across days and routes. `journey_start_date` is the anchor — recorded by `vlan-pollers` when `trip_number` first appears, and held constant for the life of that journey. Event timestamp date is NOT used (prevents midnight-crossing key flip for journeys spanning 23:45–00:05).

**Implementation note:** `vlan-pollers` records `journey_start_date` at trip_number first-seen. All containers receive this from the context state object. Schema DDL must include a comment documenting the midnight-crossing decision.

**Test required:**
```
tests/unit/test_journey_id.py
- Assert journey_id is stable when trip_number is unchanged but wall-clock date rolls past midnight
- Fixture: trip starting 23:45, event at 00:05, same trip_number
- Expected: journey_id does NOT change mid-journey
```

#### ADR-3: PostgreSQL Schema Strategy

**Decision:** Two tables for PoC:
- `journeys` — journey metadata (vehicle_id, trip_number, route_name, origin, destination, start_time, end_time)
- `events` — all events with JSONB payload, foreign key to `journeys.journey_id`

**Rationale:** Denormalizing journey metadata into every event payload is "convenient at ingestion, painful at query time." Separate table enables clean journey-level queries for the Control Centre analytics panel without parsing JSONB.

**Schema intentionally minimal — not migration-hardened for v1.** Revisit at fleet rollout.

**Fleet scale note:** PostgreSQL is shared state at the cloud boundary for all vehicles. At 50+ vehicles, a Postgres failover is a fleet-wide write outage. Acknowledge this now; address with read replicas / HA at fleet rollout gate.

#### ADR-4: SQLite Journey Archival — Sync Cursor Pattern

**Decision:** Sync-then-truncate with an explicit `sync_cursor` — NOT a naive two-operation sequence.

**Implementation:**
- `event-store` maintains a `sync_state` table with `last_synced_event_id` (updated atomically when cloud acks a batch)
- Truncation only removes rows where `event_id <= last_synced_event_id` AND ack is confirmed
- Keep last 3 journeys as debug buffer (ring buffer by journey_id)
- On restart: re-sync any events with `event_id > last_synced_event_id` — cloud DB idempotency constraint handles duplicates transparently

**Test required:**
```
tests/integration/test_sync_cursor.py
- Simulate cloud ack for events 1–50
- Kill process (SIGKILL) before truncate executes
- Restart — assert events 1–50 still present
- Assert events 1–50 are deduplicated on re-sync via DB unique constraint
- Assert no data loss across simulated tunnel disconnection cycle
```

#### ADR-5: Event Type Taxonomy

**Decision:** Canonical event type enum lives in `events/types.py`, shared across all containers. Append-only — new types require ADR review before adding.

**Initial taxonomy (extend as needed):**
```python
# events/types.py
from enum import StrEnum

class EventType(StrEnum):
    # Occupancy
    OCCUPANCY_UPDATE = "OCCUPANCY_UPDATE"
    OCCUPANCY_THRESHOLD_CROSSED = "OCCUPANCY_THRESHOLD_CROSSED"
    # Alerts
    ALERT_RAISED = "ALERT_RAISED"
    ALERT_RESOLVED = "ALERT_RESOLVED"
    # Congestion
    VESTIBULE_CONGESTION = "VESTIBULE_CONGESTION"
    LUGGAGE_RACK_SATURATION = "LUGGAGE_RACK_SATURATION"
    # Safety
    UNATTENDED_BAG = "UNATTENDED_BAG"
    DOOR_OBSTRUCTION = "DOOR_OBSTRUCTION"
    # Accessibility
    ACCESSIBILITY_DETECTED = "ACCESSIBILITY_DETECTED"
    RAMP_DEPLOYED = "RAMP_DEPLOYED"
    # TCMS / Alarms
    ALARM_ACTIVE = "ALARM_ACTIVE"
    ALARM_CLEARED = "ALARM_CLEARED"
    # Journey
    JOURNEY_STARTED = "JOURNEY_STARTED"
    JOURNEY_ENDED = "JOURNEY_ENDED"
    # System
    CAMERA_DEGRADED = "CAMERA_DEGRADED"
    CAMERA_RECOVERED = "CAMERA_RECOVERED"
    SYNC_COMPLETED = "SYNC_COMPLETED"
```

**Affects:** All containers, all UI consumers, cloud ingestion schema, analytics queries.

**Extended taxonomy (ADR-15/17/18 additions — 2026-05-17):**
```python
    # Counting / calibration
    CALIBRATION_DRIFT = "CALIBRATION_DRIFT"
    # Inter-wagon movement (ADR-17)
    WAGON_EXIT = "WAGON_EXIT"
    WAGON_ENTRY = "WAGON_ENTRY"
    LEDGER_DRIFT_ALERT = "LEDGER_DRIFT_ALERT"
    # Comfort (ADR-18)
    COACH_COMFORT_INDEX = "COACH_COMFORT_INDEX"
    # Internal commands (not persisted to SQLite, not published via MQTT)
    STREAM_PRIORITY = "STREAM_PRIORITY"
```

---

#### ADR-15: Camera-Based Primary Passenger Counting (2026-05-17)

**Decision:** Camera vision pipeline is the **primary and authoritative** source for passenger counting. APC (Automatic Passenger Counting) hardware data is a **calibration reference only** — it does not influence real-time occupancy counts.

**Mechanism:** Directional tripwire polygons are configured at each door threshold in `cameras.json`. The `inference` container uses the native `hailotracker` GStreamer plugin (Kalman+IoU, part of TAPPAS) to assign stable track IDs across frames. Track IDs flow through GStreamer buffer metadata into the Python callback layer. When a track ID crosses the entry or exit side of a door tripwire, the `local-fusion-engine` increments or decrements the coach passenger count atomically. The result is emitted as `OCCUPANCY_UPDATE`.

**APC role:** `vlan-pollers` continues to poll APC (VLAN 8) via `APCAdapter`. The APC count is compared to the camera-derived count on each APC poll cycle. If the delta exceeds a configurable threshold (default: ±10 passengers), a `CALIBRATION_DRIFT` event is emitted to `event-store` — flagging that zone configs may need recalibration. The APC count does **not** modify the live occupancy state.

**Phase 2 — Passenger Counting System Integration:** When an onboard passenger counting system feed is confirmed available, it replaces `MockAPCAdapter` as the calibration reference. The calibration comparison logic is unchanged.

**Supersedes:** The 70/30 camera/APC weighted average in `fusion/occupancy.py` is removed. `weight_camera` and `weight_apc` configuration parameters are removed. Camera count is the sole occupancy signal.

**Rationale:** Vision-primary enables directional boarding/alighting flows (not just net deltas), is measurable at door level, and is the correct foundation for a Hailo-8-based system.

**Test required:**
```
tests/unit/test_occupancy_primary.py
- Assert APC delta above threshold emits CALIBRATION_DRIFT event
- Assert APC delta does NOT modify occupancy count
- Assert camera-only count is used when APC is unavailable (MockAPCAdapter)
```

---

#### ADR-16: Spatial Zone Masking for Seated vs Standing Distribution (2026-05-17)

**Decision:** Per-coach seating occupancy distribution (seated vs standing) is calculated by intersecting `yolov8m.hef` bounding box coordinates with pre-configured static zone polygon masks — not by running pose estimation across all cameras.

**Rationale:** Deploying `yolov8m_pose.hef` across 25–30 streams would exhaust Hailo-8 TOPS budget and produce degraded accuracy due to high-back seat occlusion on ÖBB rolling stock. Static zone masks deliver equivalent seating vs aisle metrics at a fraction of compute cost.

**Pose estimation scope (unchanged):** `yolov8m_pose.hef` is restricted to P1 cameras covering accessibility spaces and vestibule fall-detection zones only.

**Zone config:** Static polygon masks are defined per coach type in `config/zones/{coach_type}.json`. Masks define `seating`, `aisle`, `vestibule`, and `door_threshold` polygons. Zone configs are **not updated per-frame** — they are loaded at container startup.

**Constraint:** `inference` container must assert at startup that zone configs exist for all configured coaches. Missing zone config → container refuses to start (logged at CRITICAL, not silently defaulted).

---

#### ADR-17: Inter-Wagon Movement Ledger Reconciliation (2026-05-17)

**Decision:** Passenger movement between coaches (wagons) is tracked via virtual directional tripwires at P1 gangway cameras, using a closed-ledger accounting model.

**Mechanism:**
1. Each gangway camera is configured with two tripwire polygons: one facing Coach N, one facing Coach N+1.
2. When a track ID crosses the Coach N exit polygon → `WAGON_EXIT` event emitted: `{ track_id, coach_from, coach_to, direction }`.
3. When the same track ID crosses the Coach N+1 entry polygon → `WAGON_ENTRY` event emitted.
4. The `local-fusion-engine` maintains a `coach_ledger` table in SQLite tracking net movement per coach per journey.
5. **Closed-ledger invariant:** The sum of all coach passenger counts must remain constant between station stops (no passengers appear or disappear mid-journey). Any variance triggers a `LEDGER_DRIFT_ALERT` event.
6. Before each station arrival (triggered by GPS/HAFAS proximity signal), the fusion engine reconciles ledger drift against seat zone mask counts and emits a corrected `OCCUPANCY_UPDATE` if the delta exceeds 2 passengers.

**PoC scope:** Gangway cameras must be identified in `cameras.json` with `"zone": "gangway"` and `"priority": "P1"`. Tripwire configs must exist in `config/zones/gangway.json`. The closed-ledger reconciliation logic is a **Phase 1 PoC deliverable** — it is required for accurate coach-level counts on long journeys.

**Schema additions:** `WAGON_EXIT`, `WAGON_ENTRY`, `LEDGER_DRIFT_ALERT` added to `EventType` enum.

---

#### ADR-18: Operational Telemetry Fusion Rules (2026-05-17)

**Decision:** The `local-fusion-engine` applies three operational triggers that cross-correlate VLAN telemetry with camera pipeline state:

**Trigger 1 — Door Release → Platform Camera Optimization:**
When VLAN 2/7 reports `doors_released = true` for a coach, `fusion` issues a `STREAM_PRIORITY` command to `rtsp-ingest` nominating the platform-facing cameras for that coach as high-priority for the duration of the dwell window. `rtsp-ingest` adjusts frame buffer allocation accordingly. `STREAM_PRIORITY` is an internal command — it is not written to `event-store` or published via MQTT.

**Trigger 2 — Coach Comfort Index:**
On each station approach (and on significant occupancy change), `fusion` computes a Coach Comfort Index per coach by joining:
- Camera-derived `occupied_seats` and `standing_count` (from zone mask counts)
- Reservation data from VLAN 6 (`reserved_seats` per coach via `vlan-pollers`)

The result is emitted as a `COACH_COMFORT_INDEX` event with payload: `{ car_id, reserved_seats, occupied_seats, standing_count, comfort_score }` where `comfort_score` is a float 0.0–1.0 (1.0 = all reserved seats occupied, no standing). Primary consumer: Control Centre Dashboard analytics. Phase 2: Conductor App.

**Trigger 3 — GPS/HAFAS Proximity Alert Escalation:**
When VLAN 7 GPS + HAFAS timetable data indicates the train is within 2 minutes of a scheduled station stop, any `ALERT_RAISED` event generated in that window receives `"priority": "escalated"` in its payload. This signals the Control Centre Dashboard to surface the alert with elevated urgency. The `priority` field is added to the `ALERT_RAISED` payload schema.

---

### Authentication & Security

#### ADR-6: Onboard Authentication

**Decision (PoC):** VLAN isolation only. Staff interfaces on VLAN 30 (Conductor App, Driver Display) are trusted by network membership. Passenger Portal on VLAN 10 (demo screen) has no auth.

**Rationale:** Token infrastructure (issuance, rotation, revocation) is disproportionate for a single-vehicle controlled PoC.

**Phase 2 trigger (explicit gate):** JWT required when ANY of the following is true:
- Multi-conductor deployment where per-conductor action attribution is required
- ÖBB contractual security requirement specifies token auth
- Conductor App moves to production passenger service

**Deferred work:** JWT implementation is a named Phase 2 story, not an open question.

#### ADR-7: Cloud Backend Authentication

**Decision (PoC):** API key authentication for Control Centre Dashboard → cloud backend. Single key per deployment, rotated on personnel change.

**Upgrade path:** OAuth2 / OIDC with ÖBB identity provider at fleet rollout. Architecture must not assume API key is permanent — no hardcoded key logic in business layer.

**Constraint:** API key must never appear in source control. Managed via `.env` file (PoC) or Docker secrets (fleet).

---

### API & Communication Patterns

#### ADR-8: REST API Versioning

**Decision:** `/api/v1/` prefix on all endpoints from day one.

**Rationale:** Costs nothing to add; avoids a breaking migration when the first v2 endpoint is needed. No unversioned routes permitted.

#### ADR-9: WebSocket Subscription Model

**Decision:** Client-driven subscription model. Clients declare interest at connection time; server filters delivery server-side.

**Subscription message spec:**
```python
# ws/subscription.py
from dataclasses import dataclass

@dataclass
class SubscriptionRequest:
    event_types: list[str]        # subset of EventType enum
    min_severity: str             # "info" | "warning" | "critical"
    coach_ids: list[str] | None   # None = all coaches
    reconnect_replay_depth: int = 50  # events to replay on reconnect
```

**Reconnect replay:** On WebSocket reconnection, server replays last `reconnect_replay_depth` events matching the subscription filter. Prevents silent gaps for safety-relevant events. Default 50 events; configurable per client.

**Rationale:** Eliminates silent data gaps on CCU restart or tunnel reconnection. Safety-relevant alerts (ALERT_RAISED, DOOR_OBSTRUCTION, UNATTENDED_BAG) must not be silently missed.

**Test required:**
```
tests/unit/test_ws_subscription_filter.py
- Assert events below min_severity are not delivered to subscriber
- Assert events not in event_types list are not delivered
- Assert reconnect replay delivers exactly last N matching events
- Assert no duplicate delivery if client was not disconnected
```

#### ADR-10: API Error Envelope

**Decision:** Standard error response for all REST and WebSocket error conditions:

```json
{
  "error": "<ERROR_CODE>",
  "detail": "<human-readable description>",
  "recoverable": true | false
}
```

`recoverable: true` = client should retry or degrade gracefully.
`recoverable: false` = requires operator intervention.

**Affects:** All API consumers. All containers must use this envelope — no ad-hoc error formats.

---

### Infrastructure & Deployment

#### ADR-11: Container Orchestration

**Decision:** `docker-compose` for PoC deployment on single-vehicle CCU.

**Rationale:** Appropriate for constrained hardware, single-vehicle scope. No Kubernetes or Swarm overhead warranted for PoC. Nomad Digital's existing SYS1 remote management handles container health monitoring and image updates.

**Fleet rollout note:** docker-compose per vehicle is viable at fleet scale (each CCU is independent). Orchestration upgrade only needed if cross-vehicle coordination is required — explicitly not in scope.

#### ADR-12: CI/CD Pipeline

**Decision:** **GitLab CI/CD** (confirmed 2026-05-16). Pipeline config will use `.gitlab-ci.yml` with GitLab Container Registry (GCR) for Docker images. Ruff, mypy --strict, bandit, detect-secrets, and pytest stages as documented in ADR-14 quality gates.

**Constraint:** Pipeline YAML unblocked — platform confirmed.

#### ADR-13: Environment & Secret Management

**Decision:**
- PoC: `.env` files per deployment. Must never contain production credentials.
- Fleet: Docker secrets.
- `pre-commit` hook using `detect-secrets` baseline — blocks commit if `.env` contains strings matching `password|secret|key|token|credential`.

**Separation discipline:** PoC `.env` uses development/staging credentials only. Production credentials enter only via Docker secrets at fleet rollout.

#### ADR-14: Horizontal Scaling Model

**Decision:** Horizontal scale-out by vehicle. Each CCU runs the full stack independently. No shared state between CCUs onboard.

**Shared state exists only at the cloud boundary** (PostgreSQL). This is an intentional architectural decision — acknowledged fleet-scale implication: PostgreSQL HA must be addressed before fleet rollout, not during.

---

### Decision Impact Analysis

**Implementation sequence (ordered by dependency):**

> **Dev priority decision (2026-05-16):** Control Centre Dashboard is the first interface to build. It drives WebSocket API contract design and provides an early stakeholder demo surface. Conductor App follows once the event-store API is stable.

1. `events/types.py` — EventType taxonomy (all containers depend on this)
2. Event envelope schema + `journey_id` scheme (event-store schema, sync buffer)
3. `journeys` + `events` PostgreSQL DDL with idempotency constraint
4. `sync_state` table + sync cursor logic in event-store
5. `APCAdapter` Protocol stub + `MockAPCAdapter`
6. WebSocket subscription spec + `SubscriptionRequest` dataclass
7. FastAPI routes + WebSocket handler in event-store
8. **React + Vite Control Centre Dashboard** ← first interface (depends on event-store WebSocket API; camera/inference data can be mocked)
9. `rtsp-ingest` container (camera count confirmed: 25–30/train)
10. `vlan-pollers` container (TCMS taxonomy partially blocked on Stadler alarm list)
11. `inference` container (TOPS budget now unblocked: 25–30 cameras/train)
12. `fusion` container (depends on APCAdapter, inference output schema)
13. GitLab CI/CD pipeline (.gitlab-ci.yml)
14. PWA Conductor App (depends on event-store REST + WebSocket API)

**Cross-component dependencies:**

| Decision | Depends on | Blocks |
|---|---|---|
| journey_id scheme | `vlan-pollers` recording `journey_start_date` | All events, cloud sync, PostgreSQL schema |
| Event taxonomy | Architecture ADR (this doc) | All containers, all UI consumers |
| APC Protocol stub | None — internal decision | `fusion` container, APC-dependent tests |
| WebSocket subscription spec | Event taxonomy | Conductor App, Control Centre Dashboard |
| SQLite sync cursor | Event envelope schema | Cloud sync reliability, truncation safety |
| Inference container | Camera count + TOPS budget | `fusion` container, all occupancy-dependent alerts |

---

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

9 areas where AI agents or developers could make contradictory local decisions without explicit rules: naming at the API boundary, DB column casing, endpoint pluralisation, event payload field naming, timestamp format, test file placement, container module structure, logging level semantics, retry implementation.

---

### Naming Patterns

**Python (all 5 onboard containers + cloud backend):**

| Element | Convention | Example |
|---|---|---|
| Variables, functions, methods | `snake_case` | `get_occupancy_reading` |
| Classes | `PascalCase` | `OccupancyReading` |
| Constants / enums | `UPPER_SNAKE_CASE` | `EventType.ALERT_RAISED` |
| Files and modules | `snake_case.py` | `apc_adapter.py` |
| Private functions/methods | `_leading_underscore` | `_validate_frame` |

**Database (PostgreSQL + SQLite):**

| Element | Convention | Example |
|---|---|---|
| Table names | `snake_case` plural | `events`, `journeys`, `sync_state` |
| Column names | `snake_case` | `journey_id`, `event_type`, `source_timestamp` |
| Foreign keys | `{ref_table_singular}_id` | `journey_id` |
| Indexes | `ix_{table}_{column(s)}` | `ix_events_journey_id` |
| Primary keys | always `id` | UUID string for events, serial for journeys |

**REST API endpoints:**

| Element | Convention | Example |
|---|---|---|
| Resource paths | Plural nouns | `/api/v1/events`, `/api/v1/journeys` |
| Path parameters | `snake_case` | `/api/v1/journeys/{journey_id}` |
| Query parameters | `snake_case` | `?event_type=ALERT_RAISED&min_severity=warning` |
| No verbs in URLs | HTTP method is the verb | `GET /events` not `GET /getEvents` |

**JSON field naming:**
- All JSON (onboard API + cloud API + event payloads): `snake_case`
- React frontend: converts to `camelCase` at the API client layer only — never in raw API responses
- Rationale: Python producers are authoritative; JS consumers adapt at their boundary

---

### Format Patterns

**Timestamps:**
- All timestamps: ISO-8601 UTC with `Z` suffix — `"2026-05-14T09:14:33Z"`
- No Unix timestamps in API responses or event payloads
- No local time at rest — always UTC; convert to local time in UI display only
- **Anti-pattern:** `datetime.now()` — produces naive datetime, timezone-unaware
- **Correct:** `datetime.now(timezone.utc)` — always

**API response envelopes:**

Success (list):
```json
{
  "data": [ ... ],
  "count": 42,
  "journey_id": "V1_4821_20260514",
  "next_cursor": "event_id_after_which_to_page | null"
}
```

Success (single item):
```json
{ "data": { ... } }
```

Error (ADR-10):
```json
{
  "error": "CAMERA_DEGRADED",
  "detail": "Coach C3 interior camera offline — occupancy estimate from APC only",
  "recoverable": true
}
```

**Pagination:** `next_cursor` required on all list endpoints. Cursor-based (not offset-based) — offset pagination breaks under concurrent event writes. `next_cursor: null` indicates last page.

**HTTP status codes:**

| Code | When to use |
|---|---|
| `200` | Successful GET; idempotent POST (including duplicate event ingestion) |
| `201` | Resource created (non-idempotent) |
| `400` | Client validation error |
| `404` | Resource not found |
| `429` | Rate limited (cloud sync path) — client must back off |
| `503` | Container not ready (startup race) — client must retry with backoff |
| `504` | Upstream timeout (cloud sync, SNMP poll) |
| `500` | Unexpected server error — log, return `recoverable: false` |

**API versioning and deprecation:**
- All routes prefixed `/api/v1/` from day one
- When v2 is needed: v1 and v2 coexist for one full release cycle; v1 removed only after all clients have migrated
- Deprecation signalled via `Deprecation: true` response header on v1 routes before removal

---

### Structure Patterns

**Python container layout (all 5 onboard containers + cloud backend):**

```
{container_name}/
  src/
    {container_name}/
      __init__.py
      main.py           # entry point; wires dependencies
      config.py         # pydantic-settings env var loading
      models.py         # dataclasses / Pydantic models (no I/O)
      {domain}.py       # domain logic modules (I/O injected)
  tests/
    unit/               # pure logic, no I/O
    integration/        # real SQLite / real HTTP / testcontainers
    contract/           # schema version compatibility tests
  Dockerfile
  pyproject.toml
  .env.example          # committed template; .env is gitignored
```

**Tests in `tests/` directory — NOT co-located with source.** Rationale: Docker build context excludes `tests/` cleanly; co-located test files leak into production images.

**Shared code monorepo directory:**

```
shared/
  events/
    types.py            # EventType enum (ADR-5) — append-only
    envelope.py         # Event dataclass with schema_version
  adapters/
    apc/
      base.py           # APCAdapter Protocol / ABC
      mock.py           # MockAPCAdapter (deterministic fixtures)
    pis/
      base.py           # PISAdapter Protocol
      mock.py
  ws/
    subscription.py     # SubscriptionRequest dataclass
  http/
    retry.py            # tenacity defaults and primitives
```

**React + Vite (Control Centre Dashboard):**

```
control-centre/
  src/
    api/                # fetch client + camelCase converters (boundary only)
    components/         # organised by feature, not by type
    hooks/              # useEvents, useJourney, useWebSocket
    types/              # TypeScript interfaces (camelCase)
  tests/
    unit/
    e2e/                # Playwright
```

---

### Communication Patterns

**Event schema versioning:**
- `Event` dataclass in `shared/events/envelope.py` MUST include `schema_version: int`
- Current version: `1`
- Consumers MUST reject events where `schema_version` is not in their supported set — log at `WARNING` with `recoverable: True`, do not crash
- Producers MUST NOT remove fields without a deprecation cycle (add field, release, remove field in next release)
- Contract test required:

```python
# tests/contract/test_event_schema_version.py
# Publish Event(schema_version=999)
# Assert consumer logs WARNING and does not raise
```

**Correlation ID propagation:**
- Every event carries `journey_id` as the primary correlation ID throughout its lifecycle
- `structlog` context binding: bind `journey_id` at the start of every request/task handler — it propagates automatically to all nested log calls
- Pattern:
```python
with structlog.contextvars.bound_contextvars(journey_id=event.journey_id):
    process_event(event)
# All log calls inside process_event automatically include journey_id
```
- If `journey_id` is unavailable (pre-trip startup), bind `vehicle_id` instead

**Logging (all Python containers):**
- Library: `structlog` — JSON output, consistent across all containers
- Never `print()`, never `logging.basicConfig()`
- Required keyword args on every structured log call: at minimum one ID field (`journey_id`, `camera_id`, `event_id`) + descriptive action keyword

```python
# ✅ correct
log.info("event_stored", event_id=event.event_id, journey_id=event.journey_id)
log.warning("camera_degraded", camera_id="C3_INT", recoverable=True)
log.error("sync_failed", journey_id=journey_id, error=str(e), recoverable=False)

# ❌ forbidden
print("stored event")
log.info(f"stored {event.event_id}")
```

**Log level discipline:**

| Level | When to use |
|---|---|
| `DEBUG` | Frame-level, per-detection — disabled in production |
| `INFO` | State changes, journey events, sync completions |
| `WARNING` | Degraded but recoverable (camera offline, APC stale, schema_version unsupported) |
| `ERROR` | Unexpected failures requiring investigation |
| `CRITICAL` | Safety-relevant failures (CCU shutdown, TCMS alarm at speed > 0) |

**Retry pattern — `tenacity` based:**
- `shared/http/retry.py` provides **defaults and primitives** using `tenacity`
- Each container configures its own retry policy via pydantic-settings — not shared policy
- No ad-hoc `time.sleep()` loops anywhere
- Rationale: shared defaults ensure consistent backoff behaviour; per-container config allows different timeout characteristics (inference vs cloud sync have different latency budgets)

```python
# shared/http/retry.py — primitives only
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

DEFAULT_RETRY = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, max=30) + wait_random(0, 1),
)
```

**Health check semantics:**
- Every container exposes `GET /health/live` (liveness) and `GET /health/ready` (readiness)
- Liveness: container process is alive — always returns `200` unless the process is crashing
- Readiness: container is ready to serve traffic — returns `503` during startup race, `200` when ready
- `rtsp-ingest`: liveness = process alive; readiness = at least one P1 camera stream connected
- `inference`: liveness = process alive; readiness = Hailo-8 device initialised
- `event-store`: liveness = process alive; readiness = SQLite WAL open + FastAPI routes registered
- `vlan-pollers`: liveness = process alive; readiness = SNMP connection established
- `fusion`: liveness = process alive; readiness = event-store health check passes

---

### Process Patterns

**Dependency injection (mandatory):**
- All I/O dependencies MUST be injected via constructor or factory parameter — never instantiated inside domain logic
- Rationale: testability seam; unit tests inject mocks, integration tests inject real adapters

```python
# ✅ correct — injectable
class FusionService:
    def __init__(self, apc: APCAdapter, event_client: EventStoreClient):
        self.apc = apc
        self.event_client = event_client

# ❌ forbidden — instantiates own dependency
class FusionService:
    def __init__(self):
        self.apc = RealAPCAdapter()  # no test seam
```

**No module-level side effects:**

```python
# ❌ forbidden — triggers real connection on import
db_pool = create_pool(settings.DB_URL)

# ✅ correct — lazy, injectable
def get_pool() -> Pool:
    return create_pool(settings.DB_URL)
```

**No `assert` as runtime guard:**

```python
# ❌ forbidden — stripped in -O mode
assert frame is not None

# ✅ correct — explicit domain exception
if frame is None:
    raise FrameValidationError("frame must not be None")
```

**Error handling:**
- Catch at the top of each async task — log with structlog, emit domain event, never swallow silently
- FastAPI exception handlers for all HTTP error paths — always return ADR-10 envelope
- Domain-specific exception classes in each container (`CameraUnavailableError`, `SyncFailedError`, `FrameValidationError`)
- Never `raise Exception(...)` — always a named domain exception
- Never bare `except:` or `except Exception:` without logging and re-raising

**Validation:**
- Pydantic models for all FastAPI request/response bodies (`event-store`, cloud backend)
- `dataclasses` with `__post_init__` for internal container models
- `pydantic-settings` for all config loading — required fields validated at startup; container exits with clear error if missing
- No `os.environ.get()` scattered through business logic — config object injected

---

### CI Enforcement

**`.pre-commit-config.yaml` (committed to repo root):**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: ["--select=E,F,B,S101,DTZ,RUF"]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
        args: ["--strict"]
  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ["-r", "src/"]
  - repo: https://github.com/Yelp/detect-secrets
    hooks:
      - id: detect-secrets
```

**`pyproject.toml` (shared template):**
```toml
[tool.ruff.lint]
select = ["E", "F", "B", "S101", "DTZ", "RUF", "I", "UP"]
# S101 = assert as guard; DTZ = naive datetime; UP = Python 3.11 upgrades

[tool.pytest.ini_options]
addopts = "--tb=short --strict-markers"
markers = [
  "unit: pure logic, no I/O",
  "integration: real adapters",
  "contract: schema version compatibility"
]

[tool.coverage.report]
fail_under = 90
```

**What each gate enforces:**

| Tool | What it catches |
|---|---|
| `ruff S101` | `assert` used as runtime guard |
| `ruff DTZ` | Naive `datetime.now()` without timezone |
| `ruff B` | Common bug patterns (mutable default args, etc.) |
| `mypy --strict` | Protocol/ABC contract violations; mock divergence from base |
| `bandit` | Security anti-patterns |
| `detect-secrets` | Credentials accidentally staged |
| `pytest --strict-markers` | Unmarked tests fail — forces `unit`/`integration`/`contract` classification |
| `fail_under = 90` | Coverage floor — raised from 80 given safety-relevant codebase |

---

### Enforcement Summary — All Agents MUST

1. Use `EventType` enum from `shared/events/types.py` — never hardcode event type strings
2. Use `tenacity` via `shared/http/retry.py` defaults — never roll custom retry or `time.sleep()` loops
3. Return ADR-10 error envelope from all API error paths — never raw strings or unstructured dicts
4. Use `structlog` for all logging — never `print()` or `logging.basicConfig()`
5. Use `snake_case` for all JSON fields in API responses — never `camelCase` at the API layer
6. Put tests in `tests/{unit,integration,contract}/` — never co-locate with source
7. Use `.env.example` as committed template — never commit `.env`
8. Use `pydantic-settings` for config — never `os.environ.get()` in business logic
9. Use `httpx` async client — never `requests`
10. Prefix all API routes `/api/v1/` — no unversioned routes
11. Inject all I/O dependencies — never instantiate adapters inside domain logic
12. Use `datetime.now(timezone.utc)` — never `datetime.now()`
13. Include `schema_version` in every `Event` — consumers reject unsupported versions at WARNING
14. Bind `journey_id` to structlog context at task entry — propagates to all nested log calls

**Anti-patterns (explicitly forbidden):**

```python
# ❌ hardcoded event type
{"event_type": "ALERT_RAISED"}
# ✅ use enum
Event(event_type=EventType.ALERT_RAISED)

# ❌ ad-hoc retry
for i in range(3):
    try: ...
    except: time.sleep(2)
# ✅ tenacity primitive
@DEFAULT_RETRY
async def post_event(event): ...

# ❌ bare except
except:
    pass
# ✅ named exception + log
except CameraUnavailableError as e:
    log.warning("camera_unavailable", camera_id=camera_id, error=str(e), recoverable=True)

# ❌ assert as guard
assert frame is not None
# ✅ domain exception
if frame is None: raise FrameValidationError(...)

# ❌ naive datetime
datetime.now()
# ✅ timezone-aware
datetime.now(timezone.utc)

# ❌ module-level side effect
db_pool = create_pool(settings.DB_URL)
# ✅ lazy factory
def get_pool() -> Pool: return create_pool(settings.DB_URL)
```

---

## Project Structure & Boundaries

### Hailo-Apps Dependency Decision

**Source:** `hailo-ai/hailo-apps` (MIT licensed, HailoRT 4.23 for Hailo-8, actively maintained); `hailo-ai/hailo-apps-core` (LGPL-2.1, used as library — no modification, no source disclosure required)

Rather than building RTSP ingestion, object detection, and tracking from scratch, we extend hailo-apps components natively via TAPPAS GStreamer pipelines. Thin Python callbacks handle zone counting and event emission only — no Python tracker wrapper.

| Our container | Hailo-apps / TAPPAS component | Reuse strategy |
|---|---|---|
| `rtsp-ingest` | `multisource` pipeline | GStreamer `HailoRoundRobin` + `HailoStreamRouter` handles parallel RTSP streams, reconnect, decode — saves significant custom code |
| `inference` | `detection` app + `GStreamerDetectionApp` | Full GStreamer pipeline: `hailonet` (YOLOv8m) → `hailofilter` (NMS) → `hailotracker` → Python callback |
| `inference` | `hailotracker` GStreamer plugin | Native Kalman+IoU tracker in TAPPAS; outputs track IDs as buffer metadata consumed by thin Python callback |
| `inference` | `reid_multisource` pipeline | Cross-camera re-ID for multi-car person identity continuity (E4-S5+) |

**Pose estimation removed from PoC scope.** Seated vs. standing classification uses static zone polygon masks (`seat_zones` in `cameras.json`) — not pose keypoints. This eliminates `yolov8m_pose.hef` and `pose.py` from the inference container. Re-evaluate for E4-S5 (accessibility detection).

**Still custom-built (not in hailo-apps):**
- Thin Python callbacks: zone mask application, per-coach 1 Hz occupancy count, OCCUPANCY_UPDATE / OCCUPANCY_THRESHOLD_CROSSED event emission
- P1/P2/P3 priority budget manager — on top of `multisource` Python callbacks
- Unattended bag stationary timer — custom post-processor in `fusion`
- Luggage / wheelchair classification — COCO multi-class heuristics (person + suitcase + bicycle) + domain post-processing in `fusion`

**Docker base image change:**
- `rtsp-ingest` + `inference`: base from **Hailo Software Suite Docker image** (HailoRT 4.23 + TAPPAS 5.1.0, available from Hailo Developer Zone) rather than `python:3.11-slim-bookworm`
- All other containers remain on `python:3.11-slim-bookworm`

---

### Complete Project Directory Structure

```
oebb-smart-rail/
├── .pre-commit-config.yaml
├── .gitignore                        # .env, __pycache__, *.pyc, hailo models
├── docker-compose.yml                # PoC single-vehicle deployment
├── docker-compose.dev.yml            # local dev overrides (mock cameras, synthetic SNMP)
├── cameras.json                      # per-train RTSP URL → camera_id/coach_id/zone/priority
├── README.md
│
├── shared/                           # shared Python code — all containers import from here
│   ├── pyproject.toml
│   ├── events/
│   │   ├── __init__.py
│   │   ├── types.py                  # EventType StrEnum (append-only, ADR-5)
│   │   └── envelope.py               # Event dataclass with schema_version: int
│   ├── adapters/
│   │   ├── apc/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # APCAdapter Protocol (ADR — format TBD)
│   │   │   └── mock.py               # MockAPCAdapter (deterministic fixtures)
│   │   └── pis/
│   │       ├── __init__.py
│   │       ├── base.py               # PISAdapter Protocol
│   │       └── mock.py
│   ├── ws/
│   │   ├── __init__.py
│   │   └── subscription.py           # SubscriptionRequest dataclass (ADR-9)
│   └── http/
│       ├── __init__.py
│       └── retry.py                  # tenacity DEFAULT_RETRY primitive (ADR)
│
├── rtsp-ingest/                      # P1/P2/P3 camera ingestion via hailo-apps multisource
│   ├── Dockerfile                    # FROM hailo-software-suite:4.23 (HailoRT + TAPPAS)
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   └── rtsp_ingest/
│   │       ├── __init__.py
│   │       ├── main.py               # entry point; loads cameras.json, starts pipeline
│   │       ├── config.py             # pydantic-settings: RTSP creds, priority thresholds
│   │       ├── models.py             # Frame, CameraConfig, CameraState dataclasses
│   │       ├── pipeline.py           # hailo-apps multisource wrapper; GStreamer pipeline setup
│   │       ├── scheduler.py          # P1/P2/P3 budget enforcement on top of multisource callbacks
│   │       ├── gate.py               # P3 station window gate (speed + door_release + next_station)
│   │       └── health.py             # /health/live + /health/ready (ready = ≥1 P1 stream active)
│   └── tests/
│       ├── unit/
│       │   ├── test_scheduler.py     # frame rate enforcement per priority tier
│       │   └── test_gate.py          # P3 activation/deactivation conditions
│       └── integration/
│           └── test_rtsp_connect.py  # real RTSP stream (dev env only, marked integration)
│
├── vlan-pollers/                     # SNMP, APC, PIS, Reservation context state
│   ├── Dockerfile                    # FROM python:3.11-slim-bookworm
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   └── vlan_pollers/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py             # pydantic-settings: VLAN IPs, community strings, intervals
│   │       ├── models.py             # ContextState, VehicleState, TripInfo, AlarmEntry
│   │       ├── snmp_poller.py        # VLAN 7 — Stadler IM SNMP TRAP/INFORM + GET/GetBulk
│   │       ├── apc_poller.py         # VLAN 8 — APCAdapter impl (MockAPCAdapter until format confirmed)
│   │       ├── pis_poller.py         # VLAN 3 — PIS state + delay/platform change
│   │       ├── reservation_poller.py # VLAN 6 — reservation by coach
│   │       ├── context_state.py      # in-memory ContextState + delta push to inference/fusion
│   │       ├── journey_tracker.py    # journey_start_date on trip_number first-seen; journey_id gen
│   │       └── health.py             # ready = SNMP connection established
│   └── tests/
│       ├── unit/
│       │   ├── test_journey_id.py    # midnight-crossing stability (ADR-2)
│       │   ├── test_context_state.py # delta push on state change only
│       │   └── test_snmp_decoder.py  # im0VstGeneral + im0Alarm + im0Trip parsing
│       └── integration/
│           └── test_snmp_live.py     # real SNMP endpoint (dev env only)
│
├── inference/                        # Hailo-8 detection + tracking via hailo-apps + TAPPAS natively
│   ├── Dockerfile                    # FROM hailo-software-suite:4.23 (HailoRT + TAPPAS)
│   ├── pyproject.toml
│   ├── .env.example
│   ├── models/                       # pre-compiled .hef model files (gitignored, fetched at build)
│   │   └── yolov8m.hef               # object detection (person, suitcase, bicycle)
│   ├── src/
│   │   └── inference/
│   │       ├── __init__.py
│   │       ├── main.py               # entry point; builds GStreamer pipeline via hailo-apps-core helpers
│   │       ├── config.py             # pydantic-settings: model paths, TOPS budget, zone config, thresholds
│   │       ├── models.py             # ZoneMask, OccupancyState, DetectionClass dataclasses
│   │       ├── pipeline.py           # GStreamerDetectionApp subclass; INFERENCE + TRACKER + USER_CALLBACK pipeline
│   │       ├── callback.py           # thin Python callback: extract ROI metadata → zone_counter
│   │       ├── budget.py             # TOPS budget manager; P2 throttle on overload via context state
│   │       ├── zone_counter.py       # per-zone people counting from hailotracker track IDs; POST events
│   │       └── health.py             # FastAPI: /health/ready, /health/live, POST /context
│   └── tests/
│       ├── unit/
│       │   ├── test_budget.py        # TOPS enforcement; P2 throttle triggers correctly
│       │   ├── test_zone_counter.py  # zone boundary logic with synthetic track ID sequences
│       │   └── test_security.py      # Rule 8: no os.environ.get(); payload schema validation
│       └── integration/
│           └── test_pipeline.py      # real Hailo-8 + TAPPAS (hardware dev env only)
│
├── fusion/                           # rules, suppression, enrichment, alert generation
│   ├── Dockerfile                    # FROM python:3.11-slim-bookworm
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   └── fusion/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py             # pydantic-settings: occupancy thresholds, bag timer duration
│   │       ├── models.py             # OccupancyReading, AlertCandidate, FusedEvent
│   │       ├── occupancy.py          # camera + APC fusion; 3-band (staff) + 4-band (portal) models
│   │       ├── congestion.py         # vestibule congestion + luggage rack saturation
│   │       ├── unattended_bag.py     # stationary object timer + owner-absent detection
│   │       ├── accessibility.py      # wheelchair/pushchair + TCMS PRM door correlation
│   │       ├── door_obstruction.py   # camera detection + ZFR door command cross-reference
│   │       ├── suppression.py        # suppression state machine (maintenance, GPS, degraded)
│   │       ├── enrichment.py         # trip labelling, journey_id, severity mapping, schema_version
│   │       └── health.py             # ready = event-store health check passes
│   └── tests/
│       ├── unit/
│       │   ├── test_occupancy.py         # 3-band + 4-band threshold logic
│       │   ├── test_suppression.py       # state machine: maintenance→normal, GPS invalid
│       │   ├── test_unattended_bag.py    # stationary timer + owner-detected resolution
│       │   ├── test_accessibility.py     # wheelchair detection + PRM door correlation
│       │   └── test_enrichment.py        # journey_id attachment, severity, schema_version
│       └── integration/
│           └── test_fusion_pipeline.py   # synthetic frames → normalised events end-to-end
│
├── event-store/                      # SQLite WAL, REST + WebSocket API, cloud sync
│   ├── Dockerfile                    # FROM python:3.11-slim-bookworm
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   └── event_store/
│   │       ├── __init__.py
│   │       ├── main.py               # FastAPI app factory, router + WS registration
│   │       ├── config.py             # pydantic-settings: DB path, sync endpoint, API key
│   │       ├── models.py             # Pydantic request/response models
│   │       ├── database.py           # SQLite WAL setup; get_pool() lazy factory
│   │       ├── schema.sql            # DDL: events, journeys, sync_state tables + indexes
│   │       ├── routes/
│   │       │   ├── events.py         # GET /api/v1/events (cursor-paginated)
│   │       │   ├── journeys.py       # GET /api/v1/journeys/{journey_id}
│   │       │   └── health.py         # GET /health/live + /health/ready
│   │       ├── websocket/
│   │       │   ├── handler.py        # WS connection manager + subscription dispatch (ADR-9)
│   │       │   └── replay.py         # reconnect replay: last N events per subscription filter
│   │       ├── sync/
│   │       │   ├── agent.py          # cloud sync loop; batch + retry via shared/http/retry.py
│   │       │   └── cursor.py         # sync_state table: last_synced_event_id read/write
│   │       └── exceptions.py         # SyncFailedError, EventValidationError
│   └── tests/
│       ├── unit/
│       │   ├── test_ws_subscription_filter.py  # severity + event_type filtering
│       │   └── test_sync_cursor.py             # SIGKILL + re-sync dedup (ADR-4)
│       ├── integration/
│       │   ├── test_event_store_concurrent_writes.py  # 4-thread burst; p99 latency < 50ms
│       │   └── test_cloud_event_ingestion.py          # idempotency via DB unique constraint
│       └── contract/
│           └── test_event_schema_version.py           # schema_version=999 → WARNING, no crash
│
├── cloud-backend/                    # FastAPI + PostgreSQL, fleet analytics, WS push
│   ├── Dockerfile                    # FROM python:3.11-slim-bookworm
│   ├── pyproject.toml
│   ├── .env.example
│   ├── src/
│   │   └── cloud_backend/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── config.py             # pydantic-settings: DB URL, API key, WS config
│   │       ├── models.py             # Pydantic models: all request/response shapes
│   │       ├── database.py           # PostgreSQL pool; get_pool() lazy factory
│   │       ├── migrations/
│   │       │   └── 001_initial_schema.py   # Alembic: events + journeys DDL
│   │       ├── routes/
│   │       │   ├── ingest.py         # POST /api/v1/events (idempotent, ADR-3)
│   │       │   ├── journeys.py       # GET /api/v1/journeys (fleet-wide, cursor-paginated)
│   │       │   ├── analytics.py      # GET /api/v1/analytics (Control Centre panel, scenario-04)
│   │       │   └── health.py
│   │       ├── websocket/
│   │       │   └── handler.py        # WS push to Control Centre Dashboard on new event
│   │       └── exceptions.py
│   └── tests/
│       ├── unit/
│       │   └── test_ingest_idempotency.py        # duplicate event → 200, single DB row
│       ├── integration/
│       │   └── test_postgres_schema.py            # testcontainers-python, DDL + constraints
│       └── contract/
│           └── test_event_schema_version.py       # cloud-side schema_version rejection
│
├── control-centre/                   # React + Vite dashboard (cloud-hosted) — see DD-001
│   ├── package.json
│   ├── vite.config.js
│   ├── .env.example
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx                   # react-router-dom routes: /dashboard/live, /health, /analytics
│   │   ├── context/
│   │   │   └── FleetContext.jsx      # single MockWebSocketClient instance; shared across all views
│   │   ├── hooks/
│   │   │   └── useFleetData.js       # consumes FleetContext; exposes trains + escalations
│   │   ├── mock/
│   │   │   ├── MockWebSocketClient.js  # 5s tick mock — replace with real WS in production
│   │   │   └── analytics.js          # historical mock data; getOccupancyHeatmap(), getDwellData()
│   │   ├── constants/
│   │   │   └── escalation.js         # SOURCE_LABEL, SEV_CLASS maps
│   │   ├── styles/                   # CSS custom properties (design tokens)
│   │   ├── components/
│   │   │   ├── shell/
│   │   │   │   ├── AppShell.jsx      # top nav, tab bar, critical alert hook (pid-app-shell-alert-hook)
│   │   │   │   └── AppShell.css
│   │   │   ├── live/
│   │   │   │   ├── LiveMonitoring.jsx        # layout: FleetList + TrainDetail + UnifiedFeed
│   │   │   │   ├── FleetList.jsx             # TrainCard sub-component; severity sort + normal collapse
│   │   │   │   ├── FleetList.css
│   │   │   │   ├── UnifiedFeed.jsx           # FeedItem sub-component; filter pills; resolve form
│   │   │   │   ├── UnifiedFeed.css
│   │   │   │   ├── EscalationDetail.jsx      # createPortal modal; ack + resolve; still frame
│   │   │   │   └── EscalationDetail.css
│   │   │   ├── train-detail/
│   │   │   │   ├── TrainDetail.jsx   # coach grid; active alerts (coach-tap filter); open escalations
│   │   │   │   └── TrainDetail.css
│   │   │   ├── health/
│   │   │   │   ├── SystemHealth.jsx  # fleet grid; train summary panel; MAINTENANCE_APP_ENABLED flag
│   │   │   │   └── SystemHealth.css
│   │   │   └── analytics/
│   │   │       ├── Analytics.jsx             # tab router; date range picker; Export CSV
│   │   │       ├── Analytics.css
│   │   │       ├── ExceptionWorkflow.jsx     # scenario-04: exception list + service detail + modal
│   │   │       ├── ExceptionWorkflow.css
│   │   │       ├── OccupancyHeatmap.jsx      # route×hour heatmap; peak hour table
│   │   │       ├── OccupancyHeatmap.css
│   │   │       ├── DwellTime.jsx             # station bar chart; scatter plot; correlation insight
│   │   │       ├── DwellTime.css
│   │   │       ├── AIDetection.jsx           # KPI strip; stacked bar chart; per-train uptime
│   │   │       └── AIDetection.css
│   └── tests/
│       ├── unit/
│       │   └── useWebSocket.test.js  # reconnect + replay behaviour
│       └── e2e/
│           └── control-centre.spec.js  # Playwright: WS drop + reconnect
│
├── conductor-app/                    # PWA — served from SYS2 media server (VLAN 30)
│   ├── src/
│   │   ├── index.html
│   │   ├── sw.js                     # service worker — cache strategy deferred to Phase 2
│   │   ├── css/
│   │   │   └── shared.css            # single shared stylesheet (all static UIs share this)
│   │   ├── js/
│   │   │   ├── api.js                # REST client; WS subscription setup
│   │   │   ├── alert-feed.js         # scenario-01: Conrad home screen
│   │   │   ├── congestion.js         # scenario-02: vestibule congestion alert
│   │   │   ├── accessibility.js      # scenario-06: Conrad accessibility alert + space detail
│   │   │   └── capacity-flag.js      # scenario-03: Conrad capacity flag form
│   │   └── components/
│   │       ├── train-diagram.js      # 3-band occupancy colour model
│   │       └── alert-card.js         # severity-aware alert card (critical/warning/info)
│   └── tests/
│       └── unit/
│           └── alert-feed.test.js
│
├── passenger-portal/                 # Static HTML — SYS2 media server (VLAN 10, PoC demo)
│   ├── index.html
│   ├── css/
│   │   └── shared.css                # same shared stylesheet
│   ├── js/
│   │   ├── websocket.js              # WS subscription (occupancy + accessibility guidance)
│   │   ├── train-diagram.js          # 4-band occupancy model (scenario-05)
│   │   └── accessibility-guidance.js # scenario-06: portal pre-boarding + journey states
│   └── assets/
│       └── oebb-logo.svg
│
├── pis-templates/                    # Static HTML templates for PIS exterior/interior screens
│   ├── exterior/
│   │   ├── boarding-guidance.html    # scenario-01: PIS exterior boarding guidance
│   │   └── dwell-states.html         # scenario-10: PIS exterior dwell states
│   └── interior/
│       ├── rebalance-guidance.html   # scenario-02b: PIS interior rebalance
│       └── dwell-states.html         # scenario-10: PIS interior dwell states
│
├── driver-display/                   # Static HTML — read-only, SYS2 (VLAN 30)
│   ├── index.html
│   ├── css/
│   │   └── shared.css
│   └── js/
│       └── feed.js                   # read-only critical/warning severity passthrough
│
└── docs/
    ├── adr/                          # individual ADR markdown files
    │   ├── ADR-001-event-envelope.md
    │   ├── ADR-002-journey-id.md
    │   └── ...
    ├── api/
    │   └── openapi.yaml              # auto-generated from FastAPI (event-store + cloud-backend)
    └── runbooks/
        └── poc-deployment.md
```

---

### Architectural Boundaries

**API Boundaries:**

| Boundary | Protocol | Auth | Direction |
|---|---|---|---|
| `rtsp-ingest` → `inference` | GStreamer pipeline (shared TAPPAS process; no HTTP) | VLAN isolation | onboard internal |
| `vlan-pollers` → `rtsp-ingest` | HTTP (context delta: P3 gate) | VLAN isolation | onboard internal |
| `vlan-pollers` → `fusion` | HTTP POST (context delta) | VLAN isolation | onboard internal |
| `inference` → `fusion` | HTTP POST (detections) | VLAN isolation | onboard internal |
| `fusion` → `event-store` | HTTP POST `/api/v1/events` | VLAN isolation | onboard internal |
| `vlan-pollers` → `event-store` | HTTP POST `/api/v1/events` | VLAN isolation | onboard internal |
| `event-store` → Conductor App | WebSocket `/ws` + REST `/api/v1/` | VLAN 30 isolation | outbound |
| `event-store` → Passenger Portal | WebSocket `/ws` (read-only) | VLAN 10 | outbound |
| `event-store` → Driver Display | WebSocket `/ws` (read-only, critical only) | VLAN 30 | outbound |
| `event-store` → cloud sync | HTTP POST (batched, retry) | API key | outbound via SYS1 |
| Cloud backend → Control Centre | WebSocket `/ws` | API key | outbound |
| Control Centre → cloud backend | HTTP GET `/api/v1/` | API key | inbound |

**Data Boundaries:**

| Boundary | What crosses | What does not cross |
|---|---|---|
| Hailo-8 → `fusion` | Structured detections (person counts, keypoints, object classes) | Raw video frames |
| `event-store` → cloud sync | Structured JSON events (anonymised) | SQLite file, raw detections, PII |
| Cloud backend → PIS screens | HTML display values only | Event payloads, raw data |
| SYS2 → internet | Structured anonymised events via SYS1 | Raw video, biometric data, PII |

**Component Ownership:**

| Domain | Owner | No other component touches this |
|---|---|---|
| Hailo-8 device | `inference` (exclusive) | HailoRT device handle is singleton |
| SQLite event store | `event-store` (sole writer) | All others write via HTTP POST |
| Context state | `vlan-pollers` | Others receive deltas, never write |
| Journey scoping | `vlan-pollers/journey_tracker.py` | Authoritative source of `journey_id` |
| Suppression decisions | `fusion/suppression.py` | Fusion is the single decision point |
| Cloud sync cursor | `event-store/sync/cursor.py` | Sync agent owns exclusively |

---

### Scenario → Structure Mapping

| Scenario | Primary implementation files |
|---|---|
| 01 — Conductor home + PIS boarding | `fusion/occupancy.py`, `conductor-app/js/alert-feed.js`, `pis-templates/exterior/boarding-guidance.html` |
| 02 — Vestibule congestion | `fusion/congestion.py`, `conductor-app/js/congestion.js` |
| 02b — Occupancy imbalance + PIS rebalance | `fusion/occupancy.py`, `pis-templates/interior/rebalance-guidance.html` |
| 02c — Luggage rack saturation | `fusion/congestion.py`, `inference/zone_counter.py` |
| 02d — Unattended bag | `fusion/unattended_bag.py`, `conductor-app/js/alert-feed.js`, `control-centre/src/components/alerts/UnattendedBagEscalation.tsx` |
| 03 — Capacity flag form | `conductor-app/js/capacity-flag.js`, `event-store/routes/events.py` |
| 04 — Control Centre analytics | `cloud-backend/routes/analytics.py`, `control-centre/src/components/analytics/CapacityPanel.tsx` |
| 05 — Passenger portal load guidance | `passenger-portal/js/train-diagram.js`, `fusion/occupancy.py` |
| 06 — Accessibility boarding | `fusion/accessibility.py`, `inference/pose.py`, `conductor-app/js/accessibility.js`, `passenger-portal/js/accessibility-guidance.js` |
| 10 — Station dwell | `vlan-pollers/context_state.py`, `pis-templates/exterior/dwell-states.html`, `pis-templates/interior/dwell-states.html` |

---

### Data Flow

```
cameras.json
     │
     ▼
rtsp-ingest (hailo-apps multisource — GStreamer HailoRoundRobin)
  P1 10fps always / P2 5fps always / P3 8fps station-window
     │ GStreamer pipeline (frames flow internally via TAPPAS — no HTTP)
     ▼
inference (hailo-apps detection + hailotracker — TAPPAS native)
  Hailo-8 M.2 — yolov8m.hef (person/suitcase/bicycle)
  hailotracker GStreamer plugin → thin Python callback → zone_counter
     │ detections + tracking IDs (HTTP POST to fusion/event-store)
     │
     ├──────────────────────────────────────┐
     ▼                                      │
fusion ◄── context deltas (vlan-pollers)    │
  suppression · occupancy · congestion      │
  unattended bag · accessibility · enrichment
     │ normalised Events (HTTP POST)        │
     ▼                                      │
event-store (SQLite WAL, single writer) ◄───┘
  journey-scoped · sync_cursor · /api/v1/ · /ws
     │
     ├─── WebSocket ──► Conductor App (VLAN 30)
     ├─── WebSocket ──► Passenger Portal (VLAN 10)
     ├─── WebSocket ──► Driver Display (VLAN 30, critical only)
     └─── HTTP batch ─► cloud-backend (via SYS1)
                              │
                         PostgreSQL
                              │
                         WebSocket ──► Control Centre Dashboard
                         REST API   ──► Control Centre Dashboard
```


---

## Step 7 — Architecture Validation Results

**Date:** 2026-05-16
**Overall Status: READY FOR IMPLEMENTATION**
**Confidence level: High**

### Validation Checklist (all 16 items passing)

- [x] All technology choices are mutually compatible
- [x] hailo-apps MIT licensed (application layer); hailo-apps-core LGPL-2.1 (used as library, no modification) — multisource, detection, hailotracker, reid_multisource directly reusable; pose_estimation deferred (out of PoC scope)
- [x] `shared/` package installable in both `python:3.11-slim-bookworm` and Hailo Suite Docker base images
- [x] snake_case / PascalCase / UPPER_SNAKE_CASE naming consistent across all layers
- [x] All 14 MUST rules traceable to specific ADRs
- [x] All 6 Passenger AI capabilities architecturally supported
- [x] TCMS/PIS have known external dependencies — stubs in place, not blockers
- [x] All 3 pilot success criteria measurable from event timestamps from day one
- [x] 14 ADRs with rationale documented
- [x] Implementation sequence ordered by dependency (14 steps)
- [x] All 10 scenarios mapped to specific files
- [x] All architectural boundaries defined with protocol + auth + direction
- [x] Single-writer SQLite pattern eliminates common embedded event store concurrency bug
- [x] APC Protocol stub means APC format uncertainty cannot block critical path
- [x] Suppression state machine elevated to correctness requirement
- [x] journey_id midnight-crossing bug prevented by `journey_start_date` anchor

### Coherence Validation ✅

All technology choices compatible: HailoRT 4.23, Python 3.11, asyncio, httpx, FastAPI, SQLite WAL, PostgreSQL, React + Vite.

hailo-apps (MIT) + hailo-apps-core (LGPL-2.1, library use) confirmed. TAPPAS-native pipeline: multisource + GStreamerDetectionApp + hailotracker + reid_multisource reusable without modification. Pose estimation deferred (not in PoC scope). `shared/` package installable in both `python:3.11-slim-bookworm` and Hailo Suite Docker base images — each `Dockerfile` must include `pip install -e ./shared`.

### Requirements Coverage ✅

All 6 Passenger AI capabilities architecturally supported. TCMS/PIS have known external dependencies (not blockers — stubs in place). All 3 pilot success criteria (dwell time, passenger congestion, luggage congestion) measurable from event timestamps from day one.

### Implementation Readiness ✅

14 ADRs with rationale, implementation sequence (14 steps ordered by dependency), all 10 scenarios mapped to specific files, all architectural boundaries defined with protocol + auth + direction.

### Gaps — Resolved and Remaining

| Gap | Status |
|---|---|
| `shared/` pip install in both Docker base images | Document in each `Dockerfile` + `README.md` |
| Camera count per train | **Resolved 2026-05-16: 25–30 cameras/train** |
| Source control platform | **Resolved 2026-05-16: GitLab (.gitlab-ci.yml)** |
| Wheelchair/pushchair COCO proxy accuracy | **Deferred to post-PoC** — acceptable for pilot |
| PIS L2 write API | Still waiting on Stadler/ÖBB network team |
| CI/CD platform | **Resolved: GitLab CI/CD** |
| GDPR sign-off from ÖBB legal | Pending — cloud sync data policy |
| Cloud backend hosting (Nomad vs Azure/AWS) | Pending — Nomad Digital commercial decision |

### Key Strengths

- hailo-apps eliminates highest-risk custom engineering (RTSP + GStreamer + Hailo device)
- Single-writer SQLite pattern eliminates most common embedded event store concurrency bug
- APC Protocol stub means APC uncertainty cannot block critical path
- Suppression state machine elevated to correctness requirement
- journey_id midnight-crossing bug prevented by `journey_start_date` anchor in `vlan-pollers`
- 14 MUST rules + CI enforcement config (ruff S101/DTZ, mypy --strict, bandit, detect-secrets)

### Post-PoC Enhancements (documented, not open)

- JWT auth (Phase 2 explicit gate)
- PWA offline service worker (Phase 2)
- PostgreSQL HA (fleet rollout gate)
- Custom wheelchair/pushchair model (post-PoC if COCO proxy insufficient)
- Multi-CCU coupled-train topology (explicit deferral)
- ML predictive fault models (month 4–6)

---

## Architecture Update — Control Centre Dashboard (DD-001)

**Date:** 2026-05-16
**Reason:** Control Centre Dashboard prototype built and acceptance-tested. Component structure, WebSocket event contracts, and API routes now confirmed via DD-001. This section supersedes the earlier `control-centre/` notes where they conflict.

---

### ADR-15: Control Centre Frontend Stack (confirmed)

**Decision:** React + Vite SPA (JavaScript, not TypeScript for PoC). JSX components, CSS Modules pattern via co-located `.css` files. No component library — custom CSS with design token system.

**Rationale:** Prototype was built in JavaScript to move fast. TypeScript migration is a Phase 2 item — add `tsconfig.json` and migrate incrementally when team stabilises. The prototype's component structure is production-worthy; no rewrite needed, only wiring replacements.

**Design token source:** CSS custom properties on `:root` in `src/styles/`. All components reference tokens — no hardcoded colour values in component CSS.

| Token group | Prefix | Purpose |
|---|---|---|
| Severity colours | `--obb-sev-*` | critical / warning / medium / normal |
| Surface elevation | `--obb-surface-1..5` | Background depth scale |
| Text contrast | `--obb-text-on-dark-1..4` | Legibility scale |
| Borders | `--obb-border-dark` / `--obb-border-bright` | Dividers / interactive |
| Accent | `--obb-blue-accent` | Links, selected states, info |
| Typography | `--font-mono` / `--font-body` | JetBrains Mono / Inter |

---

### ADR-16: Control Centre State Management

**Decision:** Single `FleetContext` (React Context) wrapping one `MockWebSocketClient` instance. All views consume via `useFleetData()` hook. No Redux or Zustand for PoC.

**Production replacement path:** Replace `MockWebSocketClient` with a real WebSocket client in `FleetContext.jsx`. All consumers (`LiveMonitoring`, `SystemHealth`, `TrainDetail`, `AppShell`) update automatically — no component changes required for the wiring swap.

**Derived state pattern:** Components derive display state from context — e.g. `TrainDetail` filters escalations from the shared list rather than fetching separately. This is intentional for PoC simplicity. In production, per-train escalation queries may be preferable for large fleets.

---

### WebSocket Event Contracts (Control Centre ↔ Cloud Backend)

These are the confirmed contracts from DD-001, aligned with ADR-1 (event envelope) and ADR-9 (WebSocket subscription). The cloud backend's WebSocket handler must emit events in these shapes.

**Train state event** (replaces earlier sketch in architecture doc):
```json
{
  "id": "R5001C-031",
  "severity": "red | amber | green",
  "route": "Wien → Salzburg",
  "avgOccupancy": 78,
  "dwellStatus": { "station": "Linz", "delayMin": 4 } ,
  "coaches": [
    { "id": "C1", "occupancy": 45, "hasAlert": false }
  ]
}
```

**Escalation event** (maps to `ALERT_RAISED` / `ALERT_RESOLVED` in EventType taxonomy):
```json
{
  "id": "esc-001",
  "type": "ai | staff | roland",
  "severity": "red | amber | green",
  "train_id": "R5001C-031",
  "coach_id": "C4",
  "title": "Unattended item detected",
  "detail": "Detection confidence 94%…",
  "timestamp": "2026-05-16T11:23:00Z",
  "status": "unacknowledged | acknowledged | resolved",
  "still_frame": {
    "camera": "C4-INT-2",
    "captured_at": "11:23",
    "confidence": 94,
    "url": "/frames/esc-001.jpg"
  }
}
```

**System health event** (emitted by cloud backend aggregating `event-store` health signals per train):
```json
{
  "train_id": "R5001C-031",
  "cctv_status": "green | amber | red",
  "app_status": "green | amber | red",
  "containers": [
    { "name": "inference", "status": "healthy | unhealthy", "exited_at": "09:43" }
  ],
  "last_healthy": "09:43"
}
```

**Naming note:** JSON field names follow ADR snake_case rule. The React client converts to camelCase at the `FleetContext` boundary only — all API responses use snake_case.

---

### Control Centre Routes and API Endpoints

**Frontend routes** (react-router-dom):
| Route | Component | View |
|-------|-----------|------|
| `/dashboard/live` | `LiveMonitoring.jsx` | Default — fleet list + unified feed |
| `/dashboard/health` | `SystemHealth.jsx` | System health grid + train panel |
| `/dashboard/analytics` | `Analytics.jsx` | Analytics tab router |

Train Detail panel opens within `/dashboard/live` — no separate route. State managed by `selectedTrainId` in `LiveMonitoring`.

**Cloud backend REST endpoints required** (additions to `cloud-backend/routes/`):

| Method | Path | Component consumer | Notes |
|--------|------|--------------------|-------|
| `GET` | `/api/v1/analytics/exceptions` | `ExceptionWorkflow.jsx` | Query params: `date_range=7d\|14d\|30d`. Returns capacity exceptions with Conrad flag data. |
| `GET` | `/api/v1/analytics/occupancy-heatmap` | `OccupancyHeatmap.jsx` | Query params: `date_range`. Returns route×hour avg occupancy matrix. |
| `GET` | `/api/v1/analytics/dwell-time` | `DwellTime.jsx` | Query params: `date_range`. Returns station dwell actual vs scheduled. |
| `GET` | `/api/v1/analytics/detection-quality` | `AIDetection.jsx` | Query params: `date_range`. Returns daily event counts + FP rate + uptime per train. |
| `POST` | `/api/v1/escalations/{id}/acknowledge` | `EscalationDetail.jsx` | Marks escalation acknowledged; triggers Conrad push. |
| `POST` | `/api/v1/escalations/{id}/resolve` | `EscalationDetail.jsx` | Body: `{ outcome, tags[] }`. Marks resolved; triggers Conrad push with outcome. |
| `POST` | `/api/v1/capacity-review-queue` | `ExceptionWorkflow.jsx` | Body: `{ exception_id, note, priority }`. Writes to fleet planning queue. |

All endpoints follow ADR-8 (`/api/v1/` prefix), ADR-10 (error envelope), cursor pagination where lists are returned.

---

### Control Centre Component → Scenario Mapping (updated)

Supersedes the earlier scenario→structure table for Control Centre rows:

| Scenario | Component | File |
|---|---|---|
| 04 — Claudia morning review (capacity exceptions) | `ExceptionWorkflow.jsx` | `analytics/ExceptionWorkflow.jsx` |
| 04 — Occupancy heatmap | `OccupancyHeatmap.jsx` | `analytics/OccupancyHeatmap.jsx` |
| 04 — Dwell time analysis | `DwellTime.jsx` | `analytics/DwellTime.jsx` |
| 04 — AI detection quality | `AIDetection.jsx` | `analytics/AIDetection.jsx` |
| 02d — Unattended bag escalation | `EscalationDetail.jsx` | `live/EscalationDetail.jsx` |
| 03 — Conrad capacity flag (view in dashboard) | `ExceptionWorkflow.jsx` (Conrad flag box) | `analytics/ExceptionWorkflow.jsx` |
| 11 — System health check | `SystemHealth.jsx` | `health/SystemHealth.jsx` |
| 12 — Live fleet monitoring | `LiveMonitoring.jsx`, `FleetList.jsx`, `UnifiedFeed.jsx` | `live/` |
| 12 — Train detail drill-in | `TrainDetail.jsx` | `train-detail/TrainDetail.jsx` |

---

### Production Implementation Delta (from Prototype)

These are the confirmed gaps from DD-001 §6 that implementation must close. Each is an explicit dev story, not an open question:

| # | Gap | Affected component | Priority |
|---|-----|--------------------|----------|
| 1 | Sort fleet list by passenger count (not severity) | `FleetList.jsx` | P1 — core spec |
| 2 | Alerts as first-class events from event-store (not derived from coach data) | `TrainDetail.jsx` | P1 — data integrity |
| 3 | Replace 3-option range picker with full 90-day date picker | `Analytics.jsx` | P1 — spec requirement |
| 4 | Wire "View Conrad's full flag →" to capacity flag record | `ExceptionWorkflow.jsx` | P1 — workflow complete |
| 5 | Replace mock data with real API queries for all analytics tabs | `ExceptionWorkflow`, `OccupancyHeatmap`, `DwellTime`, `AIDetection` | P1 — production data |
| 6 | Enable Maintenance App CTA (`MAINTENANCE_APP_ENABLED = true`) | `SystemHealth.jsx` | P2 — blocked on URL scheme |
| 7 | Loading skeleton states for all data-driven sections | All views | P2 — production polish |
| 8 | "N new items ↑" chip in unified feed | `UnifiedFeed.jsx` | P2 — Claudia UX |
| 9 | Wire KPI tile taps to activate matching filter pill | `LiveMonitoring.jsx` + `UnifiedFeed.jsx` | P2 — spec completeness |

---

### Open Questions Inherited from DD-001

These require stakeholder answers before the affected implementation stories can be closed:

| # | Question | Blocks | Owner |
|---|----------|--------|-------|
| 1 | `pose_estimation` per-coach seated/standing split feasible? | `TrainDetail` coach grid columns | Hailo-8 / Nomad Digital |
| 2 | WebSocket staleness threshold (default assumed 2 min) | Staleness banner + occupancy dimming | ÖBB operations |
| 3 | AI escalation confidence threshold | Alert volume management | ÖBB operations |
| 4 | Maintenance App deep-link URL scheme + auth handoff | `SystemHealth` CTA | Maintenance App team |
| 5 | 7-day trend query key — by train number or route+timeslot? | `ExceptionWorkflow` trend chart accuracy | Nomad Digital backend |
| 6 | Fleet planning queue — internal PostgreSQL or ÖBB external system? | `ExceptionWorkflow` "Add to review" POST | ÖBB operations |
| 7 | CCTV stream amber vs red threshold | `SystemHealth` badge colour logic | ÖBB / Nomad Digital |
| 8 | Applications amber vs red threshold (restarting vs exited?) | `SystemHealth` badge colour logic | ÖBB / Nomad Digital |
| 9 | Health poll interval for `rtsp-ingest` and `event-store` | "Updated Xs ago" freshness computation | Nomad Digital |
| 10 | Dismissed exceptions — stay visible (greyed) or fully hidden? | `ExceptionWorkflow` list state | ÖBB operations / Claudia |
