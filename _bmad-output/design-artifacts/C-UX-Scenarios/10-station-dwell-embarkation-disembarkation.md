# Scenario 10 — Station Dwell: Full Embarkation & Disembarkation

**Personas:** Conductor Conrad (primary) · Passenger (general) · Passenger (accessibility)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14
**Status:** Draft — storyboard

---

## Core Feature

Full station stop intelligence — the system monitors the entire dwell window from train arrival through to door close, surfacing real-time occupancy shifts to Conrad and guiding passengers on the platform. Covers three sequential phases: **Arrival & Alighting**, **Active Dwell**, and **Pre-Departure**.

## Why a Separate Scenario from Scenario 01

Scenario 01 covers Conrad watching the train *fill* from the platform at a busy departure. This scenario starts earlier — at train arrival — and includes the alighting side of the stop: passengers leaving the train change the occupancy picture before new passengers board. The system must track both flows simultaneously, and Conrad's mental model must account for occupancy *dropping then rising* rather than only rising. The dual-protagonist framing also makes the passenger-facing guidance system (PIS + portal) a first-class part of the narrative, not a footnote.

---

## Entry Point

**Conrad:** Is on the platform or inside the train as it pulls into the station. His handheld is in his pocket or in hand. He knows this stop has a 4-minute dwell window. It is a busy intercity stop — a known high-load station.

**Passenger (general):** Is on the platform, arriving 90 seconds before the train pulls in, standard ticket, no seat reservation. Has one rolling suitcase.

**Passenger (accessibility):** Is on the platform with a pushchair and a toddler. Has pre-selected the accessible coach via the portal. Is anxious about ramp deployment timing.

---

## Mental States

### Conrad
**Trigger:** Train is slowing into platform. He cannot yet see whether the coaches that are boarding here will become overloaded — it depends on how many alight, how many are waiting, and where the crowd concentrates.
**Hope:** That the system gives him a clear picture of net occupancy change as it happens so he knows which coach door to stand at, and can redirect before the crowd commits.
**Worry:** That he will be standing at coach 3 managing a crowd while coach 8 quietly tips to overloaded, and he only finds out when the door-close alarm sounds.

### Passenger (general)
**Trigger:** Train arrives. Platform crowd surges toward the nearest doors. They can see door 4 is already backed up.
**Hope:** To board quickly, find a seat, and stow their suitcase without blocking the aisle.
**Worry:** That every coach is equally packed and they will spend the journey standing.

### Passenger (accessibility)
**Trigger:** Train arrives. They need coach 2, door 1, with the ramp. They have had bad experiences where the ramp was not ready and they had to shout across the platform.
**Hope:** Conrad is already at the door with the ramp deployed before they reach it.
**Worry:** Ramp not deployed. Accessible space already taken. Wrong door.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  PHASE 1             │────▶│  PHASE 2             │────▶│  PHASE 3             │
│  Arrival & Alighting │     │  Active Dwell        │     │  Pre-Departure       │
│  T-0 → T+90s        │     │  T+90s → T+3min      │     │  T+3min → T+4min     │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

| Phase | Name | Entry | Conrad focus | Passenger focus |
|-------|------|-------|-------------|-----------------|
| **1** | Arrival & Alighting | Train doors open | Occupancy dropping — which coaches clearing? | Board or wait for alight rush to clear? |
| **2** | Active Dwell | Alighting flow eases | Boarding surge — which coaches loading fast? | Find the right door, board efficiently |
| **3** | Pre-Departure | T-2 min warning | Final check — any coach still red? Any door blocked? | Seated, luggage stowed, settled |

---

## Phase 1 — Arrival & Alighting (T-0 to T+90s)

### What happens

The train pulls in. Doors open. Passengers alighting exit. Occupancy per coach falls, at different rates depending on how many had reserved seats in each coach.

### Conrad's experience — Phase 1

**State 1a: Train approaching (pre-door-open)**

Conrad's handheld shows the **pre-arrival dashboard** — a new state the app enters automatically when the train is within 60 seconds of a scheduled stop:

- Train diagram locks to show **current occupancy** (snapshot before doors open)
- A **dwell timer** appears top-right: "Dwell: 4:00" — counting down from scheduled stop time
- An **expected alighting estimate** appears per coach as a lighter band beneath the current occupancy bar — derived from reservation data and historical patterns for this stop
- Coaches with no reservations to alight show "Unknown" in grey

**Conrad's decision at this point:** He can already see which coaches are likely to empty significantly (coach 4 has 34 reservations ending here) versus which will stay loaded (coach 9 has 2 departures).

**State 1b: Doors open — alighting in progress**

Occupancy numbers begin falling in real time. The train diagram updates every 15 seconds (Hailo-8 inference cycle).

- Each coach bar animates downward as passengers leave
- Coaches that clear below 50% threshold flip from amber to green
- Conrad sees the **net headcount** updating: actual current count, not predicted

**Accessibility alert fires here if applicable:**

If Hailo-8 detects a wheelchair or pushchair in the alighting flow at a PRM door, Conrad receives an alert:
> "Accessibility — alighting — Coach 2 Door 1 — ramp needed"

Conrad confirms ramp deployment. The accessibility passenger watching from the platform sees the portal update: "Ramp deployed at Coach 2 Door 1."

**Conrad's movement decision:** By T+60s he can see which coaches have cleared and which remain packed. He positions himself at the coach where the boarding surge is predicted to hit hardest — not at the coach that was busiest before the stop.

---

### Passenger (general) experience — Phase 1

The passenger is on the platform. The train pulls in.

**PIS exterior screens (per coach):**

Before doors open: screens show the **pre-board state** — occupancy snapshot with a hold indicator:
> "Doors opening — please allow passengers to alight"

This is a new screen state not present in Scenario 01 or 05. It explicitly tells waiting passengers not to rush the door before alighting is complete.

Once alighting flow eases (T+60s), the screen switches to the **boarding guidance state**:
> "Coach 4 — Available · Coach 7 — Plenty of space →"

**Passenger decision:** They see coach 7 has space, walk 20 metres down the platform.

---

### Passenger (accessibility) experience — Phase 1

The accessibility passenger has the portal open. They watched the train pull in.

Portal shows:
- Live train diagram with coach 2 highlighted with a wheelchair icon
- Status: "Accessible space — 1 of 1 available"
- "Ramp deployment: waiting for conductor confirmation"

When Conrad confirms ramp deployment on his handheld, the portal updates immediately:
> "Ramp deployed at Coach 2 Door 1 — proceed to board"

The accessibility passenger moves to coach 2, door 1 with confidence.

---

## Phase 2 — Active Dwell (T+90s to T+3min)

### What happens

Alighting rush subsides. Boarding begins in earnest. Occupancy starts climbing from its post-alighting low. The system now tracks both the rising occupancy and the platform crowd (inferred from boarding rate vs. expected load for this stop).

### Conrad's experience — Phase 2

**State 2a: Boarding surge begins**

Conrad's train diagram transitions to **boarding mode** — a label change on the UI, same visual but now occupancy numbers climbing:

- Coaches boarding fast show the **rate of change** — a small upward arrow with "+12 in last 30s" alongside the count
- The **expected final load** forecast appears below each coach: "Projected: 84% at departure"
- If any coach's projected load exceeds the amber threshold, it appears in the forecast in amber before it actually tips — Conrad gets 60-90 seconds of warning

**State 2b: Imbalance detected**

Coach 4 is boarding fast — it was at 45% after alighting but the crowd on the platform concentrated there. Projected load: 95% (red). Conrad gets a **proactive alert**:
> "Coach 4 projecting overcapacity — PIS redirecting to coach 7 and 8 — position at coach 4 door?"

This alert is different from Scenario 02 (vestibule congestion mid-journey) — it is a *pre-boarding* forecast alert, not a detected incident. Conrad does not have to physically be there for the system to respond — PIS exterior screens on coach 4 have already updated to:
> "Coach 4 — nearly full · Try coach 7 →"

Conrad taps the alert. It shows:
- Current load: 58 (was 38 post-alighting)
- Rate: +12 per 30 seconds
- Projected at T+4min: 101%
- PIS action: Auto-redirected (no manual step needed)
- Suggestion: "Walk to coach 4 to assist redirect or monitor remotely?"

Conrad decides remotely — he is at the accessibility coach and cannot leave. He confirms "Monitor remotely." The system notes this decision and continues auto-redirecting via PIS.

**State 2c: Accessibility boarding completes**

Conrad deploys ramp, accessibility passenger boards, Conrad confirms via app. The accessibility alert resolves — green tick, archived in the alert log.

Conrad moves to platform mid-point to have sightline over the highest-boarding coaches.

---

### Passenger (general) experience — Phase 2

They have walked to coach 7. PIS screen shows:
> "Coach 7 — Plenty of space · Board here"

They board. The interior is calm — there is a seat available. They stow their suitcase. Done.

---

### Passenger (accessibility) experience — Phase 2

They board coach 2 via the ramp. Conrad is present. They find the accessible space. They fold the pushchair, stow it, settle. Conrad confirms the ramp retracted. The accessible space status in the portal updates from "Available" to "Occupied."

---

## Phase 3 — Pre-Departure (T+3min to T+4min)

### What happens

Dwell timer hits T-1 min. Boarding has effectively stopped — late arrivals are running. Conrad needs a final train-wide check before calling doors.

### Conrad's experience — Phase 3

**State 3a: Pre-departure dashboard**

The app automatically surfaces a **pre-departure summary** when the dwell timer hits 60 seconds:

- All coaches shown in a condensed summary table (not the full diagram):
  - Coach number · Final load % · Status
  - Any coach at ≥90% shown in amber with count
  - Any coach with an **open alert** (unresolved) shown in red with alert icon
- Door obstruction detection active — any coach with a door sensor anomaly flagged immediately
- Dwell timer: "0:58... 0:57..."

**State 3b: All clear**

All coaches amber or below. No unresolved alerts. No door anomalies. Conrad taps **"Doors clear — ready to depart"** — a single large button at the bottom of the pre-departure summary.

This logs a departure readiness event:
- Timestamp
- All-coach snapshot
- Conrad's confirmation
- Any alerts that resolved during the dwell

**State 3c: Late alert (door obstruction)**

*Edge case — shown as an additional state.*

At T-30 seconds, Hailo-8 detects a door obstruction at coach 6. Conrad's handheld vibrates urgently. The pre-departure summary highlights coach 6 in red:
> "Door obstruction — Coach 6 — item detected in doorway"

Conrad walks 10 metres to coach 6. The bag is removed. The obstruction clears. The alert auto-resolves. Conrad confirms "Clear — proceed." Departure is 45 seconds late. The delay is logged against the door obstruction event, not as unexplained delay.

### Passenger experiences — Phase 3

Both passengers are seated and not interacting with the system. The portal updates to show **journey mode** — train diagram with current occupancy, now showing the interior-facing view for the journey ahead.

PIS exterior screens switch from boarding guidance back to **route/destination display** — the boarding guidance state is over.

---

## Success Goals

**Conrad:**
- Entire station stop managed without walking more than 30 metres from his chosen position
- Accessibility boarding completed proactively — ramp was ready before the passenger arrived
- Coach 4 imbalance corrected by PIS without Conrad physically redirecting anyone
- Departure readiness confirmed via one-tap rather than walking the full train

**Passenger (general):**
- Boarded the right coach in under 60 seconds without asking staff or guessing
- Found a seat. Luggage stowed. No aisle blocking.

**Passenger (accessibility):**
- Arrived at the correct door to find Conrad ready and ramp deployed
- Boarded in under 30 seconds. Zero stress.

**Business (Nomad Digital):**
- Full dwell window instrumented — arrival, alighting, boarding, departure readiness all logged as distinct events
- Measurable reduction in door-hold time at this stop (latency between last passenger board and door-close signal)
- Accessibility use case demonstrated end-to-end with audit trail
- PIS auto-redirect validated — Conrad did not need to manually intervene for the coach 4 imbalance

---

## Trigger Map Connections

| Force | Addressed? | Where |
|-------|-----------|-------|
| Know the whole train at a glance | ✅ | Pre-arrival dashboard + real-time dwell diagram |
| Act before problems escalate | ✅ | Pre-boarding forecast alert (State 2b) |
| Feel in control at departure | ✅ | Pre-departure summary + one-tap readiness confirmation |
| Look authoritative to passengers | ✅ | Conrad at accessibility door before passenger arrives |
| Less walking, more managing | ✅ | Remote monitoring confirmation in State 2b |
| Fear missing accessibility need | ✅ | Ramp alert in Phase 1 with portal feedback loop |
| Fear delayed departure blame | ✅ | Door obstruction event logged with delay attribution |
| Fear alert overload | ⚠️ | Pre-boarding forecast alert must be clearly differentiated from incident alerts — see Design Notes |

---

## New UI States Introduced in This Scenario

| State | Description | Applies to |
|-------|------------|-----------|
| Pre-arrival dashboard | Locked occupancy snapshot + dwell timer + expected-alighting bands | Conductor App |
| Alighting-in-progress | Real-time occupancy descent with per-coach animation | Conductor App |
| PIS hold state | "Allow passengers to alight" message before boarding guidance activates | PIS Exterior |
| Pre-boarding forecast alert | Projected overcapacity warning with rate-of-change data | Conductor App |
| Pre-departure summary | Condensed all-coach table with one-tap readiness confirmation | Conductor App |
| Portal ramp status | "Ramp deployed" confirmation triggered by Conrad's app action | Passenger Portal |
| Portal accessible space occupied | Post-boarding status update for accessible space | Passenger Portal |
| Journey mode (portal) | Interior-facing diagram replacing boarding guidance after departure | Passenger Portal |

---

## Design Notes

- **Occupancy descent must be as visible as ascent** — the train diagram needs to animate falling numbers during alighting phase, not just rising numbers during boarding. The visual language of the dwell is two-directional.
- **Expected-alighting estimate** relies on reservation data from ÖBB's ticketing system — this is a new data dependency not present in Scenarios 01–09. Flag for technical validation.
- **PIS hold state ("allow passengers to alight")** must auto-clear without Conrad interaction — it should switch to boarding guidance automatically when alighting rate drops below threshold, not when Conrad taps something. Conrad should not be babysitting PIS screen state.
- **Pre-boarding forecast alert** must be visually distinct from incident alerts — colour or iconography must distinguish "this is a prediction" from "this is happening now." Conrad's alert fatigue risk is highest in this scenario.
- **One-tap departure readiness** is a new concept — it creates a formal digital record of Conrad's go/no-go decision. ÖBB may need to formally accept this as part of their departure protocol. Flag for operator validation.
- **Dwell timer** must be based on scheduled stop time, not actual arrival time — if the train arrives 2 minutes late, the dwell window is already shortened, and Conrad needs to know.
- **Door obstruction in Phase 3** should escalate to an audible/haptic alert, not just visual — Conrad may not be watching the screen at T-30 seconds.
- ⚠️ **New technical dependency:** Expected-alighting estimate requires ÖBB reservation data feed per stop, per coach. Confirm availability and latency with ÖBB integration team.
- ⚠️ **New technical dependency:** Boarding rate inference ("+12 in 30s") requires Hailo-8 to count entry events per coach, not just static headcount. Confirm directional entry/exit differentiation accuracy.

---

## Scenario Connections

| Scenario | Relationship |
|----------|-------------|
| Scenario 01 | Continuation — Scenario 10 covers the dwell window; Scenario 01 picks up the boarding surge at a fresh departure where no alighting occurs |
| Scenario 05 | Embedded — Scenario 10 is the first place the PIS hold state ("allow alighting") is introduced before the Scenario 05 boarding guidance activates |
| Scenario 06 | Embedded — accessibility boarding in Phase 1-2 of this scenario expands Scenario 06 with the arrival and ramp-deployment timing context |
| Scenario 02d | Edge case overlap — if an unattended bag is left behind by an alighting passenger, Scenario 02d's detection logic activates during Phase 1 of this scenario |
