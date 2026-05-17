# Page Spec — Passenger Portal: Coach Load Guidance

**Scenario:** 05 — Passenger Guided to a Free Coach via Platform Screen
**Interface:** Passenger Portal (CNA — ÖBB Railnet, served from R5001C)
**States covered:** Coach Guidance Panel — Load Indicators (Space Available / Nearly Full / Full)
**Base state:** Coach Guidance Panel — existing states 1–3 (`E-Passenger-Portal/passenger-portal-ux-design.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

While the train is at a platform, passengers who open the Nomad Digital portal on their phone can see a live train diagram showing which coaches have space and which are crowded — allowing them to walk to the right door before they board, without asking staff or guessing.

The portal load guidance must mirror the PIS exterior screen states exactly — same data source, same thresholds, same three-band classification. A passenger who sees "Plenty of space — Coach 7" on the platform screen and "Coach 7 — green" on their portal must be seeing the same underlying state. No divergence.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  PORTAL OPEN         │────▶│  COACH GUIDANCE      │────▶│  JOURNEY MODE        │
│  (pre-boarding)      │     │  PANEL — LOAD VIEW   │     │  (post-departure)    │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| **Coach Guidance — Load View** | Portal opened while train is at platform + doors open | TCMS departure signal |
| Journey Mode | Departure | End of journey |

---

## Coach Guidance Panel — Load View

> **The Story:** Mia is walking toward the platform at Linz Hbf. She opens the portal while still on the concourse stairs. A train diagram appears — 10 coaches in a row. Coaches 3 and 4 are red. Coach 7 is green. She's entering the platform at the coach 7 end. She doesn't slow down. She walks straight to coach 7, boards, and finds a seat in 20 seconds.

### New Element: `pp-coach-load-diagram`

**OBJECT ID:** `pp-coach-load-diagram`
**Type:** Interactive train diagram within Coach Guidance Panel
**Shown:** When train is at platform and portal is open (automatic — no user action required)

#### Per-Coach Card — `pp-coach-load-card`

**OBJECT ID:** `pp-coach-load-card` (one per coach; referenced as `pp-coach-load-card-[N]`)

| Element | Space Available (<75%) | Nearly Full (75–89%) | Full / Redirect (≥90%) |
|---------|----------------------|---------------------|----------------------|
| Fill colour | `--color-occupancy-green` | `--color-occupancy-amber` | `--color-occupancy-red` |
| Label (DE) | "Platz vorhanden" | "Fast voll" | "Voll" |
| Label (EN) | "Plenty of space" | "Nearly full" | "Full" |
| Tap action | Expands `pp-coach-load-detail` | Same | Same |
| Coach number | "[N]" — always shown, white text | Same | Same |

Visual treatment of the diagram matches the PIS exterior screen classification — green/amber/red — so a passenger who has seen the platform screen and opens the portal sees the same signal. Thresholds are identical: <75% / 75–89% / ≥90%.

#### `pp-coach-load-detail` — Coach Detail on Tap

**OBJECT ID:** `pp-coach-load-detail`
**Type:** Inline expansion below the tapped coach card

| Element | Content |
|---------|---------|
| Coach number | "Wagen [N] / Coach [N]" — heading |
| Status label | "Platz vorhanden / Plenty of space" (coloured) |
| Direction cue | "← Board here" or "Board here →" (derived from train direction on platform) |
| Reservation note | "Reserved seats available in this coach" / "Mostly reserved — limited free seats" / omitted if unknown |

The detail expansion does not navigate away — it opens inline so the passenger retains the full train diagram context.

---

## Guidance Banner — `pp-load-guidance-banner`

**OBJECT ID:** `pp-load-guidance-banner`
**Position:** Above the coach diagram — single-line recommendation
**Shown:** When the train has at least one coach ≥ 90% AND at least one coach < 75%

| Condition | Banner text (DE) | Banner text (EN) |
|-----------|-----------------|-----------------|
| Clear imbalance (some full, some free) | "Wagen [N] und [M] haben viel Platz →" | "Coaches [N] and [M] have plenty of space →" |
| Most coaches ≥ 75% | "Zug stark ausgelastet — Platz begrenzt" | "Train heavily loaded — limited space" |
| All coaches < 75% | Banner not shown — diagram is sufficient | — |

The banner names up to 2 of the greenest coaches. If more than 2 are green, the two with lowest occupancy are named. If the banner would name the coach the passenger is already at (derived from GPS or platform position — not attempted; just named by load), still show it — the passenger can verify by looking at the diagram.

---

## Refresh and Sync

| Parameter | Value |
|-----------|-------|
| Refresh cycle | 30 seconds — matches PIS exterior screen refresh cycle |
| Data source | Same Hailo-8 occupancy data as PIS screens — served from Nomad Digital backend |
| Sync guarantee | Portal and PIS screens are within one refresh cycle of each other (≤ 30s divergence). They are not guaranteed to be identical at every moment — they pull from the same source but may poll at different offsets. |
| No-data state | "Live load data unavailable — check platform screens" — neutral message; coach diagram still shown in greyed-out state |
| Departure transition | On TCMS departure signal: load diagram fades out, replaced by Journey Mode panel |

---

## Interaction Rules

1. The coach diagram is shown automatically when the portal is opened while the train is at a platform. No user action required to enter this view.
2. The diagram is scrollable horizontally on trains with more than 6 coaches visible at the default zoom level.
3. Tapping a coach card expands the detail inline. Tapping the same card again collapses it. Tapping a different card collapses the current expansion and opens the new one.
4. The accessibility entry point ("Rollstuhl / Kinderwagen") link remains in the panel footer in all load states — not hidden during the load view. Tapping it enters the accessibility panel flow (Spec 03 of Scenario 06).
5. The portal does not show the exact passenger count — only the three-band classification. Exact counts are Conrad's operational data, not passenger-facing information.

---

## Design Rationale

**Why three bands matching PIS rather than more granular data?**
The PIS screens and portal must tell the same story. A passenger who reads "Nearly full" on the platform screen must not see "68% occupied" on their phone — the two signals would feel different even though they represent the same underlying truth. Consistent vocabulary builds trust. Exact percentages also invite gaming (passengers all rush to the "32% full" coach, making it 60% before anyone boards).

**Why a guidance banner naming specific coaches rather than just showing the diagram?**
The diagram requires the passenger to scan all 10 coaches and make a relative judgement under time pressure. The banner pre-answers the question: "which coach should I walk to?" The diagram remains available for passengers who want to verify or choose differently. Banner + diagram serves both the decision-in-motion passenger and the deliberate one.

**Why no exact passenger counts in the portal?**
Passenger counts are operational data used by Conrad for triage — they are not inherently useful to a boarding passenger who just needs to know "is there space?" Showing "47 passengers" also raises privacy questions about who is being counted and how. The three-band model is accurate, actionable, and privacy-preserving.

---

## Accessibility (Portal UI)

- Each `pp-coach-load-card` has `aria-label`: "Coach [N] — [Plenty of space / Nearly full / Full]"
- Colour fill is supplemented by label text — not colour alone
- `pp-load-guidance-banner` uses `role="status"` — announced on update without requiring focus
- Coach cards minimum 44px touch target height
- `pp-coach-load-detail` expansion announced via `aria-expanded` attribute toggle

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Threshold bands | Identical to PIS: <75% / 75–89% / ≥90% |
| Data source | Same Hailo-8 source as PIS — not a separate data feed |
| Refresh cycle | 30 seconds — matching PIS |
| Sync guarantee | Within one cycle (≤30s) — not real-time identical |
| Passenger count shown | Not shown — three-band label only |
| Guidance banner | Shown only when meaningful imbalance exists; names up to 2 best coaches |
| No-data state | Greyed diagram + "check platform screens" message |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Does the ÖBB CNA portal support the live-updating train diagram component technically? Confirm whether the existing portal uses a static render or a dynamic component that can update every 30s without a full page reload. | Nomad Digital portal team |
| 2 | Is train direction of travel (for direction cue in `pp-coach-load-detail`) reliably available in the portal session? GPS-derived or TCMS-derived — confirm source. | Systems integration |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-01-specs/02-pis-exterior-boarding-guidance.md` | PIS exterior screens — same three-band model; portal must match |
| `scenario-06-specs/03-passenger-portal-pre-boarding-states.md` | Accessibility panel accessed from footer of this panel |
| `E-Passenger-Portal/passenger-portal-ux-design.md` | Base portal spec — existing states 1–3 |
