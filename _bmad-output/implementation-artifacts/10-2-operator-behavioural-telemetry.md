# Story 10.2: Operator Behavioural Telemetry

Status: ready-for-dev

<!-- Created 2026-06-13 via bmad-create-story (Amelia).
     DEPENDS ON 10-6 (escalation-lifecycle-persistence) — must land first. 10-6 builds the `escalations`
     table + ack/resolve endpoints that this story audits. Sequence: 10-1 (done) → 10-6 → 10-2.
     Source: research workflow wf_bb727ef4-f6e + independent verification. Schema decisions inherited from 10-6. -->

## Story

As an **AI PM measuring whether alerts change operator behaviour**,
I want **every escalation lifecycle transition (raised → acknowledged → resolved → silently-dismissed) recorded as operator-attributable audit telemetry, queryable via a funnel endpoint, and summarised in a weekly effectiveness report**,
so that **after 8 weeks of pilot operation I can identify which alert classes have the highest ack-to-action rate, which are silently dismissed, and which confidence thresholds need retuning**.

## Context — depends on 10-6

10-6 establishes the authoritative server-side `escalations` table and the `acknowledge`/`resolve` endpoints (the backend half of E2-S5 that never shipped). **This story does not re-derive lifecycle state from the client** — it audits the real transitions 10-6 persists. Before 10-6, there was no server-side write-trigger for an audit table; that gap is why this story was unblockable until now (research `wf_bb727ef4-f6e`, schema-payload-audit agent).

Silent dismissal is the one transition 10-6 does **not** capture (it is a non-action — the operator opens an unacknowledged escalation panel and navigates away without acknowledging). This story adds client-side detection for it.

## Acceptance Criteria

**AC1 — escalation_audit row per transition**
Given an escalation transitions state in the `escalations` table (`unacknowledged`→`acknowledged`→`resolved`, written by 10-6's endpoints), when the transition is persisted, then a row is appended to `escalation_audit` with: `audit_id` (TEXT PK), `escalation_id` (TEXT, FK→`escalations.escalation_id`), `transition` (TEXT, CHECK in `raised|acknowledged|resolved|silently_dismissed`), `operator_id` (TEXT, NULL for `raised`), `alert_code` (TEXT), `t_event` (TIMESTAMPTZ — the transition time), `t_fired` (TIMESTAMPTZ — the originating raise time, denormalised for latency math), `action_tags` (JSONB, NULL except on `resolved`), `dwell_focus_ms` (INTEGER, NULL except `silently_dismissed`), `confidence_score` (DOUBLE PRECISION, NULL), `confidence_basis` (TEXT, NULL), `model_versions` (JSONB, NULL). One row **per transition** (a full lifecycle = 3+ rows).

**AC2 — silent dismissal telemetry**
Given a Claudia user opens an escalation detail panel for an escalation still in `unacknowledged` state, when the panel is closed (route change, tab close, or unmount) without an Acknowledge action and the escalation is still `unacknowledged`, then the CC emits a `silently_dismissed` telemetry POST with `{escalation_id, operator_id, t_viewed, t_dismissed, dwell_focus_ms}` to `POST /api/v1/escalations/{escalation_id}/silently-dismissed`; the backend appends an `escalation_audit` row with `transition='silently_dismissed'`. `dwell_focus_ms` = accumulated tab-focused time (visibilitychange-gated), not wall-clock.

**AC3 — funnel query endpoint**
Given `GET /api/v1/escalations-audit?from=<iso>&to=<iso>&alert_code=<code>` (all params optional; default range last 7d; `alert_code` filters to one class), when called with a valid `X-API-Key`, then it returns per-`alert_code` funnels: `{alert_code, count_raised, count_acknowledged, count_resolved, count_silently_dismissed, median_t_ack_seconds, p95_t_ack_seconds, action_tag_distribution}` where `action_tag_distribution` is `{tag: count}`. Latency percentiles use `PERCENTILE_CONT(...) WITHIN GROUP (ORDER BY ...)` over `(t_ack - t_fired)`. Invalid ISO/range → `422` with `{"error":"INVALID_RANGE", ...}` (analytics error shape).

**AC4 — weekly effectiveness report (callable)**
Given the report generator is invoked (callable entrypoint; scheduling is external per D4), when it runs for an ISO week, then it writes `reports/alert-effectiveness-{YYYY-WW}.md` containing: top-5 high-volume / low-ack-rate alert classes (retune candidates), median ack latency by class, any `alert_class_state` disable/enable events in the window and their effect on ack rate, and the silent-dismissal rate trend. The generator is idempotent (re-running the same week overwrites, does not duplicate).

**AC5 — migration safe + indexed**
Given migration `0007_escalation_audit.py` (`down_revision="0006"`), then it creates `escalation_audit` (new-table-only → concurrent-read-safe) with indices on `alert_code`, `operator_id`, `t_fired`; `test_upgrade_head_idempotent` passes.

**AC6 — coverage, GDPR, gates**
`cloud-backend` unit tests cover the funnel aggregation (AC3) and report generation (AC4) at ≥80%; no PII beyond `operator_id` is logged (GDPR per NFR6 — `operator_id` is already in scope from the ack/resolve schema); `ruff`+`mypy` clean; CC `vitest` green for the dismissal module; the silent-dismissal flow is browser-verified.

## Decisions (locked — schema inherited from 10-6)

- **D1 — audit granularity.** `escalation_audit` is **append-only, one row per transition** (raised/acknowledged/resolved/silently_dismissed), NOT one mutable row per escalation. This makes the funnel a simple `GROUP BY alert_code, transition` count and preserves per-event timestamps. (Resolves the schema-audit agent's "one row or per-transition?" gotcha.)
- **D2 — `alert_code` not `alert_class`; `action_tags` not `outcome_tags`; `model_versions` JSONB.** Inherited verbatim from [10-6 D2/D3/D4](10-6-escalation-lifecycle-persistence.md). The epic's `alert_class`/`outcome_tags`/`model_version` names are superseded.
- **D3 — `confidence_score` nullable in aggregations.** `sensor`-basis escalations have `confidence_score = NULL` ([payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py)); funnel avg/threshold math must `NULLIF`/filter (the exact bug pattern that broke `test_analytics_endpoints` heatmap — see [deferred-work.md](deferred-work.md)).
- **D4 — report scheduling is EXTERNAL.** Research confirmed **no in-process scheduler exists** in cloud-backend (only a FastAPI `@app.on_event("startup")` hook; no APScheduler/Celery/asyncio-timer — [main.py:47](../../cloud-backend/src/cloud_backend/main.py)). This story ships the report as an **idempotent callable** (`generate_alert_effectiveness_report(db, iso_year, iso_week)`) + a thin CLI entrypoint, triggered by an **external GitLab CI scheduled pipeline** (`.gitlab-ci.yml` schedule, Monday 06:00 UTC). Do NOT add an in-process scheduler dependency. The epic's "job runs every Monday" AC is satisfied by the external schedule calling the callable. ⚠ Confirm GitLab CI schedule placement with infra.
- **D5 — silent-dismissal `dwell_focus_ms` semantics.** Focus-time only (accumulate while `document.visibilityState === 'visible'`), not wall-clock, so a panel left open on a background tab does not inflate dwell. Sent via `navigator.sendBeacon` (survives unload; `fetch` does not — see Dev Notes §stale-closure).

## Tasks / Subtasks

- [ ] **T1 — migration `0007_escalation_audit.py`** (AC1, AC5)
  - [ ] `revision="0007"`, `down_revision="0006"` (10-6 adds 0006). Columns per AC1; `transition` CHECK constraint; `JSONB` for `action_tags`/`model_versions`; `TIMESTAMP(timezone=True)`. Indices `ix_escalation_audit_alert_code`, `_operator_id`, `_t_fired`.
  - [ ] Extend [test_migrations.py](../../cloud-backend/tests/integration/test_migrations.py) with `test_escalation_audit_table_columns`; confirm idempotency test green.
- [ ] **T2 — audit-write on transition** (AC1)
  - [ ] **READ FIRST (UPDATE file):** 10-6's `cloud-backend/src/cloud_backend/routes/escalations.py` (acknowledge/resolve handlers) and `routes/ingest.py` (ALERT_RAISED→escalations upsert). Append an `escalation_audit` insert at each transition point: `raised` (in ingest, alongside the 10-6 escalations upsert), `acknowledged`/`resolved` (in 10-6's endpoints). Reuse the same DB transaction.
  - [ ] RED tests: ingest ALERT_RAISED → 1 `raised` audit row; acknowledge → +1 `acknowledged` row; resolve → +1 `resolved` row.
- [ ] **T3 — silently-dismissed endpoint + audit** (AC2)
  - [ ] In 10-6's `routes/escalations.py`: `POST /{escalation_id}/silently-dismissed` (body `{operator_id, t_viewed, t_dismissed, dwell_focus_ms}`). Guard: only append audit row if the escalation is still `unacknowledged` (server-side re-check — client may race a concurrent ack). Does NOT change `escalations.status`. Returns `204`.
- [ ] **T4 — funnel endpoint** (AC3)
  - [ ] New `cloud-backend/src/cloud_backend/routes/escalations_audit.py`: `APIRouter(prefix="/api/v1/escalations-audit", dependencies=[Security(require_api_key)])`. `from_: str|None = Query(None, alias="from")` (‘from’ is a Python keyword), `to`, `alert_code`. Validate ISO; reuse analytics `_parse_range`/error shape ([analytics.py:39-58](../../cloud-backend/src/cloud_backend/routes/analytics.py)).
  - [ ] Single aggregation query: `GROUP BY alert_code`, conditional counts per `transition`, `PERCENTILE_CONT(0.5/0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (t_event - t_fired)))` filtered to `acknowledged` rows, `action_tag_distribution` via `jsonb_object_agg` or Python rollup over `resolved` rows' `action_tags`.
  - [ ] Pydantic response model in `cloud-backend/src/cloud_backend/api/escalations_audit.py`; `response_model=None` to allow the 422 JSONResponse path. Register router in [main.py](../../cloud-backend/src/cloud_backend/main.py).
- [ ] **T5 — CC silent-dismissal telemetry** (AC2, D5)
  - [ ] **READ FIRST (UPDATE file):** [control-centre/src/components/live/EscalationDetail.jsx](../../control-centre/src/components/live/EscalationDetail.jsx) — see Dev Notes §EscalationDetail. Add `control-centre/src/lib/telemetry/dismissal.js`: `emitSilentlyDismissed({escalationId, operatorId, tViewed, tDismissed, dwellFocusMs})` using `navigator.sendBeacon` to the AC2 endpoint.
  - [ ] In EscalationDetail: on mount capture `t_viewed`; wire `visibilitychange` to accumulate focus-time into a `useRef`; on unmount cleanup AND `beforeunload`, if `statusRef.current === 'unacknowledged'`, emit dismissal. Mirror `escalation.status` + dwell counters via `useRef` (stale-closure trap — Dev Notes).
  - [ ] **Browser-verify** (control-centre/CLAUDE.md): open an unack escalation, navigate away → confirm beacon fires with correct dwell; acknowledge then navigate → confirm NO beacon. Check console clean.
- [ ] **T6 — weekly report callable** (AC4, D4)
  - [ ] `cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py`: `async def generate_alert_effectiveness_report(db, iso_year, iso_week) -> Path`. Structure mirrors the service-module precedent [heartbeat_ingest.py](../../cloud-backend/src/cloud_backend/services/heartbeat_ingest.py). Idempotent write to `reports/alert-effectiveness-{YYYY-WW}.md`.
  - [ ] Thin CLI entrypoint (`python -m cloud_backend.services.alert_effectiveness_report`) + a `.gitlab-ci.yml` scheduled job stub (Monday 06:00 UTC) — **Tier 3, CI config, default permission mode**.
- [ ] **T7 — gates + GDPR** (AC6): cloud-backend `pytest` (≥80%), `ruff`, `mypy`; CC `lint`+`vitest`; grep audit-write paths to confirm no PII field beyond `operator_id` is persisted.
- [ ] **T8 — ADR** (freshness): extend **ADR-21** (added by 10-6) or add **ADR-22 "Behavioural Telemetry & Alert Effectiveness"** documenting `escalation_audit` append-only semantics, silent-dismissal detection, and the external report schedule. Same commit.

## Dev Notes

### Dependency on 10-6 (hard gate)
This story's T2/T3 edit files created by 10-6 (`routes/escalations.py`). **Do not start 10-2 until 10-6 is `done`.** If 10-6's schema decisions changed during its dev, reconcile this story's AC1 columns before writing tests.

### EscalationDetail.jsx — current state (UPDATE file, read fully)
[EscalationDetail.jsx](../../control-centre/src/components/live/EscalationDetail.jsx) (≈lines 49-365) is a Portal modal taking `{escalation, onClose, onAcknowledge, onResolve}`. `escalation` carries `{id, status, severity, title, detail, trainId, timestamp}`. It has three `useEffect`s (Escape-key listener with cleanup at ~119-123; status-watch form-clear at ~71-82; action-error clear at ~86-90) and a render-time `prevEscId` ref reset (~107-117). Mounted by `UnifiedFeed.jsx` and `TrainDetail.jsx` via conditional render (`selectedEsc && <EscalationDetail/>`); unmounts when parent clears `selectedEscId`. **What this story changes:** add dwell tracking + dismissal emission. **What must be preserved:** Escape-key cleanup, form-reset behaviour, the optimistic-status interplay with `FleetContext`.

### Stale-closure trap (CRITICAL — project-context.md:116-142)
The `useEffect` cleanup captures `escalation.status` at definition time. If the escalation object changes, cleanup sees the OLD object. Mirror status + dwell in `useRef`: `const statusRef = useRef(); useEffect(()=>{statusRef.current = escalation?.status},[escalation?.status])`; read `statusRef.current` in cleanup, not `escalation.status`. **`beforeunload` must be synchronous** — use `navigator.sendBeacon`, NOT `fetch`/`await` (the `_post` wrapper in escalations.js is async and will not complete during unload). `dwell_focus_ms` requires a `visibilitychange` listener accumulating focused intervals.

### Funnel query (exact patterns)
Router-level `Security(require_api_key)`; `_parse_range`/`_cutoff_dt`/`:cutoff` bind param ([analytics.py:39-47](../../cloud-backend/src/cloud_backend/routes/analytics.py)); `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY col)` (naked `PERCENTILE_CONT()` is invalid SQL); `response_model=None` for the dual JSONResponse/model return; no sync DB calls. Models in `api/` (no `api/v1/` dir).

### Report job — no scheduler infra (D4)
Cloud-backend has zero periodic-job infrastructure (only `@app.on_event("startup")`). Ship a callable + external GitLab CI schedule. Service module shape: async fn taking `db: AsyncSession` ([heartbeat_ingest.py](../../cloud-backend/src/cloud_backend/services/heartbeat_ingest.py)). `reports/` dir is repo-root-relative output (PoC); confirm path with infra.

### Schema field reference
`escalations` table + `AlertRaisedPayload` fields are defined in [10-6](10-6-escalation-lifecycle-persistence.md) AC1 / Dev Notes. Audit rows denormalise `t_fired`, `alert_code`, `confidence_*`, `model_versions` from the `escalations` row at transition time so the funnel needs no join back to `events`.

### Testing standards
cloud-backend `pytest -m unit`/`-m integration` (testcontainers), ≥80% coverage, red→green→refactor. CC Vitest + mandatory browser verification. GDPR: only `operator_id` (env-var approximation, Epic 11 will replace) — no name/email/PII.

### Project Structure Notes
- Migration `0007_escalation_audit.py`; funnel router `routes/escalations_audit.py`; models `api/escalations_audit.py`; report `services/alert_effectiveness_report.py`; CC `lib/telemetry/dismissal.js`. (Epic's `src/api/v1/...` path is wrong — no v1 dir.)
- Audit-write hooks live inside 10-6's `routes/escalations.py` + `routes/ingest.py` (do not duplicate the state machine).

### References
- [Source: epics.md#Story-E10-S2:2241-2273] (original ACs — column/name divergences resolved in Decisions)
- [Source: 10-6-escalation-lifecycle-persistence.md] (prerequisite; schema source of truth)
- [Source: cloud-backend/src/cloud_backend/routes/analytics.py] (funnel/percentile/range/auth precedent — E3-S1)
- [Source: cloud-backend/src/cloud_backend/services/heartbeat_ingest.py] (service-module precedent)
- [Source: cloud-backend/src/cloud_backend/main.py:47] (no scheduler infra — only startup hook)
- [Source: control-centre/src/components/live/EscalationDetail.jsx] (dismissal hook surface)
- [Source: project-context.md:116-142] (stale-closure useRef pattern)
- [Source: deferred-work.md] (the NULL-aggregation/date-window bugs to avoid in funnel SQL)
- Research: workflow `wf_bb727ef4-f6e` (all 5 agents)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
