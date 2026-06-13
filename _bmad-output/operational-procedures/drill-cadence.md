# Critical-Alert Drill Cadence

**Status:** PoC draft — pending ÖBB ops signoff
**Source story:** [E10-S3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md) · **Companion:** [critical-alert-sop.md](critical-alert-sop.md)

> A written SOP that is never rehearsed is a document, not a capability. This cadence keeps the [critical-alert SOP](critical-alert-sop.md) live and exercised through the pilot.

---

## Cadence

### Monthly — tabletop drill

- **Who:** the landside team (Fleet Manager + secondary Control Centre operator). For a **Fernverkehr** scenario, an onboard conductor participates (or is role-played) to exercise the onboard-ack branch (SOP §3.2).
- **What:** walk the [critical-alert SOP](critical-alert-sop.md) end-to-end for **one randomly selected critical alert class** (`slip_fall`, `door_obstruction`/`door_fault` at speed; once shipped, `fire` / `unattended_item`).
- **Cover at least one failure branch each month, rotating:** landside-unreachable (§3.3) and dead-zone (§3.4).
- **Output:** a one-paragraph drill note — which branch was walked, time-to-acknowledge observed, any SOP wording that was unclear. File alongside this doc as `drill-log-{YYYY-MM}.md`.

### Quarterly — live drill

- **What:** a **planted test event on a non-revenue service** (e.g. a depot move or a positioning run) that triggers a real critical escalation through the live pipeline (Conrad → escalation row → inbox).
- **Verify end-to-end:** the alert surfaces in the Control Centre, the on-call operator acknowledges within the amber window (10 min PoC default), and resolution with an action tag is recorded in the `escalations` table.
- **Explicitly exercise the dead-zone branch** at least once per year: trigger an event while the test train is in a known dead zone and confirm it surfaces on reconnect (SOP §3.4) without loss.
- **Output:** a live-drill report with timestamps from the `escalation_audit` trail (10-2), filed as `live-drill-{YYYY-Qn}.md`.

---

## Why these two tiers

- **Tabletop (cheap, frequent)** catches SOP wording gaps, role confusion, and "who pages whom" ambiguity before they matter in production.
- **Live (expensive, rare)** catches integration gaps the tabletop cannot — connectivity edge cases, real ack latency, telemetry correctness — without touching a revenue service.

---

## Wiring

This cadence is a line item on the [pilot-kickoff-checklist.md](pilot-kickoff-checklist.md). The first tabletop drill must complete **before** pilot go-live; the first live drill within the first quarter of operation.

*Closes Gap 1 of [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md) (the drill-cadence half).*
