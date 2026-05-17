# Page Spec — Bistro App: Trolley Routing View

**Scenario:** 08 — Brigitte Routes Her Trolley Mid-Journey
**Interface:** Bistro Staff App (tablet or handheld)
**State:** Trolley Routing View
**Base state:** Bistro App Home Screen — `scenario-07-specs/01-bistro-app-pre-departure.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Mid-journey, Brigitte needs to decide which coaches to push the trolley through first. She wants to hit the busiest coaches while passengers are settled and in buying mode — not waste the first pass on empty coaches. The trolley routing view gives her a ranked list: heaviest coaches at the top, lightest at the bottom, updating at each station stop.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  HOME SCREEN         │────▶│  TROLLEY ROUTING     │────▶│  HOME SCREEN         │
│  (mid-journey)       │     │  VIEW                │     │  (return)            │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Home Screen | — | Brigitte taps "Trolley route" |
| **Trolley Routing View** | Tap "Trolley route" | Back navigation |

---

## New Element: `ba-trolley-routing-view`

**OBJECT ID:** `ba-trolley-routing-view`
**Type:** Full-screen view (navigates from home screen)
**Entry:** Tap "Trolley route" action on home screen (persistent bottom action bar or prominent home screen card)

### Header — `ba-trolley-header`

**OBJECT ID:** `ba-trolley-header`

| Element | Content |
|---------|---------|
| Title | "Trolley route" |
| Subtitle | "Sorted by passenger count — highest first" |
| Last updated | "Updated [N] sec ago" |
| Next stop | "Next stop: [Station] · [N] min" |

---

### Coach Ranking List — `ba-trolley-coach-list`

**OBJECT ID:** `ba-trolley-coach-list`

A vertically scrollable ranked list of all coaches, sorted by current passenger count descending. Each row is a `ba-trolley-coach-row`.

#### `ba-trolley-coach-row`

**OBJECT ID:** `ba-trolley-coach-row`

| Element | Content | Notes |
|---------|---------|-------|
| Rank | "[1]" — large, left-aligned | Position in the sorted list |
| Coach number | "Wagen [N] / Coach [N]" | Prominent — Brigitte navigates by coach number |
| Passenger count | "[N] pax" — large (32sp) | The primary data point |
| Occupancy bar | Horizontal fill bar, green/amber/red | Visual reinforcement of count |
| Distance indicator | "[N] coaches away" from bistro car | Helps Brigitte trade off richness vs walking distance |
| Bistro car marker | "← You are here" on the bistro coach row | Fixed position in list, not ranked |

**Sorting:** By passenger count descending, updated at each station stop. During between-stop en-route segments, the sort order is stable (does not re-sort continuously — only at stops, when boarding/alighting changes the ranking meaningfully).

**Between-stop behaviour:** List shows the last-stop ranking with a "Sorted at last stop · [Station]" subtitle. Brigitte is mid-trolley-run between stops — she does not need real-time re-ranking while she's already in motion.

---

### Stop Re-sort Prompt — `ba-trolley-resort-prompt`

**OBJECT ID:** `ba-trolley-resort-prompt`

At each station stop (TCMS doors-open signal), a banner appears at the top of the list:

> "Train stopped at [Station] · Tap to update route"

Tap → list re-sorts based on new occupancy data (post-boarding/alighting). The prompt is a tap-to-refresh rather than automatic — Brigitte chooses when to re-sort, typically between the doors closing and her next trolley pass. Automatic re-sorting mid-list would be disorienting.

---

## Interaction Rules

1. Trolley routing view is mid-journey only. It is accessible from the home screen at any time but is most relevant between the first station stop and the penultimate stop (no value in routing at the last stop before terminus).
2. The bistro car row is always visible in the list (pinned) with "← You are here" — Brigitte uses it as a spatial anchor when scanning coach distances.
3. Coach rows are not tappable — there is no detail drill-down in this view. The only decision Brigitte makes is "which coach do I go to first." No further data is needed.
4. The distance indicator ("3 coaches away") is a simple absolute count — not a time estimate. Brigitte knows how long it takes to push a trolley through a coach better than any algorithm does.
5. Re-sort is tap-triggered at stops — not automatic. List stability during en-route periods protects Brigitte's mental route plan from being invalidated mid-trolley-run.

---

## Design Rationale

**Why sorted list rather than a map/diagram?**
The home screen already has the coach diagram. In the trolley routing view, the decision is sequential: "Coach 3 first, then 4, then 8." A ranked list is the right information shape for a sequential decision — a diagram requires Brigitte to mentally rank the colours herself. The list does that for her.

**Why tap-to-refresh rather than automatic re-sort at stops?**
If the list re-sorted automatically every time the train stopped, Brigitte would see the list rearrange while she's mid-route — potentially while she's standing in coach 4 with the trolley. Automatic re-sort is disorienting and can invalidate a plan she's mid-way through executing. Tap-to-refresh gives her control over when she adopts the new ranking.

**Why show distance from bistro car?**
Brigitte has to physically push a heavy trolley through multiple coaches. Coach 3 might have 52 passengers, but if it's 6 coaches away and coach 8 has 44 and is adjacent — she might prefer coach 8 first. The distance indicator lets her make that tradeoff explicitly without walking to check.

---

## Accessibility (App UI)

- `ba-trolley-coach-list` uses `role="list"` with `aria-label="Coach ranking by passenger count"`
- Each `ba-trolley-coach-row` uses `role="listitem"` with `aria-label`: "Rank [N] — Coach [N] — [N] passengers — [N] coaches away"
- Occupancy bars use `aria-label` with text equivalent (not relied on as the sole data source — count is also shown as text)
- Tap-to-refresh prompt uses `role="alert"` — announced when stop is detected

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Sort order | Passenger count descending — updated at station stops, stable between stops |
| Re-sort trigger | Tap-to-refresh at stops — not automatic |
| Coach row tap | Not tappable — no drill-down; decision is sequential, not investigative |
| Distance indicator | Absolute coach count from bistro car — not time estimate |
| Bistro car row | Always shown, pinned — spatial anchor |
| Between-stop label | "Sorted at last stop · [Station]" — transparency about data freshness |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | Is Hailo-8 occupancy data available per-coach during en-route segments (not just at stations)? The per-coach passenger count in the trolley list should reflect current occupancy, not last-boarding count. Confirm inference availability mid-journey. | Nomad Digital ML team |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-07-specs/01-bistro-app-pre-departure.md` | Home screen — base state, entry point to this view |
| `2026-05-14-oebb-ux-design-v2.md § Interface 3` | Bistro App UX design v2 overview |
