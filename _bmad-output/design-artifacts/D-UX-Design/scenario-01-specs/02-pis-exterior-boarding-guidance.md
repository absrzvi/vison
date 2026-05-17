# Page Spec — PIS Exterior Screens: Boarding Load Guidance

**Scenario:** 01 — Conrad Watches the Train Fill
**Interface:** PIS Exterior Screens (per-coach, platform-facing)
**States covered:** Boarding Guidance — Space Available · Boarding Guidance — Nearly Full · Boarding Guidance — Full (redirect)
**Base state:** Route/Destination Display (normal en-route state — existing ÖBB PIS system)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

While the train is at a station platform with doors open, each PIS exterior screen can reflect the current occupancy of its coach — guiding passengers to less crowded coaches before they board, without requiring staff intervention.

This is the primary passenger self-distribution mechanism. It works in parallel with Conrad's occupancy monitoring: Conrad sees the whole train on his handheld; passengers see their immediate coach on the screen in front of them. Both surfaces are driven by the same Hailo-8 occupancy data.

These states are **automatic** — triggered by occupancy thresholds, not by Conrad. Conrad does not need to trigger or dismiss them. He benefits from them silently — fewer passengers to redirect manually.

---

## Relationship to Scenario 10 PIS Specs

Scenario 10 (`scenario-10-specs/05-pis-exterior-dwell-states.md`) defines **Hold State** and **Boarding Guidance State** for a structured dwell sequence (alighting-then-boarding). Scenario 01 defines the **occupancy-driven load guidance** states that appear on each coach's screen independently based on its current load — regardless of whether a formal dwell sequence is in progress.

These are complementary, not competing:
- Scenario 10 PIS states manage the *phase* of the dwell (hold / board)
- Scenario 01 PIS states manage the *load signal* on each coach (space / nearly full / full)

Both operate simultaneously. The load signal (Scenario 01) is embedded within the Boarding Guidance State content area defined in Scenario 10.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  ROUTE / DESTINATION │────▶│  LOAD GUIDANCE       │────▶│  ROUTE / DESTINATION │
│  (en-route / normal) │     │  (doors open +       │     │  (departure)         │
│                      │     │   occupancy-driven)  │     │                      │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                        │
                             ┌──────────┴──────────┐
                             ▼                     ▼
                    ┌──────────────┐     ┌──────────────────┐
                    │ SPACE        │     │ NEARLY FULL /    │
                    │ AVAILABLE    │     │ FULL (redirect)  │
                    └──────────────┘     └──────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Route/Destination | — | Doors open (TCMS signal) AND occupancy data available |
| **Load Guidance — Space Available** | Occupancy < 75% threshold | Occupancy crosses 75% OR departure |
| **Load Guidance — Nearly Full** | Occupancy 75–89% | Occupancy drops below 75% OR reaches 90% OR departure |
| **Load Guidance — Full (redirect)** | Occupancy ≥ 90% | Occupancy drops below 90% OR departure |
| Route/Destination | Departure confirmed | — |

State transitions between load guidance variants are **in-place** — the screen updates without a full refresh, so the transition is immediate and does not flash to black.

---

## Design Constraints

Inherited from Scenario 10 PIS spec — these constraints apply to all PIS exterior states:

- Maximum 2 lines of text per screen
- Minimum font size equivalent to 72pt at 1080p (≈ 96px)
- Message understood in under 2 seconds by a native German speaker
- No icons that require learned meaning — arrows and checkmarks only
- German primary, English secondary — always both, German on top
- No animation during static states — movement draws attention; occupancy guidance is not an alarm

Additional constraint for Scenario 01:
- **Per-coach independence** — each screen shows the load state for its own coach. Coach 4 at red shows "Full — please use another coach." Coach 7 at green shows "Plenty of space." They update independently.

---

## State A: Load Guidance — Space Available (Occupancy < 75%)

> **The Story:** The passenger approaches coach 7 on the platform. The PIS screen shows: "Wagen 7 — Platz vorhanden / Coach 7 — Plenty of space." She boards without hesitation. No staff needed.

### Screen Layout — Space Available

```
┌──────────────────────────────────────────┐
│                                          │
│         Wagen 7                          │
│         Coach 7                          │
│                                          │
│         Platz vorhanden                  │
│         Plenty of space          ✓       │
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Line 1 (DE) | "Wagen [N]" |
| Line 1 (EN) | "Coach [N]" |
| Line 2 (DE) | "Platz vorhanden" |
| Line 2 (EN) | "Plenty of space" |
| Symbol | Checkmark (✓) — right-aligned, same size as EN text line |
| Background | `--pis-background-default` (dark — matches standard PIS colour scheme) |
| Text colour | `--pis-text-primary` (white or high-contrast light) |
| Status accent | Left-edge vertical bar: `--color-occupancy-green` · 16px width |
| Animation | None |

The left-edge green bar is the only colour indicator — it does not rely on background colour change (PIS screens are dark-background always; inverting to a green background for "space available" would be jarring and inconsistent with the PIS system's established visual language).

---

## State B: Load Guidance — Nearly Full (Occupancy 75–89%)

> **The Story:** The passenger approaches coach 4. The PIS screen shows "Wagen 4 — Fast voll / Nearly full →". He looks to his right — coach 5 shows a green bar and "Platz vorhanden." He walks 8 metres. Problem solved.

### Screen Layout — Nearly Full

```
┌──────────────────────────────────────────┐
│                                          │
│         Wagen 4                          │
│         Coach 4                          │
│                                          │
│         Fast voll — →                    │
│         Nearly full — →                  │
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Line 1 (DE) | "Wagen [N]" |
| Line 1 (EN) | "Coach [N]" |
| Line 2 (DE) | "Fast voll — →" (arrow indicates direction of less-crowded coaches) |
| Line 2 (EN) | "Nearly full — →" |
| Arrow direction | Derived from train layout — points toward the nearest coach with lower occupancy. If no adjacent coach has lower occupancy, arrow is omitted. |
| Symbol | Directional arrow (→ or ←) |
| Background | `--pis-background-default` |
| Text colour | `--pis-text-primary` |
| Status accent | Left-edge vertical bar: `--color-occupancy-amber` · 16px width |
| Animation | None |

**Arrow direction logic:**
- Find the nearest coach (left or right in train order) with occupancy < this coach's occupancy
- If left: ← arrow
- If right: → arrow
- If both adjacent coaches are equal or higher occupancy, or if this is the only coach with available space: arrow omitted, message becomes "Fast voll / Nearly full" without direction
- Arrow direction confirmed against train direction of travel (so "→" always means "walk in the direction the arrow points on the platform" regardless of which end of the train is which)

---

## State C: Load Guidance — Full / Redirect (Occupancy ≥ 90%)

> **The Story:** Coach 3 is at 94%. Its PIS screen shows "Wagen 3 — Bitte anderen Wagen nutzen / Please use another coach →". The cluster of passengers at coach 3's door reads it and splits — half walk right, half see coach 2's green bar and walk left. Conrad, standing 30 metres away, sees the self-distribution happening and does not need to move.

### Screen Layout — Full / Redirect

```
┌──────────────────────────────────────────┐
│                                          │
│         Wagen 3                          │
│         Coach 3                          │
│                                          │
│  Bitte anderen Wagen nutzen →            │
│  Please use another coach   →            │
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Line 1 (DE) | "Wagen [N]" |
| Line 1 (EN) | "Coach [N]" |
| Line 2 (DE) | "Bitte anderen Wagen nutzen →" |
| Line 2 (EN) | "Please use another coach →" |
| Arrow direction | Same logic as Nearly Full — points toward nearest lower-occupancy coach |
| Background | `--pis-background-default` |
| Text colour | `--pis-text-primary` |
| Status accent | Left-edge vertical bar: `--color-occupancy-red` · 16px width |
| Animation | None — no flashing, no colour inversion. The message is firm but calm. |

**No "Full — do not board" language.** The message directs, it does not prohibit. Passengers with reservations for this coach must still be able to board — the PIS screen cannot know who has a reservation for coach 3 vs. who is boarding by choice. The message guides non-reserved passengers; reserved passengers are unaffected.

---

## State D: No Data / Offline

If the Nomad Digital backend loses connection during a station stop and no occupancy data is available for a coach, the PIS screen for that coach **returns to Route/Destination display** — it does not show a stale load state or an error message.

Rationale: a stale "Plenty of space" message on a coach that is now full is worse than no message at all. Silence is correct. Passengers who see the Route/Destination display (no load indicator) understand that load information is not available — they make their own boarding decision, as they would without the system.

---

## Interaction Rules

1. PIS screens are not interactive. No user action triggers or changes these states — they are driven entirely by Hailo-8 occupancy data via the Nomad Digital backend and L2 network write access to the PIS screens.
2. Each coach's screen updates independently based on that coach's own occupancy. There is no synchronised update across the train — coach 4 and coach 7 may be in different load states simultaneously.
3. Threshold transitions trigger an in-place content update — no full screen flash or black-out between states.
4. The update cycle for PIS screens is 30 seconds — the same as the portal refresh rate. This is slower than the Conductor App (15s) because PIS updates are visible to the platform crowd and too-frequent changes create confusion.
5. On departure (Conrad one-tap confirmation or GPS fallback), all PIS exterior screens simultaneously return to Route/Destination display.
6. If TCMS door-close signal is received before departure confirmation, PIS screens return to Route/Destination at door close.

---

## Design Rationale

**Why left-edge colour bar rather than full background colour change?**
Full background colour change (green screen / amber screen / red screen) would be alarming and visually dominant from platform distance. A 16px left-edge bar provides the colour signal at the correct visual weight — noticeable on approach, not overwhelming. It also keeps the text legible at maximum contrast (white on dark) regardless of state.

**Why no animation in any state?**
Movement on a PIS screen at platform distance draws the eye from 20+ metres away. If load guidance animated — pulsing, scrolling, flashing — it would compete with safety-critical PIS information (door warning lights, departure signals) for passenger attention. Static text is the correct choice for a guidance surface that should inform, not alarm.

**Why 30-second update cycle rather than 15-second?**
A passenger reading the PIS screen at coach 4 sees "Nearly full." She decides to walk to coach 7. If the screen updates to "Plenty of space" in 15 seconds while she is mid-walk, it creates no confusion — she's already going to coach 7. But if the screen flickers rapidly between states as the boarding crowd shifts, passengers hesitate and cluster. 30 seconds provides stability for the boarding decision window while remaining meaningful for a 2–5 minute dwell.

**Why "Bitte anderen Wagen nutzen" rather than "Voll / Full"?**
"Voll" (Full) is a prohibition that reserved passengers cannot comply with — they must board coach 3 regardless. "Bitte anderen Wagen nutzen" (Please use another coach) is directional guidance aimed at non-reserved passengers. It is accurate: the system is asking unreserved passengers to redistribute, not blocking anyone. The distinction matters for ÖBB's passenger relations obligations.

---

## Accessibility (PIS Screens)

- Minimum font size 96px (≈ 72pt at 1080p) — meets legibility requirements at 8 metre platform distance
- Left-edge colour bar is supplemented by German text stating the condition — passengers with colour vision deficiency can read the state from the text without the colour indicator
- No reliance on icons requiring learned meaning — text is the primary carrier of information
- Language: DE primary / EN secondary — always both lines shown simultaneously

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Load states | 3 bands: Space Available (<75%) / Nearly Full (75–89%) / Full / Redirect (≥90%) — matching Conductor App thresholds |
| Colour indicator | Left-edge 16px vertical bar — not background colour change |
| Animation | None in any state |
| Arrow direction | Nearest lower-occupancy coach; omitted if no better adjacent coach |
| "Full" message | "Please use another coach" (directional) — not "Full / Do not board" (prohibitive) |
| Update cycle | 30 seconds (PIS) vs 15 seconds (Conductor App) — platform stability vs staff responsiveness |
| No-data state | Return to Route/Destination — no stale or error message shown |
| Per-coach independence | Each screen reflects its own coach — no train-wide synchronised update |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | L2 network write access to PIS exterior screens — confirmed as an open dependency (flagged in scenarios index). This spec cannot be implemented until this is resolved. What is the protocol for writing to the Nomad Digital portal screens? MQTT assumed — confirm. | Systems integration / Nomad Digital infrastructure |
| 2 | Arrow direction requires knowledge of train orientation on the platform (which end is which). Is train direction of travel reliably available from TCMS/GPS at the point of PIS update? | Systems integration / Stadler |
| 3 | Does the ÖBB PIS system support partial content updates (in-place text change) or require a full screen refresh per update? Full refresh may introduce a visible flash between states. | ÖBB PIS system / Nomad Digital integration |
| 4 | What is the physical PIS screen resolution and aspect ratio on R5001C? 1080p landscape assumed — confirm with Stadler. This affects minimum font size calculation. | Stadler |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-home-screen.md` | Same occupancy data drives both surfaces |
| `scenario-10-specs/05-pis-exterior-dwell-states.md` | Scenario 10 dwell states — the load guidance (this spec) is embedded within Scenario 10's Boarding Guidance State content area |
| `scenario-05-specs/` | Passenger guidance scenario — portal load indicators match these PIS states exactly |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | Conductor App base spec |
