# Page Spec — Conductor App: Alighting Mode

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** Conductor App (handheld)
**State:** Home Screen — Alighting Mode
**Base state:** Home Screen — Pre-Arrival Mode (`01-conductor-app-pre-arrival-dashboard.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When doors open at a station stop, the home screen transitions from Pre-Arrival Mode into **Alighting Mode** — the diagram unfreezes, occupancy numbers begin falling in real time, and the dwell timer continues counting down. Conrad sees which coaches are clearing and at what rate, giving him 60–90 seconds to decide where to position himself before boarding begins.

This state lasts from doors-open until the alighting rate drops below a defined threshold (indicating the alighting rush has subsided), at which point the app transitions automatically to Boarding Mode (Active Dwell).

---

## State Flow

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  PRE-ARRIVAL MODE   │────▶│  ALIGHTING MODE     │────▶│  BOARDING MODE      │
│  (T-60s)            │     │  (doors open)       │     │  (alighting subsides│
│                     │     │                     │     │   → Active Dwell)   │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

| Entry trigger | Doors open signal from Stadler system via SNMP (automatic) |
| Exit trigger | Alighting rate per coach drops below 2 passengers per 30s across majority of coaches — sustained for 15s |

---

## State 3: Alighting Mode — Differences from Pre-Arrival Mode

> **The Story:** The doors open. Conrad watches coach 4's bar start dropping — 62, 58, 51. Coach 9 barely moves. The alighting bands from Pre-Arrival Mode are still visible, fading as real numbers close in on the expected departure count. He can see coach 4 will clear well. Coach 9 is sticky — only 2 people have left. He already knows coach 9 will need managing during boarding.

| Property | Value |
|----------|-------|
| Purpose | Show real-time occupancy descent per coach so Conrad can predict post-alighting distribution before boarding starts |
| Entry | Doors open |
| Previous | Pre-Arrival Mode |
| Next | Boarding Mode (Active Dwell) |

### Changes from Pre-Arrival Mode

| OBJECT ID | Change | Details |
|-----------|--------|---------|
| `ca-coach-diagram` | Modified | **Diagram unfreezes.** Occupancy values update on Hailo-8 inference cycle (every 15s). Lock border (`--color-dwell`) removed. Alighting bands from pre-arrival state remain visible but now **fade proportionally** as the real count approaches the expected post-alighting count — band shrinks as actual alighting matches expectation. |
| `ca-coach-diagram-alighting-band` | Modified | Transitions from static preview to **live progress indicator.** Band height decreases as passengers alight. When actual alighted count matches expected alighting count, band disappears entirely for that coach. If actual exceeds expected (more people leaving than had reservations), band overshoots to zero and a small "+N extra" label appears. |
| `ca-dwell-timer` | Modified | Label changes from "Dwell: 3:42" to "Doors open · 3:42". Colour remains `--color-dwell` (slate blue). |
| `ca-alert-banner` | Conditional | If accessibility ramp alert fires (wheelchair/pushchair detected alighting at PRM door): alert banner shows `ca-accessibility-alight-alert` (see below). Displaces any lower-priority alert in the banner slot. |

### New Elements in Alighting Mode

---

#### Per-Coach Descent Indicator

**OBJECT ID:** `ca-coach-descent-rate`

| Property | Value |
|----------|-------|
| Component | Small downward arrow + count label, overlaid on each coach bar |
| Visibility | Only shown on coaches where alighting rate > 0 (at least 1 passenger alighted in current 30s window) |
| Content | Downward arrow icon + "-N" (passengers alighted since doors opened) |
| Position | Top-right corner of each coach bar cell |
| Colour | `--color-alighting` (cool grey) — explicitly not red, not amber. Descent is neutral information. |
| Update rate | Refreshes on each Hailo-8 inference cycle (15s) |
| Tap | Tap coach bar → standard coach detail panel, now showing: current count, alighted since doors opened (running total), expected to alight (original estimate), remaining expected alighters |
| Disappears | When alighting rate for that coach reaches zero and has been zero for 15s |

---

#### Accessibility Alighting Alert

**OBJECT ID:** `ca-accessibility-alight-alert`

| Property | Value |
|----------|-------|
| Component | Alert banner — same visual container as `ca-alert-banner` |
| Trigger | Hailo-8 detects wheelchair or pushchair in the alighting flow at a PRM door |
| Content | Icon: wheelchair · Title: "Accessibility — alighting" · Sub: "Coach [N] · Door [N] · Ramp needed" |
| Severity | High — appears in active alert banner slot, displaces lower-priority alerts |
| Actions | Tap → full alert detail with two quick-action buttons: **"Deploy ramp"** (marks ramp deployed, sends confirmation to passenger portal) · **"Not needed"** (dismiss with reason logged) |
| Auto-dismiss | If Conrad does not respond within 90s: escalates to a push notification (device vibration + audio) and logs as unacknowledged. Does not auto-resolve. |
| Portal sync | When Conrad taps "Deploy ramp": passenger portal immediately updates from "Ramp deployment: waiting" to "Ramp deployed at Coach [N] Door [N] — proceed to board" |

---

#### Alighting Complete Indicator

**OBJECT ID:** `ca-alighting-complete-chip`

| Property | Value |
|----------|-------|
| Component | Small chip label, per coach, within the coach diagram |
| Trigger | Alighting rate for that coach drops to zero and has been sustained for 15s |
| Content | Small checkmark + "Clear" label in `--color-alighting` |
| Position | Bottom-left of coach bar cell |
| Meaning | "This coach has finished alighting — boarding can begin here" |
| Clears | Disappears when first boarding passenger detected in that coach (Hailo-8 count rises) |

---

#### Alighting Mode → Boarding Mode Transition

**OBJECT ID:** `ca-boarding-mode-transition-toast`

| Property | Value |
|----------|-------|
| Component | Toast notification, bottom of screen, 3s auto-dismiss |
| Trigger | Majority of coaches have `ca-alighting-complete-chip` displayed AND overall alighting rate has dropped below threshold |
| Content | "Boarding open — occupancy rising" |
| Colour | `--color-dwell` (slate blue) — not an alert, a mode shift |
| Tap | Dismisses early. No navigation. |
| Effect | App transitions to Boarding Mode (Active Dwell) state — `ca-dwell-timer` label changes, descent indicators clear, boarding rate indicators appear |

---

## Interaction Rules

- **Diagram tap behaviour unchanged** — tapping any coach opens the standard detail panel. In alighting mode the detail panel shows the enhanced alighting breakdown (see `ca-coach-descent-rate` above).
- **New alerts are not suppressed** — if a door obstruction, unattended bag, or other alert fires during alighting, it appears normally. The accessibility alighting alert takes the banner slot; all other alighting-phase alerts go to the feed.
- **Ramp deploy confirmation is one tap** — the most time-pressured action in this state. Conrad is physically moving toward a door. The tap target for "Deploy ramp" must be ≥56px height, reachable with one thumb, positioned in the lower half of the screen.
- **Coach bars never show negative values** — if inference produces a momentary artefact (count dips below zero), floor to zero and hold until next cycle.

---

## Design Rationale

**Why show descent rate as a count ("-N") not a percentage?**
Conrad thinks in people, not percentages. "Coach 4 has lost 18 people" is instantly meaningful. "Coach 4 is at 62% occupancy" requires a mental calculation he does not have time for while walking a platform.

**Why keep the alighting band visible and shrinking, rather than removing it?**
The shrinking band gives Conrad a live "expected vs actual" comparison without requiring him to remember what the band looked like when doors opened. When the band hits zero, alighting matched expectations. When it stops shrinking before zero — the coach is stickier than expected, and Conrad should notice.

**Why is the descent indicator cool grey, not green?**
Green already means "this coach is below occupancy threshold — good to board." Passengers leaving is not the same as "board here." A separate colour prevents Conrad from reading a falling count as a boarding signal before alighting is complete.

**Why 15-second inference cycle?**
Hailo-8 runs inference at this rate. The UI does not interpolate between cycles — it shows the last confirmed count. Fake smoothing would erode Conrad's trust in the numbers faster than a 15-second lag.

---

## Accessibility

- Descent arrows accompanied by `aria-label`: "Coach [N]: [count] passengers alighted since doors opened."
- "Deploy ramp" button meets minimum 44px touch target; spec calls for ≥56px given the urgency context.
- Mode transition toast has sufficient contrast and is also announced via system accessibility API as a status message (not an alert — does not interrupt VoiceOver focus).

---

## Resolved Decisions

1. **Doors-open signal source** — ✅ Automatic from Stadler system via SNMP. No Conrad action required. Manual confirmation rejected — adds friction at the worst possible moment.
2. **Alighting rate threshold** — ✅ "2 passengers per 30s sustained for 15s" accepted as the starting heuristic. Must be configurable per operator in the admin settings. To be validated against real ÖBB dwell data during pilot.
3. **Ramp deploy confirmation sync latency** — ✅ Target <3s confirmed. Portal infrastructure team to confirm feasibility. If latency exceeds 3s, "Rampe wird vorbereitet …" holds — no intermediate failed/stale state shown to Hanna.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `01-conductor-app-pre-arrival-dashboard.md` | Previous state |
| `03-conductor-app-boarding-mode.md` | Next state — active dwell, occupancy rising |
| `05-pis-exterior-dwell-states.md` | Parallel — PIS screens in "allow alighting" state during same window |
| `06-passenger-portal-dwell-states.md` | Dependent — ramp deploy action here triggers portal update |
