# Page Spec — Passenger Portal: Post-Boarding Journey State (Accessibility)

**Scenario:** 06 — Passenger with Pushchair Finds Accessible Space
**Interface:** Passenger Portal (CNA — ÖBB Railnet, served from R5001C)
**State:** Journey Mode — Persistent Accessibility Indicator
**Base state:** Journey Mode — existing state (`E-Passenger-Portal/passenger-portal-ux-design.md § Journey Mode`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Once a passenger with an accessibility need has boarded and the train departs, the portal's Coach Guidance Panel transitions to Journey Mode. For passengers who self-identified an accessibility need during boarding, Journey Mode must include a **persistent accessibility status strip** — confirming that the accessible space is occupied (by them) and surfacing relevant journey information (e.g. accessible toilet location, next stop accessibility info).

The storyboard notes: "Portal accessibility indicator must be persistent throughout the journey — not just at boarding." This spec defines what that persistence looks like and what information it carries.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  RAMP CONFIRMED      │────▶│  JOURNEY MODE        │────▶│  JOURNEY MODE        │
│  (spec 05)           │     │  + ACCESSIBILITY     │     │  + ACCESSIBILITY     │
│                      │     │  STRIP               │     │  STRIP (next stop)   │
└──────────────────────┘     │  (en-route)          │     │  (updated)           │
         OR                  └──────────────────────┘     └──────────────────────┘
┌──────────────────────┐
│  PRE-BOARDING        │
│  (if departed before │
│   ramp confirmed)    │
└──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Pre-boarding / Ramp confirmed | — | TCMS departure signal |
| **Journey Mode + Accessibility Strip** | TCMS departure signal (train leaves station) | End of journey (final destination) |
| Journey Mode (no strip) | End of journey | — |

---

## State: Journey Mode — Persistent Accessibility Strip

> **The Story:** Hanna is on the train. They've departed Wien Hbf. She glances at her phone — the ramp status is gone, replaced by a quieter persistent strip: "Rollstuhlplatz belegt — Wagen 2." Below it, the next stop: "Linz Hbf · barrierefrei — Aufzug Gleis 3." She puts her phone in her pocket. She knows she's in the right place and what to expect at Linz.

### New Element: `pp-accessibility-journey-strip`

**OBJECT ID:** `pp-accessibility-journey-strip`
**Type:** Persistent strip within Journey Mode Coach Guidance Panel — shown only to passengers who self-identified accessibility need during this session
**Position:** Pinned below the journey header (train ID, destination, next stop), above the standard coach load view
**Language:** German primary, English secondary

| Section | Content (DE) | Content (EN) |
|---------|-------------|-------------|
| Space status | "Rollstuhlplatz belegt — Wagen 2" | "Accessible space occupied — Coach 2" |
| Space status icon | Wheelchair icon + green "occupied by you" indicator | Same |
| Next stop accessibility | "Nächster Halt: [Stop] · [accessibility status]" | "Next stop: [Stop] · [accessibility status]" |
| Accessible toilet | "Behindertentoilette: Wagen 2 · Tür 2" (fixed per formation) | "Accessible toilet: Coach 2 · Door 2" |
| Dismiss option | "Ausblenden" (hide) — collapses strip for this session; re-expandable | "Hide" |

**Next stop accessibility status values:**

| Value | Condition | Display (DE) | Display (EN) |
|-------|-----------|-------------|-------------|
| Accessible | Station confirmed step-free | "barrierefrei" (green dot) | "Step-free access" |
| Assistance required | Station has lifts but may need staff | "Aufzug vorhanden" (amber dot) | "Lift available" |
| Not confirmed | No accessibility data for this stop | — (field omitted) | — |

**Visual treatment:**
- `pp-accessibility-journey-strip` background: `rgba(74,158,255,0.06)` — subtle blue tint, quieter than the boarding panel (journey context, not urgent)
- Left border: 3px solid `rgba(74,158,255,0.4)` (blue — persistent accessibility colour)
- Space status: `--text-primary` · 16sp · normal weight — confirmatory, not alarming
- Next stop accessibility: `--text-secondary` · 14sp — supporting context
- Accessible toilet: `--text-tertiary` · 12sp — reference information, lowest visual weight

**Behaviour:**
- Strip appears automatically for sessions where the passenger self-identified an accessibility need during the most recent station dwell
- Strip does not appear for passengers who did not self-identify — no unsolicited accessibility information is shown
- If the passenger taps "Ausblenden" (hide), the strip collapses to a single-line summary ("♿ Rollstuhlplatz aktiv") with a chevron to re-expand — it is never fully dismissed
- At each stop, the "Nächster Halt" field updates automatically to reflect the next station's accessibility data

---

## Interaction Rules

1. `pp-accessibility-journey-strip` is session-persistent — it remains visible for the entire journey unless the passenger hides it, and survives page refreshes within the portal session.
2. The "space occupied by you" indicator is display-only — it does not update if the passenger moves to another coach. The system does not track passenger position post-boarding.
3. Accessible toilet location is fixed per train formation (not Hailo-8 inferred) — sourced from Stadler formation data. Shown as static reference, not real-time status (toilet availability is not monitored).
4. Next stop accessibility data is sourced from ÖBB station accessibility database (HAFAS supplementary data). If data is unavailable for a stop, the field is omitted rather than showing an unknown state.
5. The strip is not shown for the final destination — Journey Mode ends at destination arrival and the portal reverts to a standard arrival view.

---

## Design Rationale

**Why a persistent strip rather than a dismissable panel?**
The storyboard explicitly requires the accessibility indicator to persist throughout the journey. However, making it a full-sized panel in journey context would be visually dominant for information that is confirmatory rather than actionable. A strip — always present but low-height — satisfies the persistence requirement without dominating the screen.

**Why show accessible toilet location?**
For a passenger with a pushchair or wheelchair, knowing where the accessible toilet is has high practical value. It is discoverable from train formation data, costs nothing to surface, and directly serves the accessibility persona's practical needs on a longer journey. It is shown at lowest visual weight (tertiary text) so it does not clutter the strip for passengers who don't need it immediately.

**Why next stop accessibility information?**
Hanna may need to alight at an intermediate stop with accessibility assistance. Surfacing this proactively — before the stop — allows her to prepare (signal to staff, position at the door) rather than being surprised on arrival. It also reduces demand on Conrad at busy stops.

**Why "occupied by you" rather than just "accessible space occupied"?**
"Accessible space occupied" (without context) could suggest to Hanna that someone else is in her space. "Occupied by you" confirms her occupancy is registered and prevents anxiety about whether she is in the right place. It is also a small but meaningful personalisation in an otherwise impersonal system.

---

## Accessibility (Portal UI)

- `pp-accessibility-journey-strip` uses `role="complementary"` with `aria-label="Zugänglichkeitsstatus"` — screen reader identifies it as supplementary journey information
- Next stop accessibility updates use `role="status"` — announced without requiring focus
- Hide/expand control meets 44px touch target
- Colour indicators (green/amber dots for station accessibility) accompanied by text labels — not colour alone

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Persistence mechanism | Strip pinned in Journey Mode; collapsible to single-line summary but never fully dismissed |
| Session tracking | Session-scoped self-identification — no login, no persistent data |
| Accessible toilet data source | Stadler formation data (static per train formation) |
| Next stop accessibility data source | ÖBB HAFAS supplementary accessibility database |
| "Occupied by you" framing | Confirmatory personalisation — avoids ambiguity about space ownership |
| No tracking post-boarding | Passenger position is not tracked after boarding — space status is fixed at boarding |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Is ÖBB station accessibility data (step-free, lifts, assistance required) available via HAFAS supplementary feed per stop? Confirm field availability and completeness. | ÖBB integration team |
| 2 | Is accessible toilet location available in Stadler formation data per consist, or must it be manually configured per train type? | Stadler / Nomad Digital fleet configuration |
| 3 | Does the portal session survive a passenger locking their phone screen and returning 20 minutes later? Confirm portal session timeout and re-authentication behaviour. | Nomad Digital portal team |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `03-passenger-portal-pre-boarding-states.md` | Prior state — boarding guidance leading into this state |
| `05-passenger-portal-ramp-confirmed-state.md` | Transition state between boarding and journey |
| `E-Passenger-Portal/passenger-portal-ux-design.md § Journey Mode` | Base Journey Mode spec this state extends |
