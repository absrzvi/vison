# Page Spec — Passenger Portal: Ramp Confirmed State

**Scenario:** 06 — Passenger with Pushchair Finds Accessible Space
**Interface:** Passenger Portal (CNA — ÖBB Railnet, served from R5001C)
**State:** Pre-Boarding — Ramp Confirmed (TCMS ramp-ready signal received)
**Base state:** `pp-accessibility-panel` — Pre-Boarding Space Available state (`03-passenger-portal-pre-boarding-states.md § State A`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Once the automatic ramp deployment is confirmed by TCMS (ramp physically deployed and locked in position), the passenger portal must update the accessibility panel from "Ramp preparing …" to "Ramp ready." This is the moment Hanna needs to commit to the door — she walks with confidence, not with a question mark.

This state is transitional: it exists between the space-available pre-boarding state and post-departure Journey Mode. Its job is to remove the final uncertainty before the passenger physically arrives at the door.

---

## State Flow Overview

```
┌──────────────────────────┐     ┌──────────────────────────┐     ┌──────────────────────┐
│  PRE-BOARDING            │────▶│  RAMP CONFIRMED          │────▶│  JOURNEY MODE        │
│  Space available         │     │  (TCMS ramp-ready        │     │  + Accessibility     │
│  "Rampe wird             │     │   signal received)       │     │  Strip (spec 04)     │
│   vorbereitet …"         │     │  "✓ Rampe bereit"        │     │                      │
└──────────────────────────┘     └──────────────────────────┘     └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Pre-boarding — space available | Passenger self-identification | TCMS ramp-ready signal |
| **Ramp Confirmed** | TCMS ramp-ready signal | TCMS departure signal |
| Journey Mode | TCMS departure signal | End of journey |

---

## State: Ramp Confirmed — Differences from Pre-Boarding Space Available

> **The Story:** Hanna is walking toward coach 2. Her phone shows "Rampe wird vorbereitet …" in italic. She's 15 metres from the door. The text shifts: "✓ Rampe bereit." The panel border pulses green for a moment. She picks up her pace. She arrives at the door and the ramp is there, exactly as promised. Conrad is standing beside it.

This state is a targeted update to `pp-accessibility-panel`. All elements not listed below remain as specified in `03-passenger-portal-pre-boarding-states.md § State A`.

### Changes from Pre-Boarding State A

| Element | Pre-Boarding — Space Available | Ramp Confirmed |
|---------|-------------------------------|---------------|
| Ramp status line (DE) | "Rampe wird vorbereitet …" · italic · `--text-tertiary` | "✓ Rampe bereit" · normal weight · `--sev-normal` green |
| Ramp status line (EN) | "Ramp preparing …" · italic · `--text-tertiary` | "✓ Ramp ready" · normal weight · `--sev-normal` green |
| Panel border colour | `rgba(74,158,255,0.25)` (blue) | `rgba(34,197,94,0.35)` (green) |
| Panel background | `rgba(74,158,255,0.08)` (blue tint) | `rgba(34,197,94,0.08)` (green tint) |
| Entry animation | None | Single pulse: panel border brightens to full green (`rgba(34,197,94,1.0)`) for 400ms, then settles to `rgba(34,197,94,0.35)`. Draws attention without startling. |
| `role` attribute on ramp status | `role="status"` (non-interruptive) | `role="alert"` — announces "Rampe bereit" immediately to screen reader |

### No Changes

- Status heading: "Rollstuhlplatz frei" — unchanged (the space remains available)
- Coach and door: "Wagen 2 · Tür 1" — unchanged
- Coach diagram: unchanged (coach 2 still highlighted in `--color-accessibility`)
- Directional arrow: unchanged
- Staff note: "Unser Personal ist informiert." — unchanged

---

## Timing and Latency

| Requirement | Value | Rationale |
|-------------|-------|-----------|
| Portal update latency after TCMS ramp-ready signal | ≤ 15 seconds (within one polling cycle) | 15s polling is the standard portal refresh cycle. A passenger walking from 40 metres away takes ~30s — the update should arrive before she reaches the door in most cases. |
| If latency > 15s | "Rampe wird vorbereitet …" continues to show — no error or stale state displayed | Better to show "preparing" than to show a wrong state. The ramp is deployed regardless of portal display. |
| No intermediate error state | — | Do not show "Ramp deployment failed" or similar — the portal has no ground truth on failure. Failure modes are TCMS alerts to Conrad and operations, not passenger-facing portal states. |

---

## Edge Case: TCMS Signal Not Received

If the TCMS ramp-ready signal is not received before the train departs:
- The portal never transitions to Ramp Confirmed state
- Pre-boarding state A ("Rampe wird vorbereitet …") persists until TCMS departure signal
- On departure, portal transitions directly to Journey Mode + accessibility strip
- The accessibility strip in Journey Mode does not reference the ramp state — it only shows post-boarding information

The passenger in this case has already boarded (or not). The ramp has either deployed or it hasn't — the portal simply never confirmed it. This is acceptable: the confirmation is a convenience for the walking passenger, not a safety-critical gate.

---

## Interaction Rules

1. The ramp confirmed state is a visual-only update. No new tap actions are introduced — all interaction rules from Spec 03 continue to apply.
2. The transition from "preparing" to "confirmed" is one-way during a single dwell. If the ramp is retracted and re-deployed (exceptional operational event), the portal cycles back to "preparing" and then "confirmed" again — matching the TCMS signal sequence.
3. The entry animation (single green pulse) plays once on transition. It does not loop or repeat.

---

## Design Rationale

**Why change the panel colour from blue to green on confirmation?**
Blue in the pre-boarding panel communicates "accessibility — active, ongoing." Green on confirmation communicates "complete — you can proceed." The colour shift is the primary signal that something has changed, supported by the text change. A passenger glancing at their phone while walking receives the "go" signal through colour before reading the text.

**Why `role="alert"` on confirmation but `role="status"` on preparing?**
"Ramp ready" is time-sensitive information that the passenger should know immediately — the screen reader should announce it as soon as the content changes, without waiting for the user to navigate to it. "Preparing" is background context that does not require immediate announcement.

**Why not show a "boarding window" timer?**
A countdown to departure creates pressure and anxiety, particularly for a passenger who is already managing a pushchair on a platform. The Scenario 10 dwell timer is for Conrad's operational use — it does not belong in the passenger portal. The ramp will be deployed for as long as the train is at the platform; Hanna's boarding window is not a UX concern she should manage.

---

## Accessibility (Portal UI)

- All requirements from Spec 03 apply
- `role="alert"` on ramp status ensures immediate screen reader announcement on confirmation — critical for passengers using assistive technology who may not be watching the screen
- Panel colour change (blue → green) accompanied by text change — not colour alone
- Entry animation respects `prefers-reduced-motion` — if reduced motion is preferred, panel transitions instantly without the pulse

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Trigger | TCMS ramp-ready signal (automatic — no Conrad action required) |
| Portal update latency tolerance | ≤ 15s (one polling cycle); show "preparing" if delayed |
| Colour shift | Blue → green on confirmation |
| Screen reader behaviour | `role="alert"` on confirmation — immediate announcement |
| No-signal fallback | Stay in "preparing" until departure; no error state shown |
| Boarding timer | Not shown — passenger-facing anxiety risk, not a useful UX signal |
| Animation | Single green pulse; respects `prefers-reduced-motion` |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Does the TCMS ramp deployment system emit a discrete "ramp ready" signal that the Nomad Digital backend can subscribe to? Or is ramp state polled? Confirm integration point. | Systems integration / Stadler |
| 2 | What is the typical time between ramp deploy command and ramp-ready signal from TCMS? This determines how long "Rampe wird vorbereitet …" shows in practice. | Systems integration / Stadler |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `03-passenger-portal-pre-boarding-states.md` | Prior state — this spec describes the transition from State A of that spec |
| `04-passenger-portal-journey-state.md` | Next state — post-departure journey mode |
| `01-conductor-app-accessibility-alert.md` | Conrad's concurrent view — informs that ramp is automatic, Conrad is pastoral |
| `E-Passenger-Portal/passenger-portal-ux-design.md` | Base portal spec |
