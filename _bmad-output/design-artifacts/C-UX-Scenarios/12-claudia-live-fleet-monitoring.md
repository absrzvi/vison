# Scenario 12 — Claudia Monitors the Live Fleet and Resolves an Escalation

**Persona:** Control Centre Claudia (primary)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-16

---

## Core Feature

Live fleet monitoring — Claudia's primary operational mode. She watches the fleet in real time: occupancy across all trains, active AI alerts, and incoming escalations from Conrad and onboard staff. When something needs action, she acknowledges and resolves it directly from the dashboard. This is not a periodic review — it is continuous, ambient monitoring throughout her shift.

---

## Entry Point

Claudia arrives at her workstation at the start of shift. The Control Centre Dashboard opens to the live monitoring view by default — the System Health tab and Analytics tab are secondary. The live view is what she looks at all day.

---

## Mental State

**Trigger:** Start of shift, or return from break. Claudia needs to re-establish situational awareness across the fleet within 60 seconds.
**Hope:** That the view surfaces the things that need attention without requiring her to scan every train card. Problems should come to her, not the other way around.
**Worry:** That a genuine incident — a fall, a door obstruction, an unattended bag — is buried beneath lower-priority alerts and she responds late. Or that she's flooded with false positives and starts ignoring the feed.

---

## Sunshine Path — Quiet Shift

1. Claudia opens the dashboard. KPI strip shows: 14 active trains · avg 62% occupancy · 0 open incidents · 2 open escalations (both amber, no action required yet).
2. Fleet list shows all 14 trains, sorted by severity. All are green or amber — no red.
3. Claudia scans the escalations inbox: Conrad on train 017 flagged a chronic overcrowding pattern (Scenario 03 — capacity flag, not urgent). Roland's technical note on train 022 is shown in muted style below.
4. Nothing requires immediate action. Claudia returns to monitoring. The dashboard updates in real time.

---

## Exception Path — Active Incident

1. Mid-shift: the escalations inbox pulses. A new item appears at the top with an **AI badge**: "Unattended item — Coach C4 · Train R5001C-031 · Detected 11:23". This is an AI-direct escalation — no Conrad needed, the AI surfaced it.

2. Simultaneously the fleet list card for R5001C-031 updates: status badge changes to **Alert** (red). The mini coach bar shows a luggage icon on C4.

3. Claudia taps the escalation. The detail panel opens:
   - Still frame from the moment of detection (C4 overhead camera)
   - Detection confidence: 94%
   - Item type: unattended bag
   - Duration: 8 minutes unattended
   - Conrad's status: notified (Conductor App push sent at 11:23)
   - Conrad's response: "Investigating — 2 min" (received 11:24)

4. Claudia taps **Acknowledge** → Conrad receives push: "Control Centre aware — Claudia acknowledged."

5. Two minutes later Conrad updates: "Owner located — bag retrieved." Claudia taps **Resolve** → resolution form:
   - Outcome text: "Owner located, item retrieved by Conrad. No further action."
   - Action tag: "Passenger assisted"
   - Submit → Conrad receives push with outcome. Escalation moves to Resolved.

6. R5001C-031's fleet card returns to green. The incident is logged.

---

## Exception Path — Conrad Capacity Flag During Live Shift

1. Conrad raises a capacity flag mid-journey on train 017 (Scenario 03 flow).
2. It appears in Claudia's escalations inbox — below any AI-direct escalations, amber severity, labelled "Capacity flag · Conrad · Train 017."
3. Claudia taps it: Conrad's note + 7-day trend chart. She sees the pattern — third consecutive Friday, coaches 3–4.
4. She taps **Acknowledge** → Conrad receives push. She then opens the Analytics tab (Scenario 04) to review the historical data and log a capacity review request.
5. Escalation marked "In review" in the inbox.

---

## Success Goals

**Claudia:** Maintains situational awareness across 14+ trains without being overwhelmed. AI-direct escalations reach her immediately and with enough context to act. She never has to ask Conrad "what's the status?" — the dashboard tells her.
**Conrad:** Knows Claudia has seen his escalations. Gets confirmation and outcome back without chasing.
**Business (Nomad Digital):** Demonstrates that the platform replaces radio-based operational coordination with a structured, auditable escalation loop — the core commercial value proposition for fleet operators.

---

## Trigger Map Connections

- ✅ Claudia: Make defensible decisions — every escalation carries evidence (still frame, confidence score, occupancy data)
- ✅ Claudia: Reduce radio dependency — structured escalation replaces voice calls
- ✅ Claudia: Fear missing safety-critical incident — AI-direct escalations (fall, fire, unattended item) surface at top of inbox with AI badge, above staff-raised items
- ❌ Claudia: Fear alert overload — AI-direct escalations are high-confidence only (configurable threshold); lower-confidence events stay in the incident feed, not the escalations inbox
- ❌ Conrad: Fear his reports disappear — acknowledgement + outcome pushed back to Conrad

---

## Design Notes

- **Escalations inbox is Claudia's primary action surface** — it is not a log. Unacknowledged items pulse. Acknowledged items are calmer. Resolved items move to history.
- **AI-direct escalations always at top** — fire, fall, door obstruction at speed, unattended item (high confidence). These are surfaced by the AI without Conrad raising them. They carry an AI badge so Claudia knows Conrad may not yet be aware.
- **Conrad escalations below AI-direct** — sorted by severity then time. Roland's technical escalations shown in muted style at the bottom — Claudia is informed but these are Roland's domain.
- **Still frame in escalation detail** — single frame from detection moment only. No live video feed. Privacy boundary: Claudia sees the frame that triggered the alert, not a live view.
- **Fleet list is ambient** — Claudia does not actively read every card. The sort order (alert trains at top) and colour coding (red/amber/green) mean problems surface without requiring active scanning.
- **KPI strip is glanceable** — "0 open incidents" vs "3 open incidents" tells Claudia the state of the fleet in one number. She should be able to read the strip without her glasses from across the room.
- **Expected vs actual on fleet cards** — shown only when anomalous (+15% above reservation threshold). Clean by default; flagged delta appears only when it matters.
- **Resolution is required to close** — Claudia cannot dismiss an escalation without an outcome text. This creates the audit trail Nomad Digital needs to demonstrate platform value to ÖBB.

---

## Technical Dependencies

| Dependency | Status |
|---|---|
| WebSocket push from cloud-backend to Control Centre Dashboard | Required — real-time escalation + alert delivery (ADR-9) |
| AI-direct escalation routing (inference → fusion → event-store → cloud → Control Centre) | Required — high-confidence detections must bypass Conrad and route directly to Claudia |
| Still-frame delivery with escalation payload | Required — single JPEG at detection time, stored in event-store, delivered with escalation |
| Conrad acknowledgement / outcome push notification | Required — Conductor App must receive Control Centre responses |
| Escalation audit log (outcome text + action tags) | Required — stored in PostgreSQL, queryable for reporting |
| Occupancy + alert real-time sync (onboard event-store → cloud → Control Centre) | Required — fleet list and KPI strip update without page refresh |
| Configurable AI escalation confidence threshold | Required — prevents alert overload; ÖBB must agree threshold before go-live |
