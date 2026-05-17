# Page Spec — Conductor App: Home Screen (Train Diagram)

**Scenario:** 01 — Conrad Watches the Train Fill
**Interface:** Conductor App (handheld)
**State:** Home Screen — Normal (en-route and platform boarding)
**Base state:** This document IS the base state. All other Conductor App specs reference this as their baseline.
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

The Conductor App home screen is Conrad's primary operational surface. It is the first screen he sees when he opens the app, and it must answer the question "what's happening on my train right now?" within 3 seconds — without any navigation, filtering, or setup.

The home screen serves two distinct operational modes:
1. **En-route mode** — train is moving between stations; occupancy is relatively stable; Conrad monitors for developing issues
2. **Platform boarding mode** — train is at a station; passengers are boarding; occupancy is changing fast; Conrad needs to see load building in real time and be ready to redirect

Both modes use the same home screen layout. The difference is the rate of change in the coach diagram — faster updates during boarding, stable en-route. No mode switch is needed; the screen adapts to what the data shows.

---

## State Flow Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  APP LAUNCH /       │────▶│  HOME SCREEN        │────▶│  COACH DETAIL       │
│  RETURN TO HOME     │     │  NORMAL             │     │  PANEL (tap coach)  │
│                     │     │                     │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
                                      │
                                      ▼ (alert fires)
                             ┌─────────────────────┐
                             │  HOME SCREEN        │
                             │  + ALERT BANNER     │
                             │  (overlay)          │
                             └─────────────────────┘
```

| State | Entry trigger | Exit trigger |
|-------|--------------|-------------|
| **Home Screen — Normal** | App launch; back navigation from any screen; post-alert resolution | Alert fires (banner overlay); coach tap (detail panel) |
| Coach Detail Panel | Tap on any coach in diagram | Back navigation |
| Alert Banner overlay | Alert event detected | Alert resolved / dismissed / escalated |

---

## Home Screen Layout

### Section 1: App Header — `ca-header`

**OBJECT ID:** `ca-header`
**Height:** 56px
**Background:** `--color-surface-elevated`

| Element | Content | Notes |
|---------|---------|-------|
| Train ID | "[Train number]" | e.g. "RJ 123" — large, prominent |
| Route | "[Origin] → [Destination]" | e.g. "Wien Hbf → Salzburg Hbf" |
| Next stop | "Next: [Station] · [N] min" | Updates in real time from TCMS/HAFAS |
| Current time | "[HH:MM]" | Device clock |
| Conductor name | "[First name]" | From login session |
| Connection indicator | Green dot (connected) / amber dot (degraded) / red dot (offline) | Reflects Nomad Digital backend connectivity |

The connection indicator is critical: if the system is offline, Conrad must know immediately so he doesn't act on stale data. The dot is always visible — it does not hide when connected.

---

### Section 2: Active Alert Banner — `ca-alert-banner`

**OBJECT ID:** `ca-alert-banner`
**Height:** 64px (visible) / 0px (hidden when no active alert)
**Visibility:** Shown only when at least one active alert exists

| Element | Content |
|---------|---------|
| Alert icon | Category icon (bag, wheelchair, fire, door, etc.) |
| Alert title | Highest-priority active alert title |
| Alert sub-detail | Coach · location · duration |
| Severity colour | `--color-warning-red` (critical) / `--color-warning-amber` (warning) / `--color-review` (review) / `--color-accessibility` (accessibility) |
| Animation | Pulsing (critical/warning) / slow fade (review) / steady (accessibility) |
| Tap action | Opens alert detail panel for this alert |
| Long-press | "Escalate this" shortcut |
| Badge | If multiple alerts active: "+[N] more" badge on right |

When no alerts are active, `ca-alert-banner` collapses to 0px height — it does not show a "No alerts" state. Absence of the banner IS the "no alerts" signal.

---

### Section 3: Coach Occupancy Diagram — `ca-coach-diagram`

**OBJECT ID:** `ca-coach-diagram`
**Height:** 120px
**This is the primary information surface of the entire app.**

A horizontal row of coach cards representing every coach on the train, left to right in train order (direction of travel). Each coach is a tappable card.

#### Coach Card — `ca-coach-card`

**OBJECT ID:** `ca-coach-card` (one per coach; referenced as `ca-coach-card-[N]` for individual coaches)

| Element | Content | Notes |
|---------|---------|-------|
| Coach number | "[N]" | Large, centred, white text |
| Occupancy fill | Vertical fill bar from bottom, 0–100% | Height proportional to occupancy %; not a colour band |
| Fill colour | `--color-occupancy-green` (<75%) / `--color-occupancy-amber` (75–89%) / `--color-occupancy-red` (≥90%) | Configurable thresholds per operator |
| Luggage icon | Bag icon shown when luggage density exceeds threshold | Icon only — no number at this level |
| Congestion icon | Pulse icon shown when vestibule congestion score exceeds threshold | Icon only |
| Accessibility flag | Wheelchair icon shown when accessibility alert active for this coach | Icon only |
| Alert badge | Red dot (top-right corner) when any active alert references this coach | |
| Tap action | Opens `ca-coach-detail-panel` for this coach | |

**Width:** All coach cards equal width, filling full screen width. On a 10-coach train at 375px screen width, each card is ~37px wide. Coach number displayed at minimum 11sp — confirmed legible at this width. On longer trains (>10 coaches), the diagram scrolls horizontally; current-coach position indicated by a position indicator dot below the scroll area.

**Update rate:** Hailo-8 inference cycle is 15 seconds. Coach card fill and icon overlays update on each inference cycle. During active boarding (doors open signal from TCMS), the update rate increases to 8 seconds — faster feedback when load is changing quickly.

**Reservation overlay:** When expected occupancy (from HAFAS reservation data) differs from actual by ≥ configured threshold (default ±15%), a thin reservation band appears above the fill bar in `--color-reservation` (light purple). This is the "expected vs actual" delta indicator — visible only when anomalous, invisible when within threshold.

---

### Section 4: Coach Detail Panel — `ca-coach-detail-panel`

**OBJECT ID:** `ca-coach-detail-panel`
**Type:** Bottom sheet (slides up from bottom of screen; home screen content visible above)
**Entry:** Tap on any `ca-coach-card`

| Element | Content |
|---------|---------|
| Coach header | "Coach [N]" · occupancy pill (green/amber/red) |
| Passenger count | "[N] passengers (actual)" — large, prominent |
| Reservation count | "[N] reserved" — secondary |
| Delta | "±[N] vs reservation" — amber if over, green if under, grey if within threshold |
| Luggage count | "[N] items detected" |
| Congestion score | "[Low / Medium / High]" — derived from vestibule density inference |
| Accessibility flags | "Wheelchair space [available / occupied]" / "PRM reservation: [Y/N]" |
| Occupancy trend | 5-point sparkline showing last 5 inference cycles (last 75s en-route, last 40s boarding) |
| Active alerts | List of any active alerts referencing this coach |
| Flag for review | "Flag for capacity review" — entry point to Scenario 03 escalation flow |

**Close:** Tap outside panel or swipe down. Returns to home screen with no state change.

---

### Section 5: Unified Alert Feed — `ca-alert-feed`

**OBJECT ID:** `ca-alert-feed`
**Position:** Below coach diagram; scrollable list
**Content:** Both AI services (Passenger AI + Diagnostics AI) sorted by severity then time

Each alert feed item — `ca-alert-feed-item`:

| Element | Content |
|---------|---------|
| Severity dot | Red / Amber / Blue (review) / Blue-teal (accessibility) |
| Category icon | Alert type icon |
| Title | Alert title |
| Sub-detail | Coach · location · duration |
| Timestamp | Time since alert fired |
| Left border colour | Matches severity dot colour |

Tap → alert detail panel for that alert.

**Empty state:** When no alerts are active: "No active alerts" in `--text-tertiary` · centred · 16sp. This is the only place the empty state is shown — the banner is simply absent, but the feed shows explicit confirmation.

---

### Bottom Navigation — `ca-bottom-nav`

**OBJECT ID:** `ca-bottom-nav`

| Tab | Icon | Badge |
|-----|------|-------|
| Home | House icon | — |
| Train | Train icon | — |
| Alerts | Bell icon | Count of active alerts (red badge) |
| Escalations | Shield icon | Count of open escalations (amber badge) |

Active tab indicated by `--color-primary` icon + label. Inactive tabs: `--color-secondary` icon, no label.

**Note:** Diagnostics chat is descoped from the Conductor App — it is part of a separate Technician App. No chat entry point exists in this interface.

---

## Interaction Rules

1. Home screen is the default on app launch and on back navigation from any screen. Conrad never has to navigate to reach the train diagram.
2. The coach diagram scrolls horizontally on trains with more than the screen can display. Scroll position is preserved across app backgrounding and foreground return within the same session.
3. Alert banner always shows the highest-priority active alert. If the highest-priority alert resolves, the next highest takes its place immediately — no animation delay.
4. Coach card icons (luggage, congestion, accessibility, alert badge) are additive — multiple icons can appear simultaneously on a single coach card. Stacking order (top to bottom): alert badge (top-right) > accessibility flag > congestion icon > luggage icon.
5. Tapping a coach card while an alert detail panel is open (from another coach) closes the open panel and opens the tapped coach's panel.
6. The connection indicator changes state within 5 seconds of connectivity change. In offline mode, the coach diagram shows the last known state with a "Last updated [N] min ago" timestamp below the diagram. Conrad is never shown stale data without being told it is stale.
7. "Flag for capacity review" in `ca-coach-detail-panel` is only shown in en-route mode — not during active boarding. Capacity reviews are raised between stops, not during a station dwell.

---

## Design Rationale

**Why is the train diagram the home screen with zero navigation?**
Conrad's primary anxiety is "what's happening in the coaches I can't see." The diagram must be the answer — instantly, without a tap. Every layer of navigation between app-open and train-overview is a moment where Conrad might miss a developing situation. The diagram is not a dashboard feature; it is the app.

**Why vertical fill bars rather than text percentages?**
At 37px card width, a text percentage ("87%") is too small to read while walking. A fill bar communicates quantity through height — Conrad reads it peripherally. Green/amber/red provides the categorical signal; the bar height provides the quantitative one. Together they replace a number he would otherwise have to process consciously.

**Why icons-only on coach cards (no numbers at this level)?**
The diagram must be readable in a single glance. Numbers on a 37px card require reading; icons require recognition. Conrad recognises "luggage icon" in under 200ms; he reads "3 items" in 800ms. At the diagram level, icons are sufficient — the count is available in the detail panel when Conrad taps to investigate.

**Why does the reservation overlay only appear when anomalous?**
A train running at expected occupancy gives Conrad nothing actionable about reservations. The overlay appears only when the delta is significant — when it tells him something he doesn't already know from the fill bar. Clean by default; informative when useful.

**Why is the connection indicator always visible rather than hidden when connected?**
Conrad needs to know the system is working, not just know when it isn't. A permanently visible indicator (green dot = working) builds trust in the data. An indicator that only appears on failure leaves Conrad uncertain about whether the absence of an indicator means "fine" or "not implemented."

---

## Accessibility (App UI)

- `ca-coach-card` colour fill is supplemented by a pattern fill in high-contrast mode — green = diagonal lines (sparse), amber = diagonal lines (medium), red = cross-hatch — ensuring occupancy level is colour-independent
- `ca-coach-card` has `aria-label`: "Coach [N] — [occupancy %] — [Green/Amber/Red] — [alert: yes/no]"
- `ca-alert-banner` uses `role="alert"` — screen reader announces immediately when a new alert appears
- `ca-bottom-nav` tabs use `role="tab"` with `aria-selected`
- All touch targets minimum 44px; coach cards on a 10-coach train are 37px wide — horizontal tap target is met by the row height of 120px (vertical direction) combined with generous vertical touch area

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Home screen content | Train diagram is default; zero taps to reach |
| Occupancy thresholds | 3-band: <75% green / 75–89% amber / ≥90% red. Configurable per operator. |
| Coach card visual | Vertical fill bar + colour + icon overlays — no numbers at diagram level |
| Update rate | 15s en-route; 8s during boarding (doors open) |
| Reservation overlay | Shown only when delta ≥ configured threshold (default ±15%); invisible when within range |
| Connection indicator | Always visible (green = connected) — not hidden when connected |
| Offline mode | Last known state shown with "Last updated [N] min ago" timestamp |
| "Flag for review" | Shown in coach detail panel — en-route only, not during boarding dwell |
| Diagnostics chat | Descoped from Conductor App — separate Technician App. No chat tab or chat entry point in this interface. |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the minimum viable inference update rate during boarding? 8s assumed — confirm with ML team whether Hailo-8 can sustain this rate across all 10 coaches simultaneously without thermal throttling. | Nomad Digital ML team |
| 2 | Is TCMS "doors open" signal reliably available per coach (to trigger the 8s update rate) or only train-level? If train-level only, the 8s rate applies to all coaches simultaneously from first door open. | Systems integration / Stadler |
| 3 | Operator-configurable thresholds — what is the configuration surface? Admin web console assumed — confirm whether ÖBB operations team manages this or Nomad Digital. | Nomad Digital product / ÖBB ops |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `02-pis-exterior-boarding-guidance.md` | PIS exterior screens driven by the same coach occupancy data |
| `scenario-10-specs/01-conductor-app-pre-arrival-dashboard.md` | Pre-arrival mode overlays this base state |
| `scenario-10-specs/02-conductor-app-alighting-mode.md` | Alighting mode overlays this base state |
| `scenario-10-specs/03-conductor-app-boarding-mode.md` | Boarding mode overlays this base state |
| `scenario-02d-specs/01-conductor-app-unattended-item-alert.md` | Alert banner — unattended item variant |
| `scenario-06-specs/01-conductor-app-accessibility-alert.md` | Alert banner — accessibility variant |
| `2026-05-14-oebb-ux-design-v2.md § Interface 1` | UX design v2 overview — this spec is the definitive detail |
| Technician App (descoped) | Diagnostics AI chat and SNMP fault drill-down are part of a separate Technician App — not in scope for this spec set |
