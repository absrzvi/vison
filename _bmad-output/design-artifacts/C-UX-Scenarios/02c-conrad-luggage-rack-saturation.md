# Scenario 02c — Conrad Heads Off a Luggage Bottleneck

**Persona:** Conductor Conrad (Primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Luggage rack saturation alert — Conrad is notified when Hailo-8 camera inference detects that overhead racks in a specific coach are at or near capacity before a major boarding stop, giving him time to prepare passengers or redirect boarding.

## Entry Point
The train is 8 minutes from a major interchange stop where a large boarding group is expected (known from the schedule). Conrad is in the conductor cab area reviewing his schedule on the handheld.

## Mental State
**Trigger:** Alert reads: "Coach 3 — luggage racks at 94% capacity. Large boarding expected at next stop (est. 22 pax). Conflict likely."
**Hope:** That he can either make space or redirect boarding passengers to coaches with available rack space — before the platform chaos begins.
**Worry:** That passengers boarding with large luggage will block the aisle for 3–4 minutes trying to find rack space, delaying departure and frustrating everyone already seated.

## Sunshine Path

1. Conrad taps the alert — the coach 3 detail view shows a rack occupancy bar at 94%, with a note: "Detected items: 18 bags, 3 oversized cases, 1 bicycle bag (upper deck)"
2. He checks adjacent coaches: coach 2 is at 41%, coach 4 at 55% — both have comfortable headroom
3. Conrad decides on a two-part response:
   - He makes a PA announcement: "Passengers boarding at the next stop with large luggage — coaches 2 and 4 have the most available overhead space. Please use the nearest door to those coaches."
   - He also checks the PIS exterior screen setting: coaches 2 and 4 exterior screens will show "Luggage space available" after the PA
4. He walks toward the coach 3 door to personally direct passengers with oversized bags as they board
5. Boarding completes: coach 3 racks tip to 100% (2 bags from existing passengers rearranged), but aisle is clear. Coaches 2 and 4 absorbed the boarding group's luggage without issue
6. Departure is on time. App logs: "Luggage rack alert actioned — PA + platform presence. No delay."

## Success Goals
**Conrad:** Anticipated the problem before it happened. Directed passengers proactively rather than firefighting mid-boarding.
**Business (Nomad Digital):** Dwell time within SLA. Luggage detection accuracy validated. Conductor engagement with proactive alerts demonstrated.

## Trigger Map Connections
- ✅ Act before problems escalate
- ✅ Know the whole train at a glance — rack occupancy as a first-class data layer
- ✅ Fear missed incident causing delay — addressed proactively
- ✅ Feel in control at boarding stops, not just initial departure

## Design Notes
- Rack saturation alert must fire with enough lead time — minimum 6 minutes before a boarding stop is the target; 3 minutes is too late to act
- Detected item count (bags, oversized, bicycles) is more useful than a percentage alone — Conrad needs to know what he's dealing with
- Alert should cross-reference schedule data to flag stops with large expected boarding — prevents alert fatigue on quiet stops
- Rack occupancy must be a visible secondary layer on the main train diagram (not buried in a detail view) — conductors should be able to monitor it passively
- Hailo-8 luggage inference accuracy for oversized/bicycle items needs validation before trusting the "oversized" classification in production
- PA draft for luggage alerts should pre-fill with the specific coaches that have available space — saves Conrad from mentally calculating which ones to name
