# E4 Remaining Stories — EventType Coverage Audit

**Date:** 2026-05-19  
**Source of truth:** `shared/src/oebb_shared/events/types.py` + `_bmad-output/planning-artifacts/event-payload-schemas.md`  
**Audit scope:** E4-S5, E4-S6, E4-S7, E4-S8, E4-S9, E4-S10, E4-CS1  
**Action item:** Epic-1 retrospective A2 (gap detection *before* writing stories, not after f6d377c)

---

## Current EventType Inventory

The canonical enum in `shared/src/oebb_shared/events/types.py` (lines 4–40) defines 25 EventTypes:

### By Category

**Occupancy (2)**
- `OCCUPANCY_UPDATE`
- `OCCUPANCY_THRESHOLD_CROSSED`

**Alerts (2)**
- `ALERT_RAISED`
- `ALERT_RESOLVED`

**Congestion & Luggage (2)**
- `VESTIBULE_CONGESTION`
- `LUGGAGE_RACK_SATURATION`

**Safety (2)**
- `UNATTENDED_BAG`
- `DOOR_OBSTRUCTION`

**Accessibility (2)**
- `ACCESSIBILITY_DETECTED`
- `RAMP_DEPLOYED`

**TCMS / Alarms (2)**
- `ALARM_ACTIVE`
- `ALARM_CLEARED`

**Journey (2)**
- `JOURNEY_STARTED`
- `JOURNEY_ENDED`

**System (2)**
- `CAMERA_DEGRADED`
- `CAMERA_RECOVERED`

**Inter-wagon Movement (3)**
- `WAGON_EXIT`
- `WAGON_ENTRY`
- `LEDGER_DRIFT_ALERT`

**Calibration (1)**
- `CALIBRATION_DRIFT`

**Comfort (1)**
- `COACH_COMFORT_INDEX`

**Internal/System (2)**
- `SYNC_COMPLETED`
- `STREAM_PRIORITY` (never written to event-store; fusion→rtsp-ingest internal command only)

---

## Per-Story Coverage

### E4-S5 — `inference` Safety & Accessibility Detection

**Emits:**
- `DOOR_OBSTRUCTION` ✓ (line 1326; inference sends candidate to fusion; payload defined)
- `ACCESSIBILITY_DETECTED` ✓ (line 1330; emitted with car_id, zone, detection_type, door_id, confidence)
- `RAMP_DEPLOYED` ✓ (line 1334; fusion receives ramp signal from vlan-pollers and emits; payload defined)
- `ALERT_RAISED` ✓ (line 1338; slip/fall heuristic emitted to fusion with alert_type: "slip_fall"; payload defined)
- `VESTIBULE_CONGESTION` ✓ (line 1342; emitted with car_id, zone, count, threshold; payload defined)

**Consumes:**
- `JOURNEY_STARTED` (context state — journey_id / consist) ✓
- Ramp signal via context state (not an event; TCMS signal routed through vlan-pollers) ✓

**Gaps:** None. All events have defined EventTypes and payload schemas.

---

### E4-S6 — `fusion` Alert Correlation & Suppression State Machine

**Emits:**
- `ALERT_RAISED` ✓ (lines 1367, 1371; door obstruction, speed-correlated escalation; payload defined)
- `JOURNEY_ENDED` ✓ (line 1375; on depot shutdown; payload defined)
- `OCCUPANCY_UPDATE` ✓ (line 1379; fusion uses camera count as authoritative; payload defined at E1-S3)

**Consumes:**
- `DOOR_OBSTRUCTION` (candidate from E4-S5) ✓
- `ACCESSIBILITY_DETECTED` (implied enrichment at line 1391) ✓
- `UNATTENDED_BAG` (implied in acceptance — line 1391 lists `unattended_bag.py` module) — EventType exists ✓
- `VESTIBULE_CONGESTION` (context/suppression logic) ✓
- Context state signals: `MAINTENANCE_MODE`, `speed_kmh`, `im0vstShutdownAll` (SNMP, not events) ✓

**Gaps:** None. All event references have existing EventTypes and payload schemas. Internal suppression signals (MAINTENANCE_MODE, SNMP) are context state, not events.

---

### E4-S7 — `event-store` Onboard REST API & WebSocket Fan-Out

**Emits:**
- No new events. This is a **transport/storage layer** story. It reads events from `inference` and `fusion` and stores/distributes them.
- Consumes: All EventTypes via `POST /api/v1/events` (generic EventEnvelope handler; line 1403).

**Filters/Queries supported:**
- `event_type`, `journey_id`, `min_severity` (line 1411 — generic filtering, not event-type-specific).

**Gaps:** None. E4-S7 is envelope-agnostic.

---

### E4-S8 — Gangway Tripwire Ingest (Inter-Wagon Movement)

**Emits:**
- `WAGON_EXIT` ✓ (line 1472; payload: track_id, coach_from, coach_to, camera_id, direction, confidence; schema at lines 338–350)
- `WAGON_ENTRY` ✓ (line 1476; same payload; schema at lines 354–365)

**Consumes:**
- `OCCUPANCY_UPDATE` (implied — initial ledger count source) ✓

**Internal:** 
- Orphaned exit notification to fusion (structured log, not event) — no EventType needed ✓

**Gaps:** None. Both WAGON_* EventTypes and schemas defined; confidence threshold logic (< 0.70) covered in AC.

---

### E4-S9 — Closed-Ledger Reconciliation Engine

**Emits:**
- `LEDGER_DRIFT_ALERT` ✓ (line 1517; payload: expected_total, actual_total, delta, coach_breakdown, reconciliation_applied; schema at lines 368–385)

**Consumes:**
- `WAGON_EXIT` ✓
- `WAGON_ENTRY` ✓
- `OCCUPANCY_UPDATE` (initial ledger at journey start) ✓
- Context state: `station_approach` flag (not an event) ✓

**Internal:**
- `coach_ledger` SQLite state machine (line 1505; not an event) ✓
- Orphaned timeout (line 1509; 10-second window, no event emitted) ✓

**Gaps:** None. All emitted and consumed EventTypes and schemas defined.

---

### E4-S10 — Coach Comfort Index

**Emits:**
- `COACH_COMFORT_INDEX` ✓ (line 1542, 1546; payload: car_id, reserved_seats, occupied_seats, standing_count, comfort_score, service_tier; schema at lines 393–407)

**Consumes:**
- `OCCUPANCY_UPDATE` (line 1540; triggers comfort calculation on 10% delta or station approach) ✓
- Context state: `ContextState.reservations`, `ContextState.station_approach` (not events) ✓

**Gaps:** None. EventType and schema defined.

---

### E4-CS1 — Cloud-Sync Container (Onboard MQTT Gateway)

**Emits:**
- No new EventTypes. This is a **pure transport layer** (line 1451).
- Subscribes to `event-store` SQLite sync cursor and publishes all events to Mosquitto broker on topic `oebb/events/{vehicle_id}/{event_type}`.
- **Does NOT interpret or transform payloads** — reads envelope verbatim.

**Consumes:**
- All EventTypes (generic; follows sync cursor) ✓

**Gaps:** None. E4-CS1 is envelope-agnostic, never generates new event types.

---

## Summary of Gaps

| Missing EventType | Proposed Payload Fields | Which Stories Need It | Severity | Status |
|---|---|---|---|---|
| **(None)** | — | — | — | **✓ All gaps filled** |

### Reconciliation vs. Acceptance Criteria

A detailed review of all acceptance criteria in E4-S5 through E4-S10 and E4-CS1 confirms:

1. **E4-S5** emits 5 events (DOOR_OBSTRUCTION, ACCESSIBILITY_DETECTED, RAMP_DEPLOYED, ALERT_RAISED, VESTIBULE_CONGESTION) — all have EventTypes and schemas.
2. **E4-S6** consumes those 5 and emits ALERT_RAISED, JOURNEY_ENDED, OCCUPANCY_UPDATE — all defined. Suppression signals (MAINTENANCE_MODE, speed_kmh, SNMP) are context state, not event types.
3. **E4-S7** is envelope-agnostic transport; no new EventTypes needed.
4. **E4-S8** emits WAGON_EXIT, WAGON_ENTRY (both defined; commit f6d377c addressed this pre-PoC).
5. **E4-S9** consumes WAGON_* and OCCUPANCY_UPDATE; emits LEDGER_DRIFT_ALERT (all defined).
6. **E4-S10** consumes OCCUPANCY_UPDATE and context state; emits COACH_COMFORT_INDEX (defined).
7. **E4-CS1** is stateless transport; no new EventTypes.

**Note on vague deliverables:**
- E4-S6 acceptance criteria explicitly list 7 modules: `suppression.py`, `door_obstruction.py`, `occupancy.py`, `congestion.py`, `accessibility.py`, `unattended_bag.py`, `enrichment.py` (line 1391). All referenced events have defined types.
- E4-S7 acceptance criteria are precise: REST endpoints (POST, GET), WebSocket subscription, cursor pagination (lines 1403–1425).
- E4-S8 through E4-S10 deliverables are concrete (specific .py files and schemas).

---

## Recommendation

**No EventType contract-test work required before E4-S5–S10 story implementation begins.** The shared/events/types.py enum and event-payload-schemas.md are **complete and sufficient** for all remaining E4 stories. The schema contract tests should verify:

1. **Payload structure parity:** Every acceptance criterion's emitted event matches its schema in event-payload-schemas.md (verified ✓).
2. **Roundtrip via event-store:** E4-S7 accepts and stores all EventTypes without crashing (generic envelope handler; contract test already proposed at line 1428).
3. **Suppression state isolation:** E4-S6's internal context signals (MAINTENANCE_MODE, speed_kmh, SNMP) do **not** leak into the event envelope (verified ✓; ADR-1 enforces this).

**Proceed with story development immediately.** No blockers detected. If any acceptance criterion in S5–S10 discovers a new event type at implementation time, add it to types.py and the schema doc, then backfill a contract test — but this is not expected given the detailed AC coverage.

---

## Audit Metadata

- **Reviewed files:**
  - `shared/src/oebb_shared/events/types.py` (lines 1–40; 25 EventTypes)
  - `_bmad-output/planning-artifacts/event-payload-schemas.md` (lines 1–450; 17 schemas defined)
  - `_bmad-output/planning-artifacts/epics.md` (lines 1316–1565; E4-S5 through E4-S10, E4-CS1 stories)
- **Verification method:** Line-by-line mapping of story acceptance criteria to EventType enum and schema definitions.
- **Date:** 2026-05-19
- **Next action:** Proceed to story development; no contract or enum changes required.