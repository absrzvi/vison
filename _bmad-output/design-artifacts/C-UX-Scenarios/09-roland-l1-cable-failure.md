# Scenario 09 — Roland Diagnoses a Degrading L1 Cable and Notifies Stadler

**Persona:** Roland (Fleet Manager / Technical Champion)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-16
**Revised:** 2026-05-16 — Roland's full diagnostic workflow moves to the Maintenance App. The Control Centre (System Health tab) is only the entry point.

---

## Core Feature

Roland spots a degraded inter-coach cable via the System Health tab in the Control Centre Dashboard, then moves to the **Maintenance App** to diagnose the fault and send a structured Stadler notification. The Control Centre shows the signal that something is wrong; all diagnosis and action happen in the Maintenance App.

---

## Entry Point

Roland opens the System Health tab in the Control Centre Dashboard (Scenario 11). He sees R5001C-017 with a VLAN 5 amber indicator — camera streams on coaches 4–6 are showing degraded ingestion. He taps the train, sees "VLAN 5 degraded — packet loss on rtsp-ingest" in the summary panel, and opens the Maintenance App via the deep link.

---

## Mental State

**Trigger:** System Health tab surfaces R5001C-017 VLAN 5 amber. Roland suspects an inter-coach L1 cable — the most common failure mode on the DOSTO fleet.
**Hope:** That the Maintenance App shows him the exact segment, which systems are affected, and lets him send Stadler a complete structured report in one action — no SSH, no manual email.
**Worry:** That the degradation spreads to full failure before Stadler is notified, and that the report sits in his drafts while the coach goes out of service mid-run.

---

## Sunshine Path

1. Roland taps "Open in Maintenance App →" from the Control Centre System Health summary for R5001C-017.

2. The Maintenance App opens to the per-train network view for R5001C-017:
   - **Inter-coach link map** — a spatial chain of coach nodes. Segment 4–5 is amber: packet loss 6.2%, 4 link-down events in the last hour.
   - **Affected systems panel** — automatically derived: CCTV VLAN 5 (coaches 4–6), PIS interior coach 5 at risk.
   - **7-day trend** — today's degradation is new; no prior drops on this segment.

3. Roland reviews the plain-language fault summary ("Inter-coach cable 4–5: signal degraded — packet loss 6.2%, 4 link-down events in last 60 min") and taps **"Notify Stadler"**.

4. A pre-populated fault report opens:
   - Train ID, fault type, affected segment, SNMP data, affected systems, current location, next stop, severity (auto-classified: amber)
   - Roland adds one optional note: "Seen intermittent drops since 09:42 — recommend inspection at next depot visit."

5. Roland sends. Confirmation: "Stadler notified — ref #ST-2741. Fault logged in platform."

6. Back in the Control Centre System Health tab, R5001C-017 VLAN 5 indicator now shows a small envelope icon: "Reported to Stadler." No further action required from the Control Centre view.

---

## Alternate Path — Full Link Failure

If the link goes red (full failure) before Roland acts:
- The Control Centre System Health tab escalates R5001C-017 from amber to red
- In the Maintenance App, the affected systems panel expands: CCTV on coaches 4–6 shown as offline
- Stadler notification form auto-upgrades severity to red
- If train is in service, Roland sees current location + next stop + estimated depot arrival

---

## Success Goals

**Roland:** Confirmed fault, identified affected systems, sent Stadler a complete structured report in under 3 minutes — from a tablet, without SSH.
**Stadler:** Received a machine-readable fault report with all diagnostic data, not a free-text email.
**Business (Nomad Digital):** Platform self-reports infrastructure failures and replaces manual network diagnostics — a commercial differentiator for the Stadler DOSTO market.

---

## Trigger Map Connections

- ✅ Roland: Act before problems escalate — degradation caught at amber before full failure
- ✅ Roland: Replace SSH + manual email — one-tap structured Stadler notification
- ✅ Roland: See all onboard systems from one place — in Maintenance App, not Control Centre
- ❌ Roland: Fear fault sitting unreported — confirmation receipt + platform fault log close the loop

---

## Interface Boundary

| Step | Interface |
|---|---|
| Spot the signal | Control Centre Dashboard — System Health tab |
| Diagnose + act | Maintenance App — per-train network view |

The Control Centre never shows raw SNMP data, link maps, or Stadler notification forms. Those belong in the Maintenance App.

---

## Design Notes (Maintenance App)

- **SNMP plain language translation is essential** — translate OIDs to human-readable fault descriptions; raw SNMP available as expandable detail for export only.
- **Inter-coach link map must be spatial** — coach chain with colour-coded link segments, not a table.
- **Affected systems automatically derived** — platform knows which systems route through which switches; Roland never manually calculates impact.
- **Stadler notification form pre-populated** — Roland adds an optional note only. Zero manual data entry for fault data.
- **Fault log persists** — Stadler reports logged with timestamp, ref number, resolution status.
- **Tablet-first** — fully operable at ~1280px landscape; all touch targets ≥44px.

---

## Technical Dependencies

| Dependency | Interface | Status |
|---|---|---|
| VLAN 5 connectivity signal from `rtsp-ingest` | Control Centre + Maintenance App | Required — per Scenario 11 |
| SNMP data feed from Stadler diagnostic system | Maintenance App | Nomad feature confirmed |
| L2 network topology map per train | Maintenance App | OID list to confirm with Stadler |
| System routing table (switch-to-coach mapping) | Maintenance App | Internal Nomad config |
| Stadler notification API / structured email endpoint | Maintenance App | Integration format to confirm with Stadler |
| Historical SNMP link quality data store | Maintenance App | Retention period to confirm |
| Maintenance App deep-link URL scheme | Both | Required — per Scenario 11 |
