# Page Spec — Maintenance Dashboard: Network Health + Stadler Notification

**Scenario:** 09 — Roland Spots a Degrading L1 Cable Link and Notifies Stadler
**Interface:** Control Centre Dashboard / Maintenance Dashboard (web, tablet-first at ~1280px)
**States covered:** Network Health Tab — Fleet Grid · Per-Train Network View · Stadler Notification Form
**Base state:** Maintenance Dashboard — documented in `2026-05-14-oebb-ux-design-v2.md § Interface 6`
**Date:** 2026-05-14
**Status:** Draft

---

## Purpose

Roland monitors inter-coach cable health across the fleet. When SNMP data shows a degrading or failed L1 link, the platform surfaces the fault in plain language, shows which onboard systems are affected, and gives Roland a pre-populated Stadler notification form — one tap to notify, no SSH, no manual email.

The workflow must complete in under 3 minutes from passive alert to Stadler notification sent.

---

## State Flow Overview

```
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  FLEET GRID          │────▶│  PER-TRAIN NETWORK   │────▶│  STADLER             │
│  (Network Health tab)│     │  VIEW                │     │  NOTIFICATION FORM   │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
                                                                    │
                                                                    ▼
                                                          ┌──────────────────────┐
                                                          │  CONFIRMATION        │
                                                          │  (ref # + fault log) │
                                                          └──────────────────────┘
```

---

## Network Health Tab — `md-network-health-tab`

**OBJECT ID:** `md-network-health-tab`
**Position:** Tab in main Maintenance Dashboard navigation ("Network Health")
**Badge:** Alert count badge when active faults exist

### Fleet Grid — `md-fleet-network-grid`

**OBJECT ID:** `md-fleet-network-grid`

A grid of all active trains (cards), showing network health status. Cards are sorted: faults at top, degraded second, healthy below (not shown — healthy trains are invisible by default).

**Default view: exceptions only.** Trains with all L2 links healthy are not shown in the network health tab — they are not Roland's concern. If all trains are healthy: "All inter-coach links healthy — no faults to review."

#### Fleet network card — `md-fleet-network-card`

**OBJECT ID:** `md-fleet-network-card`

| Element | Content |
|---------|---------|
| Train ID | "[R5001C-017]" |
| Status | Red (fault) / Amber (degraded) / — (healthy, not shown) |
| Fault summary | "Inter-coach cable 4–5: degraded · [N] link-down events" |
| Reported indicator | Envelope icon — "Reported to Stadler" if notification already sent |
| Tap | Opens `md-per-train-network-view` |

---

## Per-Train Network View — `md-per-train-network-view`

**OBJECT ID:** `md-per-train-network-view`
**Type:** Full panel / page (replaces fleet grid or opens as main content)

### Layout

**1. Train header**

| Element | Content |
|---------|---------|
| Train ID | "R5001C-017" |
| Current location | "Currently between [Station A] and [Station B] · Next stop: [Station] · [N] min" |
| Overall health | "Degraded" (amber) / "Fault" (red) pill |
| Health score | "[N]/100" — derived from active fault count and severity |

---

**2. Inter-coach link map — `md-link-map`**

**OBJECT ID:** `md-link-map`

A horizontal chain of coach nodes connected by link segments — a spatial representation of the train's network topology:

```
[C1]──[C2]──[C3]──[C4]──⚠──[C5]──[C6]──[C7]──[C8]──[C9]──[C10]
                         ↑
                   Degraded link
                   Packet loss 6.2%
                   4 drops / 60 min
```

| Element | Spec |
|---------|------|
| Coach nodes | Labelled circles: "C1", "C2", etc. |
| Link segments | Lines between nodes; colour: green (healthy) / amber (degraded) / red (failed) |
| Fault callout | Tooltip/callout on degraded/failed segment: plain-language fault summary |
| Hover/tap | Segment tap → expands to full fault detail panel below |

This is the spatial representation Roland needs — he understands inter-coach topology as a physical chain, not a table. The map confirms which segment is affected without requiring him to read a list.

---

**3. Fault detail panel — `md-fault-detail`**

**OBJECT ID:** `md-fault-detail`
**Shown:** Below the link map, when a fault segment is tapped

| Element | Content |
|---------|---------|
| Plain-language summary | "Inter-coach cable 4–5: signal degraded. Packet loss 6.2% over the past 15 minutes. 4 link-down events in the last hour." |
| Raw SNMP expandable | "View raw SNMP data ↓" — collapsed by default. Expands to OID values for export/reference. |
| Severity | "Amber — degraded (not failed)" |
| Duration | "Degradation detected at [HH:MM:SS] ([N] min ago)" |
| 7-day trend chart | `md-link-quality-chart` — see below |

**7-day link quality chart — `md-link-quality-chart`:**

**OBJECT ID:** `md-link-quality-chart`

A time-series line chart:
- X axis: last 7 days
- Y axis: packet loss % (0–15%)
- Threshold line at 5% (configurable — above this = "degraded")
- Today's data shown to current time; prior days shown as full-day averages
- "No prior degradation on this segment" shown as annotation if 7-day history is clean

---

**4. Affected systems panel — `md-affected-systems`**

**OBJECT ID:** `md-affected-systems`

Automatically derived from the platform's system routing table — which onboard systems use network segments that pass through the affected link:

| System | Status | Notes |
|--------|--------|-------|
| CCTV — Coaches 4, 5, 6 | ⚠️ At risk | Route passes through segment 4–5 |
| PIS interior — Coach 5 | ⚠️ At risk | L2 routing dependency on segment 4–5 |
| Passenger AI — Coaches 4, 5 | ⚠️ At risk | Hailo-8 data uplink may be affected |
| CCTV — Coaches 1–3, 6–10 | ✅ Unaffected | Route does not pass through segment 4–5 |

Only affected and at-risk systems are shown expanded; healthy systems shown as a collapsed "All other systems: unaffected" row.

Roland never manually calculates which systems are affected — the platform derives this automatically from the network topology configuration.

---

**5. Action: Notify Stadler — `md-notify-stadler-btn`**

**OBJECT ID:** `md-notify-stadler-btn`
**Label:** "Notify Stadler"
**Position:** Prominent — full-width button below affected systems panel
**Colour:** `--color-primary` (action — not amber/red; this is a structured workflow, not an emergency alarm)
**Tap:** Opens `md-stadler-notification-form`

---

## New Element: Stadler Notification Form — `md-stadler-notification-form`

**OBJECT ID:** `md-stadler-notification-form`
**Type:** Full-screen modal / full-panel form

### Pre-populated fields (read-only — system-populated)

| Field | Value | Source |
|-------|-------|--------|
| Train ID | "R5001C-017" | TCMS |
| Fault type | "L1 inter-coach cable degradation" | SNMP fault classification |
| Affected segment | "Coach 4–5" | Link map detection |
| SNMP data | Packet loss %, link-down event log (timestamped) — formatted | SNMP data store |
| Affected systems | List from `md-affected-systems` | Platform routing table |
| Current location | "[Between A and B]" | GPS / TCMS |
| Next scheduled stop | "[Station] · [HH:MM]" | HAFAS |
| Severity | "Amber — degraded" (auto-classified) | SNMP threshold |

### Editable fields

| Field | Type |
|-------|------|
| Note | Free text · 200 char · optional — "Seen intermittent drops since 09:42 — recommend inspection at next depot visit or earlier if full failure" |
| Severity override | Dropdown: Amber (degraded) / Red (failed) — auto-classified, Roland can override if his assessment differs |

### Routing preview (before send)

> "This report will be sent to Stadler via [configured endpoint — API / structured email]. A copy will be logged in the platform fault record."

### Buttons

| Button | Action |
|--------|--------|
| "Send to Stadler" — 56px, full width | Submits; shows `md-stadler-confirmation` |
| "Cancel" | Dismisses form; returns to per-train view |

---

## New Element: Stadler Notification Confirmation — `md-stadler-confirmation`

**OBJECT ID:** `md-stadler-confirmation`
**Type:** Confirmation state (inline, replaces the "Notify Stadler" button area)

| Element | Content |
|---------|---------|
| Reference | "Stadler notified · Ref #ST-[XXXX]" |
| Timestamp | "Sent [HH:MM:SS]" |
| Log note | "Fault logged in platform — awaiting Stadler response" |
| Fleet card update | Fleet grid card for R5001C-017 gains envelope icon: "Reported to Stadler · Ref #ST-[XXXX]" |

After confirmation, Roland returns to the fleet grid. The affected train card shows the reported status — Roland can see at a glance which trains have been notified and which haven't.

---

## Full Failure Escalation Path

If the link transitions from amber (degraded) to red (failed) — either before Roland acts or while the notification is pending:

| Change | Behaviour |
|--------|-----------|
| Fleet card | Updates from amber to red automatically |
| Per-train header | Updates to "Fault — link failed" |
| Notification form | If open: severity auto-updates to "Red — failed"; Roland sees the change before sending |
| If already sent | A follow-up notification prompt appears: "Link has failed since initial report. Send updated severity to Stadler?" |
| Push notification | Roland receives a push (tablet) if he's not actively viewing the dashboard: "R5001C-017 — inter-coach link 4–5 FAILED" |

---

## Interaction Rules

1. Raw SNMP data is collapsed by default — Roland's primary workflow uses the plain-language summary. Raw OIDs are available for export or for Roland's reference when he wants to verify the translation.
2. The affected systems derivation is automatic — Roland does not confirm or curate the list. If the platform's routing table is incorrect, the affected systems list may be wrong — this is a data quality dependency, not a UX flaw.
3. Roland can send multiple Stadler notifications for the same fault (e.g., severity escalation from amber to red). Each sends a new notification with a new reference number. The fault record in the platform links all notifications to the same fault event.
4. The "Notify Stadler" button is always available from the per-train view — Roland is not forced to review all panels before notifying. He can notify as soon as he has enough context.
5. The dashboard is tablet-first at ~1280px landscape — all elements must be fully operable without a mouse. Minimum touch targets 44px throughout.

---

## Design Rationale

**Why plain language rather than raw SNMP?**
Roland understands SNMP data — but reading "IF-MIB::ifOperStatus.4 = down(2)" while trying to write a Stadler notification is a context switch. The plain language translation lets him understand the fault at a glance; the raw data is available for verification without being the primary presentation. Roland should not need to remember OID mappings to do his job.

**Why spatial link map rather than a fault table?**
Inter-coach cables are physical — coach 4–5 means the physical cable between those two coach bodies. A table entry "Segment 4-5: DEGRADED" is accurate but requires Roland to mentally map it to the train. The spatial chain makes the location immediately obvious — he sees which joint in the chain is affected. For a fleet manager who thinks physically about train topology, this is the right information model.

**Why automatic affected systems derivation?**
The platform knows the network topology and which systems route through which segments. Requiring Roland to manually look up which systems use segment 4–5 would be: (a) slow, (b) error-prone, (c) the exact manual work the platform is designed to eliminate. Automatic derivation is both faster and more reliable.

**Why "Notify Stadler" is a `--color-primary` button rather than amber/red?**
The notification is a structured workflow action — it is not an emergency alarm trigger. Making it amber or red would imply urgency that may not be appropriate (Roland is notifying a supplier about a degraded cable, not triggering an emergency stop). Primary blue communicates "this is the main action to take" without implying alarm.

---

## Accessibility (Dashboard UI)

- `md-link-map` has `aria-label`: "Inter-coach link map — R5001C-017 — fault on segment 4–5"
- Each link segment has `role="button"` with `aria-label`: "Link [C4]–[C5] — degraded — tap for details"
- `md-affected-systems` table has proper `<thead>` and `<th>` structure for screen reader traversal
- All form fields have visible labels
- Fault detail panel expansion announced via `aria-expanded`

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Fleet grid default | Exceptions only — healthy trains not shown |
| SNMP presentation | Plain language primary; raw SNMP collapsed/expandable |
| Affected systems | Automatically derived — not manually curated by Roland |
| Severity classification | Automatic (SNMP threshold); Roland can override |
| Notification form | Pre-populated; Roland adds optional note only |
| Full failure escalation | Auto-updates severity; follow-up notification prompt |
| Tablet-first | ~1280px landscape; all targets 44px minimum |
| Reference numbering | Per-notification; fault record links all notifications to one event |

## Open Questions

| # | Question | Owner |
|---|----------|-------|
| 1 | What is the Stadler notification endpoint? "Structured API or structured email" — confirm format (JSON payload to API vs formatted email to a ticket system). This determines how the "Send to Stadler" action is implemented. | Stadler / Nomad Digital integration |
| 2 | What is the L2 network topology map source? "OID list to confirm with Stadler" per scenarios index — this is required for the link map and affected systems derivation. | Stadler |
| 3 | What is the historical SNMP data retention period? "Confirm retention period" per scenarios index — required for the 7-day trend chart. | Nomad Digital data governance |
| 4 | Is the system routing table (which systems use which switch segments) a Nomad Digital internal config, or does it require Stadler-provided data? Affects how the affected systems panel is maintained across fleet variants. | Nomad Digital infrastructure / Stadler |

---

## Related Specs

| Spec | Relationship |
|------|-------------|
| `2026-05-14-oebb-ux-design-v2.md § Interface 6` | Base Maintenance Dashboard spec |
| `2026-05-13-oebb-hailo8-ai-service-design.md` | AI service architecture — Diagnostics AI (SNMP feed) |
