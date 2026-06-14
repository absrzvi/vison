# ÖBB Pilot Kickoff Checklist

**Status:** PoC draft — living document, owned by Nomad AI PM
**Source story:** [E10-S3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md)

> Gates that must clear before pilot go-live. E10-S3 contributes the operational-procedures + drill items; other gates are stubs to be filled as their stories land.

---

> **Severity tags:** `[BLOCKER]` = pilot cannot go live until closed; `[TUNABLE]` = a PoC default that should be confirmed/adjusted but does not block go-live. Tags are E10-S3's recommendation, subject to ÖBB ops override.

## Operational procedures (E10-S3)

- [ ] `[BLOCKER]` **Critical-alert SOP signed off** — [critical-alert-sop.md](critical-alert-sop.md) reviewed and signed by ÖBB ops owner (`TBD — ÖBB signoff`).
- [ ] `[BLOCKER]` **Routing matrix signed off** — [alert-routing-matrix.md](alert-routing-matrix.md): every row has a named ÖBB ops owner and a signoff date; the `TBD` placeholders are replaced.
- [ ] `[BLOCKER]` **Operators trained on the SOP** — the on-shift staff who will execute it (Fleet Manager, secondary Control Centre operator, and any Fernverkehr conductors) have been walked through the SOP and the four action tags — signoff by an ops owner is not the same as the console team knowing the procedure.
- [ ] `[BLOCKER]` **First tabletop drill complete** — at least one monthly tabletop drill walked per [drill-cadence.md](drill-cadence.md) **before** go-live; drill note filed.
- [ ] `[TUNABLE]` **Live-drill scheduled** — first quarterly live drill booked on a non-revenue service within the first quarter of operation.

## Open dependencies surfaced by E10-S3

- [ ] `[BLOCKER]` **ÖBB ops on-call escalation path defined** — the final escalation step in SOP §3.3 (`TBD — ÖBB signoff`). This is the SOP's last line of defence; if undefined, the procedure dead-ends when both primary and secondary landside operators are unreachable.
- [ ] `[BLOCKER]` **Per-class operator response actions defined** — the SOP routes and tags alerts but does not state the real-world response per critical class (e.g. `slip_fall` → ?, `fire` → contact emergency services / driver?). ÖBB ops must define what the operator physically does after acknowledging, per class. (E10-S3 Round-2 review.)
- [ ] `[BLOCKER]` **Life-safety closure rule defined** — nothing currently prevents closing a `fire`/`slip_fall` escalation as `false_alarm`/`no_action_needed` without field verification (raw video never leaves the train, so landside cannot visually confirm). ÖBB ops must decide what may close a life-safety class. (E10-S3 Round-2 review.)
- [ ] `[BLOCKER]` **Onboard retention window sized vs worst-case dead-zone duration** — the event-store keeps only the most recent 3 journeys (`truncate_old_journeys(retain=3)`); an outage spanning >3 journeys can age out an un-pulled critical alert (SOP §3.4 caveat). Confirm `retain` is sized against the worst-case dead-zone duration on the pilot route, or accept the residual risk in writing.
- [ ] `[TUNABLE]` **Train-type fleet-config source confirmed** — ÖBB confirms the per-vehicle "conductorless vs Fernverkehr" metadata source so the routing matrix's train-type column can be populated with live fleet data (D6). *Pick a safe default for unknown/unconfirmed train type (recommend → conductorless / landside-immediate) so a mislabel never routes to a non-existent onboard conductor.*
- [ ] `[TUNABLE]` **Amber-window value confirmed** — ÖBB confirms or adjusts the 10-minute amber window (PoC default) used in the SOP and drill cadence (D4); consider a shorter window for life-safety classes (fire/slip_fall) vs the flat default.

## Other kickoff gates (stubs — filled by their owning stories)

- [ ] **Kill-switch operator named** — Nomad-side + ÖBB-side owner for the alert-class kill-switch recorded in the pilot RACI (10-1).
- [ ] **Exec-comms / rollback playbook ready** — the "day the AI is confidently wrong" playbook (gap analysis §3; tracked separately).
- [ ] **Behavioural-telemetry baseline confirmed** — the weekly Alert Effectiveness Report job is scheduled and producing output (10-2).
- [ ] **Data-protection signoff** — GDPR/operator_id-only confirmation for the pilot dataset.

---

*This checklist is referenced by [drill-cadence.md](drill-cadence.md) and [critical-alert-sop.md](critical-alert-sop.md). It closes the "drill cadence wired to the pilot kickoff checklist" requirement of [E10-S3 AC3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md).*
