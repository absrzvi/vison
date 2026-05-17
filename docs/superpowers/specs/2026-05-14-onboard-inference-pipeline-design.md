# OEBB Onboard Inference Pipeline — Design Spec
**Date:** 2026-05-14
**Status:** Approved for implementation planning
**Related specs:** `2026-05-13-oebb-hailo8-ai-service-design.md` · `2026-05-13-oebb-ux-design.md`

---

## 1. Overview

This spec defines the containerised inference pipeline that runs on SYS2 of the R5001C CCU. It sits between raw VLAN data sources and the structured event store that feeds all onboard UI surfaces.

**Scope:** Core inference + aggregation layer only. Display layer (portal pages, staff app serving) and cloud sync agent are out of scope — this pipeline produces the structured events and API they consume.

**Approach:** Five purpose-built Docker containers on SYS2, communicating over Docker internal network via HTTP/WebSocket on localhost. Each container has one clear responsibility. Journey-scoped SQLite event store. REST + WebSocket API for onboard consumers. Cloud sync buffer for SYS1.

**Phase 1 targets:** Passenger portal (railnet_passenger), Conductor App. Exterior platform cameras included from Phase 1 for platform crowd detection and accessibility pre-alerting.

---

## 2. Container Overview

```
cameras.json
    │
rtsp-ingest ──────────────────────────────────────────────┐
(P1 always · P2 always · P3 station window only)          │
                                                      frames (priority queue)
vlan-pollers ─────────────────────────────────────────────┤
(SNMP · APC · PIS · Reservation)                          │ context deltas
                                                          ▼
                                                      inference
                                                      (Hailo-8 · HailoRT)
                                                      object detection
                                                      pose · tracking
                                                          │
                                                    raw detections
                                                          ▼
                                                       fusion
                                               derived metrics · alerts
                                               suppression · enrichment
                                               portal state · trip labels
                                                          │
                                               normalised events
                                                          ▼
                                                    event-store
                                                    (SQLite · journey-scoped)
                                                          │
                                          ┌───────────────┼───────────────┐
                                       REST/WS          REST/WS        /sync
                                          │               │               │
                                   passenger portal  conductor app   SYS1 → cloud
```

| Container | Image base | Responsibility |
|---|---|---|
| `rtsp-ingest` | Python + GStreamer | Connect to all CCTV RTSP streams on VLAN 5, apply priority scheduling, feed frames to `inference` |
| `vlan-pollers` | Python | Poll/receive SNMP (VLAN 7), APC (VLAN 8), PIS (VLAN 3), Reservation (VLAN 6). Maintain live context state, push deltas to `inference` and `fusion` |
| `inference` | Python + HailoRT + TAPPAS | Own the Hailo-8 device exclusively. Receive prioritised frames, run object detection / tracking / pose. Emit raw detection structs to `fusion` |
| `fusion` | Python | Receive raw detections + live context. Apply all fusion rules, suppression, enrichment, trip labelling. Write normalised Events to `event-store` |
| `event-store` | Python + SQLite | Persist events scoped to current journey. Serve REST + WebSocket API. Manage cloud sync buffer |

**Operations:** Docker restart policies handle transient failures. Container health monitoring is handled by Nomad Digital's existing SYS1 remote management — no additional watchdog container needed.

---

## 3. `rtsp-ingest` Container

**Responsibility:** Connect to all CCTV cameras on VLAN 5, maintain prioritised frame delivery to `inference`.

### Priority tiers

| Priority | Camera type | Target frame rate | Active when |
|---|---|---|---|
| P1 — Always live | Door / vestibule cameras | 10 fps | Always |
| P2 — Regular | Coach interior cameras | 5 fps | Always (throttled first if Hailo-8 budget exceeded) |
| P3 — Station only | Exterior / platform cameras | 8 fps | Station window only |

### P3 station window gate

Activate when ALL three conditions true:
- `next_station` has changed (PIS announces upcoming stop)
- `speed_kmh < 40` (`im0vstSlowDrive`)
- `door_release_left OR door_release_right = true`

Deactivate when:
- `door_release = false` AND `driving = true`

`rtsp-ingest` holds a copy of vehicle context from `vlan-pollers`. When gate is inactive, P3 RTSP connections are maintained but frames are not decoded or queued — zero inference cost mid-journey.

### Required detections per camera type

| Camera type | Required detections |
|---|---|
| P1 door / vestibule | Person count per zone, stationary object + timer, bicycle in door zone, door obstruction (binary) |
| P2 interior | Seated headcount, rack occupancy %, luggage count, bicycle count, wheelchair/pushchair detection, smoke, vandalism, pose keypoints (slip/fall) |
| P3 exterior | Person count per platform zone per door position, crowd density per zone, wheelchair/pushchair/mobility aid detection |

### Frame tagging

Every frame tagged at ingest: `camera_id`, `coach_id`, `zone` (door-left, door-right, vestibule, interior, platform-left, platform-right), `priority`, `timestamp`.

### Stream failure

Retry with exponential backoff. Camera marked `DEGRADED` in context — fusion treats that coach/zone as stale. P3 failure during station window suppresses platform guidance for that door position only.

### Configuration

Single `cameras.json` per train formation. Maps each RTSP URL to: `camera_id`, `coach_id`, `zone`, `priority`. Only file that changes between train types.

---

## 4. `vlan-pollers` Container

**Responsibility:** Maintain a lean in-memory context state from non-video VLANs. Only fields consumed by onboard UI surfaces or needed to gate/suppress/enrich inference results.

### Context state object

```json
{
  "vehicle": {
    "maintenance_mode": false,
    "driving": true,
    "speed_kmh": 87,
    "door_release_left": false,
    "door_release_right": true,
    "prm_door_release_left": false,
    "prm_door_release_right": false,
    "wheelchair_ramp_left": false,
    "wheelchair_ramp_right": false,
    "coupling_in_progress": false,
    "shutdown_imminent": false
  },
  "trip": {
    "trip_number": 4821,
    "route_name": "Wien Hbf – Salzburg",
    "current_station": "Linz Hbf",
    "next_station": "Wels"
  },
  "alarms": {
    "active": ["DOOR_FAULT_C3L", "HVAC_WARN_C5"],
    "last_changed": "2026-05-14T09:14:33Z"
  },
  "apc": {
    "coach_counts": { "C1": 42, "C2": 38, "C3": 71, "C4": 29 }
  },
  "pis": {
    "delay_minutes": 0,
    "platform_change": null
  },
  "reservation": {
    "by_coach": { "C1": 18, "C2": 22, "C3": 55, "C4": 14 }
  }
}
```

### Fields excluded from Phase 1 and why

| Excluded | Reason |
|---|---|
| GPS lat/lon/heading/altitude | Not consumed by any onboard UI — cloud analytics only |
| Outside temperature | Diagnostics AI — cloud layer, Phase 2 |
| Energy kW/kWh | Analytics/sustainability — cloud layer, Tier 3 |
| Bistro stock/sales | Bistro app is Tier 3 — not in Phase 1 scope |
| `degraded_operation`, `energy_mode`, `parking_active`, `odometer_km` | Maintenance dashboard — landside cloud, not onboard pipeline |
| `driver_id`, `destination`, `start_station` | Analytics trip labelling — cloud sync metadata only |

### Per-source polling strategy

| Source | VLAN | Method | Interval |
|---|---|---|---|
| Stadler vehicle state | 7 | TRAP/INFORM push + GET fallback | On change |
| Stadler alarms | 7 | TRAP/INFORM push + counter-gated GET | On change |
| Stadler trip info | 7 | INFORM periodic | 30s |
| APC door counts | 8 | SNMP GET, counter-gated | On door event |
| PIS state | 3 | Poll | 10s |
| Reservation | 6 | Poll | 60s |

### Push to consumers

On any context field change, HTTP POST the delta to `inference` and `fusion`. Both containers hold a full copy in memory — no polling between containers. `shutdown_imminent = true` triggers immediate flush signal to `event-store`.

### Multi-vehicle trains

Config lists all vehicle IM IP addresses for the formation (up to 4). Each vehicle's SNMP polled independently; results merged by vehicle index. During `coupling_in_progress = true`, topology-dependent alerts suppressed in fusion.

---

## 5. `inference` Container

**Responsibility:** Own the Hailo-8 device exclusively. Run neural network inference on prioritised frames. Emit raw detection structs to `fusion`. No business logic.

### Model allocation

| Model | Camera tiers | Output |
|---|---|---|
| Object detection (YOLOv5/8) | P1 + P2 + P3 | Bounding boxes + class labels: person, bag, suitcase, bicycle, wheelchair, pushchair, mobility aid |
| Pose estimation | P2 interior only | Keypoints per person — slip/fall, seated vs standing |
| Tracking | P1 + P2 only | Persistent object IDs across frames — unattended item timer, zone dwell, vestibule crowd build-up |

P3 exterior: object detection only. No tracking, no pose. Crowd density derived from per-frame person counts — no cross-frame identity needed.

### Compute budget

- P1 always gets inference slots
- P3 active only during station window — shares budget with P2 when gate opens
- If Hailo-8 utilisation exceeds 85%: P2 throttles to 3 fps, P3 throttles to 4 fps, P1 never touched

### Context gating — applied before inference

| Context signal | Effect |
|---|---|
| `maintenance_mode = true` | Drop all frames — no inference |
| `coupling_in_progress = true` | Drop P2 + P3 frames — P1 continues |
| P3 station window inactive | Drop all P3 frames regardless of queue |

### Raw detection output struct

One per frame, HTTP POST to `fusion`:

```json
{
  "camera_id": "C3-VEST-L",
  "coach_id": "C3",
  "zone": "vestibule",
  "priority": "P1",
  "timestamp": "2026-05-14T09:14:33.412Z",
  "frame_seq": 18842,
  "detections": [
    {
      "object_id": "trk_0042",
      "class": "person",
      "confidence": 0.94,
      "bbox": [x, y, w, h],
      "pose_keypoints": [],
      "stationary_frames": 0
    },
    {
      "object_id": "trk_0078",
      "class": "bag",
      "confidence": 0.91,
      "bbox": [x, y, w, h],
      "stationary_frames": 312
    }
  ],
  "zone_counts": {
    "persons": 3,
    "bags": 1,
    "bicycles": 0,
    "wheelchairs": 0,
    "pushchairs": 0
  }
}
```

`stationary_frames` is maintained by the tracker inside `inference` — increments every frame an object's bbox doesn't move beyond jitter threshold. `fusion` derives the unattended item timer from this without tracking object history itself.

### What `inference` does NOT do

No severity classification, no alert generation, no APC calibration, no rack occupancy calculation, no knowledge of trip ID, station, alarm state, or platform context.

---

## 6. `fusion` Container

**Responsibility:** Receive raw detections from `inference` and live context from `vlan-pollers`. Apply all fusion rules, suppression logic, enrichment, trip labelling. Write normalised Events to `event-store`. No hardware access, no display logic.

### 6.1 Derived metrics — computed every inference cycle per coach

| Metric | Derived from | Output |
|---|---|---|
| `occupancy_pct` | Camera headcount fused with APC — APC is ground truth, camera fills gaps between door events | Per coach, 0–100+ % |
| `rack_pct` | Luggage bbox density in overhead zone from P2 interior | Per coach, 0–100 % |
| `luggage_flag` | `rack_pct > 80` | Per coach boolean |
| `zone_density` | Person counts per zone (seats/aisle/door/vestibule) from P1+P2 | Per coach, per zone count |
| `congestion_score` | `occupancy_pct × 0.6 + vestibule_density × 0.3 + rack_pct × 0.1` | Per coach, 0–100 |
| `bicycle_count` | P1+P2 bicycle detections | Per coach integer |
| `prm_space_status` | Wheelchair/pushchair detected in PRM zone | Per coach: `free` / `occupied` |

**APC fusion rule:** On each APC door event, recalibrate camera-derived count for that coach. If camera count diverges from APC by >15%, use APC as authoritative and log calibration delta. Camera count used between door events.

### 6.2 Alert generation rules

Each alert produces a normalised Event with: `type`, `severity`, `coach_id`, `zone`, `title`, `sub`, `timestamp`, `trip_number`, `source`.

**Passenger safety alerts:**

| Alert | Trigger | Severity | Suppressed when |
|---|---|---|---|
| Door obstruction | Person/bag/bicycle in door zone AND `door_release = true` | `high` | `maintenance_mode = true` |
| Door obstruction at speed | Above AND `speed_kmh > 0` AND `driving = true` | `fire` | Never |
| Vestibule crowding | Vestibule zone density > 8 persons for >30s | `warning` | `maintenance_mode = true` |
| Unattended item | `stationary_frames > threshold` (default 5 min) AND no owner nearby | `info` → `high` after 10 min | `maintenance_mode = true` |
| Rack saturation | `rack_pct > 90` AND large boarding predicted at next stop | `warning` | — |
| Bicycle in door zone | Bicycle class in vestibule | `medium` | `maintenance_mode = true` |
| Occupancy imbalance | Coaches 1–4 avg >80% AND coaches 7–10 avg <40% | `warning` | — |
| Slip / fall | Person horizontal + stationary >10s, no self-recovery | `high` | `maintenance_mode = true` |
| Smoke detected | Smoke class confidence >0.85 | `fire` | Never |
| Vandalism | Vandalism class detected | `high` | `maintenance_mode = true` |
| Prohibited zone | Person detected in restricted zone bbox | `high` | `maintenance_mode = true` |

**Accessibility alerts:**

| Alert | Trigger | Severity |
|---|---|---|
| Wheelchair onboard | Wheelchair/pushchair in P2 interior | `info` |
| PRM door + wheelchair | `prm_door_release = true` AND wheelchair in that coach | `info` |
| Platform wheelchair detected | P3: wheelchair class AND station window active | `info` — ramp prep alert |
| Ramp deployed | `wheelchair_ramp_left/right = true` | `info` — updates portal to `ramp_ready` |

**Door alarm cross-correlation:**

| Camera | TCMS alarm | Result |
|---|---|---|
| Obstruction detected | No TCMS alarm | `medium` — possible obstruction or camera noise |
| No obstruction | TCMS door alarm active | `medium` — possible sensor fault |
| Obstruction detected | TCMS door alarm active | `fire` — both systems agree, highest confidence |

**Global suppression rules:**
- `maintenance_mode = true` → suppress all non-fire alerts
- `coupling_in_progress = true` → suppress topology-dependent alerts
- `shutdown_imminent = true` → flush event buffer, suppress new alert generation

### 6.3 Passenger portal state output

After each inference cycle, `fusion` writes a portal state object to `event-store`:

```json
{
  "coaches": [
    { "n": 1, "pct": 88 },
    { "n": 2, "pct": 38, "recommended": true },
    { "n": 3, "pct": 60, "luggage": true },
    { "n": 4, "pct": 72, "prm": "free" }
  ],
  "guidance": {
    "tone": "recommend",
    "direction": "right",
    "primary": "Gehen Sie zu Wagen 2",
    "sub": "Viel Platz · Gepäckfach frei",
    "platformHint": "Nach rechts am Bahnsteig"
  },
  "access": {
    "tone": "free",
    "status": "Rollstuhlplatz frei",
    "detail": "Wagen 2 · Tür 1",
    "ramp": { "state": "preparing", "text": "Rampe wird vorbereitet …" },
    "conradAlert": true
  },
  "freshness": "2026-05-14T09:14:33Z",
  "stale": false
}
```

**Recommendation logic:**
- `recommended` coach = lowest `occupancy_pct` among coaches without `luggage_flag`
- `platformHint` populated only during P3 station window — derived from platform zone with lowest crowd density aligned to recommended coach door
- `stale = true` if no inference result received in last 60s
- `guidance = null` if spread between lowest and highest coach occupancy < 20%

### 6.4 Trip labelling

Every event tagged with `trip_number`, `route_name`, `current_station` from live context. If `im0triValid = false`, fall back to PIS `current_station` and generate local trip token `SYS2-{boot_timestamp}` as trip ID.

---

## 7. `event-store` Container

**Responsibility:** Persist normalised events scoped to current journey. Serve REST + WebSocket API to onboard consumers. Buffer events for cloud sync.

### 7.1 Storage

SQLite on a Docker volume. Two tables:

**`events`** — append-only log:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `trip_number` | TEXT | From fusion trip label |
| `timestamp` | TEXT | ISO-8601 |
| `type` | TEXT | `passenger_safety`, `accessibility`, `diagnostics`, `system` |
| `severity` | TEXT | `fire`, `high`, `medium`, `warning`, `info` |
| `coach_id` | TEXT | |
| `zone` | TEXT | |
| `title` | TEXT | Display-ready |
| `sub` | TEXT | Display-ready |
| `source` | TEXT | `hailo_camera`, `snmp_alarm`, `fusion_rule` |
| `resolved_at` | TEXT | NULL until resolved |
| `synced` | INTEGER | 0 = pending, 1 = synced |

**`portal_state`** — single row, overwritten each fusion cycle:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Always row 1 |
| `coaches_json` | TEXT | Serialised coach array |
| `guidance_json` | TEXT | Serialised guidance object |
| `access_json` | TEXT | Serialised accessibility object |
| `updated_at` | TEXT | Timestamp of last fusion write |

**Journey scoping:** On `shutdown_imminent`, mark journey complete and write `journey_end` system event. On next boot, new journey begins. Previous journey retained in SQLite until cloud sync confirms receipt, then pruned.

### 7.2 REST API

| Endpoint | Method | Consumer | Returns |
|---|---|---|---|
| `/portal` | GET | Passenger portal | Latest `portal_state` row |
| `/alerts/active` | GET | Conductor app | All unresolved events, sorted by severity |
| `/alerts/history` | GET | Conductor app, Technician app | All events for current journey, filterable by `?coach=`, `?type=`, `?severity=` |
| `/coaches` | GET | Conductor app | Per-coach metrics: `occupancy_pct`, `rack_pct`, `zone_density`, `congestion_score`, `bicycle_count`, `prm_space_status` |
| `/alerts/:id/resolve` | POST | Conductor app | Mark event `resolved_at = now()` |
| `/sync/pending` | GET | Cloud sync agent (SYS1) | All events where `synced = 0` |
| `/sync/confirm` | POST | Cloud sync agent | Mark event IDs as `synced = 1` |
| `/health` | GET | SYS1 remote management | Container status, last fusion write timestamp, SQLite row count |

### 7.3 WebSocket API

Single endpoint: `ws://localhost:PORT/live`

| Message type | Payload | Consumer |
|---|---|---|
| `portal_update` | Full portal state object | Passenger portal — real-time coach diagram updates |
| `alert_new` | Single new event | Conductor app — push to alert feed |
| `alert_resolved` | Event ID + resolved timestamp | Conductor app — auto-clear resolved alerts |
| `coach_update` | Per-coach metrics for all coaches | Conductor app home screen |

If no `portal_update` pushed for >60s, `event-store` emits a `portal_update` with `stale: true`.

### 7.4 Cloud sync buffer

- Cloud sync agent on SYS1 polls `/sync/pending` every 30s (configurable)
- Posts confirmed IDs to `/sync/confirm`
- During connectivity gaps events accumulate with `synced = 0` — no data loss
- Raw video never enters sync buffer — structured event rows only
- At journey end, sync agent performs final flush of all `synced = 0` rows before journey is pruned

---

## 8. Data flow summary

| Stage | Input | Output |
|---|---|---|
| `rtsp-ingest` | RTSP streams VLAN 5 | Priority-tagged frames → `inference` |
| `vlan-pollers` | SNMP/APC/PIS/Reservation VLANs 7/8/3/6 | Context state deltas → `inference` + `fusion` |
| `inference` | Frames + context gates | Raw detection structs → `fusion` |
| `fusion` | Detections + context | Normalised events + portal state → `event-store` |
| `event-store` | Normalised events | REST/WebSocket API → portal + apps; sync buffer → SYS1 |

---

## 9. Phase 1 delivery scope

| Container | Phase 1 | Notes |
|---|---|---|
| `rtsp-ingest` | P1 + P2 + P3 (station gate) | Full camera tier support from Phase 1 |
| `vlan-pollers` | SNMP + APC + PIS + Reservation | Bistro/Energy/ZFR deferred to Phase 2 |
| `inference` | Object detection + tracking + pose | All three models from Phase 1 |
| `fusion` | Tier 1 alert rules + portal state + accessibility | Tier 2/3 rules added in Phase 2 without restructuring |
| `event-store` | Full REST + WebSocket + sync buffer | Complete from Phase 1 |

---

## 10. Open questions for PoC

- [ ] RTSP stream URLs and credentials for VLAN 5 — obtain from Stadler during commissioning
- [ ] APC SNMP OIDs for door count events — confirm format from AFZ central unit (VLAN 8)
- [ ] Reservation data protocol — confirm access schema (VLAN 6)
- [ ] Hailo-8 model selection — validate YOLOv5 vs YOLOv8 on PoC hardware for accuracy/throughput trade-off
- [ ] Camera placement per coach — confirm door/vestibule/interior camera positions to populate `cameras.json`
- [ ] Unattended item timer threshold — confirm with OEBB security team (default 5 min in spec)
- [ ] Occupancy thresholds — confirm green/amber/red breakpoints with OEBB (portal mockup uses 0–60% / 61–85% / 86–100%)
