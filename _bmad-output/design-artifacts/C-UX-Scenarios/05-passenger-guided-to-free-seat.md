# Scenario 05 — Passenger Guided to a Free Coach via Platform Screen

**Persona:** Passenger (general)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Passive passenger guidance — occupancy data drives real-time coach availability messaging on PIS exterior screens and the Nomad Digital passenger portal, directing passengers to less crowded coaches before they board.

## Entry Point
A passenger is standing on the platform with a standard ticket (no reserved seat). The train is at the platform. They are looking at the exterior of the train, trying to decide which door to board through.

## Mental State
**Trigger:** The train is in front of them. They can see one carriage door has a crowd at it. They don't know if the rest of the train is equally busy or if they should walk further down the platform.
**Hope:** To find a seat quickly, avoid the scrum, and not have to carry their bag through a packed carriage.
**Worry:** That they'll board the wrong coach and spend the journey standing, or have to push through 3 carriages with luggage to find space.

## Sunshine Path

1. The passenger glances at the PIS screen on the nearest coach exterior — it shows a simple load indicator: "Coach 4 — Nearly full · Coach 7 — Plenty of space →"
2. The passenger walks 30 metres down the platform to coach 7 — takes 20 seconds
3. They board coach 7, find a seat immediately, stow their luggage in an available overhead rack
4. Journey begins without incident

**Alternate entry (passenger portal):**
1. Passenger opens the Nomad Digital passenger portal on their phone while walking to the platform
2. The portal shows a live train diagram with coach load indicators — same green/amber/red as the PIS screens
3. Passenger identifies coach 7 as the least crowded and walks directly to that door

## Success Goals
**Passenger:** Boarded the right coach in under 60 seconds without asking staff. Found a seat. Luggage stowed.
**Conrad:** One fewer passenger to redirect manually. Platform boarding smoother — fewer last-minute coach changes.
**Business (Nomad Digital):** Passenger-facing product demonstrated. PIS integration validated. Boarding efficiency improved — measurable reduction in door-hold time at busy stops.

## Trigger Map Connections
- Extends Conrad's driving forces indirectly: fewer boarding redirections means Conrad spends less time managing platform flow
- Directly addresses passenger experience — reduces friction at the moment of highest anxiety (boarding an unfamiliar train with luggage)

## Design Notes
- PIS screen message must be ultra-simple: coach number + single status word + directional arrow — nothing more
- Message language: German primary, English secondary (ÖBB standard)
- Portal load indicator must match PIS screen state exactly — same data source, same thresholds
- Refresh rate must be fast enough to be meaningful on a platform — minimum 30-second update cycle
- ⚠️ PIS integration dependency: requires confirmed L2 network write access — flag for technical validation before implementation
