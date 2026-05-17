# Page Spec — Conductor App: Unattended Item Alert

**Scenario:** 02d — Conrad Investigates an Unattended Bag
**Interface:** Conductor App (handheld)
**State:** Alert Active — Unattended Item Detected
**Base state:** Unified Alert Feed (Normal) — documented in `2026-05-14-oebb-ux-design-v2.md § Interface 1`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects a stationary unattended item (bag, luggage, parcel) in a vestibule or seat area after surrounding passengers have moved away — and the item remains stationary beyond a configurable timer threshold — the Conductor App surfaces an **Unattended Item** alert.

This alert is distinct from occupancy and congestion alerts in both visual treatment and tone: it is a **review required** signal, not an immediate action imperative. Conrad needs to assess the situation before deciding what to do. The alert gives him the information to make that assessment — including a camera still-frame captured at the moment of detection — before he leaves his position.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  NORMAL              │────▶│  UNATTENDED ITEM     │────▶│  RESOLVED            │
│  (en-route)          │     │  ALERT ACTIVE        │     │  (Conrad closes)     │
│                      │     │                      │     │                      │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                        │
                                        ▼ (Conrad taps Escalate)
                             ┌──────────────────────┐
                             │  ESCALATED TO        │
                             │  CLAUDIA             │
                             │  (spec 03)           │
                             └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | App launch / prior alert resolved | Hailo-8 unattended item detection + timer threshold elapsed |
| **Unattended Item Alert Active** | Detection + configurable timer expired | Conrad resolves (owner identified / false positive) or escalates |
| Resolved | Conrad selects resolution action | Alert removed from feed; logged |
| Escalated | Conrad taps escalate | Standard escalation flow to Claudia |

---

## State 1 (Baseline): Normal Alert Feed

> Documented in `2026-05-14-oebb-ux-design-v2.md § Interface 1`. Not repeated here.

Key elements from baseline relevant to this state:
- `ca-alert-banner` — Active alert banner (highest priority, pulsing)
- `ca-alert-feed` — Unified alert feed
- `ca-coach-diagram` — Coach occupancy bar

---

## State 2: Unattended Item Alert Active — Differences from Normal

> **The Story:** Conrad is in the conductor area, mid-journey, filling in a delay form. His handheld emits a low two-tone chime — measured, not urgent. He glances at the banner: "Unattended item — Coach 6 vestibule. Stationary 7 min." It's a review alert, not a fire alarm. He taps it. A still-frame loads in three seconds: a dark backpack, floor of the vestibule, no one around it. Area empty for 7 minutes. He reads the context. It looks like a forgotten bag. He taps "PA — owner request." His phone pre-fills the message. He sends it and starts walking.

### Alert Banner — `ca-alert-banner` (unattended item variant)

| Element | Standard alert | Unattended item alert |
|---------|---------------|----------------------|
| Background colour | `--color-warning-amber` | `--color-review` (steel blue — distinct from amber/red safety-critical and blue-teal accessibility) |
| Icon | Category-specific | Bag/luggage icon |
| Title | Alert type | "Unattended item" |
| Sub-detail | Coach + duration | "Coach 6 vestibule · Stationary [N] min · Area empty" |
| Pulsing animation | Yes (urgent) | No — slow fade-in/out (0.8s cycle) communicating "review required," not "act now" |
| Tap action | Alert detail | Navigates to `ca-unattended-item-detail` panel |

### Notification

- **Push notification tone:** Low measured two-note chime (distinct from: occupancy amber single tone, accessibility two-note soft chime, safety-critical continuous pulse)
- **Notification text:** "Unattended item — Coach 6 vestibule. Stationary 7 min. Tap to review."
- **Vibration:** Single long pulse (1s) — deliberate, not urgent

### New Element: `ca-unattended-item-feed-item`

**OBJECT ID:** `ca-unattended-item-feed-item`
**Type:** Alert feed item in `ca-alert-feed`
**Appearance:** Bag icon · `--color-review` left border · "Unattended item — Coach 6 vestibule · [N] min stationary" · timestamp
**Behaviour:** Timer in sub-detail counts up in real time (increments each minute). If Conrad has not responded within 10 minutes of alert fire, the border colour shifts to `--color-warning-amber` and the sub-detail gains "(Unreviewed)" suffix — passive escalation pressure without a new notification.

---

## Interaction Rules

1. The alert fires once per detection event per item. If the same item is detected again after a brief occlusion, the existing alert updates its timer — no duplicate alert.
2. The configurable timer threshold (default: 5 min vestibule, configurable per operator and zone type) is applied before the alert fires. The timer shown in the alert UI counts from detection time, not from alert-fire time — Conrad sees total stationary duration.
3. If Conrad does not respond within 10 minutes, the feed item border escalates to amber (visual-only escalation). No new push notification is sent — push fatigue is a documented Conrad concern.
4. The alert cannot be swiped away or dismissed from the feed without a resolution action — Conrad must tap and make an explicit choice.
5. If a second unattended item alert fires while one is active, it enters the alert feed as a separate item — both remain independently actionable.

---

## Design Rationale

**Why `--color-review` (steel blue) rather than amber?**
Amber in this system means "act now." An unattended bag is "review and decide." The colour carries semantic meaning that shapes Conrad's physiological response — amber creates urgency, steel blue creates attention without alarm. This distinction matters most in this scenario: Conrad should approach with calm professionalism, not adrenaline.

**Why a slow fade animation rather than pulsing?**
Pulsing on the alert banner is reserved for situations requiring immediate physical action (safety-critical amber/red). A slow fade-in/out communicates "this needs your attention soon" — the same message as the colour. Consistent animation-to-urgency mapping means Conrad can read urgency before he reads the text.

**Why does the in-feed timer count from detection, not from alert fire?**
Conrad needs to know how long the item has actually been stationary — the total duration. The configurable timer means there's a gap between detection and alert fire (e.g. 5 minutes). If the alert shows "0 min" when Conrad sees it, he has no sense of how stale the situation is. Showing "7 min" (5 min pre-alert + 2 min since alert) gives him accurate context for triage.

---

## Accessibility (App UI)

- `ca-unattended-item-feed-item` timer updates do not trigger screen reader announcements (they are non-critical live region updates) — use `aria-live="off"` on the timer element
- `--color-review` (steel blue) and `--color-warning-amber` (escalated) must meet WCAG AA contrast against the feed item background
- All tap targets minimum 44px

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Alert colour | `--color-review` (steel blue) — distinct from amber/red and accessibility blue-teal |
| Alert animation | Slow fade-in/out — not pulsing; communicates "review required" not "act now" |
| Timer shown | Counts from detection time (not alert-fire time) — shows total stationary duration |
| Passive escalation | Border shifts to amber at 10 min unreviewed; no re-notification (push fatigue concern) |
| Dismiss without action | Not permitted — Conrad must make an explicit resolution choice |
| Duplicate detection | Timer updates on existing alert — no duplicate alert for same item |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Is `--color-review` (steel blue) in the existing design token set? Needs to be added if not — distinct from `--color-accessibility` blue-teal. | Design system |
| 2 | What is the configurable timer range? Confirm min/max values and whether vestibule vs seat area timers are separately configurable in operator settings. | Nomad Digital product |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-unattended-item-detail.md` | Detail panel — still-frame, context, PA and escalation actions |
| `03-control-centre-unattended-item-escalation.md` | Claudia's view when Conrad escalates |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | Base Conductor App spec |
| `2026-05-14-oebb-ux-design-v2.md § Escalate flow` | Standard escalation form used when Conrad escalates |
