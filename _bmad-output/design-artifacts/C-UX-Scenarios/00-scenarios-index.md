# UX Scenarios Index — OEBB Smart Rail Passenger Intelligence

**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14
**Status:** Updated 2026-05-16 — 15 scenarios (Scenario 09 redefined; Scenarios 11 + 12 added)

---

## Scenario Set

| # | Scenario | Persona | Interface | High-Priority Forces Addressed |
|---|---|---|---|---|
| 01 | Conrad watches the train fill on the platform | Conductor Conrad | Conductor App + PIS Exterior | Know whole train at a glance (15) · Feel in control at departure (15) |
| 02 | Conrad clears a vestibule bottleneck mid-journey | Conductor Conrad | Conductor App + PA | Act before problems escalate (15) · Fear missed incident causing delay (15) |
| 02b | Conrad rebalances a lopsided train | Conductor Conrad | Conductor App + PA + PIS Interior | Know whole train at a glance (15) · Feel authoritative mid-journey |
| 02c | Conrad heads off a luggage rack bottleneck | Conductor Conrad | Conductor App + PA + PIS Exterior | Act before problems escalate (15) · Fear missed incident causing delay (15) |
| 02d | Conrad investigates an unattended bag | Conductor Conrad | Conductor App → Control Centre | Fear missing safety-critical incident (15) · Claudia escalation path |
| 03 | Conrad escalates chronic overcrowding to Claudia | Conrad → Claudia | Conductor App → Control Centre | Conrad: look authoritative · Claudia: defensible decisions (13) |
| 04 | Claudia runs her morning fleet occupancy review | Control Centre Claudia | Control Centre Dashboard | Real occupancy across fleet (14) · Make defensible decisions (13) |
| 05 | Passenger guided to free coach via platform screen | Passenger (general) | PIS Exterior + Passenger Portal | Passenger boarding anxiety · Conrad: fewer redirections |
| 06 | Passenger with pushchair finds accessible space | Passenger (accessibility) | Passenger Portal + Conductor App | Fear missing accessibility need · Accessible boarding |
| 07 | Brigitte preps stock before departure | Bistro Brigitte | Bistro App | Calibrate stock to load (12) · Fear running out |
| 08 | Brigitte routes her trolley mid-journey | Bistro Brigitte | Bistro App | Know which coaches to prioritise (12) · Maximise revenue per run |
| 09 | Roland diagnoses a degrading L1 cable — entry via Control Centre System Health tab, full workflow in Maintenance App | Roland (Fleet Manager) | Control Centre Dashboard (entry) → Maintenance App (diagnosis + action) | Act before problems escalate · Replace SSH + manual email |
| 11 | Claudia (and Roland) check system health fleet-wide — VLAN 5 + container health per train | Claudia (primary) · Roland (secondary) | Control Centre Dashboard — System Health tab | Fear acting on stale data · Platform self-reporting health |
| 12 | Claudia monitors the live fleet and resolves an escalation | Control Centre Claudia | Control Centre Dashboard — Live monitoring view | Fear missing safety-critical incident · Make defensible decisions · Reduce radio dependency |
| 10 | Station dwell — full embarkation & disembarkation | Conrad + Passenger (general) + Passenger (accessibility) | Conductor App + PIS Exterior + Passenger Portal | Feel in control at departure (15) · Act before problems escalate (15) · Fear missing accessibility need (15) |

---

## Driving Forces Coverage

| Force | Score | Scenarios |
|---|---|---|
| Know the whole train at a glance | 15 | 01, 02b, 02c, 10 |
| Fear missing safety-critical incident | 15 | 02d, 06 |
| Fear alert overload / false positives | 15 | 02 (auto-resolve), 02c (threshold tuning), 02d (configurable timer), 10 (forecast vs incident alert distinction) |
| Feel in control at departure / mid-journey | 15 | 01, 02, 02b, 02c, 02d, 10 |
| Act before problems escalate | 15 | 01, 02, 02c, 02d, 06, 10 |
| Real occupancy across fleet | 14 | 03, 04 |
| Receive alerts passively (Diego) | 14 | — (driver display descoped) |
| Fear distraction from noisy alerts (Diego) | 14 | — (driver display descoped) |
| Make defensible decisions (Claudia) | 13 | 03, 04 |
| Know which coaches to prioritise (Brigitte) | 12 | 08 |
| Calibrate stock to load (Brigitte) | 12 | 07 |

---

## Interface Coverage

| Interface | Scenarios |
|---|---|
| Conductor App | 01, 02, 02b, 02c, 02d, 03, 06, 10 |
| PIS Exterior Screens | 01, 02c, 05, 10 |
| PIS Interior Screens | 02b |
| PA System (app-triggered) | 02, 02b, 02c, 02d |
| Passenger Portal | 05, 06, 10 |
| Control Centre Dashboard | 02d (escalation), 03, 04, 09 (entry point only), 11, 12 |
| Maintenance App | 09 (full diagnostic + Stadler notification workflow) |
| Bistro App | 07, 08 |

**Note:** Driver Display descoped — Stadler provides all alerts the driver requires. Nomad Digital does not write to driver cab screens.

**Note:** Technician App and Diagnostics AI chat are descoped from this spec set — they form a separate application with its own design phase. The Diagnostics chat entry point (`ca-diagnostics-chat`) has been removed from the Conductor App. The Conductor App covers Passenger AI alerts only; Diagnostics AI faults are surfaced to the Technician App and (for network health) to the Maintenance Dashboard (Scenario 09).

---

## Technical Dependencies

| Dependency | Scenarios Affected | Status |
|---|---|---|
| PIS exterior screen L2 network write access | 01, 02c, 05 | ⚠️ Needs spec validation |
| PIS interior screen L2 network write access | 02b | ⚠️ Needs spec validation |
| Hailo-8 vestibule / zone-level crowding inference | 02 | Confirm zone segmentation accuracy |
| Hailo-8 luggage rack occupancy inference | 02c | Confirm rack-level detection accuracy |
| Hailo-8 unattended item detection + timer logic | 02d | Confirm false-positive rate; configurable timer required |
| Hailo-8 wheelchair/pushchair inference accuracy | 06 | Confirm inference accuracy |
| Historical occupancy data store (7-day trend) | 03, 04 | Required for escalation and analytics |
| Camera still-frame access scoping (privacy) | 02d | ÖBB + Nomad Digital access control decision required |
| Passenger portal live train diagram | 05, 06 | Nomad Digital provides portal — confirmed |
| SNMP data feed from Stadler diagnostic system (link up/down, all onboard switches) | 09 | Nomad feature confirmed |
| L2 network topology map per train (switch-to-coach segment mapping) | 09 | OID list to confirm with Stadler |
| Stadler notification API / structured report endpoint | 09 | Integration format to confirm with Stadler |
| Historical SNMP link quality data store | 09 | Retention period to confirm |
| ÖBB reservation data feed (per stop, per coach) — for expected-alighting estimate | 10 | ⚠️ New dependency — confirm availability and latency with ÖBB integration team |
| Hailo-8 directional entry/exit differentiation (boarding rate inference) | 10 | ⚠️ New dependency — confirm directional count accuracy per coach |
