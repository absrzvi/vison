# Owning the Gap — AI PM Analysis

"Owning the gap" means the product is judged not on what the AI detects, but on what Conrad does with the alert, what Claudia does when Conrad escalates, and whether ÖBB sees a coherent operational story when something goes wrong. The PoC is in WDS Phase 4–5 with Control Centre as the first dev target and no signed customer yet — every gap below is something an ÖBB executive will probe in the first procurement conversation, and the answer cannot be "the UI shows it."

## 1. The escalation sequence is designed, not operationalised

> **⚠️ Superseded by the actor-model correction (2026-06-13 — memory `project-actor-model-conrad`).** The two-actor "Conrad assess → escalate → Claudia acknowledge" sequence below describes a model the PoC does NOT use. **Conrad is the virtual on-train conductor (the onboard AI platform that raises alerts), not a human in the response loop.** Acknowledgement is **train-type-conditional**: conductorless trains → landside Fleet Manager / remote staff only; Fernverkehr trains → onboard conductor may also acknowledge. The ÖBB police/station security-handoff contract is out of PoC scope. The gap below (no written/rehearsed SOP) is still real, but E10-S3 now addresses it under the corrected model — see the re-scoped E10-S3 in [epics.md](epics.md). The original text is retained as the historical analysis.

> **✅ Closed by E10-S3 (2026-06-14).** This gap is now operationalised by three documents under `_bmad-output/operational-procedures/`:
> - [critical-alert-sop.md](../operational-procedures/critical-alert-sop.md) — the branched SOP (conductorless / Fernverkehr / landside-unreachable / dead-zone)
> - [alert-routing-matrix.md](../operational-procedures/alert-routing-matrix.md) — the per-`alert_code` × confidence × speed × location × train-type decision matrix
> - [drill-cadence.md](../operational-procedures/drill-cadence.md) — monthly tabletop + quarterly live drills, wired to the [pilot-kickoff-checklist.md](../operational-procedures/pilot-kickoff-checklist.md)
>
> ÖBB ops signoff on each remains a pilot-kickoff process boundary (checklist placeholders).

**The Question:** When a critical alert fires, what is the exact sequence of actions that should follow — and is that sequence written down, trained, and rehearsed?

**What our docs cover today:**
- Two-actor sequence (Conrad assess → escalate still-frame → Claudia Acknowledge → Resolve with tags + outcome text) in [scenario-02d](_bmad-output/design-artifacts/C-UX-Scenarios/02d-conrad-unattended-bag.md) and [scenario-12](_bmad-output/design-artifacts/C-UX-Scenarios/12-claudia-live-fleet-monitoring.md).
- 10-minute passive amber-escalation on Conrad's banner; resolution requires outcome text + ≥1 action tag in the same specs.
- Critical-class alerts (fire, fall, door-at-speed, high-confidence unattended) bypass Conrad direct to Claudia.

**The gap:** No SOP, no drill schedule, no training curriculum, no defined "critical confidence" threshold, no procedure for Conrad non-response past 10 min, and no handoff contract with ÖBB security (Open Question 1 in scenario-02d is still open).

**What an AI PM would add:**
- A 2-page **Conrad/Claudia SOP** in `_bmad-output/operational-procedures/` covering happy path, Conrad-unreachable, Claudia-unreachable, and dead-zone branches.
- A **critical-alert decision matrix** binding alert_code × confidence × speed × location to {auto-route-Claudia, Conrad-first, suppress}, owned by ÖBB ops with a signoff date.
- A **drill cadence** (tabletop monthly, live quarterly) wired to the pilot kickoff checklist.
- A signed **ÖBB security handoff contract** specifying who receives the "ÖBB security notified" tag and within what SLA.

## 2. On-time performance is the unused motivational frame

**The Question:** Are conductors rewarded or measured in any way the product can connect to? If on-time departure is their KPI, frame every alert in terms of dwell time impact.

**What our docs cover today:**
- Conrad's intrinsic on-time pride in [02-Conductor-Conrad](_bmad-output/design-artifacts/B-Trigger-Map/02-Conductor-Conrad.md).
- Auto-attribution of door-obstruction delays in [04-pre-departure-summary](_bmad-output/design-artifacts/D-UX-Design/scenario-10-specs/04-conductor-app-pre-departure-summary.md), explicitly to remove blame.
- Adoption + time-savings KPIs in [01-Business-Goals](_bmad-output/design-artifacts/B-Trigger-Map/01-Business-Goals.md).

**The gap:** Alerts are framed by incident type and coach, never by seconds-to-scheduled-departure. The product protects Conrad from blame but never speaks his language. No KPI in the business goals tracks delay-minutes-avoided.

**What an AI PM would add:**
- **Dwell-time-aware alert copy** spec: every pre-departure alert gets a `seconds_to_departure` suffix sourced from ZFR/PIS (`"Door obstruction · Coach 6 · 90s to departure"`).
- A new business KPI: **delay-minutes-avoided per fleet-week**, attributable to alerts acknowledged before scheduled departure.
- An **on-time hook** in the Conrad app pre-departure summary that totals "minutes saved this shift" as positive reinforcement.

## 3. No playbook for the day the AI is confidently wrong

**The Question:** What happens the first time the system gets something badly wrong in front of an ÖBB executive? Is there a response playbook?

**What our docs cover today:**
- Suppression state machine (DEPOT/MAINTENANCE/GPS_INVALID/NORMAL) in [4-6-fusion-alert-correlation](_bmad-output/implementation-artifacts/4-6-fusion-alert-correlation-suppression.md).
- Existential-risk framing in [05-Key-Insights](_bmad-output/design-artifacts/B-Trigger-Map/05-Key-Insights.md) and NFR3 (<5% FP) in [prd.md](_bmad-output/planning-artifacts/prd.md).
- Aggregated AI-quality view (UX-DR12) and unresolved threshold Q3 in the PRD.

**The gap:** No per-alert `confidence_score` in `AlertRaisedPayload`, no live AI-quality signal, no kill-switch authority, no exec-comms template, no rollback procedure.

**What an AI PM would add:**
- Add `confidence_score` + `model_version` to `AlertRaisedPayload` (Story 4-5 amendment) and surface a "low-confidence" pill in Claudia's escalations inbox.
- A **24-hour exec playbook**: who calls the ÖBB sponsor, holding statement template, evidence bundle (event-store export + Hailo logs), rollback path (per-alert-class disable via fusion config).
- A **live AI-quality tile** on System Health (rolling 1-hour FP rate, model-confidence drift) — promote UX-DR12 from 7-day aggregate to live.
- A named **alert-class kill-switch owner** (Nomad-side and ÖBB-side) recorded in the pilot RACI.

## 4. Post-launch we will not know what is working

**The Question:** After 8 weeks of live operation, which alerts have the highest acknowledge-to-action rate? Which are being silently dismissed?

**What our docs cover today:**
- Acknowledge/Resolve API wiring in [2-5-escalation-detail](_bmad-output/implementation-artifacts/2-5-escalation-detail-acknowledge-resolve.md).
- Configurable thresholds in [2-8-per-operator-configurable-alert-threshold](_bmad-output/implementation-artifacts/2-8-per-operator-configurable-alert-threshold.md).
- Historical analytics endpoints in [3-1-analytics-rest-endpoints](_bmad-output/implementation-artifacts/3-1-analytics-rest-endpoints.md).

**The gap:** Zero behavioural telemetry. Time-to-ack by alert class, outcome-tag distribution, threshold-change effects, passive dismissal (tab-away, session-end) are all invisible. The 80% adoption KPI cannot be measured.

**What an AI PM would add:**
- New **Story 3-6: Operator Behavioural Telemetry** — event log `(escalation_id, operator_id, alert_class, t_fired, t_ack, t_resolve, outcome_tags, dwell_focus_ms)`.
- New endpoint `/api/v1/escalations-audit` returning per-alert-class ack-to-action funnels.
- A **weekly Alert Effectiveness Report** auto-generated for the pilot steering committee: top-5 high-volume/low-action alerts (retune candidates), median ack latency by class, threshold-change impact.
- A **silent-dismissal signal**: navigation-away-from-unacked-escalation event, surfaced in System Health.

## Priority Order

1. **Gap 3 — Exec-failure playbook + confidence metadata.** No customer yet; the first hostile question in any procurement meeting is "what happens when it's wrong?" — without an answer we do not get past pilot signoff.
2. **Gap 4 — Behavioural telemetry.** Must be in the schema before Control Centre ships, because retrofitting event logging after the PostgreSQL contracts harden is far more expensive than adding it now in WDS Phase 5.
3. **Gap 1 — Operational SOP + drill cadence.** Required for ÖBB pilot signoff and the security handoff contract, but can land in parallel with Control Centre dev since it is procedural, not code.
4. **Gap 2 — Dwell-time alert framing.** Highest user-delight payoff but lowest existential risk; safe to defer until Conductor App leaves descope and the ZFR/PIS time-to-departure feed is wired.
