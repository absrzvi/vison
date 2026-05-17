# Persona — Passenger (Accessibility Need)

**Agent:** Saga (WDS Analyst)
**Phase:** 2 — Trigger Mapping
**Date:** 2026-05-14
**Status:** Complete

---

## Identity

**Name:** Hanna
**Role:** Passenger with mobility aid — wheelchair user or pushchair/pram user
**Frequency:** Regular ÖBB traveller who has navigated accessible boarding before
**Device:** Smartphone (iOS or Android)
**Language:** German primary

### Representative situations
- Parent with pushchair and toddler boarding at Wien Hbf
- Wheelchair user travelling independently on a Railjet intercity service
- Passenger with walking frame who needs the PRM door and ramp

---

## Mental State at the Moment of Portal Contact

Hanna is more stressed than Petra at the moment of boarding. She has done this before and knows what can go wrong.

### Emotional state
- **Heightened anxiety** — the accessible space may already be taken; the ramp may not be deployed; she may arrive at the wrong door
- **Past negative experience** — she has been caught at the wrong door before, or arrived to find the accessible space full
- **Planning-oriented** — she wants to confirm information *before* committing to a position on the platform
- **Time pressure** — deploying a ramp takes 30–60 seconds; she needs to be at the right door early

### What she is hoping for
- Confirmation that accessible space is available before she commits to that coach
- To know exactly which door the ramp will be at
- That staff (Conrad) will be ready at the door — she should not have to shout across the platform
- To board in one confident move, not in stages

### What she fears
- Arriving at the PRM door to find the accessible space is already occupied by another wheelchair
- The ramp not being deployed when she arrives
- Being stranded at the wrong door as the departure time approaches
- Staff not knowing she is coming

---

## Driving Forces

| # | Force | Score | Notes |
|---|---|---|---|
| 1 | Confirm accessible space is available before walking to that door | 15 | If space is taken, she needs to know now — not after walking 60m |
| 2 | Know exactly which door and which platform position | 15 | PRM door location is not always obvious from the platform |
| 3 | Know staff will be ready at the door | 14 | Ramp deployment requires conductor; she cannot deploy it herself |
| 4 | Persistent status — space availability throughout journey | 13 | She needs to know the space is still available when she re-checks |
| 5 | Clear negative state — "space not available" must be unambiguous | 13 | False positive (showing space available when it is taken) is the worst failure mode |
| 6 | Alert Conrad proactively — she should not have to flag herself | 12 | System should trigger Conrad alert when she opens the portal accessibility view |
| 7 | Language accessibility | 9 | German primary; clear icons reduce language dependency |

---

## Trigger Map

### Primary trigger
> "I need to board through the PRM door but I don't know if the accessible space is free or if the ramp will be ready."

### Trigger chain
```
Hanna approaches the platform with pushchair/wheelchair
    → Phone auto-connects to Railnet WiFi
    → CNA popup appears
    → Entertainment promo visible at top
    → [NEW] Coach load panel visible below — includes accessibility indicator
    → Hanna sees wheelchair/pushchair icon on accessible coach
    → Status: "Rollstuhlplatz frei — Wagen 2, Tür 1"
         OR: "Rollstuhlplatz belegt"
    → [BACKGROUND] Portal opening with accessibility coach selected triggers Conrad alert:
      "Fahrgast mit Rollstuhl/Kinderwagen nähert sich — Wagen 2, Tür 1"
    → Conrad walks to coach 2, door 1, deploys ramp
    → Hanna arrives at door 1 — Conrad is ready, ramp deployed
    → Boards in under 30 seconds
```

### Failure modes
| Failure | Cause | Design mitigation |
|---|---|---|
| Space shown as free but actually occupied | Hailo detection lag | Confidence indicator on accessibility status; refresh on portal open |
| Conrad not alerted | Portal accessibility view not triggered | Alert fires on CNA portal load when accessibility coach is displayed, not on explicit tap |
| Hanna goes to wrong door | Portal shows coach number but not door number | Always show both coach AND door number for accessibility guidance |
| Ramp not deployed | Conrad alert not received or dismissed | Conrad app escalation path if no acknowledgement within 2 min |
| Status not updated after boarding | Accessibility state only shown pre-boarding | Status persists on portal throughout journey — useful if she needs to move |

---

## Use Cases

### UC-A01 — Accessible space available, smooth boarding
**Trigger:** Hanna opens portal; Hailo confirms accessible space free in coach 2
**Portal state:** Accessibility panel shows "Rollstuhlplatz frei — Wagen 2, Tür 1 — Rampe wird vorbereitet"
**Background:** Conrad alert fires immediately on portal load
**Outcome:** Hanna walks to coach 2, door 1. Ramp is ready. Boards in under 30 seconds.
**Success:** Zero friction accessible boarding; Conrad proactively positioned

### UC-A02 — Accessible space occupied
**Trigger:** Hailo detects existing wheelchair/pushchair in accessible space
**Portal state:** "Rollstuhlplatz belegt — Bitte Schaffner kontaktieren"
**Behaviour:** Portal does not direct Hanna to the door; directs to find Conrad instead
**Outcome:** Hanna knows before committing to walk to that coach; has time to speak to staff
**Success:** No wasted journey to a full accessible space; informed expectation set early

### UC-A03 — Multiple accessible coaches (longer train)
**Trigger:** Train has two accessible coaches (e.g. coach 2 and coach 7)
**Portal state:** Both coaches shown with wheelchair icon; space status on each
**Behaviour:** Portal recommends nearest available accessible space to Hanna's current platform position
**Outcome:** Hanna chooses the most convenient accessible coach
**Success:** Correct coach selected without ambiguity

### UC-A04 — Pre-boarding alert to Conrad (automatic)
**Trigger:** CNA portal loaded; accessible coach displayed to Hanna
**No explicit action required from Hanna**
**Behaviour:** System fires Conrad alert: "Fahrgast mit Rollstuhl/Kinderwagen erkannt nähert sich Bahnsteig — Wagen [N], Tür [N]"
**Outcome:** Conrad positioned at door before Hanna arrives
**Success:** Conrad does not need to be summoned; system acts proactively

### UC-A05 — Ramp deployment confirmation loop
**Trigger:** Conrad deploys ramp and confirms in conductor app
**Portal state:** Updates to "Rampe bereit — Wagen 2, Tür 1"
**Outcome:** Hanna sees live confirmation that ramp is ready before she reaches the door
**Success:** Closed-loop confirmation; Hanna boards with full confidence
