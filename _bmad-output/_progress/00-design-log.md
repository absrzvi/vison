# Design Log — OEBB Smart Rail

**Project:** OEBB Smart Rail
**Started:** 2026-05-16
**Focus (current):** Control Centre Dashboard — all views

---

## Backlog

| Priority | Item | Scenario(s) | Notes |
|---|---|---|---|
| 1 | Control Centre — Live monitoring view | 12, 02d, 03 | Default view. Fleet list, KPI strip, escalations inbox, incident feed. |
| 2 | Control Centre — System Health tab | 11, 09 | VLAN 5 + container health fleet-wide. Read-only, deep-link to Maintenance App. |
| 3 | Control Centre — Analytics tab | 04, 03 | Morning occupancy review. Already partially specced in scenario-04-specs/. |
| 4 | Control Centre — Train detail drill-in | 12 | Coach grid, alert list, active escalations per train. |

---

## Current

| Task | Started | Notes |
|---|---|---|
| — | — | — |

---

## Design Loop Status

| Date | Scenario | Page | Status |
|---|---|---|---|
| 2026-05-16 | 04 | cc-analytics-panel | draft (from prior session) |
| 2026-05-16 | 02d | cc-unattended-item-escalation | draft (from prior session) |
| 2026-05-16 | 12 | cc-live-monitoring | discussed |
| 2026-05-16 | 12 | cc-live-monitoring | wireframed |
| 2026-05-16 | 12 | cc-live-monitoring | specified |
| 2026-05-16 | 11 | cc-system-health | specified |
| 2026-05-16 | 04 | cc-analytics-panel | specified |
| 2026-05-16 | 12 | cc-train-detail | specified |

---

## Log

| 2026-05-16 | cc-live-monitoring | 12.1 | approved |
| 2026-05-16 | cc-train-detail | 12.2 | approved |
| 2026-05-16 | cc-system-health | 11.1 | approved |
| 2026-05-16 | cc-analytics-panel | 04.1 | approved |

## Log

| Date | What was done |
|---|---|
| 2026-05-16 | Design log created. Scenarios 11 + 12 written. Scenario 09 redefined. Control Centre Phase 4 scope established. Prior session specs (04, 02d) carried forward as drafts. |
| 2026-05-16 | Acceptance testing [T] run against locked prototype. 8 gaps found and resolved. All 4 views approved: cc-live-monitoring, cc-train-detail, cc-system-health, cc-analytics-panel. |
| 2026-05-16 | Freya (UX agent) iterative review sessions — all 5 tabs assessed and improved. See DD-001 §6 for full change log. |
| 2026-05-16 | Design documentation updated to reflect locked prototype. `01-control-centre-analytics-panel.md` fully rewritten — all 4 sub-tabs specified. `DD-001` §3.6 updated (route grouping, coach chart, AI detection patterns, uptime range, heatmap accessibility). Prototype approximations #14–19 added. |

## Freya Review Iterations (2026-05-16)

### Occupancy Tab
- Passenger flow animation between coaches (directional dots, left/right)
- Coach click → inline detail panel (seat map, door congestion bar, 6 stats)
- Auto-select first coach on load; resets on train change
- Removed sparkline ("Last 8 Readings")
- Metrics restyle: no emojis, label-on-top, dividers

### Live Tab (Freya assessment → all implemented except 2 deferred)
- Active alert rows in TrainDetail now open full EscalationDetail with real escalation data
- Route delay shown in TrainDetail header
- Auto-select prefers red > amber > highest occupancy
- Fleet list: removed deselect-on-click toggle
- EscalationDetail redesigned: severity accent bar, meta strip, still frame overlaid chips, sticky footer
- Deferred: escalation audit/timeline view, green-train collapse (Phase 2)

### Luggage Tab (Freya assessment → all implemented)
- Map removed — live tab only
- Feed cards grouped by train (collapsible train header with ID, event count, next station, drill-in)
- KPI strip: "Longest Open" split into "Longest Unattended" (red) + "Longest Active" (amber)
- Filter pills show live event counts
- Confidence chips colour-coded: green ≥85% / amber ≥70% / red below
- Elapsed time on every card; next station in train row
- Unattended cards pulsing red border; door risk flag
- Resolved cards collapse to disclosure row (not in active feed)
- EscalationDetail: still frame timestamp chip; "View on Live tab" upgraded to secondary button with navigation

### EscalationDetail (Freya assessment → all implemented)
- Severity accent bar (3px top, colour from severity)
- Status pill next to source badge
- Meta bar: TRAIN · COACH · TIME · ELAPSED
- Description in left-border accent block
- Still frame: camera chip top-left, timestamp chip bottom-left, confidence chip top-right
- Sticky footer: Acknowledge + "📹 View on Live tab" secondary button

### System Health Tab (two Freya assessment rounds → all implemented)
- Round 1: Per-row severity left-border; inline side panel (replaces modal); persistent ticket-raised chip on grid row; amber app status now shows container drill-down; live-tick last-update counter; elapsed duration in Since column; appDetail data model (per-container status + notes); larger close button; Since "—" tooltip; summary tile colour reflects worst fleet severity; Train Link row (status + last seen)
- Round 2: Two-step ticket confirmation (Confirm/Cancel inline); real wall-clock elapsed (replaces hardcoded 11:35); Train Link row always rendered (shows "No data" when missing); app healthy count fixed (green-only); ticketed row opacity removed (chip-only indicator, no emoji); panel spacing standardised; summary tile label layout shift fixed
