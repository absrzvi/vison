# Page Spec — PIS Exterior Screens: Dwell States

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** PIS Exterior Screens (per-coach, platform-facing)
**States covered:** Hold State (alighting) · Boarding Guidance State (boarding)
**Base state:** Route/Destination Display (normal en-route state — existing, not specced here)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

PIS exterior screens on each coach face the platform and are visible to waiting passengers before and during a station stop. During the dwell window, these screens enter two sequential states:

1. **Hold State** — displayed from doors-open until alighting subsides. Tells waiting passengers to stand clear while people exit.
2. **Boarding Guidance State** — displayed once alighting is complete. Tells passengers whether to board this coach or walk to another.

Both states are fully automatic — no Conrad action required to trigger or dismiss them. They are driven by the same occupancy data that powers Conrad's app, via the L2 network write access to the Nomad Digital portal screens.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  ROUTE / DESTINATION │────▶│  HOLD STATE          │────▶│  BOARDING GUIDANCE   │
│  (en-route / normal) │     │  (doors open)        │     │  (alighting done)    │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                                                      │
                                                                      ▼
                                                           ┌──────────────────────┐
                                                           │  ROUTE / DESTINATION │
                                                           │  (departure confirmed)│
                                                           └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Hold | Doors open signal | Alighting rate drops below threshold (same signal as Conductor App) |
| Boarding Guidance | Alighting complete | Departure confirmed (Conrad's one-tap) OR train begins moving (GPS fallback) |
| Route/Destination | Departure | Next stop approach |

---

## Design Constraints

PIS exterior screens are **not interactive** and are viewed at **platform distance** (1–8 metres) by passengers who are moving, carrying luggage, and making a split-second routing decision. This imposes hard constraints:

- Maximum 2 lines of text per screen
- Minimum font size equivalent to 72pt at 1080p screen resolution
- Message must be understood in under 2 seconds by a native German speaker
- No icons that require learned meaning — only universally understood symbols (arrows, checkmarks)
- German primary, English secondary — always both, German on top
- No animation during Hold State — movement draws attention; stillness communicates "wait"
- Directional arrow during Boarding Guidance — rightward arrow means "walk this way along the platform"

---

## State 1 (Baseline): Route/Destination Display

Normal en-route state. Not specced here — this is the existing PIS display managed by ÖBB's standard train information system. Nomad Digital's system returns to this state on departure confirmation and does not interfere with it during the journey.

---

## State 2: Hold State — Differences from Route/Destination

> **The Story:** The train pulls in. Doors open. A crowd of passengers surges toward coach 4's door. The PIS screen on coach 4 — which was showing the route — switches. Large, calm text: "Bitte aussteigen lassen / Please allow passengers to exit." No colour change. No animation. Just a clear instruction. The crowd steps back.

| Property | Value |
|----------|-------|
| Purpose | Prevent platform passengers from blocking the doorway while people are alighting |
| Entry | Doors open (automatic, no Conrad action) |
| Exit | Alighting rate drops below threshold (automatic) |
| Applies to | All coaches simultaneously — not per-coach. Every exterior screen shows the hold state when doors open. |

### Screen Layout — Hold State

```
┌──────────────────────────────────────────┐
│                                          │
│   Bitte aussteigen lassen                │
│                                          │
│   Please allow passengers to exit       │
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Background | White — highest contrast, visible in direct sunlight |
| German line | Bold · large (primary size) · black · left-aligned with margin |
| English line | Regular weight · medium (secondary size, ~65% of German size) · dark grey · left-aligned |
| No icon | Hold state is text-only. An hourglass or person-icon would require learned interpretation. Text is unambiguous. |
| No animation | Static. Movement would compete with the physical flow of alighting passengers. |
| No coach number | Redundant — passenger is standing at this coach's door. |
| No occupancy data | Occupancy during alighting is in flux and misleading. Suppress until boarding guidance activates. |

---

## State 3: Boarding Guidance State — Differences from Hold State

> **The Story:** The alighting rush clears. Every PIS screen on the train updates simultaneously. Coach 7's screen shows "Viel Platz / Plenty of space" with a green stripe. Coach 4 shows "Fast voll / Nearly full" with an amber stripe and an arrow pointing right. A passenger with a suitcase glances at the coach 4 screen, sees the arrow, and walks 20 metres down the platform without hesitation.

| Property | Value |
|----------|-------|
| Purpose | Route boarding passengers to the least crowded coaches before they commit to a door |
| Entry | Alighting complete (automatic) |
| Exit | Departure confirmed or train begins moving |
| Applies to | Per-coach — each screen shows the status of *its own coach*, not a train-wide summary |

### Screen Layout — Boarding Guidance State

```
┌──────────────────────────────────────────┐
│  ████  Coach 4                           │  ← colour stripe (amber/green/red)
│                                          │
│   Fast voll                              │
│   Nearly full          ──────────▶       │  ← directional arrow (if redirect)
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Colour stripe | 16px horizontal band at top of screen. Green = plenty of space (<75% occupancy) · Amber = filling up (75–89%) · Red = nearly full (≥90%). Same thresholds as Conductor App. |
| Coach number | "Coach [N]" — small, top-left, within colour stripe. Confirms to the passenger which coach this screen belongs to. |
| German status line | Bold · large · black · one of three fixed strings (see Status Vocabulary below) |
| English status line | Regular · medium · dark grey · direct translation of German line |
| Directional arrow | Right-pointing arrow (→) · large · shown only when this coach is amber or red AND there is a less-loaded coach in the rightward direction along the platform. Left-pointing arrow (←) used when the less-loaded coach is leftward. No arrow shown when this coach is green (board here) or when all adjacent coaches are equally loaded. |
| Refresh rate | 30s minimum (per Scenario 05 design notes). In practice: updates on each occupancy cycle, with a 30s minimum display duration to avoid flickering. |
| Accessibility icon | Small wheelchair icon shown in bottom-right corner of the accessible coach's screen only, regardless of load state. Always present on the PRM coach — it is not an occupancy signal, it is a permanent wayfinding marker. |

### Status Vocabulary

Three fixed strings only — no dynamic number insertion, no percentage, no passenger count. Simplicity is safety at platform distance.

| Occupancy threshold | German | English |
|---------------------|--------|---------|
| < 75% | Viel Platz | Plenty of space |
| 75–89% | Füllt sich | Filling up |
| ≥ 90% | Fast voll | Nearly full |

**Why three strings, not two or four?**
Two states (available / full) loses the middle signal that drives pre-emptive walking behaviour — "filling up" is the most actionable state, the one that makes a passenger walk 10 metres before it becomes "nearly full." Four states would require passengers to learn a scale they encounter infrequently. Three is the minimum set that creates meaningful behaviour change.

### Directional Arrow Logic

| This coach | Adjacent coach (direction) | Arrow shown? |
|------------|--------------------------|-------------|
| Green | — | No arrow (board here) |
| Amber | Green exists in that direction | Yes → or ← |
| Amber | No greener coach in either direction | No arrow |
| Red | Green or amber exists in that direction | Yes → or ← |
| Red | All coaches amber or red | No arrow (no better option) |

Arrow points toward the nearest coach with lower occupancy. If equidistant, points toward the rear of the train (ÖBB convention — rear coaches are typically less boarded at busy platforms where most passengers cluster near the platform entrance).

---

## Automatic PIS Redirect (from Boarding Mode forecast alert)

When the Conductor App's boarding mode triggers a forecast alert and Conrad selects "Monitor remotely" (or the auto-redirect fires after 60s without response), the PIS system updates the affected coach's screen to the next threshold message without waiting for the next 30s refresh cycle. This is an **immediate update**, not a scheduled one.

| Trigger | Effect on PIS |
|---------|--------------|
| Forecast alert crosses 90% projected | Affected coach screen updates to "Fast voll / Nearly full" + directional arrow immediately |
| Conrad confirms "Monitor remotely" | No additional PIS action — redirect was already triggered by the forecast threshold |
| Projection improves (rate drops) | PIS reverts on next regular 30s refresh cycle — no immediate rollback |

---

## State 4: No Data / Offline

If the Nomad portal loses connection to the Hailo-8 data feed during the dwell window (network interruption, Hailo offline, API timeout):

| Property | Value |
|----------|-------|
| Trigger | Nomad portal receives no occupancy update for >60s during an active dwell |
| Effect | All PIS exterior screens revert immediately to route/destination display — the existing ÖBB-managed content takes over |
| Rationale | Showing stale occupancy data is worse than showing nothing — a passenger directed to coach 7 based on data that is 90s old may find it full. Silent fallback is the correct behaviour. |
| Recovery | When data feed resumes, PIS re-enters the appropriate dwell state (hold or boarding guidance) on the next update cycle |
| Conrad notification | No alert sent to Conrad — this is a system-level fallback, not an actionable conductor event. If Hailo-8 goes offline entirely, that is a separate Diagnostics AI alert. |

---

## State 5: Return to Route/Destination

| Trigger | Departure confirmed (Conrad's one-tap) OR GPS movement detected |
| Effect | All PIS exterior screens revert to route/destination display simultaneously |
| Transition | Immediate — no fade, no animation. Route/destination is a hard cut from dwell guidance. |
| Fallback | If Conrad does not confirm departure and the train moves, GPS movement is the fallback trigger. PIS reverts automatically. |

---

## OBJECT ID Scope Note

PIS exterior screens are **non-interactive display surfaces** — there are no tappable elements, no components to reference by ID, and no automated test targets. OBJECT IDs are therefore not applicable to this spec. Layout elements are referenced by position (top stripe, primary line, secondary line, directional arrow) and content vocabulary. If a future implementation requires traceability to a CMS or template system, element keys should be assigned at that point.

---

## Occupancy Threshold Design Decision

PIS screens use a **3-word vocabulary** (`Viel Platz / Füllt sich / Fast voll`) mapping to 3 thresholds (`<75% / 75–89% / ≥90%`). The Passenger Portal uses a **4-band system** (`0–60% / 61–85% / 86–100% / >100%`) with German labels (`Viel Platz / Mäßig besetzt / Stark besetzt / Überfüllt`).

This is an **intentional difference**:
- PIS screens are read at platform distance in under 2 seconds. Three states is the maximum that can be processed in that time without a learned scale.
- The Passenger Portal is held in hand and read deliberately. Four bands give passengers a more precise picture for decision-making before they commit to a platform position.
- The Conductor App uses the same 3-band system as PIS — staff interfaces are optimised for triage speed.

The PIS 3-word vocabulary maps to the top 3 portal bands. The 4th portal band (`>100% / Überfüllt`) has no PIS equivalent — a coach at >100% capacity should not be receiving boarding-guidance arrows at all.

---

## Interaction Rules

- **No Conrad action required at any point** — PIS state transitions are fully automatic. Conrad's "Monitor remotely" tap in the Conductor App is the only indirect interaction, and even that is optional (auto-redirect fires without it).
- **Hold state is train-wide, boarding guidance is per-coach** — this distinction matters. The hold state gives one message to the whole platform. Boarding guidance is coach-specific because different coaches have different loads.
- **PIS screens do not show Conrad's internal app state** — passengers never see alert details, boarding rate data, or forecast percentages. They see only the three-word status and an arrow.
- **Accessibility icon is permanent on PRM coach** — it is not part of the occupancy system. It is always shown on the designated accessible coach's exterior screen, in all states including route/destination.

---

## Design Rationale

**Why is Hold State text-only with no colour change?**
Colour change at the platform scale draws attention — which is appropriate for boarding guidance. During hold state, the goal is the opposite: calm, clear instruction that doesn't create urgency or anxiety. White background + black text is the most legible combination at platform distance in variable lighting, and it signals "information" not "warning."

**Why no passenger count or percentage on PIS?**
A percentage requires calculation ("89% of what?"). A count requires context ("47 passengers — is that a lot?"). Three words — "Plenty of space / Filling up / Nearly full" — are immediately actionable without any cognitive load. The passenger's only decision is: board here, or walk. The three-word vocabulary maps exactly to that decision.

**Why does the arrow point to the *nearest* lower-occupancy coach rather than the *least* occupied?**
The least occupied coach may be at the far end of a 10-coach train. Passengers with luggage or limited mobility will not walk 150 metres. The nearest lower-occupancy coach is the one that actually changes behaviour. Distance is a real constraint on the platform.

---

## Accessibility

- Colour stripe is never the sole signal — the text status line always accompanies it. A passenger who cannot distinguish green from amber can still read "Filling up."
- Wheelchair icon on PRM coach is high-contrast white on dark background, minimum 48×48px at screen resolution.
- All PIS screen content meets EN 15153-1 (European standard for railway passenger information legibility) minimum character height requirements.

---

## Open Questions

1. **Hold state exit trigger synchronisation** — the hold state exits when the alighting rate drops below threshold, which is the same signal Conrad's app uses. Confirm the PIS write latency from the Nomad portal: if there is a >5s lag between the app state change and the PIS screen update, passengers may see "Please allow passengers to exit" while boarding has already begun — confusing. Target: <3s PIS update latency from trigger.
2. **Arrow direction convention** — proposed "rear of train" as tiebreaker when equidistant greener coaches exist on both sides. Confirm with ÖBB that this matches platform boarding conventions at typical ÖBB stations (some platforms load from the front due to stairwell position).
3. **PIS screen availability** — the L2 network write access requirement (flagged in Scenario 01 and 05) is still marked as needing spec validation. All states in this spec are contingent on that access being confirmed. If not available, boarding guidance falls back to Conrad manual verbal redirection only — the hold state cannot be displayed at all.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-alighting-mode.md` | Hold state entry/exit in sync with Conductor App alighting mode |
| `03-conductor-app-boarding-mode.md` | Boarding guidance entry/exit in sync with Conductor App boarding mode; forecast alert triggers immediate PIS update |
| `04-conductor-app-pre-departure-summary.md` | Departure confirmation triggers return to route/destination |
| Scenario 05 — design notes | Boarding guidance state (this spec) implements the PIS guidance described in Scenario 05 |
