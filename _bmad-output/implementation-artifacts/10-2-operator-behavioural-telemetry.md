---
baseline_commit: 7afda88e48cb3fa36488fc330bead8ade01bb35c
---

# Story 10.2: Operator Behavioural Telemetry

Status: done

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
- **D2 — `alert_code` not `alert_class`; `action_tags` not `outcome_tags`; `model_versions` JSONB.** Inherited verbatim from [10-6 D2/D3/D4](10-6-escalation-lifecycle-persistence.md). The epic's `alert_class`/`outcome_tags`/`model_version` names are superseded. **`action_tag_distribution` buckets on the canonical KEYS** — the landside-only PoC taxonomy (single actor = Fleet Manager; no conductor/police/station): `resolved_remotely`, `field_team_dispatched`, `false_alarm`, `no_action_needed` (see [10-6 D3](10-6-escalation-lifecycle-persistence.md)) — never the display labels, so historical funnels survive UI re-wording. The audit row's `action_tags` JSONB stores the keys (10-6's resolve endpoint maps label→key). `false_alarm` + `no_action_needed` are the false-positive signal (feeds deferred E10-S5).
- **D3 — `confidence_score` nullable in aggregations.** `sensor`-basis escalations have `confidence_score = NULL` ([payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py)); funnel avg/threshold math must `NULLIF`/filter (the exact bug pattern that broke `test_analytics_endpoints` heatmap — see [deferred-work.md](deferred-work.md)).
- **D4 — report scheduling is EXTERNAL via GitLab CI (confirmed).** Research confirmed **no in-process scheduler exists** in cloud-backend (only a FastAPI `@app.on_event("startup")` hook; no APScheduler/Celery/asyncio-timer — [main.py:47](../../cloud-backend/src/cloud_backend/main.py)). This project's CI/CD is **GitLab** (`.gitlab-ci.yml`, per root CLAUDE.md). Ship the report as an **idempotent callable** (`generate_alert_effectiveness_report(db, iso_year, iso_week)`) + a thin CLI entrypoint, invoked by a **GitLab CI scheduled pipeline** (Monday 06:00 UTC, `rules: - if: $CI_PIPELINE_SOURCE == "schedule"`). Do NOT add an in-process scheduler dependency. The epic's "job runs every Monday" AC is satisfied by the GitLab schedule calling the callable.
- **D5 — silent-dismissal `dwell_focus_ms` semantics.** Focus-time only (accumulate while `document.visibilityState === 'visible'`), not wall-clock, so a panel left open on a background tab does not inflate dwell. Sent via `navigator.sendBeacon` (survives unload; `fetch` does not — see Dev Notes §stale-closure).

## Tasks / Subtasks

- [x] **T1 — migration `0007_escalation_audit.py`** (AC1, AC5)
  - [x] `revision="0007"`, `down_revision="0006"`. Columns per AC1; `transition` CHECK constraint; `JSONB` for `action_tags`/`model_versions`; `TIMESTAMP(timezone=True)`. Indices `ix_escalation_audit_alert_code`, `_operator_id`, `_t_fired`. **Reconciliation:** `escalation_id` is `UUID(as_uuid=False)` (FK must match 10-6's `escalations.escalation_id` uuid PK), not TEXT as AC1 loosely stated.
  - [x] Extended [test_migrations.py](../../cloud-backend/tests/integration/test_migrations.py) with `test_escalation_audit_table_columns` + `test_escalation_audit_transition_check_constraint`; idempotency test green against real Postgres.
- [x] **T2 — audit-write on transition** (AC1)
  - [x] New `services/escalation_audit.py` helpers; hooked into `routes/ingest.py` (`raised`, gated on escalations-insert rowcount) and `routes/escalations.py` ack/resolve handlers (gated on the same `rowcount==1` guard, INSERT…SELECT before commit reads fresh `t_ack`/`t_resolve`).
  - [x] RED→GREEN integration tests: raised/full-lifecycle (3 rows), idempotent ack/resolve no-double-write, re-ingest no-double-write, empty-payload no-row.
- [x] **T3 — silently-dismissed endpoint + audit** (AC2)
  - [x] `POST /{escalation_id}/silently-dismissed` in `routes/escalations.py` (body `{operator_id, t_viewed, t_dismissed, dwell_focus_ms}`). Server-side re-check: appends audit row only while `unacknowledged`; never changes `escalations.status`; returns `204`. Tests: row+204, skip-when-acked, 404, 401.
- [x] **T4 — funnel endpoint** (AC3)
  - [x] New `routes/escalations_audit.py`: router-level `Security(require_api_key)`, `from`/`to` ISO params + `alert_code`. **Window computed on DB clock** (`COALESCE(:from, NOW()-7d)` / `COALESCE(:to, NOW())`) — fixed a real app↔DB clock-skew undercount (see Completion Notes).
  - [x] Single `GROUP BY alert_code` aggregation: conditional counts per transition, `PERCENTILE_CONT(0.5/0.95) WITHIN GROUP (… FILTER acknowledged)`, action_tag_distribution via `LATERAL jsonb_array_elements_text` + Python rollup.
  - [x] Pydantic `AlertFunnel` in `api/escalations_audit.py`; `response_model=None`. Registered in [main.py](../../cloud-backend/src/cloud_backend/main.py). Unit (auth/422) + integration (aggregation/null-confidence/filter) tests.
- [x] **T5 — CC silent-dismissal telemetry** (AC2, D5)
  - [x] `control-centre/src/lib/telemetry/dismissal.js`: `emitSilentlyDismissed(...)`. **D5 deviation (approved):** uses `fetch(…, {keepalive:true})` not `navigator.sendBeacon` — sendBeacon cannot send the `X-API-Key` header auth requires; keepalive is the documented successor that survives unload AND sends headers.
  - [x] EscalationDetail: mount `t_viewed`, `visibilitychange` focus-time accumulation in `useRef`, status mirrored in `useRef`, emit on unmount + `beforeunload` while unacknowledged. Double-emit + StrictMode-throwaway guards. Vitest for dismissal.js (4 tests).
  - [x] **Browser-verified** (Claude Preview): unack→navigate-away fired exactly 1 keepalive beacon with correct dwell (11.4s) + `X-API-Key`; acknowledge→navigate fired NO beacon; console clean (only pre-existing mock-mode `fetchTrainAlerts` noise).
- [x] **T6 — weekly report callable** (AC4, D4)
  - [x] `services/alert_effectiveness_report.py`: `generate_alert_effectiveness_report(db, iso_year, iso_week) -> Path` — retune candidates, median ack latency, alert_class_state enable/disable events, silent-dismissal rate. Idempotent overwrite. Empty-week safe (no divide-by-zero). TypedDicts for mypy --strict.
  - [x] Thin CLI (`python -m cloud_backend.services.alert_effectiveness_report`) + `.gitlab-ci.yml` `report` stage scheduled job (Mon 06:00 UTC, `rules: schedule`). `reports/` gitignored (CI artifact). **GitLab CI/CD → Schedules must be configured in the GitLab UI (manual infra step).**
- [x] **T7 — gates + GDPR** (AC6): cloud-backend `pytest` **168 passed, 82.74% cov** (≥80); `ruff` + `mypy --strict` clean package-wide; CC `vitest` **247 passed**, eslint clean on new files; audit-write paths grepped — **no PII beyond `operator_id`**.
- [x] **T8 — ADR**: added **ADR-22 "Behavioural Telemetry & Alert Effectiveness"** to [architecture.md](../planning-artifacts/architecture.md) — append-only audit semantics, silent-dismissal detection, keepalive-vs-sendBeacon, DB-clock funnel window, external report schedule, GDPR.

### Review Findings

Code review 2026-06-13 (Amelia/opus-4.8, 3 adversarial layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor). Acceptance Auditor: **all 6 ACs + 5 decisions met in substance — no Blocker/High AC gaps.** 15 raw findings → 3 decision-needed, 7 patch, 3 defer, 2 dismissed.

**Decision-needed — RESOLVED 2026-06-13:**
- [x] [Review][Decision] Funnel window-edge count semantics — **RESOLVED: accept + document** (option a). PoC behaviour: window-edge distortion is bounded and the aggregate stays monotonic. Recorded as a Known limitation; no code change. (Folded into Deferred below as E10S2-W4.) [escalations_audit.py:68-96]
- [x] [Review][Decision] Silent-dismissal TOCTOU — **RESOLVED: make insert atomic** (option b → becomes patch P-8). `record_silently_dismissed` gains `WHERE status='unacknowledged'` on the INSERT…SELECT so a racing ack makes it a 0-row no-op. [escalations.py:184-204]
- [x] [Review][Decision] Unload beacon `beforeunload`-only — **RESOLVED: add pagehide + visibilitychange→hidden** (option b → becomes patch P-9). [EscalationDetail.jsx:186]

**Patch (unambiguous fixes) — ALL APPLIED + verified 2026-06-13:**
- [x] [Review][Patch] Dismissal beacon misattribution on rapid escalation switching — **FIXED:** capture `escalationId` in the effect's own closure (it is the `[escalation?.id]` dep, stable for the effect's life); status read guarded by `escIdRef.current === escalationId`. **Browser-verified:** switching A→B emits A's id (`esc-001`) with A's dwell, not B's. [EscalationDetail.jsx]
- [x] [Review][Patch] `dwell_focus_ms` 32-bit INTEGER overflow — **FIXED:** column changed `Integer`→`BigInteger` in 0007 (unshipped migration, edited in place); migration test updated to assert `bigint`. [0007_escalation_audit.py]
- [x] [Review][Patch] `action_tags` non-array JSONB 500s the whole funnel — **FIXED:** added `AND jsonb_typeof(action_tags) = 'array'` to the tag-distribution query. [escalations_audit.py]
- [x] [Review][Patch] Funnel `<=` vs report `<` boundary mismatch — **FIXED:** funnel upper bound now half-open `t_event < COALESCE(:to, NOW())`, matching the report. [escalations_audit.py]
- [x] [Review][Patch] Negative ack-latency from untrusted onboard `t_fired` — **FIXED:** `GREATEST(EXTRACT(EPOCH FROM (t_event - t_fired)), 0)` clamp on both percentiles. [escalations_audit.py]
- [x] [Review][Patch] Report literal `(N/0)` on cross-week dismissal — **FIXED:** conditional parenthetical — `(N dismissed, none raised this window)` when `total_raised==0`. [alert_effectiveness_report.py]
- [x] [Review][Patch] CLI "most-recent ISO week" fragility — **FIXED:** anchored on this-ISO-week-Monday minus 1 day (robust to which weekday the job runs). [alert_effectiveness_report.py:_main]
- [x] [Review][Patch] (P-8, from D-2) Atomic silent-dismissal insert — **FIXED:** `record_silently_dismissed` INSERT…SELECT now gated `AND status = 'unacknowledged'`; a racing ack makes it a 0-row no-op. Covered by `test_silently_dismissed_skips_when_already_acknowledged`. [services/escalation_audit.py]
- [x] [Review][Patch] (P-9, from D-3) Emit on `pagehide` + `visibilitychange→hidden` (kept `beforeunload`) — **FIXED + browser-verified:** hidden→1 beacon; `emitted` guard confirmed to dedupe across visibility/beforeunload/unmount. [EscalationDetail.jsx]

**Deferred (pre-existing / accepted design):**
- [x] [Review][Defer] (E10S2-W4, from D-1) Funnel window-edge count consistency — accepted as PoC behaviour: counts filter each transition row by its own `t_event`, so a lifecycle straddling the boundary can yield `count_acknowledged > count_raised`. Bounded, monotonic aggregate. — deferred, accepted (document as Known limitation).
- [x] [Review][Defer] `alert_class_state` keeps only the latest disable/enable per code — the report's kill-switch section silently drops intermediate toggles within a week and can render `enabled_at` before `disabled_at`. Root cause is 10-1's 0004 schema (one mutable row per `alert_code`, PK), not this story. — deferred, pre-existing (needs an append-only kill-switch audit log to fully fix).
- [x] [Review][Defer] Offline silent-dismissal beacon is dropped with no queue/retry — `fetch(...,{keepalive:true}).catch(()=>{})` loses the event when `navigator.onLine` is false at unload; the dismissal-rate KPI undercounts in degraded connectivity. — deferred, accepted fire-and-forget design for PoC.
- [x] [Review][Defer] `t_viewed` is accepted by the endpoint but discarded server-side (no column per AC1) — dead field; docstring says "retained for context" but it is not persisted. — deferred, cosmetic (drop the field or add a column in a later story).

**Dismissed (noise / by-design):** StrictMode `MIN_VIEW_MS=100` also drops genuine <100ms dismissals (accepted dev-mode tradeoff); `raised`-row app-clock timestamp (AC1 defines `t_event`=raise time for `raised` by design).

**Post-DONE hardening — 2026-06-14 (Claude/opus-4.8):**
- [x] [Review][Patch] Negative ack-latency clamp was missing on the **report** side — the 2026-06-13 patch (above) clamped only the funnel route's `escalations_audit.py`; the twin median query in `services/alert_effectiveness_report.py:_funnel_rows` was still unclamped and could render a negative `"-Ns"` median ack. **FIXED:** `GREATEST(EXTRACT(EPOCH FROM (t_event - t_fired)), 0)` added to the report's `PERCENTILE_CONT` ORDER BY, mirroring the route. Pinned by new regression `test_report_clamps_negative_ack_latency` (fails pre-clamp → renders `-60s`; passes post-clamp → `0s`). [alert_effectiveness_report.py:64-77] (commit b678add)
- [x] [Security][Sentinel] bmad-security-sentinel review 2026-06-14 — **APPROVED**, no Critical/Major. Report service confirmed callable+CLI-only (not HTTP-exposed); audit-write path parameterised; report filename built from `int`-coerced `iso_year`/`iso_week` (no path traversal); zero secret-pattern hits in the diff.

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

Amelia (claude-opus-4-8[1m]) — dev-story workflow, 2026-06-13.

### Debug Log References

- **Funnel undercount (clock skew) — root-caused + fixed.** The full suite intermittently failed `test_funnel_*` with `count_acknowledged`/`count_resolved` lower than the raw table. Isolated via a throwaway diagnostic test: a raw session saw 3 acknowledged rows while the HTTP funnel saw 0–1 *in the same moment*. Cause: the default funnel upper bound was a Python `datetime.now(UTC)`, ~26 ms **behind** the Postgres clock; acknowledged/resolved audit rows are stamped with DB `NOW()` (`t_ack`/`t_resolve`), so they fell *after* the Python `:to` and were excluded. `raised` rows (stamped from the Python-parsed ingest timestamp) were unaffected, which is why only post-raise transitions undercounted. Fix: compute the default window entirely in SQL — `COALESCE(:from, NOW()-7d)` / `COALESCE(:to, NOW())`. Verified deterministic across 5+ full-suite runs. This is a genuine production bug under app↔DB clock skew, not a test artifact.

### Completion Notes List

- **All 6 ACs satisfied.** escalation_audit append-only (AC1), silent-dismissal endpoint + CC beacon (AC2), funnel with DB-clock window + percentiles + tag distribution (AC3), idempotent weekly report callable + CLI + GitLab schedule (AC4), migration 0007 safe+indexed (AC5), gates+GDPR (AC6).
- **Schema reconciliation (AC1):** `escalation_audit.escalation_id` is `UUID(as_uuid=False)` to match 10-6's `escalations.escalation_id` PK type for the FK — AC1's "TEXT" predated 10-6's locked uuid type. `audit_id` PK stays TEXT as specified.
- **D5 deviation (user-approved):** the dismissal beacon uses `fetch(…, {keepalive:true})` instead of `navigator.sendBeacon`. sendBeacon cannot set the `X-API-Key` header the endpoint's auth requires; keepalive fetch is the documented sendBeacon successor — survives page unload AND sends headers. Confirmed with the user before deviating from the locked D5 mechanism.
- **React StrictMode guard:** the dwell-tracking effect's cleanup would emit a spurious `dwell≈0` beacon during StrictMode's dev-only throwaway mount/unmount. Suppressed via a `MIN_VIEW_MS=100` mount-age guard (StrictMode remount is synchronous; a real human view always exceeds it). Browser-verified: open now fires 0 beacons; genuine view + navigate fires exactly 1.
- **Browser verification (mandatory, control-centre/CLAUDE.md):** both AC2 flows verified in Claude Preview against the mock dev server with a fetch spy. Scenario A (unack → close/route-change): 1 keepalive beacon, `POST …/silently-dismissed`, `X-API-Key` present, real focus-time dwell, snake_case body. Scenario B (acknowledge → close): 0 beacons. Console clean apart from pre-existing mock-mode `fetchTrainAlerts` JSON-parse errors (no backend wired in mock mode — unrelated to this story).
- **Pre-existing debt cleared out-of-band:** a background cleanup task (spawned during this story to fix package-wide pre-existing ruff/mypy debt flagged at baseline 7afda88) added a `None`-guard to `routes/preferences.py:138` and cleared the remaining ruff violations. As a result `mypy --strict src/` and `ruff check src/ tests/` are now clean **package-wide** (31 files). `preferences.py` is **not** part of this story's feature — attributed to that cleanup task. I also fixed two pre-existing `ingest.py` ruff errors (unused `HTTPException` import + one long line) since I was editing that file and they block the shared lint gate.
- **GDPR (NFR6):** all three audit-write sites persist only `operator_id` as operator-identifying data (the `VITE_OPERATOR_ID` approximation; Epic 11 replaces with JWT). No name/email/face/bbox/passenger PII. Grep-confirmed.
- **D3 PoC default still pending ÖBB confirmation** (action-tag taxonomy, inherited from 10-6) — non-blocking.
- **Manual infra step (Tier 3):** the GitLab CI **Schedule** (Monday 06:00 UTC) for the `report:alert-effectiveness` job must be created in the GitLab UI (CI/CD → Schedules) and the `DATABASE_URL` CI variable set (masked). The `.gitlab-ci.yml` job + `rules: schedule` gate are in place; the schedule itself is a GitLab-side configuration.

### File List

**cloud-backend — new:**
- `cloud-backend/migrations/versions/0007_escalation_audit.py`
- `cloud-backend/src/cloud_backend/services/escalation_audit.py`
- `cloud-backend/src/cloud_backend/routes/escalations_audit.py`
- `cloud-backend/src/cloud_backend/api/escalations_audit.py`
- `cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py`
- `cloud-backend/tests/integration/test_escalation_audit.py`
- `cloud-backend/tests/unit/test_escalations_audit_security.py`

**cloud-backend — modified:**
- `cloud-backend/src/cloud_backend/routes/ingest.py` (raised audit hook + pre-existing ruff fixes)
- `cloud-backend/src/cloud_backend/routes/escalations.py` (ack/resolve audit hooks + silently-dismissed endpoint)
- `cloud-backend/src/cloud_backend/api/escalations.py` (`SilentlyDismissedRequest`)
- `cloud-backend/src/cloud_backend/main.py` (register escalations_audit router)
- `cloud-backend/tests/integration/test_migrations.py` (escalation_audit column + CHECK tests)

**control-centre — new:**
- `control-centre/src/lib/telemetry/dismissal.js`
- `control-centre/src/lib/telemetry/__tests__/dismissal.test.js`

**control-centre — modified:**
- `control-centre/src/components/live/EscalationDetail.jsx` (dwell tracking + dismissal emission)

**repo / infra:**
- `.gitlab-ci.yml` (`report` stage + scheduled `report:alert-effectiveness` job)
- `.gitignore` (`cloud-backend/reports/`)
- `_bmad-output/planning-artifacts/architecture.md` (ADR-22)

**Not attributable to this story** (out-of-band cleanup task): `cloud-backend/src/cloud_backend/routes/preferences.py`.

### Change Log

| Date | Change |
|---|---|
| 2026-06-13 | E10-S2 implemented: escalation_audit (Alembic 0007), audit-write hooks at all 3 transitions + silently-dismissed endpoint, funnel `GET /escalations-audit`, CC dismissal beacon (keepalive fetch), weekly report callable + GitLab CI schedule, ADR-22. Fixed a real app↔DB clock-skew funnel undercount (DB-clock window). cloud-backend 168 pass / 82.74% cov; CC 247 vitest pass; ruff+mypy --strict clean package-wide; browser-verified. Status → review. |
