# ÖBB Pilot Kickoff Checklist

**Status:** PoC draft — living document, owned by Nomad AI PM
**Source story:** [E10-S3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md)

> Gates that must clear before pilot go-live. E10-S3 contributes the operational-procedures + drill items; other gates are stubs to be filled as their stories land.

---

## Operational procedures (E10-S3)

- [ ] **Critical-alert SOP signed off** — [critical-alert-sop.md](critical-alert-sop.md) reviewed and signed by ÖBB ops owner (`TBD — ÖBB signoff`).
- [ ] **Routing matrix signed off** — [alert-routing-matrix.md](alert-routing-matrix.md): every row has a named ÖBB ops owner and a signoff date; the `TBD` placeholders are replaced.
- [ ] **First tabletop drill complete** — at least one monthly tabletop drill walked per [drill-cadence.md](drill-cadence.md) **before** go-live; drill note filed.
- [ ] **Live-drill scheduled** — first quarterly live drill booked on a non-revenue service within the first quarter of operation.

## Open dependencies surfaced by E10-S3

- [ ] **Train-type fleet-config source confirmed** — ÖBB confirms the per-vehicle "conductorless vs Fernverkehr" metadata source so the routing matrix's train-type column can be populated with live fleet data (D6).
- [ ] **Amber-window value confirmed** — ÖBB confirms or adjusts the 10-minute amber window (PoC default) used in the SOP and drill cadence (D4).
- [ ] **ÖBB ops on-call escalation path defined** — the final escalation step in SOP §3.3 (`TBD — ÖBB signoff`).
- [ ] **Onboard retention window sized vs worst-case dead-zone duration** — the event-store keeps only the most recent 3 journeys (`truncate_old_journeys(retain=3)`); an outage spanning >3 journeys can age out an un-pulled critical alert (SOP §3.4 caveat). Confirm `retain` is sized against the worst-case dead-zone duration on the pilot route, or accept the residual risk in writing.

## Other kickoff gates (stubs — filled by their owning stories)

- [ ] **Kill-switch operator named** — Nomad-side + ÖBB-side owner for the alert-class kill-switch recorded in the pilot RACI (10-1).
- [ ] **Exec-comms / rollback playbook ready** — the "day the AI is confidently wrong" playbook (gap analysis §3; tracked separately).
- [ ] **Behavioural-telemetry baseline confirmed** — the weekly Alert Effectiveness Report job is scheduled and producing output (10-2).
- [ ] **Data-protection signoff** — GDPR/operator_id-only confirmation for the pilot dataset.

---

*This checklist is referenced by [drill-cadence.md](drill-cadence.md) and [critical-alert-sop.md](critical-alert-sop.md). It closes the "drill cadence wired to the pilot kickoff checklist" requirement of [E10-S3 AC3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md).*
