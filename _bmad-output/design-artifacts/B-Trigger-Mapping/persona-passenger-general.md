# Persona — Passenger (General Traveller)

**Agent:** Saga (WDS Analyst)
**Phase:** 2 — Trigger Mapping
**Date:** 2026-05-14
**Status:** Complete

---

## Identity

**Name:** Petra
**Role:** General rail passenger — unreserved or reserved seat, travelling with hand luggage
**Frequency:** Regular to occasional ÖBB traveller
**Device:** Smartphone (iOS or Android)
**Language:** German primary

### Representative situations
- Commuter on a busy Friday evening Railjet (Wien → Salzburg)
- Tourist joining a regional train mid-journey with a rolling suitcase
- Day-tripper boarding at a busy intermediate stop with no seat reservation

---

## Mental State at the Moment of Portal Contact

Petra connects to the WiFi either:
- **On the platform**, before boarding — phone auto-connects, CNA popup appears
- **Just after boarding**, before sitting down — walking the vestibule, phone connects

### Emotional state
- **Mild anxiety** — the train is in front of her, she has 90 seconds to board, she doesn't know where to go
- **Low trust in her own judgment** — she can see one door has a crowd but doesn't know if that's representative
- **Aversion to effort** — she does not want to walk the length of a 10-coach train with a suitcase

### What she is hoping for
- To find a seat without walking far
- To stow her luggage without fighting for overhead rack space
- To avoid standing for a long journey
- To board confidently without asking anyone

### What she fears
- Boarding the wrong coach and being stuck standing
- Having to push through packed coaches with luggage after departure
- Missing the departure while looking for a seat

---

## Driving Forces

Scored 1–15 (15 = maximum importance to this persona).

| # | Force | Score | Notes |
|---|---|---|---|
| 1 | Know where space is available before committing to a door | 15 | Highest anxiety moment — wrong door = standing for 2 hours |
| 2 | Get guidance without asking staff or other passengers | 14 | Self-service preference; staff not always visible on platform |
| 3 | Act in the 60–90 second boarding window | 14 | Guidance must be instant and readable at a glance |
| 4 | Confirm the guidance matches reality (trust) | 13 | If the portal says "plenty of space" but she sees a crowd, she'll ignore it next time |
| 5 | Know which direction to walk on the platform | 12 | Critical when recommended coach is far from current position |
| 6 | Not be overwhelmed with information | 11 | CNA popup context — she wants one clear action, not a dashboard |
| 7 | Understand luggage rack availability | 9 | Secondary to seat availability but relevant with large luggage |
| 8 | Language accessibility (German) | 9 | Portal in German; tourist variant needs English fallback (future) |

---

## Trigger Map

### Primary trigger
> "The train is in front of me and I don't know which door to use."

This is the moment the CNA portal appears. Petra has 60–90 seconds. She is not going to read — she will scan.

### Trigger chain
```
Train arrives at platform
    → Petra's phone auto-connects to Railnet WiFi
    → CNA popup appears (OS-native, no app needed)
    → Portal loads instantly (served locally from R5001C)
    → Entertainment promo visible at top (existing)
    → [NEW] Coach load panel visible below promo
    → Petra scans the train diagram in under 3 seconds
    → Decision: walk to recommended coach OR confirm current position is fine
    → Boards confidently
    → Portal dismissed / WiFi connected
```

### Failure modes (triggers that lead to bad outcomes)
| Failure | Cause | Design mitigation |
|---|---|---|
| Petra ignores the panel | Too much text, too small, buried below promo | Coach diagram must be visually dominant; load colours immediately readable |
| Petra follows guidance and finds it wrong | Data stale (>60s old) | Show data freshness timestamp; refresh on portal open |
| Petra can't tell which direction to walk | No directional indicator | Show arrow when one coach is clearly best; omit when load is even |
| Petra boards before portal loads | Slow portal render | Portal must load in <1s (all data served locally) |

---

## Use Cases

### UC-P01 — Glance and go (evenly distributed load)
**Trigger:** Train is moderately occupied across all coaches
**Portal state:** Coach diagram shows mixed green/amber — no single best option
**Behaviour:** Portal shows load colours only, no directional recommendation
**Outcome:** Petra boards nearest door, confident there is space
**Success:** Boarded without anxiety in under 30 seconds

### UC-P02 — Directed to a specific coach (clear best option)
**Trigger:** Coaches 1–3 are red/amber, coaches 5–8 are green
**Portal state:** One coach is clearly the least occupied
**Behaviour:** Portal shows "Gehen Sie zu Wagen 6 →" with directional arrow
**Outcome:** Petra walks to coach 6, finds a seat and overhead rack space
**Success:** Boarded correct coach in under 60 seconds without staff assistance

### UC-P03 — Train is full
**Trigger:** All coaches at >85% occupancy
**Portal state:** All coaches amber/red
**Behaviour:** Portal shows "Zug stark besetzt — Wagen 3 am wenigsten voll" (least-worst option)
**Outcome:** Petra knows in advance the train is full; she boards near the least-crowded coach
**Success:** Informed expectation; no false promise of empty space

### UC-P04 — Already aboard, checking load mid-journey
**Trigger:** Petra boards before connecting to WiFi; connects mid-journey
**Portal state:** Same coach diagram, now showing current journey load
**Behaviour:** Panel shows current load; guidance shifts to "move to a quieter coach" if applicable
**Outcome:** Petra can reposition before the next busy stop if she wishes
**Success:** Guidance remains useful post-boarding, not just at platform

### UC-P05 — Luggage rack signal
**Trigger:** Hailo detects high luggage density in vestibule of recommended coach
**Portal state:** Coach diagram shows luggage icon overlay on affected coaches
**Behaviour:** Guidance steers to a coach with available rack space
**Outcome:** Petra stows luggage without conflict
**Success:** Luggage rack stress avoided; correlates with existing Hailo luggage density detection
