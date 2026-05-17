# Page Spec — Conductor App: Accessibility Alert State

**Scenario:** 06 — Passenger with Pushchair Finds Accessible Space
**Interface:** Conductor App (handheld)
**State:** Alert Detail — Accessibility Need Detected
**Base state:** Unified Alert Feed (Normal) — documented in `2026-05-14-oebb-ux-design-v2.md § Interface 1`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects a pushchair or wheelchair in the vestibule or doorway of the accessible coach, the Conductor App surfaces an **Accessibility Need** alert. This is an informational alert — Conrad's role is to be present and offer assistance. The ramp deploys automatically via TCMS. The alert auto-resolves when the train departs the station.

Conrad does not need to take any mechanical action. He needs to know: which coach, which door, and what the passenger needs.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  NORMAL (en-route /  │────▶│  ACCESSIBILITY ALERT │────▶│  NORMAL (en-route)   │
│  station approach)   │     │  ACTIVE              │     │  (post-departure)    │
│                      │     │  (Hailo-8 detection  │     │                      │
└──────────────────────┘     │   → train departure) │     └──────────────────────┘
                             └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | App launch / post-departure | Hailo-8 detects pushchair or wheelchair in accessible coach vestibule/doorway |
| **Accessibility Alert Active** | Hailo-8 detection event (confidence ≥ threshold) | Train departure signal from TCMS |
| Normal (post-departure) | TCMS departure signal | — |

---

## State 1 (Baseline): Normal Alert Feed

> Documented in `2026-05-14-oebb-ux-design-v2.md § Interface 1`. Not repeated here.

Key elements from baseline relevant to this state:
- `ca-alert-banner` — Active alert banner (highest priority, pulsing)
- `ca-alert-feed` — Unified alert feed (both AI services, prioritised by severity)
- `ca-coach-diagram` — Coach occupancy bar (all coaches, green/amber/red)

---

## State 2: Accessibility Alert Active — Differences from Normal

> **The Story:** Conrad is on the platform at Vienna Hbf. His handheld chimes — a different tone from the occupancy alerts, a softer two-note signal. The screen shows: "Accessibility need — Coach 2, Door 1. Passenger with pushchair detected. Ramp deploying automatically." He doesn't need to do anything to the ramp. He just needs to be at coach 2, door 1, to make sure boarding goes smoothly. He pockets the phone and walks.

| Property | Value |
|----------|-------|
| Purpose | Inform Conrad that a passenger with an accessibility need is boarding; direct him to the correct coach and door |
| Trigger | Hailo-8 pushchair/wheelchair detection event, confidence ≥ configured threshold |
| Duration | Until TCMS departure signal (train leaves station) |
| Conrad's action | Walk to the indicated coach and door; be present |

### Alert Banner — `ca-alert-banner` (modified)

The accessibility alert takes the `ca-alert-banner` position at the top of the home screen with the following differences from a standard alert:

| Element | Standard alert | Accessibility alert |
|---------|---------------|-------------------|
| Background colour | `--color-warning-amber` | `--color-accessibility` (blue-teal — distinct from safety-critical amber/red) |
| Icon | Category-specific (luggage, door, etc.) | Wheelchair icon |
| Title | Alert type | "Accessibility need" |
| Sub-detail | Coach + duration | Coach + door + "Ramp deploying automatically" |
| Pulsing animation | Yes (urgent) | No (informational — steady, not urgent) |
| Tap action | Navigates to alert detail | Navigates to `ca-accessibility-alert-detail` panel |

### New Element: `ca-accessibility-alert-detail`

**OBJECT ID:** `ca-accessibility-alert-detail`
**Type:** Full-screen detail panel (replaces home screen on tap)
**Entry:** Tap on `ca-alert-banner` (accessibility variant)

| Section | Content |
|---------|---------|
| Header | "Accessibility need — Coach 2, Door 1" |
| Detection badge | "Detected by onboard camera" · Hailo-8 confidence indicator (e.g. "High confidence") |
| Ramp status | "Ramp deploying automatically" — with animated status indicator: Requested → Deploying → Ready |
| HAFAS context | "1 PRM reservation at this stop" (if HAFAS data available for this stop; omitted if no reservation data) |
| Accessible space status | "Accessible space available" (green pill) or "Accessible space occupied" (red pill — see Spec 02) |
| Map strip | Simplified coach diagram highlighting coach 2, door 1 in `--color-accessibility`; all other coaches greyed |
| Dismiss | Not available — alert persists until departure |
| Auto-resolve notice | "This alert will clear automatically when the train departs" (shown as footer note) |

### New Element: `ca-accessibility-alert-feed-item`

**OBJECT ID:** `ca-accessibility-alert-feed-item`
**Type:** Alert feed item (in `ca-alert-feed`)
**Appearance:** Wheelchair icon · "Accessibility need — Coach 2, Door 1" · `--color-accessibility` left border · timestamp

The feed item persists in the alert feed alongside the banner for the duration of the dwell. It does not have an independent dismiss control.

### Notification

- **Push notification tone:** Distinct two-note soft chime (different from occupancy/safety alert tones)
- **Notification text:** "Accessibility need — Coach 2, Door 1. Ramp deploying automatically."
- **Vibration:** Single pulse (not repeated — informational, not urgent)

---

## Interaction Rules

1. The alert fires once per detection event. If the same passenger re-enters the field of view after briefly leaving, no duplicate alert is sent.
2. If Hailo-8 detects a second distinct accessible passenger at the same stop, a second alert fires referencing the same coach/door (deduplication at the coach level — not passenger level).
3. Conrad cannot dismiss this alert manually. It auto-resolves on departure. This prevents accidental dismissal of a live accessibility need.
4. Tapping anywhere on the `ca-alert-banner` opens `ca-accessibility-alert-detail`. Back navigation returns to the home screen with the banner still present.
5. The ramp status indicator in `ca-accessibility-alert-detail` reflects live TCMS state — it is not a Conrad-controlled action.

---

## Design Rationale

**Why `--color-accessibility` (blue-teal) rather than amber?**
Amber and red signal "action required immediately." This alert is informational and pastoral — Conrad should walk calmly, not sprint. A distinct colour communicates the difference in urgency. Blue-teal has no pre-existing meaning in the alert system and is available for this role.

**Why no manual dismiss?**
An accessible passenger is on or approaching the train. If Conrad accidentally dismisses the alert, he loses the coach/door reference and may not be present when needed. Persistence until departure protects against this at the cost of minor friction — acceptable given the stakes.

**Why "Ramp deploying automatically" in the banner sub-detail?**
Conrad's prior mental model is that ramps are his responsibility. The banner must immediately correct this assumption before he starts looking for a ramp control in the app. Surfacing it in the sub-detail — the first thing he reads after the title — prevents a confused search.

**Why show HAFAS PRM reservation count as context only?**
The reservation count tells Conrad whether this detection is expected (1 reservation = expected) or unexpected (0 reservations = walk-up passenger). It doesn't change his action but helps him calibrate his mental model. It is shown as context, not as a trigger, so it never appears as "the system is guessing" — Hailo-8 detection is always the authoritative trigger.

---

## Accessibility (App UI)

- `ca-accessibility-alert-detail` header uses minimum 20sp font (legible at arm's length on platform)
- Coach diagram map strip: accessible coach highlighted with both colour (`--color-accessibility`) and a distinct border pattern — not colour alone
- Ramp status indicator includes text label alongside animation (not animation-only)
- All tap targets within `ca-accessibility-alert-detail` meet 44px minimum touch target

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Trigger source | Hailo-8 vestibule/doorway detection (primary). HAFAS PRM reservation shown as context only — not the trigger. |
| Ramp deployment | Automatic via TCMS. Conrad is not involved in deployment. |
| Conrad's role | Presence and pastoral assistance only. No mechanical action required. |
| Alert colour | `--color-accessibility` (blue-teal) — distinct from amber/red safety-critical colours. |
| Alert close | Auto-resolves on TCMS departure signal. Conrad cannot manually dismiss. |
| Duplicate detection | Deduplication at coach level — one alert per coach per stop regardless of passenger count detected. |
| HAFAS context | Shown if available; omitted gracefully if no PRM reservation data for this stop. |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the Hailo-8 confidence threshold for pushchair/wheelchair detection that triggers the alert? Needs confirmation from ML team to avoid false positives (bags in pushchair-like configurations). | Nomad Digital ML team |
| 2 | TCMS ramp deployment signal latency — how quickly after detection does "Ramp deploying" reflect in the status indicator? | Systems integration |
| 3 | Is `--color-accessibility` (blue-teal) available in the existing design token set, or does it need to be added? | Design system |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-space-occupied-path.md` | Variant: accessible space already occupied when passenger detected |
| `03-passenger-portal-pre-boarding-states.md` | Passenger-facing view of the same detection event |
| `05-passenger-portal-ramp-confirmed-state.md` | Portal state shown once ramp is confirmed ready |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | Base Conductor App spec |
