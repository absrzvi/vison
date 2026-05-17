# Supporting Personas — OEBB Smart Rail Passenger Intelligence

**Phase:** 2 — Trigger Map
**Date:** 2026-05-14

---

## Bistro Brigitte — Supporting

**Goal Connection:** Goal 2

### Who Brigitte Is
Brigitte runs the bistro car on an ÖBB intercity service. She manages stock, service timing, and staffing for a moving café that serves a wildly variable number of customers depending on the journey, the day, and how full the adjacent coaches are. She is practical, fast-moving, and allergic to complexity.

### Psychological Profile
Brigitte's pain is **inventory and positioning uncertainty**. She over-stocks for fear of running out; she under-staffs because she doesn't know how busy the train will be until it's too late. She doesn't need sophisticated AI — she needs one number: how full is the train, and where are the people?

### Driving Forces

**Positive ✅**
1. **Know which coaches to prioritise for trolley service** — wants to route her trolley through the heaviest coaches first so the most passengers get served while stock is fresh
2. **Calibrate stock prep to actual passenger load** — wants to know before departure whether today is a 40-person or a 200-person journey so she can prepare appropriately

**Negative ❌**
1. **Fear running out of key stock mid-journey** — embarrassing, generates complaints, reflects on her personally
2. **Frustration with wasted prep when the train is nearly empty** — over-preparation is costly and demoralising; she wants the data to be right, not always pessimistic

---

## Driver Diego — Supporting

**Goal Connection:** Goal 2, Goal 3

### Who Diego Is
Diego is a cab-based ÖBB train driver. His job is operating the train safely; passenger management is not his responsibility. He receives the Passenger Intelligence feed on a cab-mounted display as a passive, read-only summary — highest-severity alerts only.

### Psychological Profile
Diego's relationship to the system is defined entirely by **cognitive load**. He is operating a train at speed. Anything that divides his attention is a safety risk. He does not want a feature-rich display — he wants zero distraction and the assurance that if something genuinely critical is happening in the passenger saloon, he will know about it without having to look for it.

### Driving Forces

**Positive ✅**
1. **Receive critical safety alerts passively without having to monitor** — wants the display to be silent and dark when nothing is wrong, and clearly visible when there is a genuine issue requiring his awareness
2. **Trust that the system won't distract him unnecessarily** — the only way Diego adopts this is if it proves reliable and non-intrusive from day one

**Negative ❌**
1. **Fear distraction from a noisy alert system** — one unnecessary alert during a critical operational moment and Diego mentally writes off the entire system
2. **Fear responsibility creep** — does not want the display to imply he should be acting on passenger events; that is the conductor's domain, not his

---

## Fleet Manager Finn — Supporting

**Goal Connection:** Goals 1, 2

### Who Finn Is
Finn manages ÖBB's regional fleet. He makes deployment, maintenance scheduling, and capacity planning decisions on a weekly and monthly horizon. He never sees the occupancy data in real time — he sees aggregated trends, historical patterns, and exception reports.

### Psychological Profile
Finn thinks in **fleet economics**. Every train is a capital asset. Occupancy data tells him whether assets are being deployed efficiently. He is interested in patterns, not incidents — what is the average load on the 07:15 Salzburg service on Tuesdays? Which routes are chronically under-served? This data currently doesn't exist in a clean, actionable form.

### Driving Forces

**Positive ✅**
1. **Make deployment decisions based on actual occupancy data** — wants to replace gut-feel and anecdote with evidence when arguing for additional rolling stock or route changes
2. **Identify chronic capacity mismatches** — wants to surface routes where demand consistently exceeds or underutilises deployed capacity so he can make a business case for change

**Negative ❌**
1. **Fear making fleet decisions on bad data** — if the occupancy figures are inaccurate, his deployment arguments are undermined; data quality is a prerequisite for use
2. **Frustration with reports that require manual extraction** — Finn needs this data in a format he can put directly into a management presentation, not a raw data export that requires processing

---

## Relationship to Business Goals (All Supporting Personas)

- **Brigitte** → Goal 2: Her improved stocking and routing efficiency is a secondary operational win for ÖBB
- **Diego** → Goal 2 + 3: His passive alert receipt requires robust suppression logic (maintenance mode, false positive control) — proving Goal 3 privacy and reliability in the most demanding context
- **Finn** → Goal 1 + 2: His analytics use case is the long-term stickiness mechanism — fleet managers who build workflows around occupancy data become advocates for expansion to new routes and operators
