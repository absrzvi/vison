# Scenario 02b — Conrad Rebalances a Lopsided Train

**Persona:** Conductor Conrad (Primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Mid-journey occupancy imbalance detection — Conrad is alerted when one end of the train is significantly fuller than the other, and can broadcast a rebalancing message via PA announcement and PIS interior screens showing live coach availability.

## Entry Point
The train departed 20 minutes ago. Conrad completed his ticket check sweep of coaches 1–5. He's in the gangway between coaches 5 and 6 when his handheld flags an imbalance.

## Mental State
**Trigger:** Alert reads: "Occupancy imbalance — Coaches 1–4 avg 87% · Coaches 7–10 avg 31%. Consider rebalancing."
**Hope:** That he can shift even 15–20 passengers without making a disruptive announcement that annoys the people who are already settled.
**Worry:** That passengers will ignore a generic PA message, or that he'll have to physically walk people to empty coaches — which takes time he doesn't have.

## Sunshine Path

1. Conrad taps the imbalance alert — the train diagram opens with a clear visual split: coaches 1–4 deep amber/red, coaches 7–10 green
2. He checks the detail panel: coaches 8 and 9 are less than 25% full, with unreserved seating. Coach 10 has 4 reserved seats unoccupied — likely no-shows
3. Conrad decides to act: he taps "Announce + Show on screens" — a pre-filled PA draft appears: "Passengers in coaches 1 to 4 — coaches 8, 9 and 10 have plenty of available seating and are a short walk through the train. We encourage you to move for a more comfortable journey."
4. He reviews and sends. Simultaneously, PIS interior screens in coaches 1–4 display a simple graphic: coach silhouette with coaches 8–10 highlighted green and a seat count: "Seats available: 38"
5. Within 5 minutes, the train diagram shows movement: coaches 1–4 drop slightly to amber, coaches 8–9 tick upward to light amber
6. Conrad doesn't need to intervene further. The app logs: "Rebalance initiated via PA + screens. Estimated 14 passengers moved."

## Success Goals
**Conrad:** Improved passenger comfort without physically escorting anyone. Announcement felt targeted and useful, not generic.
**Business (Nomad Digital):** Average comfort score across train improved. Interior PIS integration demonstrated. Conductor adoption event logged.

## Trigger Map Connections
- ✅ Know the whole train at a glance
- ✅ Act before problems escalate (crowded coaches lead to complaints, slow alighting)
- ✅ Feel in control and authoritative mid-journey
- ✅ PIS interior screens serve dual purpose: passenger-facing and conductor-action tool

## Design Notes
- Imbalance threshold needs tuning: a 56-point gap (87% vs 31%) is clearly worth acting on; a 15-point gap probably isn't
- PA draft must be pre-filled but editable — Conrad's voice and tone matter; he shouldn't feel like a recorded announcement
- "Announce + Show on screens" must be a single action — splitting it into two steps will mean the screens get skipped
- PIS interior screen content must be simple: coach number, seat count, and a green indicator. No complex graphics on a moving train
- Imbalance alert should not fire if the train is at its last stop before terminus — no point rebalancing 10 minutes from end
- ⚠️ PIS interior screen integration dependency: requires confirmed L2 network write access — same dependency as exterior PIS (scenarios 01, 05)
