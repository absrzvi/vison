# Page Spec — Conductor App: Pre-Arrival Dashboard State

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** Conductor App (handheld)
**State:** Home Screen — Pre-Arrival Mode
**Base state:** Home Screen (Normal) — documented in `2026-05-14-oebb-ux-design-v2.md § Interface 1`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When the train is within 60 seconds of a scheduled stop, the Conductor App home screen enters **Pre-Arrival Mode** — a temporary overlay state that augments the standard train diagram with dwell-specific context: a countdown timer, locked occupancy snapshot, and per-coach expected-alighting bands derived from reservation data.

Conrad does not navigate to this state. It activates automatically and dismisses automatically when doors open and Phase 1 (alighting) begins.

---

## State Flow Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  HOME — NORMAL      │────▶│  PRE-ARRIVAL MODE   │────▶│  ALIGHTING MODE     │
│  (en-route)         │     │  (T-60s to doors    │     │  (doors open →      │
│                     │     │   open)             │     │   Phase 2)          │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
        ▲                                                         │
        └─────────────────────────────────────────────────────────┘
                        (departure confirmed)
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | App launch / post-departure | Train within 60s of scheduled stop |
| **Pre-Arrival** | GPS + schedule: train ≤60s from stop | Doors open signal received |
| Alighting | Doors open | Alighting rate drops below threshold (→ Boarding Mode) |

---

## State 1 (Baseline): Home Screen — Normal

> Documented in `2026-05-14-oebb-ux-design-v2.md`. Not repeated here. OBJECT IDs defined there are referenced by change records below.

Key elements from baseline relevant to this state:
- `ca-header` — App header (Train ID, route, time, conductor name)
- `ca-alert-banner` — Active alert banner (highest priority, pulsing)
- `ca-coach-diagram` — Coach occupancy bar (all coaches, green/amber/red)
- `ca-alert-feed` — Unified alert feed
- `ca-diagnostics-chat` — Diagnostics chat entry point

---

## State 2: Pre-Arrival Mode — Differences from Normal

> **The Story:** Conrad is 45 seconds out from Salzburg Hbf. The app quietly shifts into dwell-awareness — the diagram freezes to show him the pre-arrival snapshot, a countdown appears, and faint reservation bands appear beneath each coach bar so he can see at a glance which coaches are expected to empty significantly. He hasn't touched the phone. He knows what's coming.

| Property | Value |
|----------|-------|
| Purpose | Surface dwell-specific context before doors open so Conrad can pre-position |
| Entry | Train ≤60s from scheduled stop (GPS + schedule fusion) |
| Previous | Home — Normal |
| Next | Alighting Mode (doors open) |
| Duration | ~60s maximum — dismissed automatically |
| Dismissable by user? | No — auto state. Conrad can still tap through to coach detail as normal. |

### Changes from Normal State

| OBJECT ID | Change | Details |
|-----------|--------|---------|
| `ca-header` | Modified | Station name added as a secondary line below route: **"Next stop: Salzburg Hbf"** in a subdued weight. Replaces or appends below existing route line — does not push content below. |
| `ca-coach-diagram` | Modified | Occupancy values **locked** (frozen snapshot). Visual lock indicator: thin border on the diagram container changes from transparent to a muted `--color-dwell` (slate blue). Coach bars no longer animate. Reservation bands appear beneath each bar (see `ca-coach-diagram-alighting-band`). |
| `ca-alert-banner` | Modified | If no active alert: replaced by `ca-dwell-timer` (see below). If active alert present: alert banner stays, `ca-dwell-timer` appears as a **secondary strip** immediately below the alert banner — smaller, no pulse. |
| `ca-alert-feed` | No change | Feed continues to scroll. New alerts still appear. Not suppressed during dwell. |

### New Elements in Pre-Arrival State

---

#### Dwell Timer Strip

**OBJECT ID:** `ca-dwell-timer`

| Property | Value |
|----------|-------|
| Component | Strip — full width, 44px height |
| Position | Top of screen, below `ca-header`, above `ca-alert-banner` (or replacing it if no alert) |
| Background | `--color-dwell` (slate blue, 90% opacity) |
| Content | Left: station name + stop type icon · Centre: countdown `MM:SS` in monospace · Right: scheduled dwell duration e.g. "4 min dwell" |
| Countdown source | Scheduled stop time (not actual arrival time). If train is running late, timer reflects remaining scheduled dwell — Conrad sees compressed time, not inflated. |
| Animation | Countdown ticks every second. At 30s remaining: text colour shifts to `--color-amber`. At 10s: `--color-warning-red`, no pulse (pulse reserved for alerts). |
| Tap | Tap anywhere on strip → expands to `ca-dwell-detail-panel` (stop info: platform number, scheduled dwell duration, next stop ETA) |

---

#### Expected-Alighting Bands

**OBJECT ID:** `ca-coach-diagram-alighting-band`

| Property | Value |
|----------|-------|
| Component | Overlay layer beneath each coach bar within `ca-coach-diagram` |
| Visual | A lighter, hatched or translucent band at the bottom of each coach bar, height proportional to the number of passengers expected to alight at this stop. Colour: `--color-alighting` (cool grey, distinct from green/amber/red occupancy colours). |
| Label | On tap of a coach: detail panel shows "Expected to alight: 23" as a new row, below the existing actual/expected/delta rows. |
| Data source | ÖBB reservation data feed — reservations ending at this stop, per coach. Where data unavailable: band hidden, detail panel shows "Alighting estimate unavailable for this coach." |
| Zero-alighting coaches | No band rendered — coach bar unchanged. |
| Unknown coaches | Grey hatching at fixed 10% height + "?" label on tap. Does not guess. |

---

#### Dwell Detail Panel (expanded, on timer tap)

**OBJECT ID:** `ca-dwell-detail-panel`

| Property | Value |
|----------|-------|
| Component | Bottom sheet, 40% screen height, draggable |
| Dismisses | Swipe down or tap outside |
| Contents | Stop name · Platform number (from PIS feed) · Scheduled arrival time · Scheduled departure time · Dwell duration · Next stop name + ETA · "Running X min late / on time" indicator |
| Tap-outside behaviour | Dismisses panel. Does not change app state. |

---

## Interaction Rules

- **Conrad does not activate or dismiss this state** — it is fully automatic.
- **No alerts are suppressed** — if a new alert fires during pre-arrival, it appears normally in the alert banner and feed.
- **Diagram freeze is visual only** — tap interactions on the coach diagram still work. Tapping a coach in pre-arrival mode opens the normal detail panel showing the locked (snapshot) values, with a label: "Snapshot — updating when doors open."
- **If stop is skipped operationally** (e.g. emergency non-stop through a station) — pre-arrival mode activates and then dismisses without transitioning to alighting mode. Timer shows "Stop cancelled" and returns to Normal state within 10s.
- **Multiple stops in quick succession** — state resets cleanly between stops. No residual band data from the previous stop.

---

## Design Rationale

**Why auto-activate at 60 seconds?**
Conrad is busy approaching a station — managing passengers, checking doors, sometimes not even looking at the phone. 60 seconds gives him a meaningful window without being so early that the data becomes noise. The app coming to him, not the other way around, is core to Conrad's adoption criteria: "Does it tell me something I didn't know, faster than I could find it myself?"

**Why lock the diagram?**
The train is still moving. Hailo-8 is still counting. But the relevant reference point is what Conrad needs to *plan from* — the pre-arrival occupancy. Showing a live-updating number while the train is pulling in would make the data feel unstable. The lock communicates: "this is your baseline for this stop."

**Why slate blue for dwell context?**
Green/amber/red are already semantically loaded as occupancy thresholds. A fourth colour reserved exclusively for dwell-state context means Conrad's eye learns the pattern: blue = dwell awareness, not a problem, just a different mode. It should feel calm, not urgent.

**Why a hatched band for alighting, not a number?**
Numbers compete with the occupancy count for attention. The band is a directional signal — "some of these people are leaving" — not a precise count. The precision lives in the detail panel on tap, where Conrad actively seeks it.

---

## Accessibility

- Dwell timer colour shift (blue → amber → red) accompanied by increasing font weight, not colour alone.
- All band overlays have `aria-label` equivalents describing expected alighting count.
- Bottom sheet (`ca-dwell-detail-panel`) is accessible via swipe-up gesture and standard focus traversal.

---

## Occupancy Threshold Design Decision

The Conductor App uses a **3-band threshold system** (`<75% green / 75–89% amber / ≥90% red`) throughout all dwell states (pre-arrival, alighting, boarding, pre-departure). This is an intentional difference from the Passenger Portal, which uses a 4-band system (`0–60% / 61–85% / 86–100% / >100%`).

**Rationale:** Staff interfaces are optimised for triage speed — 3 states maps to "fine / watch / act" and can be processed at a glance. The portal is read deliberately by a passenger making a routing decision, where finer granularity drives better behaviour. Same underlying data, different presentation granularity for different audiences. See `05-pis-exterior-dwell-states.md § Occupancy Threshold Design Decision` for the full rationale.

---

## Resolved Decisions

1. **Platform number data** — ✅ Available from the passenger info systems (PIS feed). Include in `ca-dwell-detail-panel` without caveat.
2. **Scheduled dwell vs actual** — ✅ Real-time dwell duration confirmed. Timer reflects live operational dwell — updates if ÖBB extends the stop (e.g. connecting service late). No static schedule fallback needed.
3. **Minimum dwell threshold** — ✅ Pre-arrival mode activates for all stops regardless of dwell duration. No minimum threshold.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-alighting-mode.md` | Next state — activates when doors open |
| `03-conductor-app-pre-departure-summary.md` | Final state before departure confirmation |
| `05-pis-exterior-dwell-states.md` | Parallel — PIS screens show "allow alighting" during same window |
