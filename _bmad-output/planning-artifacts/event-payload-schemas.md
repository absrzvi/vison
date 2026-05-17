# Event Payload Schemas — OEBB Smart Rail PoC

**Status:** Approved  
**Date:** 2026-05-16  
**Relates to:** ADR-1 (Event Envelope), ADR-5 (EventType Taxonomy)  
**Referenced by:** epics.md, architecture.md

All payloads are the `payload` field inside the canonical event envelope:
```json
{
  "event_id": "<uuid-v4>",
  "journey_id": "<vehicle_id>_<trip_number>_<journey_start_date_YYYYMMDD>",
  "vehicle_id": "<string>",
  "timestamp": "<ISO-8601 UTC with Z suffix>",
  "event_type": "<EventType enum value>",
  "severity": "critical | warning | info",
  "source": "inference | fusion | vlan-pollers",
  "payload": { }
}
```

---

## Cross-Cutting Constraints

| Rule | Detail |
|---|---|
| All timestamps | ISO-8601 UTC, `Z` suffix, millisecond precision preferred |
| `car_id` | Always matches a value in `consist` from JOURNEY_STARTED |
| `camera_id` | Format `cam-<car_number>-<index_two_digit>` e.g. `cam-3-02` |
| `door_id` | Format `<car_id>-door-<L\|R>-<index>` e.g. `car-1-door-L-2` |
| `rack_id` | Format `<car_id>-rack-<descriptor>` e.g. `car-2-rack-upper-left` |
| `track_id` | Short-lived per-journey tracking ID — not globally stable |
| Lifecycle pairs | ALERT_RAISED/RESOLVED, ALARM_ACTIVE/CLEARED, CAMERA_DEGRADED/RECOVERED must share their ID field |
| `confidence` | Omitted (not set to 0) when inference is unavailable |
| `zone` | Nullable where detection zone cannot be determined — never omitted entirely |

---

## Occupancy

### OCCUPANCY_UPDATE
**Source:** `inference` · Published ~1 Hz per car

```json
{
  "car_id": "car-3",
  "zone": null,
  "occupancy_count": 142,
  "occupancy_pct": 0.71,
  "capacity": 200,
  "confidence": 0.94,
  "service_tier": "business"
}
```

### OCCUPANCY_THRESHOLD_CROSSED
**Source:** `inference` · Fired when pct crosses a configured threshold boundary (rising or falling)

```json
{
  "car_id": "car-1",
  "zone": null,
  "threshold_pct": 0.80,
  "direction": "rising",
  "occupancy_pct": 0.82,
  "occupancy_count": 164,
  "capacity": 200,
  "service_tier": "standard"
}
```

---

## Alerts

### ALERT_RAISED
**Source:** `fusion` · `alert_id` is a stable UUID — must pair with ALERT_RESOLVED using the same `alert_id`

```json
{
  "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
  "alert_code": "OVERCROWDING",
  "car_id": "car-2",
  "zone": "vestibule-b",
  "description": "Occupancy exceeded 90% for more than 60 seconds.",
  "auto_resolve_after_s": 300
}
```

### ALERT_RESOLVED
**Source:** `fusion` · `alert_id` must match a prior ALERT_RAISED

```json
{
  "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
  "alert_code": "OVERCROWDING",
  "car_id": "car-2",
  "zone": "vestibule-b",
  "resolve_reason": "manual | auto | condition_cleared"
}
```

---

## Congestion & Luggage

### VESTIBULE_CONGESTION
**Source:** `inference` · Fired when congestion score crosses threshold

```json
{
  "car_id": "car-4",
  "vestibule_id": "vestibule-a",
  "congestion_score": 0.87,
  "person_count": 11,
  "dwell_time_avg_s": 42.5,
  "threshold_score": 0.75
}
```

### LUGGAGE_RACK_SATURATION
**Source:** `inference` · Fired once per saturation event, not on every frame

```json
{
  "car_id": "car-2",
  "rack_id": "car-2-rack-upper-left",
  "fill_pct": 0.95,
  "item_count": 7,
  "confidence": 0.88
}
```

---

## Safety

### UNATTENDED_BAG
**Source:** `inference` · `dwell_s` = elapsed time since owner last detected near bag; payload immutable once emitted

```json
{
  "car_id": "car-3",
  "zone": "seating-mid",
  "track_id": "bag-0042",
  "dwell_s": 180.0,
  "bbox": { "x": 412, "y": 308, "w": 64, "h": 48 },
  "camera_id": "cam-3-02",
  "confidence": 0.91
}
```

### DOOR_OBSTRUCTION
**Source:** `inference` · Fired on detection; clearance triggers ALERT_RESOLVED

```json
{
  "car_id": "car-1",
  "door_id": "car-1-door-L-2",
  "obstruction_type": "person | object | unknown",
  "track_id": "person-0117",
  "camera_id": "cam-1-door-L2",
  "confidence": 0.96,
  "door_state": "open | closing | closed"
}
```

---

## Accessibility

### ACCESSIBILITY_DETECTED
**Source:** `inference` · Triggers downstream ramp/staff workflow; `assistance_type` is an array (multiple types possible)

```json
{
  "car_id": "car-2",
  "zone": "vestibule-b",
  "track_id": "person-0204",
  "assistance_type": ["wheelchair"],
  "camera_id": "cam-2-vest-b",
  "confidence": 0.89,
  "near_door_id": "car-2-door-R-1"
}
```

`assistance_type` values: `wheelchair | pram | crutches | visual_impairment | other`

### RAMP_DEPLOYED
**Source:** `fusion` · Emitted after ACCESSIBILITY_DETECTED + ramp actuation signal confirmed from vlan-pollers

```json
{
  "car_id": "car-2",
  "door_id": "car-2-door-R-1",
  "triggered_by_track_id": "person-0204",
  "deployed_by": "auto | manual",
  "station_id": "Wien Hauptbahnhof"
}
```

---

## TCMS / Alarms

### ALARM_ACTIVE
**Source:** `vlan-pollers` · `alarm_id` is the hardware-side identifier; must pair with ALARM_CLEARED

```json
{
  "alarm_id": "hw-alarm-00391",
  "alarm_type": "passenger_call",
  "car_id": "car-5",
  "zone": "seating-rear",
  "hardware_code": "PC-04",
  "triggered_by": "passenger | automatic | unknown"
}
```

`alarm_type` values: `emergency_brake | fire | passenger_call | intrusion | other`

### ALARM_CLEARED
**Source:** `vlan-pollers` · `alarm_id` must match a prior ALARM_ACTIVE

```json
{
  "alarm_id": "hw-alarm-00391",
  "alarm_type": "passenger_call",
  "car_id": "car-5",
  "cleared_by": "crew | automatic | unknown",
  "duration_s": 47.2
}
```

---

## Journey

### JOURNEY_STARTED
**Source:** `vlan-pollers` · Emitted once on departure; `journey_id` in envelope is constructed from these fields

```json
{
  "trip_number": "RJ-0847",
  "origin_station_id": "Wien Hbf",
  "scheduled_departure": "2026-05-16T06:00:00Z",
  "actual_departure": "2026-05-16T06:02:14Z",
  "consist": ["car-1", "car-2", "car-3", "car-4", "car-5"],
  "service_class": "railjet"
}
```

### JOURNEY_ENDED
**Source:** `vlan-pollers` · `journey_id` in envelope must match JOURNEY_STARTED

```json
{
  "trip_number": "RJ-0847",
  "destination_station_id": "Salzburg Hbf",
  "scheduled_arrival": "2026-05-16T08:50:00Z",
  "actual_arrival": "2026-05-16T08:53:41Z",
  "total_duration_s": 10287.0,
  "peak_occupancy_pct": 0.91
}
```

---

## System

### CAMERA_DEGRADED
**Source:** `inference` · Must pair with CAMERA_RECOVERED

```json
{
  "camera_id": "cam-3-02",
  "car_id": "car-3",
  "degradation_type": "low_fps",
  "fps_actual": 3.2,
  "fps_expected": 25.0,
  "quality_score": 0.21,
  "affected_zones": ["seating-mid"]
}
```

`degradation_type` values: `offline | low_fps | blur | occlusion | night_failure`

### CAMERA_RECOVERED
**Source:** `inference` · `camera_id` must match a prior CAMERA_DEGRADED; `downtime_s` = wall-clock duration of degraded period

```json
{
  "camera_id": "cam-3-02",
  "car_id": "car-3",
  "downtime_s": 214.5,
  "fps_actual": 24.8,
  "quality_score": 0.93
}
```

### STREAM_PRIORITY
**Source:** `fusion` · Internal command to `rtsp-ingest` only — **not written to SQLite, not published via MQTT**

```json
{
  "camera_ids": ["cam-2-door-L1", "cam-2-door-R1"],
  "priority_override": "P1",
  "reason": "door_release",
  "duration_s": 120
}
```

`reason` values: `door_release | station_approach | manual`

---

## Counting & Calibration

### CALIBRATION_DRIFT
**Source:** `fusion` · Emitted when APC count delta vs camera count exceeds threshold; does NOT modify occupancy state

```json
{
  "car_id": "car-3",
  "camera_count": 47,
  "apc_count": 58,
  "delta": 11,
  "threshold": 10,
  "journey_elapsed_s": 1840.0
}
```

---

## Inter-Wagon Movement (ADR-17)

### WAGON_EXIT
**Source:** `inference` · Emitted when a track ID crosses the exit tripwire at a gangway; must pair with WAGON_ENTRY on the adjacent coach

```json
{
  "track_id": "person-0312",
  "coach_from": "car-3",
  "coach_to": "car-4",
  "camera_id": "cam-3-gangway-fwd",
  "direction": "forward",
  "confidence": 0.88
}
```

`direction` values: `forward | backward` (relative to train direction of travel)

### WAGON_ENTRY
**Source:** `inference` · Emitted when a track ID crosses the entry tripwire; `track_id` must match a prior WAGON_EXIT

```json
{
  "track_id": "person-0312",
  "coach_from": "car-3",
  "coach_to": "car-4",
  "camera_id": "cam-4-gangway-aft",
  "direction": "forward",
  "confidence": 0.91
}
```

### LEDGER_DRIFT_ALERT
**Source:** `fusion` · Emitted when closed-ledger invariant is violated (net passenger sum changed between station stops)

```json
{
  "expected_total": 312,
  "actual_total": 307,
  "delta": -5,
  "coach_breakdown": {
    "car-1": 52,
    "car-2": 61,
    "car-3": 48,
    "car-4": 71,
    "car-5": 75
  },
  "reconciliation_applied": false
}
```

`reconciliation_applied`: `true` if fusion auto-corrected counts before station arrival; `false` if drift exceeded reconciliation threshold and human review is needed.

---

## Comfort

### COACH_COMFORT_INDEX
**Source:** `fusion` · Emitted on station approach and on significant occupancy change (>10% delta); primary consumer is Control Centre Dashboard analytics

```json
{
  "car_id": "car-2",
  "reserved_seats": 64,
  "occupied_seats": 58,
  "standing_count": 12,
  "comfort_score": 0.72,
  "service_tier": "business"
}
```

`comfort_score` = float 0.0–1.0. Computed as: `1.0 - (standing_count / car_capacity)`. Score degrades as standing count rises regardless of reservation fill. `1.0` = no standing passengers. `0.0` = all capacity standing.

---

## Alert Priority Field (ADR-18 Trigger 3)

All `ALERT_RAISED` payloads gain an optional `priority` field:

```json
{
  "alert_id": "a3f1c2d4-89ab-4ef0-b123-000000000001",
  "alert_code": "OVERCROWDING",
  "car_id": "car-2",
  "zone": "vestibule-b",
  "description": "Occupancy exceeded 90% for more than 60 seconds.",
  "auto_resolve_after_s": 300,
  "priority": "escalated | normal"
}
```

`priority` is omitted (not set to `"normal"`) when no escalation condition is active. Escalation is triggered when GPS/HAFAS reports train is within 2 minutes of a scheduled station stop (ADR-18 Trigger 3).

---

### SYNC_COMPLETED
**Source:** `vlan-pollers` · Emitted after successful clock/config sync cycle

```json
{
  "sync_type": "ntp",
  "nodes_synced": 12,
  "nodes_failed": 0,
  "max_skew_ms": 4.7,
  "skew_by_node": {
    "cam-1-01": 1.2,
    "cam-2-01": 4.7,
    "cam-3-02": -0.3
  },
  "sync_server": "192.168.10.1"
}
```

`sync_type` values: `ntp | config | firmware`
