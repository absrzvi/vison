# Persona: Control Centre Claudia — Secondary 👤

**Phase:** 2 — Trigger Map
**Date:** 2026-05-14
**Goal Connection:** Goals 1, 2

---

## Who Claudia Is

Claudia is a ÖBB control centre operator managing a regional rail network from a landside web dashboard. She monitors multiple trains simultaneously, coordinates service disruptions, and makes real-time capacity decisions. She has no physical presence on the trains she manages — she operates entirely through data.

---

## Psychological Profile

Claudia thinks in **patterns and exceptions**. Her job is to keep a mental model of the whole network current, notice when something deviates from expected, and respond before it cascades. She is comfortable with dashboards, accustomed to high information density, and skilled at filtering signal from noise.

She is **frustrated by data blindness**. Right now she knows a train is running on time or late. She does not know why a train is late, whether it is because of a door incident, an overcrowding delay, or something else. She is making network decisions with incomplete information and she knows it.

Claudia has a **cool, analytical relationship with urgency**. She does not panic. She triages. But she needs the right information fast enough to triage correctly — a 5-minute-old occupancy reading is worse than no reading at all if it causes a wrong capacity decision.

---

## Internal State

Claudia feels **professionally constrained** — her skills exceed her data. She is capable of making better network decisions but is limited by what the current systems tell her. The Passenger Intelligence service represents, to her, the possibility of finally seeing what is actually happening on her trains.

---

## Usage Context

**Access:** Web dashboard on a dedicated workstation. Always running, always visible alongside other monitoring systems.

**Emotional State:** Watchful, efficient. Will integrate the occupancy feed if it proves reliable; will ignore it if it generates noise.

**Behaviour Pattern:** Glances at occupancy overview on event triggers (delays, disruptions). Does not monitor continuously. Needs the feed to be ambient and accurate — noticed when something is wrong, invisible when everything is fine.

**Decision Criteria:** Is this data reliable enough to act on? Can I explain a capacity decision to a manager by referencing it?

**Success Outcome:** Claudia redirects a disrupted service based on real occupancy data rather than guesswork, and the decision proves correct. She cites the system in the post-incident report.

---

## Driving Forces

### Positive Drivers ✅

1. **See real occupancy across the fleet in real time** — wants to know which coaches and which trains are heavy, light, or at capacity right now so that disruption management is based on facts, not assumptions
2. **Make defensible capacity decisions** — when Claudia acts on occupancy data, she needs to be able to justify the decision to management; a logged, timestamped data source makes her decisions auditable
3. **Spot developing situations before they become incidents** — a train that is progressively filling beyond capacity at each stop is a pattern; Claudia wants to see patterns forming, not just current snapshots
4. **Reduce dependence on radio communications from conductors** — current process requires conductors to report verbally; Claudia wants the data direct, not filtered through a voice call she may have missed

### Negative Drivers ❌

1. **Fear acting on stale or inaccurate data** — a wrong capacity decision based on bad occupancy data is worse than a decision made without it; Claudia's highest concern is data reliability, not data availability
2. **Frustration with systems that require active monitoring** — she cannot watch another feed continuously; the occupancy data must surface alerts passively, not demand attention
3. **Fear of accountability gaps** — if an occupancy-related incident happens and she had access to the data but didn't act on it, the exposure is significant; she needs clear thresholds and logged alerts
4. **Resentment of duplicate systems** — if occupancy data lives in a separate tool that doesn't integrate with her existing dashboard, she will not use it; integration is a prerequisite, not a feature

---

## Relationship to Business Goals

- ✅ **Goal 1 (Infrastructure Intelligence Provider):** Claudia's dashboard integration is a key proof point in operator sales — "your control centre gets fleet-wide occupancy in the same screen you already use"
- ✅ **Goal 2 (ÖBB Staff Effectiveness):** Claudia's improved decision quality is the landside component of the effectiveness story alongside Conrad's onboard improvements
