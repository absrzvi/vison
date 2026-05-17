# OEBB Smart Rail — Agentic AI Use Cases
**Date:** 2026-05-16
**Status:** Draft
**Related specs:** `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md` · `_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md`

---

## Overview

These use cases describe closed-loop agentic AI workflows running on the onboard `local-diagnostic-agent` container. Each follows the ReAct (Reasoning + Action) pattern:

**Trigger → Agent reasons across live data sources → Executes actions autonomously → Delivers human-readable audit trail**

The agent does not just notify — it investigates, decides, and acts across train systems. Humans receive a pre-diagnosed briefing with the full decision chain, not a raw alert.

### Agent Tool Belt

The agent has access to the following executable tools:

| Tool | Description |
|---|---|
| `poll_im_oid(oid)` | Query live sub-trees from the Stadler IM SNMP MIB |
| `query_fusion_engine(coach_id, metric)` | Query live vision metrics from `local-fusion-engine` |
| `trigger_pis_display(coach_id, message)` | Write a message to the passenger information screens in a specific coach |
| `send_conductor_alert(priority, message)` | Push a priority alert to the conductor's handheld app via onboard Wi-Fi mesh |
| `send_control_centre_event(payload)` | Queue a structured event for landside control centre via `cloud-sync` |
| `send_platform_alert(station, payload)` | Push an alert to the station view for an upcoming stop |
| `query_reservation_data(coach_id, station)` | Query VLAN 6 reservation system for alighting/boarding volumes |
| `query_fleet_history(pattern)` | Query landside fleet history database for precedent matching |
| `query_route_data(trip_id)` | Query timetable and route metadata including platform side at each stop |

---

## UC-A01 — Autonomous Door Obstruction Resolution

**Trigger:** Vision pipeline detects a bag blocking door D2L for >8 seconds while the train is stationary at a station. Departure time is T−45 seconds.

**Agent reasoning:**
- Checks `im0vstDriving` — train is stationary, intervention is safe.
- Checks coach occupancy — Coach 2 has standing passengers near the door.
- Checks timetable — 38 seconds to scheduled departure.

**Agent actions (no human required):**
1. Fires `trigger_pis_display(2, "Please clear the doors. Train cannot depart until doors are clear.")` in the affected coach.
2. Sends conductor mesh alert: *"Agent action: Bag detected blocking Door 2L. PIS message triggered. 38 seconds to scheduled departure. Coach 2, Row 1."*
3. If obstruction persists after 20 seconds, escalates alert severity and logs a departure delay event tagged to the trip ID.

**Human role:** Conductor receives a pre-diagnosed, already-actioned briefing — not a raw alert.

---

## UC-A02 — Offline Overcrowding Redistribution

**Trigger:** Vision pipeline detects Coach 4 exceeding 95% capacity. Train is in a cellular dead zone — cloud sync offline.

**Agent reasoning:**
- Queries occupancy across all coaches from `local-fusion-engine` — Coaches 1 and 6 are under 40% occupied.
- Checks `im0triNextStationName` — next stop in 4 minutes.
- Determines redistribution is possible before arrival and no cloud authorisation is available.

**Agent actions:**
1. Fires `trigger_pis_display(4, "Coach 4 is full. Seats available in Coaches 1 and 6.")`.
2. Updates PIS in Coaches 1 and 6: *"Passengers welcome from Coach 4."*
3. Notifies conductor: *"Agent action: Coach 4 at 95% capacity. Coaches 1 and 6 at 38% and 41%. PIS guidance issued across 3 coaches. Cloud offline — action taken locally. Next stop: Linz Hbf in 4 min."*
4. Queues a redistribution event in the `cloud-sync` buffer for upload when cellular resumes.

**Human role:** Conductor receives a post-action summary. Control centre receives the event log once connectivity is restored.

---

## UC-A03 — Unattended Luggage Autonomous Protocol

**Trigger:** Vision pipeline detects a bag stationary in the Coach 3 vestibule for >5 minutes with no associated person tracking ID in the zone.

**Agent reasoning:**
- Cross-checks tracking history — the bag's last associated person ID exited via Door 3R 6 minutes ago (alighting event at Wien Hbf).
- Checks `im0triCurrentStationName` — train departed Wien Hbf 7 minutes ago.
- Bag was not present at boarding. Classifies as high-confidence unattended item, not a forgotten bag from a seated passenger.

**Agent actions:**
1. Locks Coach 3 vestibule camera to dedicated tracking mode — retains bounding box and tracking metadata only, no video written to disk (GDPR compliant).
2. Sends conductor priority alert: *"Agent action: Unattended bag — Coach 3 vestibule. Owner last seen exiting Door 3R at Wien Hbf 7 min ago. Bag present for 6 min. Confidence: high. Recommend visual inspection."*
3. Notifies control centre via `cloud-sync` with full evidence chain: bag duration, owner exit event, coach, trip ID.
4. If conductor does not acknowledge within 3 minutes, escalates to control centre as a priority-1 security event.

**Human role:** Conductor investigates. Control centre receives audit trail regardless of outcome.

---

## UC-A04 — Predictive Dwell Extension Request

**Trigger:** At T−90 seconds before Salzburg Hbf, vision pipeline detects 23 passengers standing in the aisle of Coach 5 — abnormally high for a non-terminus stop.

**Agent reasoning:**
- Queries `im0triNextStationName` = Salzburg Hbf.
- Checks reservation data (VLAN 6) — 31 passengers have Salzburg as destination in Coach 5.
- Queries boarding prediction — 18 passengers expected to board Coach 5 at Salzburg.
- Calculates that standard 45-second dwell is insufficient for 31 alighting + 18 boarding through 2 doors.

**Agent actions:**
1. Sends control centre recommendation: *"Agent prediction: Coach 5 — 31 alighting, 18 boarding at Salzburg Hbf. Standard 45s dwell insufficient. Recommend 75s dwell. Confidence: high. Basis: reservation data + live aisle occupancy."*
2. Notifies conductor: *"Agent advisory: High alighting volume in Coach 5 at Salzburg. Consider requesting extended dwell from control."*
3. Logs prediction with trip ID for dwell time model training.

**Human role:** Control centre operator approves or rejects the dwell extension. Agent does not act on train movement — humans retain authority over operational decisions.

---

## UC-A05 — Accessibility Arrival Coordination

**Trigger:** Vision pipeline detects a wheelchair user in Coach 4 (`yolov8m_pose.hef` keypoint pattern). `im0triNextStationName` = Innsbruck Hbf. ETA 8 minutes.

**Agent reasoning:**
- Queries `im0vstDoorReleasePRMLeft/Right` and route data to identify platform side at Innsbruck.
- Checks conductor notification history this journey — no prior acknowledgement found.

**Agent actions:**
1. Sends conductor alert: *"Agent action: Wheelchair user detected, Coach 4. Arriving Innsbruck Hbf in 8 min. PRM door is right-side. Ramp deployment recommended at Door 4R."*
2. Pushes platform staff notification to Innsbruck station view: *"Incoming: wheelchair user, Coach 4, Door 4R. Train arrives in 8 min."*
3. At T−2 minutes, fires a ramp reminder to conductor if `im0vstWheelchairRampRight` is still `no`.

**Human role:** Conductor deploys ramp. Platform staff position themselves. Agent coordinates the handoff — humans execute the physical action.

---

## UC-A06 — HVAC Fault Passenger Redistribution (Offline)

**Trigger:** `im0Error` fires an over-temperature flag on Coach 3's HVAC secondary compressor. Train is in a tunnel — cellular offline.

**Agent reasoning:**
- Queries live temperatures across all coaches via `poll_im_oid`.
- Coach 3: 26°C and rising. Adjacent Coaches 2 and 4: 21°C. Ambient outside: 14°C — fault is localised.
- Queries Coach 3 occupancy from `local-fusion-engine` — 74 seated, 12 standing (high density).
- Calculates time-to-unsafe-temperature at current rate of rise given passenger density: approximately 8 minutes.
- Train is offline — cannot await landside instruction. Determines local action is required to preserve passenger comfort and safety.

**Agent actions:**
1. Fires `trigger_pis_display(3, "System adjustment in progress. Seats available in Coaches 2 and 4.")`.
2. Updates PIS in Coaches 2 and 4: *"Passengers welcome from Coach 3."*
3. Sends conductor mesh alert: *"Agent action: Coach 3 HVAC compressor failed. Thermal climb detected — 26°C and rising. 86 passengers affected. PIS redistribution issued to Coaches 2, 3, and 4. Cloud offline — acting locally. Inspect circuit cabinet Coach 3, Row 4 on tunnel exit."*
4. Monitors Coach 3 occupancy — if passengers do not begin moving within 90 seconds, escalates PIS message urgency.
5. Queues full fault + action log for cloud sync on tunnel exit.

**Human role:** Conductor performs physical inspection. Control centre receives the full audit trail on reconnection.

---

## UC-A07 — Go/No-Go Advisory at Terminus

**Trigger:** Train approaching terminus. Technician queries agent: *"Is it safe to continue in service tomorrow morning?"*

**Agent reasoning (multi-step):**
1. Pulls full active alarm list from `im0Alarm` table — 2 active alarms found.
2. Identifies: (a) HVAC watch state on Coach 2, (b) door sensor intermittent fault on Coach 1.
3. Queries fleet history (landside): door sensor intermittent fault at this frequency precedes door failure within 24 hours in 34% of comparable fleet cases (847 precedents).
4. Queries odometer — train is 1,200 km from scheduled inspection threshold.
5. Checks Stadler safety rulebook (embedded document store): door sensor intermittent fault at this frequency is classified as "monitor — do not isolate" under degraded operation rules §4.2.1.

**Agent response to technician:**
*"Assessment: Conditional go. HVAC watch state — low risk, monitor only. Door sensor on Coach 1 has a 34% historical correlation with door failure within 24h across 847 fleet cases. Recommend depot inspection of Coach 1 door circuit before morning service. Train is 1,200 km from scheduled inspection — consider combining visits. Basis: 2 active alarms, fleet history, Stadler rulebook §4.2.1."*

**Human role:** Technician and maintenance manager make the final go/no-go call. Agent provides the evidenced recommendation — humans retain authority.

---

## Design Principles

- **Humans retain authority over safety-critical decisions.** The agent acts autonomously only on passenger guidance (PIS) and notifications. Movement, service, and maintenance decisions always require human approval.
- **Every autonomous action is logged.** The audit trail — what the agent observed, reasoned, and did — is always surfaced to the relevant human and queued for cloud sync.
- **Offline-first.** All agentic workflows are designed to execute without cloud connectivity. Cloud sync delivers the audit trail after the fact.
- **GDPR by design.** No raw video is written to disk or transmitted. Vision outputs are bounding boxes, tracking IDs, and keypoint metadata only.
- **Confidence is always stated.** Agent outputs include the data sources and reasoning used so humans can verify or override.
