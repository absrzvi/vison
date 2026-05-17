# Page Spec — Conductor App: Vestibule Congestion Alert

**Scenario:** 02 — Conrad Clears a Vestibule Bottleneck
**Interface:** Conductor App (handheld)
**State:** Alert Active — Vestibule Congestion Detected
**Base state:** Home Screen Normal — `scenario-01-specs/01-conductor-app-home-screen.md`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

When Hailo-8 detects passengers bunching in a doorway vestibule beyond a configurable threshold, Conrad receives a **vestibule congestion alert** mid-journey. The alert gives him zone-level detail (not just coach-level), a vestibule heatmap view, and a pre-filled PA action — so he can resolve the bottleneck without walking to the coach first.

The alert auto-resolves when the congestion clears — Conrad does not need to manually close it.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  NORMAL (en-route)   │────▶│  CONGESTION ALERT    │────▶│  AUTO-RESOLVED       │
│                      │     │  ACTIVE              │     │  (congestion clears) │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                        │
                                        ▼ (Conrad sends PA)
                             ┌──────────────────────┐
                             │  PA SENT — MONITORING│
                             │  (alert stays active │
                             │   until sensor clear)│
                             └──────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| Normal | — | Vestibule zone occupancy ≥ threshold AND train NOT within 3 min of scheduled stop |
| **Congestion Alert Active** | Detection threshold + stop-exclusion zone passed | Vestibule zone drops below clear threshold (auto-resolve) |
| Auto-resolved | Sensor clears | Alert removed; "Resolved via PA" or "Resolved — auto" logged |

**Stop exclusion rule:** The alert does not fire within 3 minutes of a scheduled stop. Passengers legitimately gather at doors before alighting — this is not congestion, it is normal behaviour. The 3-minute window is the default; configurable per operator.

---

## Alert Banner — `ca-alert-banner` (congestion variant)

| Element | Value |
|---------|-------|
| Background | `--color-warning-amber` (amber — action required) |
| Icon | Crowd/density icon |
| Title | "Coach 4 vestibule — crowding" |
| Sub-detail | "[N] pax in door zone · Next stop: [N] min" |
| Animation | Pulsing (action required) |
| Tap | Opens `ca-congestion-detail` panel |

---

## New Element: `ca-congestion-detail`

**OBJECT ID:** `ca-congestion-detail`
**Type:** Full-screen detail panel
**Entry:** Tap `ca-alert-banner` (congestion variant) or `ca-alert-feed-item`

### Layout

**1. Header**
- "Coach 4 · Vestibule congestion"
- Sub-header: "[N] passengers in door zone · [N] min to next stop"
- Amber header strip matching alert colour

**2. Zone Heatmap — `ca-congestion-heatmap`**

**OBJECT ID:** `ca-congestion-heatmap`

A schematic top-down view of the coach vestibule zone — not a camera image. A density heatmap derived from Hailo-8 inference, rendered as a coloured overlay on a simple coach silhouette:

| Zone density | Colour |
|-------------|--------|
| Low (0–30%) | `--color-occupancy-green` — transparent wash |
| Medium (31–70%) | `--color-occupancy-amber` — medium wash |
| High (71–100%) | `--color-occupancy-red` — dense wash |

The heatmap shows the vestibule (door end) as a dense orange/red cluster and the mid-coach seating area as green — instantly communicating "people are at the door, seats are empty in the middle." No legend required; the spatial layout is self-evident.

The heatmap updates every 15 seconds (Hailo-8 inference cycle). Conrad can see dispersion happening in real time after sending a PA.

**Privacy note:** The heatmap is an inference-derived density map — not a camera image or video. No individual passengers are identifiable. This is a designed privacy constraint: the same Hailo-8 inference that drives Conrad's occupancy numbers also drives the heatmap, rendered as an anonymised spatial overlay.

**3. Context line**
- "Passengers appear to have pre-positioned for next stop ([N] min away)"
- Auto-generated interpretation from zone + time-to-stop data — gives Conrad a likely explanation before he decides how to respond

**4. Action strip — `ca-congestion-actions`**

**OBJECT ID:** `ca-congestion-actions`

| Action | Label | Pre-fill |
|--------|-------|---------|
| PA announcement | "PA — ask to move back" | "Passengers in coach 4, the next stop is still [N] minutes away — please move away from the doors and use available seating." |
| No action | "Monitor — no action" | Logs "Monitored — no PA sent"; alert stays active until auto-resolve |

**PA Modal — `ca-congestion-pa-modal`:**
Pre-filled text (DE primary, EN option), editable, 200 char max, Send button. On send: modal closes, detail panel shows "PA sent — [HH:MM:SS]". Heatmap continues updating.

**Auto-resolve behaviour:**
When vestibule zone drops below the clear threshold (configurable default: ≤ 30% of alert threshold), the alert auto-resolves. The resolution is logged with one of two codes:
- `RESOLVED_PA` — PA was sent before congestion cleared
- `RESOLVED_AUTO` — Congestion cleared without Conrad action

Both are logged for analytics — the auto-resolve rate indicates false positive rate or passenger self-correction without intervention.

---

## Interaction Rules

1. Alert does not fire within 3 minutes of a scheduled stop (configurable).
2. Alert does not fire if the train is within 5 minutes of the terminus — no point resolving congestion at journey end.
3. Auto-resolve on sensor clear — Conrad does not need to dismiss. This is the key differentiator from manual alert systems: the system cleans itself up.
4. If Conrad sends a PA but congestion does not clear within 5 minutes, the alert remains active — it does not auto-dismiss after a PA. The sensor determines resolution, not Conrad's action.
5. The heatmap is the vestibule zone only — it does not show the full coach. Conrad does not need a full coach view for a vestibule congestion scenario; showing only the relevant zone keeps the display focused.

---

## Design Rationale

**Why a heatmap rather than a number?**
"11 passengers in vestibule" requires Conrad to mentally model the space. The heatmap makes the spatial problem immediately visible — a red cluster at the door, green in the middle. Conrad understands the situation in under 3 seconds without reading the number. The heatmap is an inference rendering, not a camera feed, so it is privacy-safe.

**Why auto-resolve rather than requiring Conrad to close the alert?**
Conrad's alert fatigue risk is high. If every alert requires a manual close action — even after the situation is resolved — he starts ignoring them. Auto-resolve means the alert feed only contains *current* problems. Conrad can trust that an active alert means an active problem. This is the single most important behavioural design decision for the alert system.

**Why pre-fill the PA with the time-to-stop?**
The pre-fill dynamically inserts the actual minutes remaining ("the next stop is still 12 minutes away"). This makes the announcement feel specific and authoritative rather than generic. Conrad sends a message that sounds like he's paying attention — because the system is paying attention for him.

---

## Accessibility (App UI)

- `ca-congestion-heatmap` has `aria-label`: "Vestibule density heatmap — Coach 4 — High density at door zone, low in seating area"
- Heatmap colour zones supplemented by pattern fills in high-contrast mode
- PA modal text area minimum 44px height; Send button minimum 56px

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Alert suppression near stops | 3 min before scheduled stop — configurable |
| Heatmap | Inference-derived density overlay — not camera image |
| Auto-resolve | Sensor-based — not Conrad action-based |
| Resolution logging | `RESOLVED_PA` vs `RESOLVED_AUTO` — analytics feed |
| PA pre-fill | Dynamic time-to-stop insertion |
| Terminus suppression | No alert within 5 min of terminus |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the vestibule zone segmentation accuracy from Hailo-8? The scenario requires zone-level (vestibule vs mid-coach) inference — confirm whether camera placement on R5001C supports this segmentation reliably. | Nomad Digital ML / Hailo integration |
| 2 | What is the configurable threshold for "congestion" — passenger count in zone, or zone density %? Confirm the metric and default value with Nomad Digital product. | Nomad Digital product |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `scenario-01-specs/01-conductor-app-home-screen.md` | Base state — alert banner and feed |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | UX design v2 overview |
