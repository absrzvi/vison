# Scenario 11 — Claudia (and Roland) Check System Health Across the Fleet

**Persona:** Control Centre Claudia (primary) · Roland (secondary — same view, different follow-up)
**Phase:** 3 — UX Scenarios
**Date:** 2026-05-16

---

## Core Feature

System Health tab in the Control Centre Dashboard — a fleet-wide view of two operational health signals per train: VLAN 5 camera stream connectivity and Docker container health. Both Claudia and Roland use this tab to identify which trains have degraded AI service capability before problems surface in the operational view. Detail and remediation happen in the Maintenance App.

---

## Entry Point

Claudia opens the System Health tab as part of her morning routine — after the occupancy analytics review (Scenario 04). She wants to know whether the AI service is running cleanly across the fleet before the morning peak. Roland opens the same tab when he suspects a connectivity or container issue, typically after receiving a message from Conrad or noticing stale data in the fleet view.

---

## Mental State

**Trigger (Claudia):** Start of shift, or suspicion that an alert she expected to see hasn't arrived. She wants confirmation the platform is working, not just the trains.
**Hope:** That all trains are green and she can close the tab in 30 seconds.
**Worry:** That a camera VLAN is silently down on a live train and she's been looking at stale occupancy data without knowing it.

**Trigger (Roland):** Claudia messages him: "R5001C-022 shows no camera alerts since 09:15 — is inference running?" Roland opens System Health to check before SSHing into anything.
**Hope:** That the dashboard tells him which signal is degraded so he can go straight to the right fix in the Maintenance App.
**Worry:** That the view is too coarse to tell him whether it's a VLAN issue or a container crash — wasting time investigating the wrong layer.

---

## Sunshine Path — Claudia

1. Claudia opens the System Health tab. The fleet grid loads — one row per active train, two status indicators per row: **VLAN 5** and **Containers**.
2. All trains are green. Claudia closes the tab. Review complete in under 30 seconds.

---

## Exception Path — Degraded Train

1. Claudia opens the System Health tab. Two trains are not all-green:
   - **R5001C-022** — VLAN 5: amber · Containers: green
   - **R5001C-031** — VLAN 5: green · Containers: red

2. R5001C-031 is red — Claudia taps it. A summary panel opens:
   - VLAN 5: healthy — camera streams reachable
   - Containers: 1 of 5 unhealthy — `inference` container has exited
   - Last healthy state: 09:43 (41 minutes ago)
   - "Open in Maintenance App →" — the only action available from this view

3. Claudia opens the link. The Maintenance App opens to the per-train container health view for R5001C-031. She messages Roland: "031 inference container down since 09:43 — in Maintenance App now."

4. Back in the Control Centre, R5001C-031's occupancy data is shown with a staleness indicator: "Occupancy estimate — camera inference offline since 09:43. APC data only."

---

## Exception Path — Roland

1. Roland opens System Health directly after Claudia's message.
2. He sees R5001C-022 (VLAN 5 amber) — taps it. Summary: VLAN 5 degraded, packet loss on camera stream ingestion. Containers all healthy.
3. He opens the Maintenance App link → per-train VLAN 5 view. He can see which camera streams are dropping frames and action a fix from there.

---

## Success Goals

**Claudia:** Knows within 60 seconds whether the AI service is healthy fleet-wide. When it's not, she knows which train and which layer — and can hand off to Roland without guessing.
**Roland:** Gets directly to the right diagnostic layer (VLAN vs container) without SSHing blind.
**Business (Nomad Digital):** Platform self-reports its own health — operators are not discovering AI service failures through missing alerts. This is a commercial trust requirement.

---

## Trigger Map Connections

- ✅ Claudia: Fear acting on stale/inaccurate data — staleness indicator on occupancy data when inference is offline
- ✅ Roland: Act before problems escalate — degradation visible before full failure
- ✅ Roland: See all onboard systems from one place — VLAN 5 + container health in one tab
- ❌ Claudia: Fear silent platform failure — System Health tab makes failure visible, not hidden

---

## Design Notes

- **Two signals only in this view:** VLAN 5 connectivity + Docker container health. No other data surfaced here — this is a status panel, not a diagnostics tool.
- **Exceptions-first:** Trains where both signals are green are shown last (or collapsed). Degraded/failed trains surface at the top.
- **Staleness propagation:** When VLAN 5 is degraded or inference container is down, the occupancy data shown in the main fleet view must carry a visible staleness indicator. Claudia must never see occupancy numbers without knowing if the underlying inference is running.
- **"Open in Maintenance App" is the only action:** No remediation, no restart buttons, no SNMP detail in the Control Centre. This view is read-only status only.
- **Both Claudia and Roland access the same tab** — same URL, same data, same design. Role differentiation happens in the Maintenance App, not here.
- **Container granularity in summary:** The Control Centre shows "N of 5 containers unhealthy" + which container(s) by name. It does not show logs, exit codes, or restart counts — those are in the Maintenance App.

---

## Technical Dependencies

| Dependency | Status |
|---|---|
| VLAN 5 connectivity health signal from `rtsp-ingest` container | Required — `rtsp-ingest` liveness/readiness probe must expose VLAN 5 stream status per camera priority tier |
| Docker container health status API from `event-store` | Required — event-store health endpoint must aggregate container health across all 5 containers |
| Staleness timestamp on occupancy events | Required — `fusion` container must tag events with last-inference timestamp so UI can show staleness |
| Maintenance App deep-link URL scheme | Required — "Open in Maintenance App" must deep-link to the correct per-train view |
| Last-healthy-state timestamp | Required — event-store must record when each health signal last transitioned to healthy |
