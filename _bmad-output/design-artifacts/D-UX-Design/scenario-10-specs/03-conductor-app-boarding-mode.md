# Page Spec — Conductor App: Boarding Mode (Active Dwell)

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** Conductor App (handheld)
**State:** Home Screen — Boarding Mode
**Base state:** Home Screen — Alighting Mode (`02-conductor-app-alighting-mode.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Once alighting subsides, the home screen transitions into **Boarding Mode** — the active dwell phase where occupancy is rising. The diagram now shows ascending counts, per-coach boarding rate indicators, and projected final load forecasts. The key new element is the **pre-boarding forecast alert**: a distinct alert type that fires *before* a coach actually tips over threshold, giving Conrad 60–90 seconds of warning to act or delegate to PIS.

This state lasts from the alighting-subsides transition until the pre-departure summary activates at T-2min (or the configured pre-departure trigger).

---

## State Flow

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  ALIGHTING MODE     │────▶│  BOARDING MODE      │────▶│  PRE-DEPARTURE      │
│  (doors open)       │     │  (active dwell)     │     │  SUMMARY            │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

| Entry trigger | Alighting rate drops below threshold (auto) |
| Exit trigger | Dwell timer reaches T-2min before scheduled departure |

---

## State 4: Boarding Mode — Differences from Alighting Mode

> **The Story:** The alighting rush is over. Conrad's diagram shifts gear — the downward arrows are gone, replaced by upward ones. Coach 4 is climbing fast: +12 in the last 30 seconds. The projected load bar beneath it is already touching amber. An alert appears — not red, not pulsing — a calm forecast strip: "Coach 4 projecting 95% — PIS redirecting." Conrad glances at it, taps "Monitor remotely," and stays where he is. The system is already handling it.

| Property | Value |
|----------|-------|
| Purpose | Surface boarding surge data and act on imbalances via forecast alerts before they become incidents |
| Entry | Alighting mode exit (auto) |
| Previous | Alighting Mode |
| Next | Pre-Departure Summary |

### Changes from Alighting Mode

| OBJECT ID | Change | Details |
|-----------|--------|---------|
| `ca-dwell-timer` | Modified | Label changes from "Doors open · 3:12" to "Boarding · 3:12". Colour unchanged (`--color-dwell`, slate blue). |
| `ca-coach-diagram` | Modified | Descent indicators (`ca-coach-descent-rate`) cleared. Alighting bands and `ca-alighting-complete-chip` cleared. Boarding rate indicators (`ca-coach-boarding-rate`) appear. Projected load bars (`ca-coach-projected-load`) appear beneath each coach bar. |
| `ca-alert-banner` | Conditional | May be occupied by `ca-forecast-alert` (see below) if a coach is projecting overcapacity. If a real incident alert also exists, incident takes the banner slot and forecast alert moves to a dedicated strip immediately below (see `ca-forecast-alert-strip`). |

### New Elements in Boarding Mode

---

#### Boarding Rate Indicator

**OBJECT ID:** `ca-coach-boarding-rate`

| Property | Value |
|----------|-------|
| Component | Small upward arrow + count label, overlaid on each coach bar |
| Visibility | Only on coaches where boarding rate > 0 in current 30s window |
| Content | Upward arrow icon + "+N" (passengers boarded since boarding mode began) |
| Position | Top-right corner of each coach bar cell — same position as descent indicator in alighting mode |
| Colour | `--color-boarding` (warm amber-tint, distinct from occupancy amber). Not red — boarding is expected. Only the *rate* being excessive is the signal. |
| Update rate | Every 15s (Hailo-8 inference cycle) |
| Tap | Coach detail panel shows: current count, boarded since doors opened, projected final load, rate per 30s |

---

#### Projected Load Bar

**OBJECT ID:** `ca-coach-projected-load`

| Property | Value |
|----------|-------|
| Component | Thin secondary bar, rendered below each coach's occupancy bar, same width |
| Content | Fills from left proportional to projected final load at departure, based on current boarding rate extrapolated to departure time |
| Colour | Matches the *projected* threshold: green (<75%), amber (75–89%), red (≥90%) |
| Label | On tap of coach: detail panel shows "Projected at departure: 84%" as a dedicated row |
| Uncertainty | Projection confidence degrades at low boarding rates or with <90s of data. Below confidence threshold: bar shown as dashed/hatched with label "Projection unavailable — too early" |
| Does not replace | The actual occupancy bar above it. Two bars per coach: actual (top, solid) and projected (bottom, thinner, dashed outline) |
| Disappears | Clears when pre-departure summary activates — at that point actual load is the only relevant number |

---

#### Forecast Alert

**OBJECT ID:** `ca-forecast-alert`

This is the most design-critical element in the entire Scenario 10 spec. It must be visually and behaviourally distinct from incident alerts — it is a prediction, not a detected problem.

| Property | Value |
|----------|-------|
| Component | Alert banner variant — same container dimensions as `ca-alert-banner` but visually differentiated |
| Trigger | Any coach's projected load crosses the overcapacity threshold (≥90%) with ≥60s confidence window remaining |
| Visual differentiation from incident alerts | **Border:** dashed, not solid · **Icon:** graph/trend icon, not warning triangle · **Colour:** `--color-forecast` (muted teal) background, not red/amber · **Label:** "FORECAST" chip in top-left corner of the banner, small caps · **No pulse animation** — incident alerts pulse, forecast alerts are static |
| Content | Icon (trend) · "Coach [N] projecting [X]% at departure" · Sub-line: "Current rate: +[N] per 30s · [T]s to threshold" · PIS action status: "PIS redirecting to coach [M]" or "PIS redirect available" |
| Priority | Lower than any incident alert. If an incident alert is active, forecast alert moves to `ca-forecast-alert-strip` (see below). Forecast alert never displaces an incident from the banner. |
| Actions | Two buttons, equal weight: **"Go to coach [N]"** (logs Conrad moving to physically intervene) · **"Monitor remotely"** (logs decision, confirms PIS auto-redirect is active, dismisses the alert from the banner — it moves to the feed as a resolved-by-system item) |
| "Monitor remotely" effect | PIS exterior screens on the affected coach update automatically (no additional Conrad action needed). A feed item appears: "Coach [N] — PIS redirecting · Conrad monitoring remotely · [timestamp]" |
| Auto-action if Conrad does not respond | After 60s without acknowledgement: PIS redirect activates automatically. Alert moves to feed with status "Auto-redirected — no response." Conrad receives a silent feed update, no escalating push. |
| If projection improves | If boarding rate drops and projected load falls back below threshold, alert auto-dismisses with feed note: "Coach [N] projection resolved — boarding rate slowed." |
| Multiple coaches | If two or more coaches forecast overcapacity simultaneously: banner shows the highest-projected coach. A count chip appears: "+1 more forecast alert." Tap banner → expanded forecast panel listing all affected coaches. |

---

#### Forecast Alert Strip (when banner is occupied by incident)

**OBJECT ID:** `ca-forecast-alert-strip`

| Property | Value |
|----------|-------|
| Component | Slim strip, 36px height, full width, positioned immediately below `ca-alert-banner` |
| Trigger | Active incident alert occupies banner AND a forecast alert is also active |
| Content | Trend icon · "Coach [N] projecting [X]%" · "Tap to manage" |
| Colour | `--color-forecast` (muted teal), lower visual weight than the incident banner above |
| Tap | Expands to full forecast alert detail as a bottom sheet |
| Coexistence rule | Strip can show one forecast summary. If multiple forecasts: "Coach [N] +[X] more — tap to manage." |

---

#### Boarding Mode Feed Items

During boarding mode, the unified alert feed gains a new item category: **forecast items**. These are visually distinct from incident items.

| Property | Value |
|----------|-------|
| **OBJECT ID** | `ca-feed-item-forecast` |
| Left border | `--color-forecast` (teal), not the red/amber of incident items |
| Icon | Trend/graph icon |
| "FORECAST" chip | Appears inline with the item title |
| Dismissed forecast items | Appear in feed as "resolved" with the resolution method: "PIS redirected" or "Conrad intervened" or "Projection resolved — boarding slowed" |

---

## Interaction Rules

- **Forecast alert never blocks Conrad** — both action buttons are deliberate choices, not dismissals. Conrad either commits to going there or confirms remote handling. There is no "dismiss and ignore."
- **PIS auto-redirect is the default path** — Conrad's explicit action is to *confirm* it, not to *trigger* it. The system acts; Conrad approves or overrides. This is important for Conrad's workload: he should not feel responsible for triggering PIS changes.
- **Projected load bar is forward-looking, not retrospective** — it is not an average of past boarding rates; it is a linear extrapolation of the current rate to departure time. If the rate changes, the projection updates immediately on the next inference cycle.
- **Two bars per coach must be legible on a small screen** — the projected bar is 4px high (half the height of the occupancy bar). On the coach detail panel, both bars are shown full-width with explicit labels.
- **Conrad's remote-monitoring decision is logged** — every time Conrad taps "Monitor remotely," a timestamped event is written to the journey log. This creates an audit trail: "Conrad was aware of coach 4 projection and chose remote handling at 14:23:07." Relevant for post-incident review.

---

## Design Rationale

**Why is the forecast alert visually distinct from incident alerts?**
Conrad's highest alert-fatigue risk is in this exact state. If every forecast looks like an incident, he will learn to ignore the banner. The dashed border, teal colour, trend icon, and "FORECAST" chip create a visual grammar he learns in the first two journeys: teal/dashed = prediction, red/solid = happening now. These are categorically different things requiring categorically different responses.

**Why does PIS auto-redirect activate without Conrad's explicit tap?**
Because Conrad may be at the accessibility door, managing a passenger, or simply not watching his phone. The system should degrade gracefully without him. His "Monitor remotely" tap is confirmation and audit trail, not the trigger. This is the difference between an assistant and a tool — the assistant acts and reports; the tool waits to be operated.

**Why extrapolate linearly rather than use a more complex model?**
Linear extrapolation from current rate is transparent and understandable. Conrad can sanity-check it: "+12 per 30s, 90s to departure, that's ~36 more passengers." A black-box ML projection would erode trust if it ever seemed wrong. Simplicity here is a feature, not a limitation. More sophisticated models can be introduced once Conrad trusts the baseline.

**Why is "Monitor remotely" logged?**
Because delayed departures are logged and attributed. If coach 4 ends up overcrowded and Conrad chose remote monitoring, the log should show he made a deliberate, informed decision — not that he missed the alert. This protects Conrad from unfair blame attribution, which directly addresses one of his core negative driving forces.

---

## Accessibility

- Forecast alert background colour (teal) never used as the sole differentiator — "FORECAST" text label always present.
- Boarding rate upward arrow accompanied by `aria-label`: "Coach [N]: [+N] passengers boarded in last 30 seconds, projected [X]% at departure."
- "Go to coach" and "Monitor remotely" buttons both ≥44px height. Equal visual weight — neither is the "default" choice.
- Auto-redirect without response generates a feed item that is announced as a status update (not an alert interrupt) by the accessibility API.

---

## Resolved Decisions

1. **Projection confidence threshold** — ✅ 90 seconds of boarding data required before showing the projected load bar. Below this threshold: dashed/hatched bar with "Too early to project." To be validated against real dwell data during pilot.
2. **PIS redirect trigger timing** — ✅ Split thresholds confirmed: PIS redirect activates at 85% projected load; Conrad's forecast alert fires at 90% projected. This gives passengers walking time before the coach tips to the alert threshold. ÖBB operations to confirm during pilot.
3. **"Monitor remotely" logging destination** — ✅ Journey log only. Not surfaced to Claudia in real time. Rationale: adding Conrad's internal decisions to Claudia's view creates supervisory overhead without clear operational benefit during the dwell window. Available in post-journey audit log if needed.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-conductor-app-alighting-mode.md` | Previous state |
| `04-conductor-app-pre-departure-summary.md` | Next state |
| `05-pis-exterior-boarding-guidance.md` | Dependent — PIS redirect triggered from this state |
| `06-pis-exterior-hold-state.md` | Predecessor — PIS was in hold state during alighting, now switches to boarding guidance |
