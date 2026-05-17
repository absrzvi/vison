# Scenario 07 — Brigitte Preps Stock Before Departure

**Persona:** Bistro Brigitte (Supporting)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Pre-departure load forecast — Brigitte checks the current train occupancy before the service departs to calibrate how much stock to prepare and pull from the storage unit.

## Entry Point
Brigitte is in the bistro car 15 minutes before departure. Stock is in the storage unit. She needs to decide how much to pull out — too much and it spoils or takes up counter space, too little and she runs out mid-journey.

## Mental State
**Trigger:** She has 15 minutes. She's done this journey 80 times. She knows a full train on a Friday is 3x the work of a Tuesday morning. But she never knows in advance exactly how full it'll be until it's too late to adjust.
**Hope:** A number. Just tell her how many people are on the train so she can make a sensible decision.
**Worry:** Over-prepping on a light day (waste, mess, effort) or under-prepping on a heavy day (running out, complaints, stress).

## Sunshine Path

1. Brigitte opens the Bistro App on her tablet — the home screen shows current train occupancy: 187 passengers across 10 coaches, 74% of capacity, trending upward (6 minutes to departure)
2. The app shows a simple recommendation: "Heavy service — prepare full stock allocation"
3. Brigitte pulls full stock from the storage unit — hot drinks, cold drinks, snacks, sandwiches to the high-load level
4. Train departs. She serves 40+ passengers in the first 90 minutes without running low.
5. At the midpoint stop, she checks the app again — occupancy has dropped to 58% (alighting passengers). She scales back the next prep cycle.

## Success Goals
**Brigitte:** Made the right stock decision in under 2 minutes. Didn't run out. Didn't over-prep.
**Business (Nomad Digital):** Bistro efficiency use case validated — occupancy data creates value beyond safety and operations, extending the commercial story for operator sales.

## Trigger Map Connections
- ✅ Calibrate stock to actual passenger load — directly addressed
- ✅ Know which coaches to prioritise — sets up trolley routing in Scenario 08
- ❌ Fear running out of key stock mid-journey — addressed through pre-departure data
- ❌ Frustration with wasted prep on a light day — data prevents over-preparation

## Design Notes
- The home screen number must be the total across the whole train, not per-coach — Brigitte needs the aggregate, not the breakdown, for stocking decisions
- Simple recommendation label ("Light / Moderate / Heavy service") is more useful than a raw percentage to Brigitte
- Trend indicator (occupancy still rising at T-6 min) is valuable — she should prep for the peak, not the current count
- Mid-journey re-check is a natural behaviour — the app should support this without requiring navigation
