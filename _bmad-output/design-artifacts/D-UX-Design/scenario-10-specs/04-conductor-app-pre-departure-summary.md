# Page Spec — Conductor App: Pre-Departure Summary

**Scenario:** 10 — Station Dwell: Full Embarkation & Disembarkation
**Interface:** Conductor App (handheld)
**State:** Home Screen — Pre-Departure Summary
**Base state:** Home Screen — Boarding Mode (`03-conductor-app-boarding-mode.md`)
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

At T-2min before scheduled departure, the home screen transitions into **Pre-Departure Summary** — a compressed, all-coach status view that replaces the full diagram. Conrad sees every coach in a single scannable table, any unresolved alerts flagged inline, and a single large confirmation button. One tap logs his go/no-go decision and closes the dwell window.

The pre-departure summary is the formal close of the station stop from Conrad's perspective. It creates an auditable departure readiness record.

---

## State Flow

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  BOARDING MODE      │────▶│  PRE-DEPARTURE      │────▶│  HOME — NORMAL      │
│  (active dwell)     │     │  SUMMARY            │     │  (en-route)         │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
                                      │
                                      ▼
                             ┌─────────────────────┐
                             │  DOOR OBSTRUCTION   │
                             │  EDGE CASE          │
                             │  (if alert fires    │
                             │   at T-30s)         │
                             └─────────────────────┘
```

| Entry trigger | Dwell timer reaches T-2min before scheduled departure |
| Exit trigger (normal) | Conrad taps "Doors clear — ready to depart" |
| Exit trigger (delay) | Door obstruction resolves + Conrad confirms clear |
| Post-exit state | Home — Normal (en-route) |

---

## State 5: Pre-Departure Summary — Differences from Boarding Mode

> **The Story:** Two minutes out. The full coach diagram slides up and is replaced by a compact table — ten rows, one per coach, each showing the final load number and a status dot. Nine coaches are amber or below. Coach 6 has a small alert icon — a door obstruction detected 25 seconds ago. Conrad is already walking there. He clears the bag. The obstruction resolves. The alert icon disappears. He taps "Doors clear — ready to depart." The train leaves 45 seconds late. The delay is logged against the door obstruction, not as unexplained.

| Property | Value |
|----------|-------|
| Purpose | Give Conrad a final all-coach check in one glance and capture his formal departure readiness decision |
| Entry | T-2min auto (or manual trigger — see interaction rules) |
| Previous | Boarding Mode |
| Next | Home — Normal (en-route) |

### Changes from Boarding Mode

| OBJECT ID | Change | Details |
|-----------|--------|---------|
| `ca-coach-diagram` | Replaced | Full visual train diagram slides up (exit animation) and is replaced by `ca-predeparture-table`. The diagram is not accessible during pre-departure summary — Conrad cannot tap into individual coach detail until after he confirms departure or manually exits the summary. |
| `ca-coach-boarding-rate` | Cleared | Boarding rate indicators removed. Boarding is effectively over. |
| `ca-coach-projected-load` | Cleared | Projected load bars removed. Actual load is now the only relevant number. |
| `ca-forecast-alert` | Cleared | Any active forecast alerts are dismissed automatically. If a coach is genuinely over threshold at T-2min, it appears as an actual occupancy alert in the pre-departure table, not a forecast. |
| `ca-dwell-timer` | Modified | Transitions to departure countdown: "Departing in 2:00" in `--color-warning-amber`. At 60s: `--color-warning-red`. Timer now counts to departure, not end of dwell. |
| `ca-alert-banner` | Retained | Active incident alerts remain in banner slot. The pre-departure summary does not suppress real alerts. A door obstruction at T-30s will appear here. |

### New Elements in Pre-Departure Summary

---

#### Pre-Departure Coach Table

**OBJECT ID:** `ca-predeparture-table`

| Property | Value |
|----------|-------|
| Component | Full-width table, replaces coach diagram area. Fixed height — all coaches visible without scrolling on standard handheld screen (min 375px width). |
| Rows | One row per coach, ordered 1 → N (front to rear) |
| Columns | Coach number · Load % · Status dot · Alert icon (if applicable) |
| Load % | Actual current occupancy as percentage of capacity. Colour: green (<75%) · amber (75–89%) · red (≥90%). |
| Status dot | Green = no issues · Amber = at threshold but no alert · Red = active unresolved alert on this coach |
| Alert icon | Appears only if coach has an unresolved active alert. Icon reflects alert type (door obstruction, unattended bag, accessibility). Tap row → alert detail sheet for that coach. |
| No-alert coaches | Status dot only, no icon. Row is tappable but tap opens coach summary (load, count) not an alert. |
| Overloaded coach | Row background tinted red, load % in bold red. Does not block departure confirmation — Conrad may choose to depart with an overloaded coach, but the state is recorded. |

---

#### Departure Readiness Button

**OBJECT ID:** `ca-departure-ready-btn`

| Property | Value |
|----------|-------|
| Component | Full-width primary button, fixed to bottom of screen above bottom navigation |
| Height | 64px — largest tap target in the app |
| Label | "Doors clear — ready to depart" |
| Colour (default) | `--color-success-green` background, white label |
| Colour (blocked) | `--color-disabled-grey` background — shown when one or more coaches have an active unresolved **door obstruction** alert. Label changes to "Resolve door alerts before departing." Other alert types (unattended bag, accessibility) do not block the button — Conrad may depart with these logged. |
| Tap (enabled) | Triggers `ca-departure-confirmation-modal` |
| Tap (disabled) | Tap shows a brief tooltip: "Door obstruction on Coach [N] — resolve before departing." Routes Conrad's attention to the alert without blocking navigation. |

---

#### Departure Confirmation Modal

**OBJECT ID:** `ca-departure-confirmation-modal`

| Property | Value |
|----------|-------|
| Component | Full-screen modal overlay |
| Trigger | Tap of enabled `ca-departure-ready-btn` |
| Content | "Confirm departure readiness" heading · Snapshot table (same as `ca-predeparture-table` but read-only, no tap) · Any active non-blocking alerts listed with status · "Confirm departure" primary button · "Back — not ready" secondary link |
| "Confirm departure" tap | Logs departure readiness event (see Logged Event below) · Dismisses modal · Transitions app to Home — Normal (en-route) · Fires departure toast |
| "Back — not ready" tap | Dismisses modal, returns to pre-departure summary. No event logged. |
| Purpose | One confirmation step prevents accidental departure confirmation from a mis-tap on the large button. Not a double-confirmation ritual — it surfaces the snapshot one more time so Conrad can see what he is signing off. |

---

#### Departure Readiness Logged Event

**OBJECT ID:** `ca-departure-event-log`

On confirmation, the following is written to the journey log:

| Field | Value |
|-------|-------|
| Event type | `departure_readiness_confirmed` |
| Timestamp | UTC + local |
| Conductor ID | Conrad's authenticated ID |
| Train ID | Current train |
| Stop | Station name + stop sequence number |
| Scheduled departure | From ÖBB schedule |
| Actual departure | Logged when train begins moving (GPS) |
| Delay (s) | Actual − Scheduled (negative = early) |
| Delay attributed to | If a door obstruction alert resolved within the last 120s: attributed automatically. Otherwise: "unattributed." |
| All-coach snapshot | Final load % per coach at confirmation time |
| Active alerts at departure | List of any alerts that were open when Conrad confirmed (non-blocking) |
| Remote-monitoring decisions | Any "Monitor remotely" taps from Boarding Mode, carried forward |

---

#### Departure Confirmation Toast

**OBJECT ID:** `ca-departure-toast`

| Property | Value |
|----------|-------|
| Component | Toast notification, bottom of screen, 4s auto-dismiss |
| Trigger | Departure confirmation logged |
| Content | Checkmark icon · "Departure confirmed · [Station] · [Time]" |
| Colour | `--color-success-green` |
| Tap | Dismisses early. No navigation. |

---

#### Door Obstruction Edge Case (T-30s)

**OBJECT ID:** `ca-door-obstruction-late`

This is a distinct state within Pre-Departure Summary — it does not replace the summary, it overlays an urgent alert.

| Property | Value |
|----------|-------|
| Trigger | Hailo-8 detects door obstruction on any coach with ≤60s to departure |
| Alert banner | Takes banner slot — solid red, pulsing. Icon: door/obstruction. "Door obstruction · Coach [N] · Item in doorway." |
| Haptic | Device vibration pattern: 3 short pulses (distinct from standard alert single pulse). Conrad feels this in his pocket. |
| Audio | System alert sound (if Conrad's device is not on silent). Cannot be suppressed for door obstruction alerts — safety-critical. |
| Effect on departure button | `ca-departure-ready-btn` transitions to disabled state immediately. Conrad cannot confirm departure while a door obstruction is active. |
| Resolution | Conrad physically clears the obstruction. Hailo-8 detects clearance on next inference cycle (≤15s). Alert auto-resolves. Departure button re-enables. |
| Manual override | Not available. Door obstructions at T-60s or later cannot be manually dismissed — only physical resolution clears them. |
| Delay logging | When obstruction resolves and Conrad subsequently confirms departure, delay is auto-attributed to door obstruction event. Conrad does not fill in a delay reason form. |

---

## Interaction Rules

- **Manual entry into pre-departure summary** — Conrad can swipe up on the dwell timer at any point during Boarding Mode to manually enter the summary early. Useful at uncrowded stops where boarding is clearly complete before T-2min.
- **Return to boarding mode** — Conrad can tap "Back to boarding view" (small text link, above the table) to return to the full diagram during pre-departure summary, if he needs to investigate a coach. This does not cancel the departure countdown.
- **Departure button is never hidden** — even when disabled it remains visible and tappable (showing the tooltip). Conrad must always know what is blocking him.
- **Non-blocking alerts at departure** — unattended bag alerts, accessibility alerts, and occupancy alerts do not block the departure button. They appear in the confirmation modal so Conrad consciously acknowledges departing with them open. They are logged as "active at departure."
- **If Conrad does not confirm** — the pre-departure summary does not expire or force-confirm. If the train departs (GPS movement detected) without Conrad's tap, a `departure_unconfirmed` event is logged. This is a flag for operations, not an error state for Conrad.

---

## Design Rationale

**Why replace the full diagram with a table?**
The full diagram is optimised for spatial navigation — finding which coach to walk to. At T-2min, Conrad is no longer navigating; he is checking. A table is faster to scan top-to-bottom than a horizontal diagram where he has to read each bar. The information density per vertical pixel is higher.

**Why is only door obstruction a hard block on departure?**
Door obstruction at departure speed is a safety hazard — an item or person caught in a closing door. All other alert types (unattended bag, overcrowded coach, accessibility need) are serious but do not create an immediate physical risk from departing. Conrad is trained to make that judgement call. The system enforces the one case where there is no judgement to make.

**Why one-tap confirmation with a modal, not two separate buttons?**
A single large button with a confirmation modal is faster than two sequential buttons and reduces mis-tap risk. The modal shows Conrad what he is confirming — the snapshot — not just "are you sure?" It is a meaningful check, not a friction ritual.

**Why auto-attribute delay to door obstruction?**
Delay attribution today is manual, inconsistent, and stressful for conductors who feel blamed. Auto-attribution from the event log removes the burden and creates accurate data for ÖBB. Conrad benefits directly: the record shows the delay had a cause he responded to, not a cause he missed.

---

## Accessibility

- `ca-predeparture-table` rows are fully accessible via focus traversal. Each row `aria-label`: "Coach [N]: [X]% load, [status], [alert description or 'no alerts']."
- `ca-departure-ready-btn` disabled state announced as "Resolve door alerts before departing" via accessibility API — not just visually greyed.
- Door obstruction haptic pattern (3 short pulses) supplements audio and visual — Conrad may have gloves, be in a noisy environment, or be looking away.
- Confirmation modal: "Back — not ready" link meets minimum touch target size despite being a secondary action.

---

## Resolved Decisions

1. **Departure button block scope** — ✅ Fire/smoke alerts added to the hard-block set alongside door obstruction. Both are safety-critical conditions where there is no conductor judgement call to make. ÖBB safety team to formally confirm during pilot sign-off.
2. **`departure_unconfirmed` event visibility** — ✅ Surfaced to Claudia's Control Centre as a low-priority advisory: "Train [X] departed [Station] without readiness confirmation." Not an alarm — no push notification, no escalation. Log entry only, visible in the fleet list train card detail view.
3. **Manual early entry threshold** — ✅ No minimum time floor. Conrad can enter pre-departure summary at any point during Boarding Mode. If dwell timer shows more than 2 minutes remaining when he enters manually, the departure button label changes to "Confirm early departure" as a caution signal. No other restriction.

---

## Naming Note

`ca-door-obstruction-late` is described both as a named state ("a distinct state within Pre-Departure Summary") and as an OBJECT ID for the alert element that appears in that state. The dual usage is intentional — the state has no separate screen; it is the pre-departure summary with an overlay alert. The OBJECT ID refers specifically to the alert element (`ca-door-obstruction-late`), not the summary screen itself. If this causes implementation ambiguity, the element may be renamed `ca-door-obstruction-predeparture-alert` without design impact.

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `03-conductor-app-boarding-mode.md` | Previous state |
| `05-pis-exterior-dwell-states.md` | Parallel — PIS switches back to route/destination display when departure confirmed |
| `06-passenger-portal-dwell-states.md` | Parallel — portal switches to journey mode on departure confirmation |
