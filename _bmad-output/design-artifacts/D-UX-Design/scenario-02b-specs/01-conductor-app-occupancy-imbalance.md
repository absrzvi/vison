# Page Spec — Conductor App: Occupancy Imbalance Alert + Rebalancing

**Scenario:** 02b — Conrad Rebalances a Lopsided Train
**Interface:** Conductor App (handheld) + PIS Interior Screens
**State:** Alert Active — Occupancy Imbalance Detected
**Base state:** Home Screen Normal — `scenario-01-specs/01-conductor-app-home-screen.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects a significant occupancy imbalance across the train — one section heavily loaded, another largely empty — Conrad receives an imbalance alert. The alert gives him an at-a-glance split view of the train, the key rebalancing opportunity (which empty coaches have unreserved seats), and a single "Announce + Show on screens" action that fires the PA and updates PIS interior screens simultaneously.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  NORMAL (en-route)   │────▶│  IMBALANCE ALERT     │────▶│  REBALANCING         │
│                      │     │  ACTIVE              │     │  IN PROGRESS         │
└──────────────────────┘     └──────────────────────┘     │  (PA + screens sent) │
                                                          └──────────────────────┘
                                                                    │
                                                                    ▼
                                                          ┌──────────────────────┐
                                                          │  RESOLVED            │
                                                          │  (gap narrows below  │
                                                          │   threshold)         │
                                                          └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | — | Occupancy gap ≥ imbalance threshold AND train NOT within 10 min of terminus |
| **Imbalance Alert Active** | Gap ≥ threshold | Conrad acts OR gap resolves naturally |
| Rebalancing in progress | "Announce + Show on screens" sent | Gap narrows below threshold (auto-resolve) |
| Resolved | Gap < threshold | Alert cleared; estimated movement logged |

**Imbalance threshold:** Default — average occupancy of the top-quartile coaches minus average of bottom-quartile coaches ≥ 50 percentage points (e.g. 87% vs 31% = 56-point gap). Configurable per operator. Does not fire within 10 minutes of terminus.

---

## Alert Banner — `ca-alert-banner` (imbalance variant)

| Element | Value |
|---------|-------|
| Background | `--color-warning-amber` |
| Icon | Balance/scales icon |
| Title | "Occupancy imbalance" |
| Sub-detail | "Coaches 1–4 avg 87% · Coaches 7–10 avg 31%" |
| Animation | Pulsing |
| Tap | Opens `ca-imbalance-detail` |

---

## New Element: `ca-imbalance-detail`

**OBJECT ID:** `ca-imbalance-detail`
**Type:** Full-screen detail panel

### Layout

**1. Split train diagram — `ca-imbalance-split-diagram`**

**OBJECT ID:** `ca-imbalance-split-diagram`

Full-width train diagram showing all coaches with their occupancy colours (green/amber/red) — same visual as the home screen `ca-coach-diagram` — but with a visual divider and labels:

```
[Coach 1][Coach 2][Coach 3][Coach 4] | [Coach 5][Coach 6] | [Coach 7][Coach 8][Coach 9][Coach 10]
  RED      RED      AMBER    AMBER         MID              GREEN    GREEN    GREEN    GREEN
  ←─── avg 87% ──────────────────────→    ←─── avg 31% ──────────────────────────────────────→
```

The divider is a soft vertical line — not hard-coded at the middle, but placed by the system at the natural inflection point between the heavy and light sections.

**2. Opportunity panel — `ca-imbalance-opportunity`**

**OBJECT ID:** `ca-imbalance-opportunity`

| Element | Content |
|---------|---------|
| Coaches with space | "Coaches 8 and 9 — less than 25% full · Unreserved seating" |
| Coach 10 note | "Coach 10 — 4 reserved seats unoccupied (possible no-shows)" |
| Available seats | "Est. [N] unreserved seats available across coaches 7–10" |

The opportunity panel identifies *actionable* empty coaches — those with unreserved seating that Conrad can legitimately encourage passengers to use. Coaches with fully reserved (but unoccupied) seats are flagged separately — Conrad cannot direct passengers to reserved seats, so they are context only.

**3. Action strip — `ca-imbalance-actions`**

**OBJECT ID:** `ca-imbalance-actions`

| Action | Label |
|--------|-------|
| Combined action | "Announce + Show on screens" |
| Monitor only | "Monitor — no action" |

### "Announce + Show on screens" — `ca-imbalance-announce-action`

**OBJECT ID:** `ca-imbalance-announce-action`

This is a single combined action — one tap fires both the PA and updates the PIS interior screens in the overcrowded coaches. Conrad does not manage them separately.

**PA Modal — `ca-imbalance-pa-modal`:**

Pre-filled PA text:
> "Passengers in coaches 1 to 4 — coaches 8, 9 and 10 have plenty of available seating and are a short walk through the train. We encourage you to move for a more comfortable journey."

- Coach numbers dynamically inserted from the imbalance data
- Editable (200 char max)
- DE primary / EN option
- Send button — 56px

On send:
1. PA fires across the train (coaches 1–4 targeted if PA zone targeting is supported; train-wide if not)
2. PIS interior screens in coaches 1–4 simultaneously update to `pis-interior-rebalance-state` (see below)
3. Modal closes; detail panel enters "Rebalancing in progress" state

**4. Rebalancing in progress state**

After "Announce + Show on screens" is sent:

| Element | Change |
|---------|--------|
| Action strip | Replaced by "PA sent [HH:MM:SS] · Screens updated" confirmation row |
| Split diagram | Continues updating live — Conrad can watch the gap narrow in real time |
| Auto-resolve note | "Alert will clear when imbalance reduces below threshold" |
| Estimated movement | "App estimated [N] passengers moved" — updated as diagram changes; this is an inference, shown as an estimate |

---

## New Element: PIS Interior Screen — Rebalance State

**OBJECT ID:** `pis-interior-rebalance`
**Interface:** PIS Interior Screens (coach-facing, inside the coach)
**Shown on:** Overcrowded coaches (1–4 in example) simultaneously with PA announcement
**Duration:** Until imbalance resolves below threshold OR 10 minutes (whichever is shorter) — then returns to standard interior display

### Screen Layout

```
┌──────────────────────────────────────────┐
│                                          │
│   Mehr Platz verfügbar:                  │
│   More space available:                  │
│                                          │
│   Wagen 8  ·  9  ·  10    →             │
│   Coach  8  ·  9  ·  10    →            │
│                                          │
│   Ca. [N] Sitzplätze frei               │
│   Approx. [N] seats free                │
│                                          │
└──────────────────────────────────────────┘
```

| Element | Spec |
|---------|------|
| Line 1 (DE/EN) | "Mehr Platz verfügbar / More space available" |
| Line 2 | Coach numbers with directional arrow |
| Line 3 | Approximate free seats count |
| Background | `--pis-background-default` (dark) |
| Text | `--pis-text-primary` (white) |
| Left-edge bar | `--color-occupancy-green` — signals positive/helpful message |
| Auto-dismiss | After 10 min or imbalance resolution — returns to standard interior display |

**⚠️ PIS interior screen integration dependency:** Same L2 network write access dependency as PIS exterior screens (Scenarios 01, 05, 10). This state cannot be implemented until that dependency is confirmed.

---

## Interaction Rules

1. "Announce + Show on screens" is atomic — if PA fires but PIS screens cannot be updated (network issue), Conrad sees a toast: "PA sent · Screens unavailable" — partial success is communicated, not silently failed.
2. Monitor only logs the observation without action. Imbalance alert remains active and may auto-resolve if passengers naturally redistribute.
3. The "estimated passengers moved" counter is an inference — it tracks the change in headcount between overcrowded and empty coaches since the action was taken. It is shown as an estimate, not a precise count.
4. If imbalance threshold is not crossed again within the same journey segment, the alert does not re-fire after resolution — one alert per imbalance event.

---

## Design Rationale

**Why a single "Announce + Show on screens" action rather than two separate steps?**
If Conrad has to tap PA then separately tap "Update screens," the screens will often get skipped — especially when he's mid-journey and moving. The combined action makes the screens a default behaviour of the rebalancing response, not an optional extra. Interior screens amplify the PA message passively — passengers who didn't hear the PA will see it on the screen as they look up.

**Why show the estimated passenger movement counter?**
Conrad needs to know whether his action worked. Without feedback, he has no way to know if the PA had any effect short of walking the full train — which defeats the purpose of the system. The counter is an estimate and is labelled as such; it gives Conrad directional feedback without false precision.

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Imbalance threshold | Default: ≥50 point gap (avg top quartile vs avg bottom quartile). Configurable. |
| Terminus suppression | No alert within 10 min of terminus |
| Combined action | PA + PIS interior screens fired simultaneously in one tap |
| PIS interior content | Coach numbers + approximate seat count + directional arrow |
| PIS interior duration | 10 min or imbalance resolution — whichever is shorter |
| Estimated movement | Shown as inference/estimate — not a precise count |
| PA zone targeting | Train-wide if zone PA not available; coaches 1–4 targeted if supported |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Does the ÖBB PA system on R5001C support coach-zone targeting (PA to specific coaches only), or is it train-wide only? | Systems integration / ÖBB onboard systems |
| 2 | PIS interior screen L2 write access — same open dependency as exterior screens. Confirm separately for interior screens. | Systems integration / Nomad Digital infrastructure |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-01-specs/01-conductor-app-home-screen.md` | Base state — alert banner and coach diagram |
| `scenario-01-specs/02-pis-exterior-boarding-guidance.md` | PIS exterior states — different interface, same L2 dependency |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | UX design v2 overview |
