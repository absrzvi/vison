# Page Spec — Conductor App: Accessibility Alert — Space Occupied Variant

**Scenario:** 06 — Passenger with Pushchair Finds Accessible Space
**Interface:** Conductor App (handheld)
**State:** Alert Detail — Accessibility Need Detected, Accessible Space Already Occupied
**Base state:** `01-conductor-app-accessibility-alert.md` — Accessibility Alert Active state
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects a new pushchair or wheelchair at the accessible coach door but the accessible space is already occupied by a prior passenger, Conrad's alert must communicate two things simultaneously:

1. A new passenger with an accessibility need is at the door
2. The accessible space is already taken — Conrad needs to manage the situation actively, not just be present

This variant changes Conrad's role from **pastoral presence** to **active intervention** — he must intercept the incoming passenger before they board into an unavailable space, and redirect them or manage the conflict on the platform.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────────┐     ┌──────────────────────┐
│  NORMAL              │────▶│  ACCESSIBILITY ALERT     │────▶│  NORMAL              │
│                      │     │  ACTIVE — SPACE OCCUPIED │     │  (post-departure)    │
└──────────────────────┘     │  (Hailo-8 detection +    │     └──────────────────────┘
                             │   space occupied signal) │
                             └──────────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | App launch / post-departure | Hailo-8 detects new accessibility need AND accessible space is currently occupied |
| **Alert Active — Space Occupied** | Compound: new detection + occupied space state | TCMS departure signal |
| Normal (post-departure) | TCMS departure signal | — |

---

## State 1 (Baseline): Accessibility Alert Active — Space Available

> Documented in `01-conductor-app-accessibility-alert.md`. The space occupied variant is a modification of that state. All elements not listed below remain as specified in Spec 01.

---

## State 2: Accessibility Alert — Space Occupied — Differences from Spec 01

> **The Story:** Conrad's handheld chimes. He reads: "Accessibility need — Coach 2, Door 1. Space occupied." His stomach drops slightly — he knows this means he needs to get there fast, before the incoming passenger tries to board and finds no space. He needs to meet them on the platform, explain, and either find an alternative or help them wait for the next service. This is the conversation he least enjoys, but the system has given him the context to handle it professionally rather than being ambushed.

| Property | Value |
|----------|-------|
| Purpose | Alert Conrad to an incoming accessibility need where the space is unavailable; prompt active platform intervention |
| Trigger | Hailo-8 detection of new pushchair/wheelchair + accessible space currently occupied (Hailo-8 inferred occupancy of accessible space) |
| Duration | Until TCMS departure signal |
| Conrad's action | Intercept the incoming passenger on the platform before boarding; manage redirect or assist |

### Alert Banner — `ca-alert-banner` (space occupied variant)

| Element | Space available (Spec 01) | Space occupied (this spec) |
|---------|--------------------------|---------------------------|
| Background colour | `--color-accessibility` (blue-teal) | `--color-warning-amber` (amber — active intervention required) |
| Icon | Wheelchair icon | Wheelchair icon + warning badge overlay |
| Title | "Accessibility need" | "Accessibility need — Space occupied" |
| Sub-detail | "Coach 2, Door 1 · Ramp deploying automatically" | "Coach 2, Door 1 · Space taken — passenger intervention required" |
| Pulsing animation | No (steady — informational) | Yes (pulsing — active intervention needed) |

The escalation to amber with pulsing is deliberate: this is no longer a pastoral situation. Conrad must act quickly to prevent a platform confrontation or an unsafe boarding attempt.

### `ca-accessibility-alert-detail` — Space Occupied Differences

**OBJECT ID:** `ca-accessibility-alert-detail` (same ID, occupied state)

| Section | Space available | Space occupied |
|---------|----------------|---------------|
| Ramp status | "Ramp deploying automatically" with status animation | "Ramp deploying automatically" (same — ramp still deploys; Conrad still manages on the platform) |
| Accessible space status | "Accessible space available" (green pill) | "Accessible space occupied" (red pill) |
| Occupancy context | Not shown | "1 wheelchair/mobility aid currently in accessible space — Coach 2" |
| Guidance strip | Not shown | "Meet passenger on platform before boarding. Suggest alternatives below." |
| Alternative options panel | Not shown | See `ca-accessibility-alternatives-panel` below |
| HAFAS context | "1 PRM reservation at this stop" (if available) | "1 PRM reservation at this stop" (if available) — same |

### New Element: `ca-accessibility-alternatives-panel`

**OBJECT ID:** `ca-accessibility-alternatives-panel`
**Type:** Collapsible panel within `ca-accessibility-alert-detail`
**Purpose:** Give Conrad options to offer the incoming passenger

| Option | Condition | Display |
|--------|-----------|---------|
| Next train | Always shown | "Next [route] service: [time] — platform [X]" (from HAFAS) |
| Alternative accessible coach | Only if another coach has accessible space | "Coach [X] has accessible space — Door [Y]" |
| No alternative | If no other accessible space on this train | "No alternative accessible space on this train" — shown in muted text |

Conrad does not tap these options to trigger any system action. They are reference information to inform his platform conversation. The panel is display-only.

### Notification (Space Occupied Variant)

- **Push notification tone:** Same two-note accessibility chime + single additional alert pulse (to distinguish from space-available variant)
- **Notification text:** "Accessibility need — Coach 2, Door 1. Space occupied — intervention required."
- **Vibration:** Double pulse (distinguishes from single-pulse space-available variant)

---

## Interaction Rules

1. If the space is occupied when the alert fires, the alert opens directly to the occupied variant. Conrad is not shown the space-available state first.
2. If the space becomes available after the alert fires (e.g. the occupying passenger moves or alights) — the alert updates in place: the red "Space occupied" pill becomes green "Space available," the amber banner returns to `--color-accessibility`, and the alternatives panel collapses. No new notification is sent.
3. The `ca-accessibility-alternatives-panel` is collapsed by default. Conrad taps to expand. It does not auto-expand — Conrad is likely already moving toward the door when the alert fires.
4. All other interaction rules from Spec 01 apply (no manual dismiss, tap banner → detail, auto-resolve on departure).

---

## Design Rationale

**Why amber + pulsing for the occupied variant, not a separate red alert?**
Red is reserved for safety-critical situations (fire, fall, door obstruction at speed). This situation is operationally serious but not a safety emergency. Amber communicates "this needs your active attention now" without triggering the same alarm response as a safety-critical event. Pulsing distinguishes it from the steady space-available alert.

**Why show alternatives in the alert detail rather than as a separate action?**
Conrad needs to have the platform conversation immediately. He cannot take time to navigate to another screen or query HAFAS manually while standing with a passenger who is about to miss their train. Pre-loading the alternatives in the detail panel means the information is ready when he arrives, not when he searches.

**Why does the ramp still deploy in the occupied variant?**
The ramp is automatic — it deploys on detection regardless of space availability. This is correct: the passenger may still board (if the occupying passenger is willing to move a bag or the space is partially obstructed rather than truly occupied), and Conrad can assess on the ground. The system should not try to prevent ramp deployment based on an AI inference about occupancy.

**Why no escalation to Claudia from this alert?**
Accessible space conflicts are Conrad's domain — he has the authority and the context to resolve them on the platform. Escalating to Claudia would add latency without adding capability. The only escalation path is if Conrad chooses to raise an operational escalation manually (e.g., if the passenger becomes distressed or the situation requires station staff involvement) — using the standard escalation flow documented in `2026-05-14-oebb-ux-design-v2.md § Escalate flow`.

---

## Accessibility (App UI)

- All accessibility requirements from Spec 01 apply
- `ca-accessibility-alternatives-panel` uses minimum 18sp font — Conrad reads this while moving
- Alternative options must be legible in direct sunlight (platform environment) — `--color-background-elevated` panel with strong contrast

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Alert urgency | Amber + pulsing (active intervention) vs blue-teal steady (pastoral presence) |
| Ramp behaviour | Still deploys automatically — space occupancy does not suppress ramp deployment |
| Alternatives panel | Display-only reference; Conrad's conversation tool, not a system action trigger |
| Escalation | Not automatic; Conrad uses standard manual escalation flow if needed |
| State update | Alert updates in-place if space status changes during the dwell — no re-notification |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | How does Hailo-8 distinguish "wheelchair user occupying the accessible space" from "pushchair parked in the accessible space while owner sits nearby"? The occupied state must be robust against false positives here. | Nomad Digital ML team |
| 2 | What is the source of "Next [route] service: [time]" in the alternatives panel? HAFAS real-time feed assumed — confirm availability and latency. | Systems integration |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-accessibility-alert.md` | Base state — space available variant |
| `03-passenger-portal-pre-boarding-states.md` | Passenger-facing view — includes occupied state shown to incoming passenger |
| `2026-05-14-oebb-ux-design-v2.md § Escalate flow` | Manual escalation path Conrad can invoke if needed |
