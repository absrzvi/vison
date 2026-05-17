# Scenario 08 — Brigitte Routes Her Trolley Mid-Journey

**Persona:** Bistro Brigitte (Supporting)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-14

---

## Core Feature
Mid-journey trolley routing — Brigitte checks live coach occupancy to decide which coaches to push the trolley through first, maximising revenue and minimising effort on a busy service.

## Entry Point
The train has been running for 20 minutes. Brigitte has finished the initial bar rush. She's about to push the trolley through the train for the first service round. She has time to do 5 coaches before the next station stop.

## Mental State
**Trigger:** 10 coaches, one trolley, 45 minutes until the next long stop. Where does she start?
**Hope:** To hit the busiest coaches first while passengers are still settled and in buying mode — not waste the first pass on empty coaches while the full ones wait.
**Worry:** That she pushes through 4 quiet coaches and arrives at the busy ones just as they start alighting at the next stop — timing a trolley run is harder than it looks.

## Sunshine Path

1. Brigitte taps the trolley routing view in the Bistro App — a coach-by-coach occupancy list appears, sorted by current passenger count: Coach 3 (52), Coach 4 (48), Coach 8 (44), Coach 1 (31), Coach 6 (18)...
2. She starts at coach 3, works through 4 and 8 — the three heaviest — completing the high-value run in 35 minutes
3. At the next station stop she checks the app again — coaches 1 and 2 have filled from boarding passengers. She adjusts: does those next rather than continuing with the lighter coaches.
4. End of journey: she served the equivalent of 8 coaches of demand in 6 passes, compared to her usual random-walk approach.

## Success Goals
**Brigitte:** Maximised revenue per trolley run by prioritising the busiest coaches first. Adjusted route dynamically at the stop without guesswork.
**Business (Nomad Digital):** Demonstrable revenue uplift for the bistro operator — quantifiable ROI for a supporting use case, strengthens the commercial story.

## Trigger Map Connections
- ✅ Know which coaches to prioritise — directly and precisely addressed
- ✅ Calibrate service to actual load — dynamic re-routing at stops
- ❌ Fear running out mid-service — by routing to busy coaches first, she can pace stock deployment accordingly

## Design Notes
- Trolley routing view must be sorted by occupancy descending — Brigitte should not need to read and rank herself
- Coach number must be prominent — Brigitte navigates by coach number, not position in the train
- View must update at each station stop — the relevant moment for re-routing decisions
- This view is distinct from the pre-departure aggregate view (Scenario 07) — different data shape, different decision context
