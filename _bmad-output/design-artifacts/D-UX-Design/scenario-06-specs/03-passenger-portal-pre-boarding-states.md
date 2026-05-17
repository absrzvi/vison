# Page Spec — Passenger Portal: Pre-Boarding Accessibility States

**Scenario:** 06 — Passenger with Pushchair Finds Accessible Space
**Interface:** Passenger Portal (CNA — ÖBB Railnet, served from R5001C)
**States covered:** Pre-Boarding — Accessible Space Available · Pre-Boarding — Accessible Space Occupied
**Base state:** Coach Guidance Panel — existing states 1–7 (`E-Passenger-Portal/passenger-portal-ux-design.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When a passenger with an accessibility need (wheelchair, pushchair, mobility aid) opens the Nomad Digital portal while their train is at a station, the Coach Guidance Panel must:

1. Surface which coach has the accessible space and which door the ramp will be at
2. Show whether that space is currently available or already occupied
3. Update in real time as space status changes during the dwell

The passenger must be able to make a boarding decision — which door to walk to — without having to ask staff or guess. They need this information before they commit to a platform position, not after.

These are two variants of the same panel section — **space available** and **space occupied** — governed by Hailo-8 occupancy inference of the accessible space.

---

## State Flow Overview

```
┌──────────────────────┐     ┌───────────────────────────┐     ┌──────────────────────┐
│  GENERAL COACH       │────▶│  PRE-BOARDING             │────▶│  RAMP CONFIRMED      │
│  GUIDANCE            │     │  ACCESSIBILITY PANEL      │     │  STATE               │
│  (states 1–3)        │     │  (space available or      │     │  (spec 05)           │
│                      │     │   occupied)               │     │                      │
└──────────────────────┘     └───────────────────────────┘     └──────────────────────┘
                                         │
                                         ▼ (if space occupied)
                             ┌───────────────────────────┐
                             │  OCCUPIED — NO BOARDING   │
                             │  (redirect guidance)      │
                             └───────────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| General guidance (1–3) | Portal opened / train at platform | Passenger self-identifies accessibility need (see Trigger below) |
| **Pre-Boarding — Space Available** | Passenger self-identifies + space available | TCMS ramp confirmed signal (→ Spec 05) or departure |
| **Pre-Boarding — Space Occupied** | Passenger self-identifies + space occupied | Space becomes available (updates in place) or departure |

---

## Trigger: How the Portal Enters the Accessibility Panel

The passenger portal does not automatically show the accessibility panel to all passengers — this would expose accessibility information unnecessarily and may create false demand signals.

**Entry path:** The passenger taps a persistent "Accessibility / Reduced mobility" link in the Coach Guidance Panel footer. This is a self-identification action — the passenger declares their need.

On tap:
1. The coach guidance panel expands to show the accessibility view (replacing or extending the standard load view)
2. The system queries the current accessible space status from Hailo-8 via the Nomad Digital backend
3. The appropriate variant (space available or space occupied) is shown within 2 seconds

**No account or login required.** Self-identification is anonymous and session-scoped. No data about the passenger's accessibility need is persisted beyond the journey.

---

## State A: Pre-Boarding — Accessible Space Available

> **The Story:** Hanna opens the portal on the platform at Wien Hbf. She taps "Rollstuhl / Kinderwagen" at the bottom of the screen. The panel shifts to show her a train diagram with coach 2 highlighted in blue. "Wagen 2 · Tür 1 — Rollstuhlplatz frei. Rampe wird vorbereitet." She's 40 metres from coach 2. She starts walking.

### New Element: `pp-accessibility-panel`

**OBJECT ID:** `pp-accessibility-panel`
**Type:** Expanded section within Coach Guidance Panel (replaces standard load strip for this session)
**Language:** German primary, English secondary (bilingual display, ÖBB standard)

| Section | Content (DE) | Content (EN) |
|---------|-------------|-------------|
| Status heading | "Rollstuhlplatz frei" | "Accessible space available" |
| Coach and door | "Wagen 2 · Tür 1" | "Coach 2 · Door 1" |
| Ramp status | "Rampe wird vorbereitet …" | "Ramp preparing …" |
| Coach diagram | Full train diagram with coach 2 highlighted in `--color-accessibility` (blue-teal); door 1 marked with wheelchair icon and animated pulsing ring | Same |
| Directional cue | Arrow pointing toward coach 2 direction on platform (derived from train direction of travel) | Same |
| Staff note | "Unser Personal ist informiert." | "Our staff have been notified." |

**Visual treatment:**
- `pp-accessibility-panel` panel background: `rgba(74,158,255,0.08)` (light blue tint — matches portal accessibility colour convention from existing spec)
- Panel border: `rgba(74,158,255,0.25)` (blue)
- Status heading: `--text-primary` · bold · 18sp minimum
- Coach/door: `--text-primary` · 22sp minimum (glanceable at platform distance)
- Ramp status: `--text-tertiary` · italic · 14sp — supporting information, not primary

**Accessibility (portal UI):**
- `role="region"` with `aria-label="Zugänglichkeitsinformationen"` on `pp-accessibility-panel`
- Coach and door number must have colour-independent identification (not colour alone — bold text + icon)
- Minimum touch target for "Rollstuhl / Kinderwagen" entry link: 44px height
- `role="status"` on ramp status line — screen reader announces updates without requiring focus

---

## State B: Pre-Boarding — Accessible Space Occupied

> **The Story:** Hanna taps "Rollstuhl / Kinderwagen." The panel shows: "Rollstuhlplatz belegt." Coach 2, door 1 is shown with a red overlay. Below it: "Nächste Alternative: Wagen 5 · Tür 2 — frei." She pauses. The panel tells her there's another option. She starts walking toward coach 5. A conductor is already moving toward her.

### `pp-accessibility-panel` — Occupied Variant

| Section | Content (DE) | Content (EN) |
|---------|-------------|-------------|
| Status heading | "Rollstuhlplatz belegt" | "Accessible space occupied" |
| Occupied coach | "Wagen 2 · Tür 1 — belegt" | "Coach 2 · Door 1 — occupied" |
| Coach diagram | Full train diagram with coach 2 in red/occupied state; door 1 marked with occupied icon (wheelchair + X) | Same |
| Alternative (if available) | "Nächste Alternative: Wagen [X] · Tür [Y] — frei" | "Alternative: Coach [X] · Door [Y] — available" |
| Alternative coach highlighted | Alternative coach shown in `--color-accessibility` (blue-teal) in diagram | Same |
| No alternative (if none) | "Kein weiterer Rollstuhlplatz in diesem Zug. Bitte sprechen Sie unser Personal an." | "No further accessible space on this train. Please speak to our staff." |
| Staff note | "Unser Personal ist informiert und kommt zu Ihnen." | "Our staff have been notified and are coming to you." |

**Visual treatment:**
- `pp-accessibility-panel` panel background: `rgba(239,68,68,0.06)` (light red tint)
- Panel border: `rgba(239,68,68,0.30)` (red)
- Status heading: `--color-warning-red` · bold · 18sp minimum
- If alternative shown: alternative section uses blue-teal border/background matching space-available state — the alternative is the positive path forward

### Real-Time Space Status Update

If the space becomes available during the dwell (e.g. the occupying passenger moves or alights):
- Panel updates in place from occupied → available variant
- Animated transition: red border fades to blue-teal over 300ms
- Status heading changes: "Rollstuhlplatz belegt" → "Rollstuhlplatz frei"
- New ramp status line appears: "Rampe wird vorbereitet …"
- No full page reload — in-place DOM update
- `role="alert"` announced by screen reader on change

If the space becomes occupied again (e.g. a second accessible passenger boards ahead of Hanna):
- Panel reverts from available → occupied in place (same transition, reversed)

---

## Interaction Rules

1. The accessibility panel persists for the remainder of the station dwell once triggered — it does not collapse if the passenger navigates away and returns.
2. The "Rollstuhl / Kinderwagen" entry link is always present in the Coach Guidance Panel footer during a station stop. It is not shown during journey (between stations).
3. Real-time updates poll every 15 seconds from the Nomad Digital backend (same as standard portal refresh cycle). Status changes are reflected within one poll cycle (≤15s).
4. The directional arrow in the coach diagram uses train direction of travel to indicate "walk this way." If train direction is unknown (e.g. terminus), the arrow is omitted and only the coach number is shown.
5. The "Staff note" ("Unser Personal ist informiert") is shown regardless of whether Conrad has acknowledged the alert — the statement reflects system behaviour (the alert was sent) not Conrad's action. It must not say "Staff is on their way" as this over-promises.
6. If Hailo-8 loses signal during the dwell (no-data state), the panel shows: "Echtzeitstatus nicht verfügbar — bitte sprechen Sie unser Personal an." ("Real-time status unavailable — please speak to our staff.") The entry trigger and coach/door information from the last known state are retained.

---

## Design Rationale

**Why self-identification rather than automatic accessibility panel for all?**
Surfacing accessibility information to all passengers would expose data about which passengers have accessibility needs (detectable from the PRM reservation), potentially visible to other passengers. Self-identification keeps the panel private to those who seek it and avoids stigma risk. It also prevents general passengers from occupying the accessible space based on "it looks available" information.

**Why show "Staff have been notified" rather than "Staff is coming"?**
"Staff is coming" is a promise Conrad may not be able to keep — he might be in another coach, or the alert may not yet have been seen. "Our staff have been notified" is factually true (the alert was sent) and sets appropriate expectations without over-promising. Hanna knows someone knows — she doesn't need a guarantee.

**Why show the alternative in the occupied panel rather than only the "no space" message?**
The passenger is standing on a platform with limited time. If there is a viable alternative coach, showing it immediately means they can act — they don't need to find a member of staff to ask. The alternative should be the dominant visual element in the occupied panel, not a footnote.

**Why 15-second refresh rather than real-time push?**
The portal is a web application served from the R5001C (onboard server). Push connections require persistent WebSocket infrastructure. For this use case — a passenger on a platform during a 2–5 minute dwell — 15-second polling is sufficient. A space that becomes occupied and then available within a single 15-second window is an edge case that does not warrant the architectural complexity of real-time push.

---

## Accessibility (Portal UI)

- All accessible space status changes announced via `role="alert"` or `role="status"` as appropriate
- Colour changes (red ↔ blue-teal) are always accompanied by heading text changes — not colour alone
- Coach and door number: minimum 22sp, meets WCAG AA contrast at both `--color-accessibility` and `--color-warning-red`
- "Rollstuhl / Kinderwagen" entry link: minimum 44px touch target, minimum 18sp label, positioned in a fixed footer position (not buried in scrollable content)

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Trigger for accessibility panel | Self-identification tap — not automatic for all passengers |
| Language | Bilingual DE/EN — ÖBB standard |
| Space status update mechanism | 15-second polling (not real-time push) |
| Staff notification language | "Notified" not "coming" — factual, not promissory |
| Alternative when occupied | Always shown if available; "speak to staff" fallback when none |
| No-data state | Retain last known coach/door; show "status unavailable" message |
| Directional arrow | Shown if train direction known; omitted if terminus or unknown |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Is the accessible coach and door number deterministic per train formation (always coach 2, door 1 for R5001C)? Or does it vary by consist? If variable, the portal needs to query formation data dynamically. | Fleet management / Stadler |
| 2 | Does the ÖBB CNA portal shell support in-place DOM updates without a full panel reload? Confirm with Nomad Digital portal team. | Nomad Digital portal team |
| 3 | Is `--color-accessibility` (blue-teal) established in the portal's design token set? The existing portal spec uses `rgba(74,158,255,...)` directly — should this be tokenised for Scenario 06? | Design system |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-accessibility-alert.md` | Conrad's view of the same detection event |
| `02-conductor-app-space-occupied-path.md` | Conrad's view when space is occupied |
| `05-passenger-portal-ramp-confirmed-state.md` | Next state — ramp confirmed, passenger commits to door |
| `04-passenger-portal-journey-state.md` | Post-boarding persistent accessibility indicator |
| `E-Passenger-Portal/passenger-portal-ux-design.md` | Base portal spec — existing states 1–7 |
