# OEBB Hailo-8 AI Service Design
**Date:** 2026-05-13
**Status:** Draft for review — v3 updated with Stadler IM MIB detail (BU_2088941f): SNMP OIDs, vehicle state objects, alarm table structure, trip data, TRAP/INFORM integration pattern, multi-vehicle polling, new AI use cases
**Related specs:** `2026-05-13-oebb-ux-design.md`

---

## 1. Overview

OEBB have requested installation of a Hailo-8 M.2 AI accelerator on the Nomad Digital R5001C CCU deployed on their fleet. Rather than treating this as a one-time hardware install, this design defines a fully managed AI Insights-as-a-Service offering plus a passenger-facing Smart Travel product and a Diagnostics AI service — all delivered and operated by Nomad Digital.

The service runs on SYS2 (Debian 12 + Docker) of the R5001C, alongside the existing media server and portal infrastructure. SYS1 continues to provide connectivity for cloud sync. Raw video never leaves the train; only structured, anonymised inference results and telemetry events are transmitted off-vehicle.

Nomad Digital owns the routing for the majority of onboard VLANs, giving unique access to data from cameras, APC sensors, reservation system, PIS, bistro telemetry, energy metering, and Stadler diagnostics. This multi-source data fusion is the core competitive advantage — no other provider on this fleet has equivalent visibility.

---

## 2. Hardware

### Hailo-8 M.2 (single module)

| Component | Detail |
|---|---|
| Host platform | Nomad Digital R5001C CCU — ADLINK cPCI-A3H20 blade |
| M.2 slot | M-key, 2242/2280, PCIe Gen 3 x4 — confirmed free (SSD on U.2) |
| Hailo-8 module | M-key 2242 or 2280, PCIe Gen 3 — confirmed compatible |
| Operating temperature | Hailo-8 rated -40°C to 85°C — suitable for rail environment |
| OS | Debian 12 (Linux) — supported by HailoRT runtime |

### Decision: Single Hailo-8 only
A second Hailo-8 was evaluated for the Diagnostics AI service. It is not required because:
- Stadler alarm data (SNMP) is structured telemetry, not video — no on-train neural network inference needed
- Rule-based fault pattern detection runs on SYS2 CPU (negligible compute)
- ML predictive models and the LLM natural language agent run landside in the cloud
- The M.2 slot remains available if a future use case requiring on-train inference emerges (e.g. acoustic anomaly detection, thermal camera processing)

---

## 3. Stadler Information Middleware (IM) — SNMP Data Available

The Stadler IM (BU_2088941f) runs on the Stadler RCU and exposes a full SNMP MIB at root OID `1.3.6.1.4.1.42054`. It is reachable via VLAN 7 (FIS-OBS / Stadler Gateway). All data is SNMPv2c on UDP port 161.

### Integration pattern
The IM provides three consumption models, in order of preference for this service:
1. **TRAP/INFORM push (preferred)** — IM sends value changes to a configured target IP:port. Configure SYS2 IP in the IM's `NotificationTarget` column per signal row. No polling overhead. Ideal for alarms and vehicle state changes.
2. **Periodic INFORM** — IM pushes data at a fixed interval regardless of change. Configure SYS2 IP in `PeriodicNotification`. Good for GPS, speed, temperature.
3. **SNMP GET/GetBulk poll** — SYS2 polls on a schedule. Use counter variables to detect changes before fetching full blocks; avoids unnecessary reads.

**Efficient polling pattern (if polling used):**
First query: `im0active` + all `im0xxxCounters` + all `im0xxxValid` flags for blocks of interest.
If counter has changed and valid=true: second query fetches the full block.
Always check `im0xxxValid` before using data. If valid=false, data is stale (source device not writing or TCMS signal lost — see §5.3.6).

### Key MIB objects

**im0VstGeneral — Vehicle state (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.60.1)**

| Object | Type | Values | AI use |
|---|---|---|---|
| `im0vstAnyDoorOpen` | bool | no/yes | Door status baseline — any door open on this vehicle |
| `im0vstDoorReleaseLeft` | bool | no/yes | Left-side doors released (driving direction) |
| `im0vstDoorReleaseRight` | bool | no/yes | Right-side doors released (driving direction) |
| `im0vstDoorReleasePRMLeft` | bool | no/yes | Left PRM (accessibility) door release |
| `im0vstDoorReleasePRMRight` | bool | no/yes | Right PRM (accessibility) door release |
| `im0vstWheelchairRampLeft` | bool | no/yes | Left wheelchair ramp deployed |
| `im0vstWheelchairRampRight` | bool | no/yes | Right wheelchair ramp deployed |
| `im0vstDriving` | bool | no/yes | Vehicle is driving — gate camera alerts during stationary periods |
| `im0vstSlowDrive` | bool | no/yes | Speed < 40 km/h — useful for dwell detection |
| `im0vstDegradedOperation` | bool | no/yes | Running on redundant/fallback systems |
| `im0vstMaintenanceMode` | bool | disabled/enabled | Suppress false positives during depot maintenance |
| `im0vstParkingPositionActive` | bool | no/yes | Train parked — trigger maintenance-mode logic |
| `im0vstEnergyMode` | enum | none/energySaving/batteryMode | Energy context for anomaly detection |
| `im0vstShutdownAll` | bool | no/yes | Imminent full shutdown — flush event buffer |
| `im0vstShutdownPartly` | bool | no/yes | Non-essential devices shutting down |
| `im0vstCouplingInProgress` | bool | no/yes | Coupling underway — vehicle index unstable, suppress topology alerts |
| `im0vstVehicleOccupied` | bool | no/yes | Cockpit occupied (driver present) |
| `im0vstSpeed` | string | km/h | Speed from vehicle odometer — correlate with door events and fault patterns |
| `im0vstOdometer` | string | km | Fleet mileage-based maintenance scheduling |
| `im0vstDistance` | int | m (since power-up) | Journey distance since power-on |

**im0Alarm — Named alarm table (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.70)**
Read table: `im0alaReadTable` — rows with `im0alaReadName` (string) and `im0alaReadValue` (no=0 / active=1).
Counter `im0alaReadCounters` changes when any alarm state changes — use as change-detection gate.
Alarm names are project-specific and defined in the STADLER-IM-MIB_Configuration Excel for the OEBB fleet. Full alarm name list to be obtained from Stadler during PoC.

**im0Error — Per-device error table (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.80)**
Rows with `im0errWriteName` and `im0errWriteValue` (no=0 / yes=1). Group rows (e.g. `errCctvCamGroup`) act as validity gates: group=yes(1) means the observer is not running and error values should not be trusted. Only consume device error rows when group=no(0).

**im0Trip — Live trip information (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.90)**

| Object | Type | Values | AI use |
|---|---|---|---|
| `im0triCurrentStationName` | string (UTF-8) | Station name | Current stop — sync with APC boarding events |
| `im0triNextStationName` | string (UTF-8) | Station name | Next stop — trigger boarding prediction |
| `im0triDestinationStationName` | string (UTF-8) | Station name | Journey destination — context for occupancy forecasting |
| `im0triStartStationName` | string (UTF-8) | Station name | Journey origin |
| `im0triRouteName` | string (UTF-8) | Route name | Route identification for analytics |
| `im0triTripNumber` | int | Timetable trip ID | Unique trip identifier for data labelling |
| `im0triDriverId` | int | Driver ID | Audit trail for events |

Note: Trip info is written by the timetable application. `im0triValid` = false if timetable app is not connected. In this case fall back to PIS VLAN 3 for station data.

**im0Gps — GPS position (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.40)**

| Object | Type | Values |
|---|---|---|
| `im0gpsLatitude` | string | Degrees, N>=0 |
| `im0gpsLongitude` | string | Degrees, E>=0 |
| `im0gpsSpeed` | string | km/h |
| `im0gpsHeading` | string | 0–360° |
| `im0gpsAltitude` | string | m |
| `im0gpsNumberOfSatellites` | int | 0–20 |

`im0gpsValid` controlled by GPS source device — false in tunnels. Use `im0vstSpeed` (odometer) as fallback for motion detection when GPS is invalid.

**im0Temperature (OID: 1.3.6.1.4.1.42054.10.1.1.10.1.50)**
`im0temOutside` — outside temperature. Correlate with HVAC alarm patterns and energy consumption anomalies.

### Multi-vehicle trains
OEBB trains may couple up to 4 vehicles. Each vehicle runs its own IM instance. `im0genNumberOfVehicles` > 1 indicates multi-traction. Each vehicle's IM is reachable at its own IP (`im0genIpv4AddressIm1–4`). The SNMP poller on SYS2 must query each vehicle's IM independently and merge results by vehicle index. During coupling (`im0vstCouplingInProgress`=yes), vehicle indexes are unstable — suppress topology-dependent alerts.

### New AI use cases unlocked by IM data

| Use case | IM signals used | Value |
|---|---|---|
| Speed-correlated door fault | `im0vstSpeed` + door alarm from `im0alaReadTable` | Door fault at speed > 0 is higher severity than at platform |
| Maintenance mode suppression | `im0vstMaintenanceMode` | Suppress false positive passenger AI alerts during depot work |
| Degraded operation alert | `im0vstDegradedOperation` | Immediate flag to control centre + maintenance dashboard |
| Parking trigger | `im0vstParkingPositionActive` | Trigger depot-mode logic: cleaning schedule review, overnight maintenance window |
| Energy mode awareness | `im0vstEnergyMode` | In battery mode, deprioritise non-safety AI alerts; note in energy KPI reports |
| PRM door tracking | `im0vstDoorReleasePRMLeft/Right` | Correlate accessibility door events with wheelchair detection from camera |
| Wheelchair ramp deployed | `im0vstWheelchairRampLeft/Right` | Real-time accessibility event — alert platform staff at next stop |
| Odometer-based maintenance | `im0vstOdometer` | Schedule inspection at mileage thresholds; ML model feature |
| Trip-labelled data | `im0triTripNumber` + `im0triRouteName` | All AI events automatically labelled with trip ID for analytics and ML training |

---

## 4. Data Sources & VLAN Access

Nomad Digital routes the following VLANs on the R5001C, each representing a data source available for AI fusion:

| VLAN | System | Data available | AI use |
|---|---|---|---|
| 5 | CCTV Internal (Stadler) | RTSP camera streams — all coaches interior + exterior | Hailo-8 #1 primary input |
| 8 | AFZ / APC | Door-mounted passenger counts per boarding/alighting event | Ground truth calibration for camera counting |
| 6 | Reservation System | Seat reservations by coach and journey | No-show detection, boarding volume prediction |
| 3 | FIS / PIS | Passenger information system state — announcements, displays | Sync portal with PIS, trigger guidance at right moment |
| 46 | Bistro Telemetry | Vending/catering stock levels, sales transactions | Demand prediction, restocking alerts |
| 47 | Bistro Display | Display state of bistro screens | Cross-reference with footfall |
| 48 | Bistro Payment | Payment transactions at bistro | Revenue per journey vs occupancy correlation |
| 12 | Energy Measurement | Power consumption per journey | Energy anomaly detection, sustainability KPIs |
| 7 | FIS-OBS / Stadler Gateway | Stadler Security Gateway — transit VLAN to Stadler systems | SNMP polling for Stadler diagnostic alarms **and TCMS alarms** (doors, HVAC, brakes, traction, pantograph, lighting) — diagnostic system aggregates both |
| 2 | ZFR | ZFR↔RCU communication — train control state, speed, braking, door commands | Correlate braking events with fault signatures |
| 30 | Onboard Staff Network | Staff device connectivity | Delivery network for all onboard staff apps |
| 10 | 1st Class WiFi | Passenger captive portal | Passenger-facing guidance display |

---

## 5. Architecture

```
╔══════════════════════════════════════════════════════════════════╗
║                        R5001C — SYS2                            ║
║                                                                  ║
║  DATA INGESTION LAYER (Docker containers)                        ║
║  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  ║
║  │ RTSP ingest  │ │APC poller│ │SNMP poller│ │ Other VLANs  │  ║
║  │ (CCTV VLAN5) │ │(VLAN 8)  │ │(VLAN 7)  │ │ 6,3,46,12,2  │  ║
║  └──────┬───────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  ║
║         │              │            │               │            ║
║  ┌──────▼──────────────▼────────────▼───────────────▼────────┐  ║
║  │                  Event Bus (internal)                      │  ║
║  └──────┬─────────────────────────────────┬──────────────────┘  ║
║         │                                 │                      ║
║  ┌──────▼──────────────────┐   ┌──────────▼──────────────────┐  ║
║  │  Hailo-8 Inference      │   │  CPU: Rule-based processing  │  ║
║  │  HailoRT + TAPPAS       │   │  Stadler alarm correlation   │  ║
║  │  - Object detection     │   │  APC↔camera fusion          │  ║
║  │  - Tracking             │   │  Energy anomaly detection    │  ║
║  │  - Pose estimation      │   │  Reservation fusion          │  ║
║  │  - Counting             │   │  PIS sync                    │  ║
║  └──────┬──────────────────┘   └──────────┬──────────────────┘  ║
║         │                                 │                      ║
║  ┌──────▼─────────────────────────────────▼──────────────────┐  ║
║  │              Structured Event Store (local)                │  ║
║  └──────┬─────────────────────────────────┬──────────────────┘  ║
║         │                                 │                      ║
║  ┌──────▼──────────────┐      ┌───────────▼────────────────────┐║
║  │  Portal Pages       │      │  Cloud Sync Agent (via SYS1)   │║
║  │  (SYS2 media server)│      │  Structured events only        │║
║  │  - Passenger display│      │  No raw video, no PII          │║
║  │  - Staff apps       │      └───────────┬────────────────────┘║
║  └─────────────────────┘                  │                      ║
╚══════════════════════════════════════════════════════════════════╝
                                            │
                              ┌─────────────▼──────────────────────┐
                              │         Cloud Backend               │
                              │  - Operations dashboard             │
                              │  - Maintenance dashboard            │
                              │  - Analytics & station view         │
                              │  - LLM agent (Claude API)           │
                              │  - ML predictive models             │
                              │  - Fleet-wide pattern matching      │
                              │  - Historical data store            │
                              └────────────────────────────────────┘
```

---

## 6. Service Modules & Tier Structure

### Tier 1 — Core Intelligence (Base Subscription)
Required foundation. All trains must be on Tier 1 to access higher tiers.

| Module | Data sources | Description |
|---|---|---|
| Passenger counting | CCTV (VLAN 5) + APC (VLAN 8) | Per-coach real-time headcount. Camera-based (Hailo-8) fused with APC door counts for self-calibrating accuracy. |
| Luggage counting | CCTV (VLAN 5) | Luggage item detection per coach via YOLO object detection |
| Congestion mapping | CCTV + APC fusion | Train-wide occupancy heatmap, zone scoring updated every few seconds |
| Unattended luggage detection | CCTV (VLAN 5) | Alert if bag stationary >X min without owner detected nearby |
| Door obstruction detection | CCTV (VLAN 5) + ZFR (VLAN 2) | Flag passengers/luggage blocking doors; correlate with door command state |
| Stadler + TCMS alarm ingestion | SNMP (VLAN 7) | Poll all Stadler diagnostic system alarms via SNMP. Covers both Stadler subsystem alarms and TCMS alarms (doors, HVAC, brakes, traction, pantograph, lighting) — the diagnostic system aggregates both. Store as structured event log, surface to staff apps. During PoC: map Stadler OIDs to TCMS subsystem taxonomy using Stadler documentation. |
| Door alarm cross-correlation | CCTV (VLAN 5) + TCMS door alarms (VLAN 7) | Cross-reference Hailo-8 camera-detected door obstructions with TCMS door fault codes. Camera alone = possible obstruction. TCMS door alarm alone = possible sensor fault. Both together = high-confidence safety event. Highest priority alert class. |

### Tier 2 — Operational Excellence (Add-on Subscription)
OEBB operations centre and fleet management value layer.

| Module | Data sources | Description |
|---|---|---|
| Operations dashboard & alerting | All Tier 1 outputs | Cloud dashboard: real-time occupancy, safety incidents, configurable threshold alerts across fleet |
| Diagnostics AI — fault pattern detection | Stadler + TCMS SNMP (VLAN 7) + Energy (VLAN 12) | Rule-based fault pattern detection across all Stadler and TCMS alarm types (doors, HVAC, brakes, traction, pantograph, lighting). Cross-reference energy consumption anomalies with alarm patterns as early warning signals. TCMS alarm taxonomy mapped during PoC. |
| Predictive fault alerting | Stadler + TCMS SNMP + fleet history | From month 4–6 post-launch: ML time-series models trained on own fleet data, covering both Stadler subsystem and TCMS alarm streams. Rules retained as fallback and explainability layer. Cites precedent from fleet history. |
| Dwell time analysis | APC (VLAN 8) + PIS (VLAN 3) | Measure boarding/alighting duration per stop using APC door events. Cross-reference with PIS stop announcements. |
| Predictive overcrowding | CCTV + APC + Reservation (VLAN 6) | Forecast coach loads N stops ahead using current occupancy + reservation data + historical boarding patterns |
| Cleaning & maintenance triggers | CCTV + APC occupancy history | Auto-generate cleaning work orders when coach usage intensity exceeds thresholds |
| Slip/fall detection | CCTV (VLAN 5) | Person-down event alert to staff/control centre via pose estimation |
| Prohibited zone detection | CCTV (VLAN 5) | Alert if someone enters restricted areas (cab door, equipment bays) |
| Natural language diagnostics agent | Cloud LLM (Claude API) + Stadler alarm log | Landside cloud agent. Staff ask questions in plain language; agent answers using alarm log, fleet history, maintenance docs. Requires SYS1 connectivity. |

### Tier 3 — Experience & Insights (Premium Add-on)
Passenger-facing product and data monetisation layer.

| Module | Data sources | Description |
|---|---|---|
| Passenger guidance display | CCTV + APC congestion output | Portal page on SYS2 showing train diagram with green/amber/red coaches. Auto-syncs with PIS announcements via VLAN 3. |
| Smart Travel API | Cloud backend | API for OEBB to push occupancy data to platform displays or their own app |
| Accessibility assistance detection | CCTV (VLAN 5) | Detect wheelchairs, pushchairs, mobility aids; alert staff and notify destination station |
| Bistro demand intelligence | CCTV + APC + Bistro Telemetry (VLAN 46/47/48) | Cross-reference passenger footfall with bistro stock and sales. Predict demand, trigger restocking alerts at next stop. |
| No-show seat detection | CCTV + Reservation (VLAN 6) | Detect reserved-but-empty seats after threshold time post-departure. Flag as available to passengers via portal. |
| Boarding volume prediction | APC + Reservation + historical | Predict how many passengers will board at each upcoming stop. Feeds platform staff display and driver. |
| PIS-synced guidance | PIS (VLAN 3) | Automatically update portal guidance when PIS announces delays, platform changes, or service disruptions |
| Anonymised ridership analytics | All occupancy + APC data | Monthly reports: travel patterns, peak loads by route/time/coach class, dwell time by stop |
| Energy efficiency reporting | Energy (VLAN 12) + APC occupancy | Occupancy-normalised energy KPIs per journey. Supports OEBB sustainability reporting. Anomalies flagged as early fault indicators. |
| Advertising audience metadata | Occupancy demographics (anonymised) | Aggregate audience profiles per route for portal content targeting |

---

## 7. Diagnostics AI — Cold Start Strategy

Trains enter service in ~3 months. No historical alarm data exists yet.

**Phase A — Rules at launch (months 1–3 of service)**
Deterministic rules derived from Stadler maintenance documentation. Example: "if alarm 0x3A12 fires 3× in 14 days on the same subsystem, flag for bearing inspection." Immediately useful, fully explainable to OEBB maintenance staff, no training data required.

**Phase B — Fleet pattern matching (months 1+ of service)**
With 14+ trains operating simultaneously, cross-train alarm patterns are statistically meaningful from day one. A cluster of the same alarm appearing across multiple trains on the same route flags a systemic issue vs. a single-train fault.

**Phase C — ML model upgrade (months 4–6 of service)**
Once sufficient fleet history is accumulated, ML time-series models (trained landside) replace and augment the rule layer. Rules remain as fallback and explainability layer. Model retraining is a managed service upsell.

**Stretch goal:** Approach Stadler for historical alarm data from the same train type on other operators. Would allow ML models from day one of service.

---

## 8. Commercial Model

### Hardware (Capex — per train)
- Hailo-8 M.2 module supply and installation
- Integration and commissioning fee per train

### Software & Managed Service (Recurring — per train per month)
- **Tier 1:** Base rate — all trains, non-optional once hardware installed
- **Tier 2:** Add-on per train per month
- **Tier 3:** Add-on per train per month; analytics/energy reporting optionally priced as annual data subscription

### Managed Service Obligations (Nomad Digital owns and operates)
- HailoRT runtime and firmware updates via existing SYS1 remote management
- Docker container updates for all inference and ingestion pipeline modules
- Cloud backend hosting, uptime, and SLA
- LLM agent (Claude API) costs absorbed into service fee
- Model retraining and accuracy improvement over time
- Dashboard and app maintenance and feature updates

### Upsell Levers
- Fleet-specific model fine-tuning — professional services fee per retraining cycle
- Stadler data partnership — if historical data obtained, accelerated ML model quality
- Energy efficiency report as standalone data product for OEBB sustainability team
- New VLAN data source integrations as additional modules (e.g. acoustic anomaly detection if microphones added)

---

## 9. Delivery Phases

### Phase 1 — Proof of Concept (Weeks 1–8, single train)
- Install Hailo-8 M.2 on one R5001C SYS2
- Deploy Tier 1 inference pipeline (HailoRT + TAPPAS) as Docker containers
- Connect to CCTV RTSP feeds (VLAN 5) and APC poller (VLAN 8)
- Activate Stadler SNMP poller (VLAN 7)
- Validate counting accuracy — camera vs. APC ground truth
- Stand up passenger guidance portal page on SYS2 media server
- Stand up Conductor App and Technician App (rule-based diagnostics)
- Deliverable: PoC demo for OEBB stakeholders

### Phase 2 — Operations & Diagnostics Layer (Weeks 6–16)
- Build cloud sync pipeline over SYS1
- Deploy Control Centre Dashboard and Maintenance Dashboard (Tier 2)
- Activate safety modules: slip/fall, prohibited zone, predictive overcrowding
- Integrate Reservation data (VLAN 6) and PIS sync (VLAN 3)
- Deploy LLM diagnostics agent (cloud, Claude API)
- Activate energy fusion (VLAN 12)
- Deliverable: Tier 1 + Tier 2 on pilot train, signed off for fleet rollout

### Phase 3 — Fleet Rollout & Tier 3 (Week 16+)
- Roll out to full OEBB fleet
- Activate Tier 3 modules: bistro intelligence, no-show detection, boarding prediction, PIS-synced guidance
- Begin accumulating fleet-wide data for ML model training
- Deliverable: Full managed service live across fleet

### Phase 4 — ML Upgrade (Month 4–6 of service)
- Train first ML predictive fault models on own fleet data
- Replace rule-based predictions with ML models (rules retained as fallback)
- First energy efficiency sustainability report delivered to OEBB
- Deliverable: ML-powered Diagnostics AI, first analytics data products

---

## 10. Technical Dependencies to Confirm

- [ ] CCTV RTSP stream access — VLAN 5 tap confirmed, credentials from Stadler
- [ ] APC data format — confirm SNMP OIDs or API from AFZ central unit (VLAN 8)
- [ ] Reservation data feed — confirm access protocol from Stadler reservation system (VLAN 6)
- [ ] PIS data feed — confirm read access to FIS/PIS state (VLAN 3)
- [ ] Bistro telemetry format — confirm data schema from vending system (VLAN 46)
- [ ] Energy metering data format — confirm OIDs/protocol (VLAN 12)
- [ ] Stadler Security Gateway access — confirm SNMP polling (or TRAP receive) permitted via FIS-OBS VLAN 7; confirm SYS2 IP can be registered as NotificationTarget in Stadler IM configuration
- [x] Stadler IM MIB structure confirmed — BU_2088941f reviewed. SNMP v2c on UDP 161. MIB root 1.3.6.1.4.1.42054. Vehicle state, alarm table, GPS, trip info, temperature all available. TRAP/INFORM push supported.
- [ ] TCMS alarm name list — obtain the project-specific STADLER-IM-MIB_Configuration.xlsm for the OEBB fleet to get full `im0alaReadTable` alarm names and indexes (doors, HVAC, brakes, traction, pantograph, lighting). Required for rule mapping at PoC launch.
- [ ] Multi-vehicle IP addresses — confirm IM IP addresses for all vehicle units in each train formation (accessible via `im0genIpv4AddressIm1–4`; SYS2 poller must query each vehicle IM separately)
- [ ] Trip information source — confirm whether timetable application writes `im0triCurrentStationName`/`im0triNextStationName` on OEBB fleet; if not, fall back to PIS VLAN 3
- [ ] Cloud backend hosting decision: Nomad-owned infra vs. Azure/AWS
- [ ] Hailo-8 M.2 form factor: 2242 or 2280 (confirm physical clearance)
- [ ] Privacy/GDPR sign-off from OEBB legal on anonymised data sync to cloud
- [ ] SLA requirements from OEBB for dashboard and app uptime
- [ ] Approach Stadler re: historical alarm data from same train type (stretch goal)

---

## 11. Key Risks

| Risk | Mitigation |
|---|---|
| CCTV RTSP stream quality/angle poor for AI accuracy | Validate in PoC; APC fusion provides independent ground truth |
| Stadler restricts SNMP access via VLAN 7 gateway | Negotiate access as part of OEBB contract; Nomad already routes this VLAN |
| APC data format incompatible or inaccessible | Confirm protocol in PoC phase; camera-only counting is fallback |
| Cold start period — no historical data for ML predictions | Rule-based system operational from day one; ML layer added at month 4–6 |
| SYS1 connectivity gaps (tunnels) affecting cloud agent | Diagnostics agent gracefully degrades — last known fault summary cached locally |
| SYS2 resource contention between media server and inference | Profile Docker allocation in PoC; Hailo-8 offloads inference from CPU |
| OEBB procurement prefers capex-only | Capex hardware install is the entry point; managed service is optional but creates lock-in |
| GDPR concerns on passenger data | Only anonymised aggregate counts leave the train; no video, no PII transmitted |
