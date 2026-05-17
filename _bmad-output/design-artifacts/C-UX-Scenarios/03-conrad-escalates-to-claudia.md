# Scenario 03 — Conrad Escalates a Chronic Overcrowding Pattern to Claudia

**Persona:** Conductor Conrad → Control Centre Claudia
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Escalation flow — Conrad flags a persistent occupancy problem on a specific route/service to the Control Centre, where Claudia receives the escalation with the occupancy data attached and can take capacity action.

## Entry Point
Conrad has noticed that coaches 3 and 4 on his Friday 17:15 service are consistently hitting red every week. He has seen it three times. He wants to flag it so capacity can be addressed — not by him, but by someone who can actually change the train configuration.

## Mental State
**Trigger:** Third Friday in a row. Same coaches, same problem. Conrad knows this is above his pay grade but he also knows nobody will fix it unless he surfaces it with evidence.
**Hope:** That he can raise it quickly, with the data already attached, without writing a long report.
**Worry:** That it'll disappear into a void and nothing will change — like every other informal complaint he's ever made.

## Sunshine Path

1. Conrad opens the app on the 17:15 service, sees coaches 3 and 4 at red again
2. He taps "Flag for review" on the coach detail panel — a simple escalation form appears, pre-populated with: service ID, date, coach numbers, current occupancy %, and a 7-day occupancy trend graph pulled automatically from historical data
3. Conrad adds a one-line note: "Third consecutive Friday, same pattern" and taps Send
4. Claudia receives the escalation in the Control Centre dashboard — a flagged service card showing Conrad's note, the current occupancy, and the 7-day trend
5. Claudia reviews the trend — coaches 3 and 4 on the 17:15 are consistently 15% over capacity on Fridays. She logs a capacity review request for that service.
6. Conrad receives a confirmation: "Escalation received by Control Centre — ref #4421"

## Success Goals
**Conrad:** Raised the issue in under 60 seconds with data already attached. Got confirmation it was received.
**Claudia:** Received a structured, evidence-backed escalation she can act on immediately rather than a vague radio message.
**Business (Nomad Digital):** Demonstrated closed-loop value — onboard AI feeds landside capacity decisions. Key narrative for operator sales.

## Trigger Map Connections
- ✅ Conrad: Look authoritative — surfaces the problem before it's a complaint
- ✅ Claudia: Make defensible decisions — escalation includes data, not just opinion
- ✅ Claudia: Reduce radio dependency — structured data replaces a voice call
- ❌ Conrad: Fear his reports disappear — confirmation receipt closes the loop

## Design Notes
- Escalation form must be pre-populated — Conrad should add nothing except an optional free-text note
- 7-day trend must pull automatically from historical occupancy data — no manual data entry
- Claudia's dashboard view of escalations must be separate from live alerts — different urgency, different workflow
- Confirmation receipt back to Conrad is essential — closes the anxiety loop
