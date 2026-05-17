# Scenario 06 — Passenger with Pushchair Finds Accessible Space

**Persona:** Passenger (accessibility need)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Accessibility-aware boarding guidance — the system detects available wheelchair/pushchair space and surfaces it to the passenger via the portal, while simultaneously alerting Conrad to be at the right door.

## Entry Point
A passenger with a pushchair arrives on the platform. They need the accessible coach with the PRM door and ramp. They don't know which coach that is, or whether the accessible space is already occupied.

## Mental State
**Trigger:** Platform is busy. They have a pushchair and a toddler. They're anxious about getting on the train smoothly — PRM doors are not always obvious, ramps need deploying, and they've been caught out before arriving at the wrong door.
**Hope:** To find the right door, board smoothly, and have someone ready to help without having to shout across the platform.
**Worry:** That the accessible space is taken, that the ramp won't be deployed in time, or that they'll board through the wrong door and block a narrow aisle with the pushchair.

## Sunshine Path

1. Passenger opens the Nomad Digital portal on their phone — the train diagram shows a wheelchair icon on coach 2 (the accessible coach) with status: "Accessible space available"
2. The portal shows which platform door the PRM ramp will be deployed at — "Board at coach 2, door 1 — ramp will be ready"
3. Conrad receives an alert on his handheld: "Accessibility need detected — pushchair/wheelchair — Coach 2, Door 1 — passenger approaching"
4. Conrad walks to coach 2, door 1, and deploys the ramp before the passenger arrives
5. Passenger arrives at the door to find Conrad ready, ramp deployed. They board in under 30 seconds.
6. Conrad confirms ramp deployed via the app — the accessibility alert resolves.

## Success Goals
**Passenger:** Boarded the correct door, ramp ready, space available. No stress, no delay.
**Conrad:** Knew where to be and when — arrived before the passenger, not after. Proactive, not reactive.
**Business (Nomad Digital):** Accessibility use case demonstrated — high visibility, strong ÖBB compliance value.

## Trigger Map Connections
- ✅ Conrad: Act before problems escalate — deployed ramp before passenger arrived
- ✅ Conrad: Look authoritative — was at the door, ready, in command
- ❌ Conrad: Fear missing accessibility need — directly addressed
- Passenger: Anxiety about accessible boarding — resolved through proactive information and readiness

## Design Notes
- Accessible space availability must account for existing wheelchair/pushchair occupants — if the space is taken, portal must say so clearly before the passenger commits to that door
- Conrad's alert must fire with enough lead time to walk to the coach — minimum 3 minutes before scheduled departure or when passenger is detected approaching the platform
- Ramp deployment confirmation by Conrad closes the loop — system knows ramp is ready, not just that the alert was sent
- Portal accessibility indicator must be persistent throughout the journey — not just at boarding
