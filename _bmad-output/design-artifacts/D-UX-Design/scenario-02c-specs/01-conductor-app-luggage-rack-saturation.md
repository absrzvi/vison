# Page Spec — Conductor App: Luggage Rack Saturation Alert

**Scenario:** 02c — Conrad Heads Off a Luggage Bottleneck
**Interface:** Conductor App (handheld)
**State:** Alert Active — Luggage Rack Saturation Detected (pre-boarding stop)
**Base state:** Home Screen Normal — `scenario-01-specs/01-conductor-app-home-screen.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects that a coach's overhead luggage racks are at or near capacity, AND a large boarding group is expected at the next stop (from schedule data), Conrad receives a **luggage rack saturation alert** with enough lead time to act — minimum 6 minutes before arrival. He can redirect incoming passengers to coaches with rack space via PA and PIS exterior screens, preventing aisle blockage during boarding.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  NORMAL (en-route)   │────▶│  LUGGAGE ALERT       │────▶│  ACTIONED            │
│                      │     │  ACTIVE              │     │  (PA ± screens sent) │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                        │                           │
                                        │                           ▼
                                        │                  ┌──────────────────────┐
                                        └─────────────────▶│  RESOLVED            │
                                                           │  (post-boarding, no  │
                                                           │   further action)    │
                                                           └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | — | Rack saturation ≥ threshold AND large boarding expected at next stop AND ≥ 6 min to stop |
| **Luggage Alert Active** | Both conditions met | Conrad acts (PA / PA+screens) OR stop passes |
| Actioned | Conrad sends PA/screens | Alert dismissed after boarding stop passes |
| Resolved | Post-boarding | Alert cleared; action logged |

**Trigger logic:** Alert fires only when BOTH conditions are true simultaneously:
1. Hailo-8 rack saturation ≥ configured threshold (default: ≥ 85%)
2. Schedule data shows large expected boarding at next stop (configurable threshold: ≥ 15 passengers expected)

This cross-reference prevents alert fatigue — a full rack on a quiet stop is not a problem Conrad needs to act on.

---

## Alert Banner — `ca-alert-banner` (luggage saturation variant)

| Element | Value |
|---------|-------|
| Background | `--color-warning-amber` |
| Icon | Luggage/rack icon |
| Title | "Coach 3 — luggage racks near capacity" |
| Sub-detail | "Large boarding expected · Next stop: [N] min" |
| Animation | Pulsing |
| Tap | Opens `ca-luggage-detail` |

---

## New Element: `ca-luggage-detail`

**OBJECT ID:** `ca-luggage-detail`
**Type:** Full-screen detail panel

### Layout

**1. Header**
- "Coach 3 · Luggage rack saturation"
- Sub-header: "Next stop [Station] — [N] min · Est. [N] boarding passengers"
- Amber header strip

**2. Rack inventory — `ca-luggage-rack-inventory`**

**OBJECT ID:** `ca-luggage-rack-inventory`

| Element | Content |
|---------|---------|
| Rack occupancy bar | Visual fill bar: "Coach 3 racks — 94%" in `--color-occupancy-red` |
| Item breakdown | "Detected: [N] bags · [N] oversized cases · [N] bicycle bags" |
| Classification note | "⚠️ Oversized/bicycle classification is estimated — verify on approach" |

The classification note is mandatory. Hailo-8 oversized/bicycle item classification is a secondary inference layer — less reliable than headcount. Conrad must know this is an estimate before he acts on it.

**3. Adjacent coach rack availability — `ca-luggage-alternatives`**

**OBJECT ID:** `ca-luggage-alternatives`

| Coach | Rack occupancy | Status |
|-------|---------------|--------|
| Coach 2 | 41% | "Rack space available" (green) |
| Coach 4 | 55% | "Rack space available" (green) |
| Coach 3 | 94% | "Near capacity" (red) |

Conrad needs to know which coaches to name in his PA — pre-loading this eliminates a mental calculation step.

**4. Action strip — `ca-luggage-actions`**

**OBJECT ID:** `ca-luggage-actions`

| Action | Label |
|--------|-------|
| PA only | "PA — redirect luggage" |
| PA + PIS exterior | "PA + platform screens" |
| Personal presence | "I'll be at the door" (logs Conrad's planned presence — no system action) |

### PA Modal — `ca-luggage-pa-modal`

Pre-filled PA:
> "Passengers boarding at [Station] with large luggage — coaches 2 and 4 have the most available overhead space. Please use the nearest door to those coaches."

- Coach numbers dynamically inserted from `ca-luggage-alternatives` (two coaches with most rack space)
- Editable, 200 char max
- DE primary / EN option

### PA + PIS Exterior Screens

When Conrad selects "PA + platform screens":
1. PA fires as above
2. PIS exterior screens on coaches 2 and 4 update to show: "Gepäckplatz verfügbar / Luggage space available ✓" — a variant of the Space Available state defined in `scenario-01-specs/02-pis-exterior-boarding-guidance.md`, with luggage-specific messaging.

**New PIS state: `pis-exterior-luggage-available`**

```
┌──────────────────────────────────────────┐
│                                          │
│         Wagen 2                          │
│         Coach 2                          │
│                                          │
│         Gepäckplatz verfügbar ✓          │
│         Luggage space available ✓        │
│                                          │
└──────────────────────────────────────────┘
```

Duration: shown until boarding stop passes and doors close. Returns to standard load guidance after departure.

**⚠️ PIS exterior screen integration dependency applies here** — same L2 write access dependency as Scenarios 01, 05, 10.

---

## Interaction Rules

1. Alert fires minimum 6 minutes before the boarding stop. If the 6-minute window cannot be met (e.g. train is delayed), the alert fires immediately on detection with a note: "Less than 6 min to stop — limited time to act."
2. "I'll be at the door" is a logging action — it records Conrad's intention for analytics (did conductors with active rack alerts position themselves at the door?) without creating any system behaviour.
3. The alert dismisses automatically once the boarding stop has passed and doors have closed. Conrad does not need to close it manually.
4. If Conrad selects "PA + platform screens" but PIS screens are unavailable (network), a toast shows: "PA sent · Screens unavailable" — same partial-success model as Scenario 02b.

---

## Design Rationale

**Why cross-reference schedule data before firing?**
A full luggage rack between stops is irrelevant — passengers can rearrange, and no new luggage is arriving. The alert only matters when large boarding is imminent. Cross-referencing schedule data eliminates false-positives that would train Conrad to ignore rack alerts.

**Why show the item breakdown (bags/oversized/bicycle) even with an accuracy caveat?**
Conrad needs to know the character of the luggage problem. "18 bags" suggests a standard boarding situation; "3 oversized cases, 1 bicycle bag" suggests items that cannot be rearranged and will block the aisle. The caveat is essential — but hiding the data entirely would deprive Conrad of useful (if imperfect) intelligence.

**Why pre-fill the PA with the two coaches that have the most rack space?**
Conrad cannot do this mental calculation quickly while preparing for a boarding stop. The system knows the rack occupancy of every coach; pre-filling with the two best options means Conrad can send an accurate, specific announcement in under 20 seconds.

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Alert trigger | Rack ≥ 85% AND large boarding expected (≥ 15 pax) — both conditions required |
| Lead time | Minimum 6 min; fires immediately with warning if < 6 min available |
| Classification caveat | Always shown for oversized/bicycle items |
| PA pre-fill | Dynamically inserts the two coaches with most rack space |
| PIS luggage state | "Gepäckplatz verfügbar" variant of Space Available — duration: until boarding doors close |
| Partial success | "PA sent · Screens unavailable" toast if PIS fails |
| Auto-dismiss | After boarding stop doors close — no manual close required |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is Hailo-8's rack-level detection accuracy for the R5001C overhead rack configuration? Camera placement and rack geometry determine whether rack-level inference is feasible. | Nomad Digital ML / Hailo integration |
| 2 | What is the source of "expected boarding passenger count" per stop? HAFAS reservation data assumed — confirm whether walk-up estimate is also included or reservations only. | Systems integration / ÖBB HAFAS |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-01-specs/01-conductor-app-home-screen.md` | Base state — `ca-coach-card` luggage icon defined here |
| `scenario-01-specs/02-pis-exterior-boarding-guidance.md` | PIS exterior base states — luggage variant extends the Space Available state |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | UX design v2 overview |
