# Page Spec — Conductor App: Capacity Flag for Review

**Scenario:** 03 — Conrad Escalates a Chronic Overcrowding Pattern to Claudia
**Interface:** Conductor App (handheld)
**State:** Coach Detail Panel — Flag for Capacity Review
**Base state:** `ca-coach-detail-panel` — documented in `scenario-01-specs/01-conductor-app-home-screen.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Conrad has noticed that certain coaches on specific services are chronically overcrowded — pattern after pattern, Friday after Friday. He cannot fix this himself. He needs to surface the pattern to Claudia with evidence attached, in under 60 seconds, without writing a report.

The "Flag for capacity review" action in the coach detail panel is the entry point. It pre-populates a structured escalation with occupancy data, 7-day trend, and service context — Conrad adds an optional note and taps Send.

This is distinct from operational escalations (unattended item, accessibility, security). It is a **capacity planning input** — non-urgent, landside-routed, analytics-backed.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  COACH DETAIL PANEL  │────▶│  CAPACITY FLAG FORM  │────▶│  CONFIRMATION        │
│  (home screen tap)   │     │  (pre-filled)        │     │  (sent to Claudia)   │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Coach Detail Panel | Tap coach card on home screen | Tap "Flag for capacity review" |
| **Capacity Flag Form** | Tap "Flag for capacity review" | Send / Cancel |
| Confirmation | Send tapped | Dismissed (returns to coach detail or home screen) |

---

## State: Coach Detail Panel — "Flag for Capacity Review"

The "Flag for capacity review" action is an additional row at the bottom of `ca-coach-detail-panel`, shown only when the coach is currently ≥ 75% occupancy and the train is **en-route** (not during a boarding dwell — a capacity flag is a pattern observation, not a live incident).

| Element | Content |
|---------|---------|
| Label | "Flag for capacity review" |
| Icon | Flag icon (neutral — not an alert icon) |
| Colour | `--color-secondary` — low visual weight; this is not urgent |
| Tap action | Opens `ca-capacity-flag-form` (full-screen modal) |

---

## New Element: `ca-capacity-flag-form`

**OBJECT ID:** `ca-capacity-flag-form`
**Type:** Full-screen modal
**Entry:** Tap "Flag for capacity review" in `ca-coach-detail-panel`

### Pre-filled Fields (read-only, system-populated)

| Field | Value | Source |
|-------|-------|--------|
| Service ID | "[Train number] · [Date] · [Departure time]" | TCMS / HAFAS |
| Route | "[Origin] → [Destination]" | HAFAS |
| Coach(es) | "Coach [N]" (the coach Conrad tapped) — editable to add more | From coach detail context |
| Current occupancy | "[N]% — [N] passengers" | Hailo-8 current inference |
| Time of observation | "[HH:MM]" | Device clock |
| 7-day trend graph | Sparkline showing occupancy % for this service on the same day-of-week over the last 7 occurrences | Historical occupancy data store |
| Trend summary | "Above 85% on [N] of last 7 [day] services" (auto-generated from trend data) | Historical data |

### Editable Fields

| Field | Type | Notes |
|-------|------|-------|
| Additional coaches | Multi-select chip picker (all coach numbers) | Conrad adds other overcrowded coaches to the flag; default is the tapped coach only |
| Note | Free text · 200 char max · optional | "Third consecutive Friday, same pattern" — Conrad's qualitative observation |

### Routing Preview (before send)

Below the form, before the Send button:
> "This flag will be sent to the Control Centre (Claudia) as a capacity planning input. It is not an urgent escalation — response may take up to 24 hours."

This framing sets Conrad's expectation: this is not a radio call, it's a structured report. It will be reviewed, not acted on immediately.

### Buttons

| Button | Action |
|--------|--------|
| "Send flag" — 56px height, full width | Submits form; shows `ca-capacity-flag-confirmation` |
| "Cancel" | Dismisses modal; returns to coach detail panel |

---

## New Element: `ca-capacity-flag-confirmation`

**OBJECT ID:** `ca-capacity-flag-confirmation`
**Type:** Confirmation toast (appears over home screen after modal closes)

| Element | Content |
|---------|---------|
| Icon | Checkmark |
| Text | "Capacity flag sent to Control Centre · Ref #[XXXX]" |
| Duration | 4 seconds auto-dismiss |
| Colour | `--color-success-green` background |

The reference number closes Conrad's anxiety loop — his flag is logged, not lost.

---

## Interaction Rules

1. "Flag for capacity review" is shown only when coach occupancy is ≥ 75% AND train is en-route. Not shown during dwell (boarding/alighting) — pattern flags are made from journey observations, not platform chaos.
2. The 7-day trend data requires the historical occupancy data store (7-day retention, same service, same day-of-week). If trend data is unavailable, the trend graph is replaced by "Trend data unavailable for this service" in muted text — the form remains submittable without it.
3. Conrad can add multiple coaches to the flag. The pre-filled coach is the one from the detail panel; additional coaches are selected from the chip picker. The form header updates to "Coaches [N], [M], [P]" as he adds them.
4. The capacity flag is routed to Claudia's Control Centre dashboard (Scenario 04 analytics panel) — not to her operational escalations inbox. It is a different workflow: landside planning, not live incident response.
5. A maximum of one capacity flag per service per conductor per journey is enforced — if Conrad has already flagged this service today, the "Flag for capacity review" row is replaced by "Flagged — ref #[XXXX]" (non-tappable, confirmation state).

---

## Design Rationale

**Why read-only pre-fill for the data fields?**
Conrad's barrier to raising capacity flags is effort — if he has to type the train number, coach number, and occupancy percentage, he won't do it. He has this information in his head but writing it is friction. The system knows all of it already. Pre-fill removes the barrier entirely; Conrad's only input is the optional qualitative note that only he can provide.

**Why is the 7-day trend shown in the form itself?**
Two reasons. First, it validates Conrad's perception — if he thinks "this is always happening," the trend confirms or contradicts that. Second, it makes the submitted flag higher-quality data for Claudia — she receives the trend as part of the report, not just Conrad's assertion that there's a pattern.

**Why "not urgent — response may take up to 24 hours"?**
Conrad's prior experience with informal complaints is that they disappear. By setting the expectation that this is a planning input, not a radio call, we frame the submission correctly: he is not waiting for an immediate response. He will get a reference number; the flag will be reviewed. This is better than the current system where nothing is confirmed at all.

---

## Accessibility (App UI)

- `ca-capacity-flag-form` chip picker for additional coaches uses `role="group"` with individual chips as `role="checkbox"` + `aria-checked`
- Trend graph has `aria-label`: "7-day occupancy trend — [summary text]" — screen reader gets the summary without needing to interpret the visual sparkline
- All form fields have visible labels (not placeholder-only)
- Send button minimum 56px height

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Entry point | "Flag for capacity review" row in `ca-coach-detail-panel` — en-route only |
| Pre-fill scope | Service ID, route, coach, occupancy, time, 7-day trend — all system-populated |
| Conrad's input | Optional note (200 char) + optional additional coaches |
| Routing | Claudia's analytics panel — not operational escalations inbox |
| Confirmation | Reference number toast — 4s auto-dismiss |
| Duplicate prevention | One flag per service per conductor per journey |
| No trend data | Form still submittable; trend graph replaced by "unavailable" message |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the retention period and query scope of the historical occupancy data store? "Same service, same day-of-week, last 7 occurrences" assumed — confirm whether this is per-train-number or per-route-and-time-slot (train numbers change across weeks on recurring services). | Nomad Digital backend / data team |
| 2 | Is the reference number system shared across operational escalations and capacity flags, or are they separate reference series? | Nomad Digital product |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-01-specs/01-conductor-app-home-screen.md` | Base state — `ca-coach-detail-panel` defined here |
| `scenario-04-specs/01-control-centre-analytics-panel.md` | Claudia's view of the submitted capacity flag |
| `2026-05-14-oebb-ux-design-v2.md § Escalate flow` | Separate operational escalation flow — different from this capacity flag flow |
