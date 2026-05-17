# Page Spec — Passenger Portal: Dwell States

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** Passenger Portal (CNA — ÖBB Railnet, served from R5001C)
**States covered:** Ramp Confirmed State · Journey Mode
**Base state:** Coach Guidance Panel — existing states 1–7 (`E-Passenger-Portal/passenger-portal-ux-design.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Two new portal states extend the existing Coach Guidance Panel for Scenario 10:

1. **Ramp Confirmed State** — a live update to the accessibility panel when Conrad taps "Deploy ramp" on his handheld. The passenger portal reflects confirmation in real time, removing Hanna's final uncertainty before she commits to walking to the door.
2. **Journey Mode** — the state the portal enters after departure confirmation. Boarding guidance is no longer relevant; the panel switches to a quieter in-journey occupancy view for passengers who want to find a seat or move coaches mid-journey.

Both states are extensions of the existing panel — they do not replace the page layout, they update the coach guidance panel section in place.

---

## State Flow

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  STATE 4             │────▶│  RAMP CONFIRMED      │────▶│  JOURNEY MODE        │
│  Accessibility       │     │  STATE               │     │  (post-departure)    │
│  (space available,   │     │  (Conrad confirms    │     │                      │
│   ramp pending)      │     │   ramp deployed)     │     │                      │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
        ↑                                                          ↑
        │                                                          │
┌──────────────────────┐                                 ┌──────────────────────┐
│  STATES 1–3          │─────────────────────────────────│  departure confirmed │
│  General boarding    │                                 │  (Conrad one-tap)    │
│  guidance            │                                 └──────────────────────┘
└──────────────────────┘
```

---

## State 8: Ramp Confirmed — Differences from State 4 (Accessibility, Space Available)

> **The Story:** Hanna is on the platform, pushchair in hand, watching the accessibility panel on her phone. It says "Rampe wird vorbereitet …" — ramp being prepared. She's walking toward coach 2. Conrad taps "Deploy ramp" on his handheld at the door. Her phone updates: "✓ Rampe bereit." She doesn't slow down. She arrives at the door, ramp is there, Conrad is there. She boards in 25 seconds.

This state already exists as the **Ramp Confirmed State** in the existing portal spec (`passenger-portal-ux-design.md` §Accessibility panel — Ramp confirmed state). Scenario 10 adds the precise trigger mechanism and timing spec that was missing.

| Property | Value |
|----------|-------|
| Purpose | Confirm to Hanna that the ramp is physically deployed before she arrives at the door |
| Entry | Conrad taps "Deploy ramp" in `ca-accessibility-alight-alert` (Conductor App alighting mode) |
| Previous | State 4 — Accessibility, space available, ramp pending |
| Next | Journey Mode (on departure) |
| Latency requirement | Portal must reflect Conrad's confirmation within 3 seconds of his tap. If latency >3s: "Rampe wird vorbereitet …" continues to show — do not show a failed/stale intermediate state. |

### Changes from State 4

| Element | State 4 (pending) | State 8 (confirmed) |
|---------|------------------|---------------------|
| Ramp status line | "Rampe wird vorbereitet …" · 12px italic · `--text-tertiary` | "✓ Rampe bereit" · 12px · `--sev-normal` green · non-italic |
| Accessibility panel border | `rgba(74,158,255,0.25)` (blue) | `rgba(34,197,94,0.35)` (green) — border colour shifts to confirm completion |
| Accessibility panel background | `rgba(74,158,255,0.08)` | `rgba(34,197,94,0.08)` — subtle green tint |
| Animation | None | Single pulse: panel border brightens to full green for 400ms then settles to `rgba(34,197,94,0.35)`. Draws Hanna's eye to the update without startling. |
| `role` attribute | `role="alert"` (existing) | Remains `role="alert"` — screen reader announces "Rampe bereit" when content changes |

### No Changes

- Coach diagram: unchanged
- Coach number and door number: unchanged ("Wagen 2 · Tür 1")
- Wheelchair icon: unchanged
- "Rollstuhlplatz frei" heading: unchanged

### If Conrad taps "Not needed" instead of "Deploy ramp"

The "Not needed" action in the Conductor App means the ramp alert was a false positive — Hanna does not actually need a ramp (e.g. she boarded independently). In this case:

- Portal accessibility panel **does not update** — it remains in State 4 (pending) until the dwell ends
- On departure, panel transitions to Journey Mode as normal
- No error state is shown to Hanna — the panel stays helpful, not alarming

Rationale: "Not needed" is Conrad's operational judgement. The passenger portal should not contradict him or confuse Hanna with an unexpected state.

---

## State 9: Journey Mode — Differences from Boarding Guidance States

> **The Story:** The train leaves Salzburg. The PIS screens outside switch back to the route display. Hanna's portal — still open — no longer shows "Rampe bereit." Instead, the panel header now reads "Zugauslastung — Aktuelle Fahrt" and the coach diagram shows the in-journey occupancy. She's seated in coach 2. She doesn't need the panel now, but it's there if she wants to move carriages mid-journey.

| Property | Value |
|----------|-------|
| Purpose | Replace boarding-specific guidance with a quieter in-journey occupancy view for passengers who want to move coaches or find space during the journey |
| Entry | Departure confirmed (Conrad's one-tap) OR GPS movement detected (fallback) |
| Previous | Any boarding guidance state (1–3) or Ramp Confirmed (State 8) |
| Next | Panel hides on journey end (terminal station) or portal session timeout |

### Changes from Boarding Guidance States

| Element | Boarding Guidance | Journey Mode |
|---------|------------------|-------------|
| Panel header label | "Zugauslastung · Wagen 1–8" | "Zugauslastung · Aktuelle Fahrt" ("Current journey") |
| Guidance instruction block | Shown when applicable (directional arrow + coach recommendation) | **Hidden** — no directional boarding instruction during journey. Passengers are already on the train; directing them to board a coach is irrelevant. |
| Accessibility panel (Hanna) | Ramp status shown | **Ramp status hidden** — ramp is retracted, stop is done. Accessibility space occupancy still shown if PRM coach still occupied. |
| Freshness pill | "Vor X Sek." | "Vor X Sek." — unchanged. Data still refreshes every 30s. |
| Coach diagram | Green/amber/orange/red per boarding occupancy | Green/amber/orange/red per current in-journey occupancy — same thresholds, same colours, same 30s refresh. No visual change to the diagram itself. |
| Panel tone | Active — directing behaviour ("go here") | Passive — informing state ("here's how the train looks") |
| "Full train" warning block | Shown when all coaches >85% | **Hidden** in journey mode — the passenger is already on the train. Telling them it's full serves no purpose and causes anxiety. |

### New Element: Mid-Journey Coach Suggestion (conditional)

**OBJECT ID:** `pp-journey-coach-suggestion`

Shown only when a significant occupancy imbalance exists mid-journey (one coach ≥30% less occupied than the passenger's likely current coach) AND the train has >10 minutes remaining to terminal.

| Property | Value |
|----------|-------|
| Component | Slim banner below the coach diagram, inside the panel |
| Content | "Wagen [N] hat viel Platz" · 13px · `--text-primary` · with coach block highlighted in diagram |
| Sub-line | "Falls Sie einen ruhigeren Platz suchen" ("If you're looking for a quieter seat") · 12px · `--text-secondary` |
| Tone | Suggestion, not instruction. Subjunctive phrasing ("falls Sie suchen") — not imperative ("gehen Sie zu"). Passengers mid-journey are not being directed; they are being informed of an option. |
| Shown | Maximum once per journey — resets at next station stop. Does not re-fire if dismissed. |
| Dismissed | Tap small ✕ on the banner. Dismissed for the rest of the journey. |
| Not shown | If passenger has an assigned seat reservation — no suggestion to move. (Reservation data from ÖBB ticketing; if unavailable, show suggestion regardless.) |

---

## Transition Animation: Boarding → Journey Mode

| Property | Value |
|----------|-------|
| Duration | 300ms |
| Effect | Guidance instruction block fades out (opacity 0 → hidden). Panel header text cross-fades to "Aktuelle Fahrt". Ramp status line in accessibility panel fades out. Coach diagram does not animate — it is continuous data. |
| Trigger | Departure confirmed event received from local API endpoint |
| Endpoint | `GET /api/v1/journey-state` → `{ state: "boarding" | "journey" | "arrived" }` — portal polls on 30s refresh cycle. Departure confirmation updates this endpoint; portal picks it up on next poll or within 5s via a push event if WebSocket is available. |

---

## Interaction Model

Both new states follow the existing portal interaction model — **read-only for passengers, no taps required** — with one addition:

- Journey mode mid-journey suggestion (`pp-journey-coach-suggestion`) has a dismiss ✕ button. This is the only new interactive element introduced in these states. Touch target: 44×44px minimum.

---

## Design Rationale

**Why shift the accessibility panel border to green on ramp confirmation, not just the text?**
The border colour change is a peripheral signal — Hanna may be walking and holding her phone at an angle. A green border pulse is visible in peripheral vision without requiring her to read a line of text. The text change ("Rampe bereit") is the primary confirmation; the border is the secondary catch.

**Why hide the guidance instruction block in journey mode?**
A directional arrow and "go to coach 7" instruction makes sense on a platform where the passenger can still choose their door. Once the train is moving, telling a seated passenger to walk to another coach is a different act — more effortful, potentially disruptive, not always desirable. The mid-journey suggestion replaces it with an opt-in framing that respects the passenger's comfort.

**Why suppress the "full train" warning in journey mode?**
During boarding, "Zug stark besetzt" sets an honest expectation before the passenger commits. After departure, the passenger is already committed — knowing the train is full creates anxiety with no actionable outlet. The coach diagram's orange/red colours communicate the density without the explicit warning framing.

**Why is the mid-journey suggestion shown at most once per journey?**
If it re-fired at every station stop, it would become nagging. The passenger either acts on it or doesn't. Showing it once respects their decision.

---

## OBJECT ID Scope Note

The base Passenger Portal spec (`passenger-portal-ux-design.md`) uses CSS selectors and structural position references rather than OBJECT IDs — it predates the OBJECT ID convention used in the Conductor App specs. State 8 (Ramp Confirmed) and State 9 (Journey Mode) follow the same pattern as the base spec: elements are referenced by their content and role, not by ID. The one new interactive element introduced (`pp-journey-coach-suggestion`) does carry an OBJECT ID as it is a new element with no precedent in the base spec.

If the portal spec is ever brought into full OBJECT ID compliance, the base spec should be updated first and these states will inherit that structure automatically.

---

## Accessibility (WCAG)

- Ramp confirmed animation: `prefers-reduced-motion` media query — if set, border colour changes immediately without the pulse animation.
- `role="alert"` on accessibility panel ensures the ramp confirmation ("Rampe bereit") is announced by screen readers without requiring focus.
- Journey mode mid-journey suggestion dismiss button: `aria-label="Waggon-Empfehlung schließen"` · 44×44px touch target.
- Panel transition (boarding → journey): `role="status"` on panel header — screen readers announce the header change ("Aktuelle Fahrt") as a status update, not an alert interrupt.

---

## Open Questions

1. **WebSocket availability** — the journey mode transition can be near-instant if a WebSocket connection exists between the R5001C local API and the portal. If only polling is available (30s cycle), there may be up to 30s where the portal still shows boarding guidance after the train has departed. Acceptable? Propose: add a lightweight push event endpoint for state transitions only, falling back to polling. Confirm with portal infrastructure team.
2. **Reservation data for mid-journey suggestion suppression** — suppressing the suggestion for passengers with assigned seats requires ÖBB ticketing data in the portal context. If not available, the suggestion shows for all passengers regardless of reservation status. Confirm availability with ÖBB integration team.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-alighting-mode.md` | "Deploy ramp" tap here triggers State 8 entry |
| `04-conductor-app-pre-departure-summary.md` | Departure confirmation here triggers Journey Mode entry |
| `E-Passenger-Portal/passenger-portal-ux-design.md` | Base spec — States 1–7 defined there; States 8–9 defined here extend that set |
