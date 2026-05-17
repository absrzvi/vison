# Key Strategic Insights — OEBB Smart Rail Passenger Intelligence

**Phase:** 2 — Trigger Map
**Date:** 2026-05-14

---

## Insight 1: Conrad is the Pilot. The Pilot is Conrad.

The 3-month pilot lives or dies on whether Conductor Conrad adopts the app and finds it genuinely useful within the first 1–2 journeys. Everything else — Claudia's dashboard, Finn's reports, Brigitte's stocking data — is downstream of Conrad's trust. If Conrad dismisses the system as noise, adoption collapses and the renewal argument fails.

**Design implication:** The Conductor App is not one of six interfaces — it is the product. Every design decision should optimise for Conrad's first 10 minutes with the system.

---

## Insight 2: False Positives Are an Existential Risk

Conrad, Claudia, and Diego all share the same deepest fear: acting (or being blamed for not acting) on bad data. The Passenger Intelligence service is a new voice in the ears of people who already have too much noise. One reliable false positive — a door obstruction that wasn't there, a bag alert that triggers every journey — and the system is muted, ignored, or actively resented.

**Design implication:** Alert suppression logic (maintenance mode, speed correlation, configurable thresholds) is not a configuration option — it is a trust mechanism. It must be correct from day one, not tuned later.

---

## Insight 3: The Data Must Justify Itself Without Asking to Be Justified

Claudia will not monitor a new feed. Diego cannot. Finn needs exportable reports, not a new dashboard login. Each persona's interaction with occupancy data needs to fit into existing workflow patterns — ambient for Claudia, passive for Diego, scheduled and formatted for Finn. The system fails if users have to change their behaviour to receive value from it.

**Design implication:** The six interfaces are not six versions of the same app. They are six radically different interaction modes shaped entirely by the workflow context of each persona.

---

## Insight 4: Privacy is a Sales Feature, Not a Compliance Checkbox

European rail operators are acutely sensitive to passenger surveillance. The "raw video never leaves the train" principle is not just technically correct — it is a commercial differentiator in a market where any hint of passenger tracking creates procurement resistance. Nomad Digital should make this visible, not just guaranteed.

**Design implication:** The privacy architecture should be explicitly surfaced in operator-facing materials and subtly reinforced in the UI (e.g., "Anonymised inference only — no images stored or transmitted" as a persistent UI element or onboarding message).

---

## Prioritisation Summary

| Driving Force | Persona | Frequency | Intensity | Fit | Total | Priority |
|---|---|---|---|---|---|---|
| Know the whole train at a glance | Conrad | 5 | 5 | 5 | 15 | HIGH |
| Act before problems escalate | Conrad | 5 | 5 | 5 | 15 | HIGH |
| Fear missing safety-critical incident | Conrad | 5 | 5 | 5 | 15 | HIGH |
| Fear false positive overload | Conrad | 5 | 5 | 5 | 15 | HIGH |
| Real occupancy across fleet in real time | Claudia | 5 | 4 | 5 | 14 | HIGH |
| Fear acting on stale/inaccurate data | Claudia | 4 | 5 | 4 | 13 | MEDIUM |
| Receive critical alerts passively | Diego | 5 | 5 | 4 | 14 | HIGH |
| Fear distraction from noisy alerts | Diego | 5 | 5 | 4 | 14 | HIGH |
| Know which coaches to prioritise | Brigitte | 4 | 3 | 5 | 12 | MEDIUM |
| Make deployment decisions on data | Finn | 3 | 4 | 4 | 11 | MEDIUM |

**Strategic focus:** Design first for Conrad's trust and Claudia's reliability needs. Diego's passive alert design is a forcing function for false-positive discipline. Brigitte and Finn are valuable but not pilot-critical.
