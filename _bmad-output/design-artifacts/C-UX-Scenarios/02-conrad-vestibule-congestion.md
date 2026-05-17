# Scenario 02 — Conrad Clears a Vestibule Bottleneck

**Persona:** Conductor Conrad (Primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Mid-journey vestibule congestion alert — Conrad is notified when camera-based occupancy detects passengers bunching in a doorway vestibule, enabling him to intervene before the crowding causes a delayed station stop.

## Entry Point
The train is 12 minutes out from the next stop. Conrad is in the bistro area checking on Brigitte's stock situation. His handheld vibrates with a warning alert.

## Mental State
**Trigger:** Alert reads: "Coach 4 vestibule — crowding detected. 11 passengers in doorway zone. Risk of delayed boarding/alighting at next stop."
**Hope:** That he can resolve this quickly without having to walk the full length of the train and disrupt other passengers.
**Worry:** That a packed vestibule will cause a slow exit at the next station, creating a cascade delay — and that it will look like he wasn't watching.

## Sunshine Path

1. Conrad's handheld shows a persistent amber banner: "Coach 4 vestibule — crowding. 11 pax in door zone. Next stop: 12 min."
2. He taps the banner — the coach detail view opens showing a camera-derived heatmap of the vestibule: a dense orange cluster at the door end, seats visible but underused toward the centre of the coach
3. Conrad sees at a glance that passengers have pre-positioned for the next stop far too early — a common behaviour on short intercity hops
4. He uses the PA button in the app to make a short announcement targeted at coach 4: "Passengers in coach 4, the next stop is still 12 minutes away — please move away from the doors and use available seating"
5. The heatmap updates within 90 seconds — cluster disperses, vestibule drops back to green
6. Alert auto-resolves. Conrad logs no action — the app marks the alert as "resolved via PA" based on the subsequent sensor change
7. Arrival at next stop: alighting and boarding complete in standard time. No delay logged.

## Success Goals
**Conrad:** Caught the problem 12 minutes out, resolved it in under 2 minutes, no disruption to his other duties.
**Business (Nomad Digital):** Conductor response event logged. Dwell time at next station within SLA. Alert accuracy validated (true positive).

## Trigger Map Connections
- ✅ Act before problems escalate
- ✅ Feel in control during journey, not just at departure
- ✅ Fear missed incident causing delay — addressed
- ✅ Fear alert overload — alert was specific, actionable, and self-resolving

## Design Notes
- Alert must specify coach AND zone (vestibule vs. mid-coach vs. upper deck) — generic "crowding" alerts will be ignored
- Heatmap must be interpretable in under 5 seconds — no legend required for trained conductors
- PA trigger from alert context (pre-filled with coach 4) reduces action time vs. navigating to a separate PA screen
- Auto-resolve on sensor improvement removes the need for Conrad to manually close alerts — reducing admin burden
- Threshold for vestibule alert must be configurable: peak Fridays vs. weekday off-peak have very different baselines
- Alert must not fire within 3 minutes of a scheduled stop — passengers legitimately gather at doors then
