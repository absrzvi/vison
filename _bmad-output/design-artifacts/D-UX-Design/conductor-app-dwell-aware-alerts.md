# Conductor App — Dwell-Aware Alert Framing (SPEC STUB)

> **Status: Phase 2 — NOT built in story 10-4.** This document captures the deferred
> Conductor-App UX so the design intent is preserved. Story 10-4 ships only the
> event-payload field (`seconds_to_departure`), the Control Centre KPI tile, and the
> business-goal wiring. The Conductor App does not exist in the PoC Control Centre;
> the UI below is gated on **Conductor App epic activation** (epics.md E10-S4 AC8).

## Context

The onboard data already exists. Story 10-4 added `seconds_to_departure: int | None`
to `AlertRaisedPayload` (stamped by fusion when a train is pre-departure at a station
and the PIS feed is healthy — see [10-4 story](../../implementation-artifacts/10-4-dwell-time-aware-alert-framing-and-kpi.md)).
A Conductor App, when built, consumes that field directly off the alert envelope —
no further backend work is required for the display pieces below.

## Deferred UX (Phase 2)

### 1. Pre-departure alert banner — dwell suffix

When an alert renders on the Conductor App pre-departure banner and its payload carries
a populated `seconds_to_departure`:

- The title gains the suffix **`· {N}s to departure`**
  (e.g. `"Door obstruction · Coach 6 · 90s to departure"`).
- When `seconds_to_departure` is `None` (in-transit or feed-degraded), the suffix is
  omitted entirely — never render `· nulls to departure` or `· —s`.

### 2. Urgency colour shift

- Default banner accent follows the alert severity (existing behaviour).
- When `seconds_to_departure < 30`, the dwell suffix (and optionally the banner edge)
  shifts from amber to **red** to signal the closing departure window. Use
  `--obb-sev-medium` (amber) → `--obb-sev-critical` (red) per the design tokens — do
  **not** invent `--obb-sev-warning`/`--obb-sev-danger` (they do not exist).

### 3. "Minutes saved this shift" totaliser (pre-departure summary)

On the Conductor App pre-departure summary screen:

- A **"minutes saved this shift"** totaliser updates when the train completes a station
  dwell, computed as Σ over acknowledged-before-departure alerts of
  `seconds_to_departure × ack_action_factor` (factor derived from the outcome-tag →
  resolution-time mapping).
- The totaliser **resets at journey start**.
- This is the onboard, per-shift analogue of the landside **"delay-min avoided (24h)"**
  fleet KPI shipped in 10-4. Both measure the same business outcome (Business Goal 2.2);
  this one is per-conductor-per-shift, the landside tile is fleet-wide.

## Actor-model note (do not regress)

Per the project actor model (`project-actor-model-conrad`), the onboard human ack step
exists **only on Fernverkehr** trains; the default conductorless case has no onboard
conductor. A Conductor App dwell banner therefore applies to the Fernverkehr branch —
on conductorless services the equivalent surface is the landside Control Centre. Keep
copy operator-neutral; do not imply an onboard human acted on a conductorless train.

## Dependencies when activated

- Conductor App epic (UI shell, alert feed, auth).
- `AlertRaisedPayload.seconds_to_departure` — **already shipped** (10-4).
- Outcome-tag → resolution-time mapping for the `ack_action_factor` (needs definition
  with ÖBB before the totaliser's coefficient is meaningful).
