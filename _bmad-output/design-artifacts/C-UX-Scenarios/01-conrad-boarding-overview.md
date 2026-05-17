# Scenario 01 — Conrad Watches the Train Fill

**Persona:** Conductor Conrad (Primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Live boarding occupancy view — Conrad monitors passenger and luggage load building per coach in real time as passengers board on the platform, with PIS exterior screens automatically reflecting coach load to guide self-distribution.

## Entry Point
Conrad is on the platform 8 minutes before scheduled departure. He opens the Conductor App on his handheld. The train diagram is the default home screen — no navigation required.

## Mental State
**Trigger:** Platform is filling fast. It's a Friday afternoon intercity. Conrad can see with his eyes that coach 3 is already crowded at the door — but he can't see coaches 6 through 10 from where he's standing.
**Hope:** That he can see the whole train at once and direct people before it becomes a problem, without walking 150 metres.
**Worry:** That he'll miss a developing pile-up in a coach he can't physically see, and it'll delay departure.

## Sunshine Path

1. Conrad opens the app — the home screen shows a colour-coded train diagram: all 10 coaches in a horizontal row, each shaded green, amber, or red based on current occupancy threshold
2. Coach 3 is amber. Coaches 8 and 9 are green. Coaches 4 and 5 are filling toward amber.
3. PIS exterior screens on coaches 8 and 9 automatically display "Plenty of space" in German/English — passengers on the platform self-direct without Conrad intervening
4. Coach 3 tips to red. Conrad taps it — the detail panel expands: 47 passengers, 23 luggage items, 89% of threshold
5. Conrad walks to the coach 3 door and verbally redirects the next 4 passengers toward coach 8. Takes 45 seconds.
6. Coach 3 drops back to amber. PIS screen on coach 3 updates to "Nearly full — please use adjacent coaches"
7. Conrad checks the diagram one more time at T-2 minutes — all coaches amber or below, no red. Departure on time.

## Success Goals
**Conrad:** Entire train assessed in under 10 seconds. Redirected passengers without walking the full length. Departed on time.
**Business (Nomad Digital):** Conductor adoption event logged. PIS integration demonstrated. On-time departure metric improved.

## Trigger Map Connections
- ✅ Know the whole train at a glance
- ✅ Feel in control during high-stress departures
- ✅ Act before problems escalate
- ❌ Fear missing what's happening in unseen coaches — addressed

## Design Notes
- Train diagram must be the default home screen — zero taps to reach it
- Coach colour thresholds must be configurable per operator (ÖBB may have specific load standards)
- PIS screen updates must be automatic — Conrad should not need to trigger them manually
- ⚠️ PIS integration dependency: requires confirmed L2 network write access to Nomad portal screens
