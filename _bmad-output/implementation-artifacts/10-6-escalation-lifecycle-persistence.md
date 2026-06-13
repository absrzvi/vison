# Story 10.6: Escalation Lifecycle Persistence (backend)

Status: ready-for-dev

<!-- Created 2026-06-13 via bmad-create-story (Amelia). Prerequisite for 10-2 (operator behavioural telemetry).
     Source: research workflow wf_bb727ef4-f6e (5-agent artifact+codebase audit) + independent verification.
     This story builds the MISSING backend half of E2-S5: the acknowledge/resolve endpoints the Control Centre
     already calls (control-centre/src/api/escalations.js:48,56) but which were never implemented server-side.
     Without server-side lifecycle persistence, 10-2's escalation_audit table has no write-trigger. -->

## Story

As a **Control Centre operator (Claudia) and the AI PM measuring adoption**,
I want **escalation acknowledge/resolve actions to be persisted server-side in an authoritative `escalations` table, with operator attribution and lifecycle timestamps**,
so that **operator actions survive page reload and are visible across operators, and there is a real server-side transition point that behavioural telemetry (10-2) can hook into**.

## Context — why this story exists

E2-S5 ("Escalation Detail — Acknowledge/Resolve", done) shipped the **Control Centre frontend only**. The CC calls `POST /api/v1/escalations/{id}/acknowledge` and `POST /api/v1/escalations/{id}/resolve` ([control-centre/src/api/escalations.js:48,56](../../control-centre/src/api/escalations.js)), but **no backend handler exists for either** — confirmed by grep across `cloud-backend/src/`: zero matches. [E2-S5's story file:29](2-5-escalation-detail-acknowledge-resolve.md) explicitly records the backend endpoints as an unbuilt dependency ("must exist (backend story dependency noted)"), and line 95 defers the backend status enum.

Today, alerts exist only as `ALERT_RAISED` / `ALERT_RESOLVED` rows in the `events` JSONB table ([0001_initial_schema.py:39-77](../../cloud-backend/migrations/versions/0001_initial_schema.py)). There is no `escalations` table and no acknowledged/resolved state persisted server-side. The CC keeps lifecycle state in `FleetContext` via optimistic updates ([FleetContext.jsx:300,322](../../control-centre/src/context/FleetContext.jsx)) — lost on reload.

This story closes that gap so that 10-2 can audit real transitions instead of inferring them client-side.

## Acceptance Criteria

**AC1 — escalations table exists**
Given a fresh database, when migration `0006` is applied, then an `escalations` table exists with columns: `escalation_id` (TEXT PK — the ALERT_RAISED `event_id`, see D1), `alert_id` (TEXT, NOT NULL — payload `alert_id`, for ALERT_RESOLVED pairing), `alert_event_id` (TEXT, FK→`events.event_id`), `alert_code` (TEXT, NOT NULL), `journey_id` (TEXT, NOT NULL), `vehicle_id` (TEXT, NOT NULL), `status` (TEXT, NOT NULL, CHECK in `unacknowledged|acknowledged|resolved`, default `unacknowledged`), `t_fired` (TIMESTAMPTZ, NOT NULL), `t_ack` (TIMESTAMPTZ, NULL), `t_resolve` (TIMESTAMPTZ, NULL), `ack_operator_id` (TEXT, NULL), `resolve_operator_id` (TEXT, NULL), `outcome` (TEXT, NULL), `action_tags` (JSONB, NULL), `confidence_score` (DOUBLE PRECISION, NULL), `confidence_basis` (TEXT, NULL), `model_versions` (JSONB, NULL).

**AC2 — escalation row created on ALERT_RAISED ingest**
Given an `ALERT_RAISED` event is ingested via `POST /api/v1/events`, when the event is persisted, then an `escalations` row is upserted with `escalation_id` = the event's **`event_id`** (the envelope id — this is the id the Control Centre uses in its acknowledge/resolve URLs; see D1), `alert_event_id` = the same `event_id`, `alert_code`/`confidence_score`/`confidence_basis`/`model_versions` copied from the `AlertRaisedPayload`, `t_fired` = event `source_timestamp`, `status` = `unacknowledged`. Also persist the payload `alert_id` in an `alert_id` column (for ALERT_RESOLVED pairing). Idempotent on `escalation_id` (ON CONFLICT DO NOTHING).

**AC3 — acknowledge endpoint**
Given an `escalations` row in `unacknowledged` state, when `POST /api/v1/escalations/{escalation_id}/acknowledge` is called with body `{"operator_id": "<id>"}` and a valid `X-API-Key`, then the row's `status` → `acknowledged`, `t_ack` = server `NOW()`, `ack_operator_id` = body `operator_id`; the endpoint returns `200` with the updated escalation; a re-acknowledge of an already-acknowledged/resolved row is a no-op returning `200` (idempotent), and an unknown `escalation_id` returns `404`.

**AC4 — resolve endpoint**
Given an `escalations` row in `acknowledged` state, when `POST /api/v1/escalations/{escalation_id}/resolve` is called with body `{"outcome": "<text ≤200 chars>", "action_tags": ["<tag>", ...], "operator_id": "<id>"}` and a valid `X-API-Key`, then `status` → `resolved`, `t_resolve` = `NOW()`, `resolve_operator_id`/`outcome`/`action_tags` persisted; returns `200`. Resolving a `resolved` row is idempotent `200`; resolving an `unacknowledged` row returns `409` (must acknowledge first); unknown id → `404`. `action_tags` must be a non-empty list of values from the locked taxonomy (D3) — invalid tag → `422`.

**AC5 — SSE fan-out of lifecycle transitions**
Given an acknowledge or resolve succeeds, when the row is updated, then an `ESCALATION_UPDATED`-equivalent is published to SSE subscribers so other operators' open panels converge (satisfies E2-S5 AC4's cross-operator sync, which currently relies on a backend broadcast that does not exist). Reuse the existing `publish_alert` fan-out path ([alerts_sse.py](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)).

**AC6 — CC acknowledge sends operator_id**
Given the CC `acknowledge` flow, when `acknowledgeEscalation(id)` is called, then the request body includes `{"operator_id": OPERATOR_ID}` (currently it sends no body — [escalations.js:47-49](../../control-centre/src/api/escalations.js)). This is the only CC change in this story; resolve already sends `operator_id` ([escalations.js:55-60](../../control-centre/src/api/escalations.js)).

**AC7 — migration safe + idempotent**
Given the migration, then it is a new-table-only migration (safe under concurrent reads, no full-table locks), `down_revision = "0005"`, and `test_upgrade_head_idempotent` passes (applying `upgrade head` twice does not raise). Indices on `status`, `alert_code`, `t_fired`.

**AC8 — coverage + gates**
`cloud-backend` unit + integration tests cover AC2–AC5 at ≥80% coverage; `ruff` + `mypy` clean on touched `src/` files; CC `vitest` green for the `escalations.js` body change.

## Decisions (locked — review before dev)

- **D1 — `escalation_id` source = event_id (VERIFIED).** Use the **`ALERT_RAISED` event's envelope `event_id`** as the `escalations` PK. **This is non-negotiable and verified against the live CC:** [RealWebSocketClient.js:172](../../control-centre/src/ws/RealWebSocketClient.js) builds the CC escalation object with `id: event_id`, so the CC calls `POST /api/v1/escalations/{event_id}/acknowledge` ([escalations.js:48](../../control-centre/src/api/escalations.js)). Keying the table on the payload `alert_id` instead would 404 every acknowledge. Store the payload `alert_id` in a separate `alert_id` column so `ALERT_RESOLVED` (which pairs on `alert_id` per the payload docstring) can still be matched. **RED test first:** assert an ingested ALERT_RAISED creates an `escalations` row whose PK equals the event's `event_id`, then assert `acknowledge` with that id returns 200.
- **D2 — `model_versions` shape.** Store the **full `model_versions` dict as JSONB** (lossless), NOT the singular `model_version` string the epic text assumes ([epics.md:2251](../../_bmad-output/planning-artifacts/epics.md)). Shipped `AlertRaisedPayload.model_versions` is `dict[str, str]` ([payloads.py:110](../../shared/src/oebb_shared/events/payloads.py)); reducing to one value is lossy and arbitrary. **This overrides the epic's `model_version` column.**
- **D3 — tag naming + taxonomy.** Field name is **`action_tags`** everywhere (the live CC contract already ships `action_tags` — [escalations.js:58](../../control-centre/src/api/escalations.js); renaming to the epic's `outcome_tags` is gratuitous churn). PoC taxonomy (enforced server-side, `422` on violation): `cctv_verified`, `passenger_assisted`, `staff_dispatched`, `security_notified`, `false_alarm`, `no_action_needed`, `escalated_external`. **⚠ Confirm this set with the PM/OEBB before dev — it is the funnel's `outcome_tag_distribution` dimension in 10-2.**
- **D4 — `alert_class` vs `alert_code`.** The epic calls the funnel dimension `alert_class`; the shipped payload field is `alert_code` ([payloads.py:102](../../shared/src/oebb_shared/events/payloads.py)). Use **`alert_code`** as the column/dimension name throughout (no separate "class" concept exists). 10-2 funnels group by `alert_code`.
- **D5 — `confidence_score` nullable.** `confidence_score` is `None` when `confidence_basis == "sensor"` ([payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py)). Column is NULLABLE; 10-2 aggregations must `NULLIF`/filter nulls.
- **D6 — operator identity.** `operator_id` stays the env-var approximation E2-S5 accepted (`VITE_OPERATOR_ID`, [FleetContext.jsx:17](../../control-centre/src/context/FleetContext.jsx)); real per-operator identity is deferred to Epic 11 (JWT). Audit inherits this limitation — acceptable for PoC.

## Tasks / Subtasks

- [ ] **T1 — Alembic migration `0006_escalations.py`** (AC1, AC7)
  - [ ] Create `cloud-backend/migrations/versions/0006_escalations.py`, `revision="0006"`, `down_revision="0005"` (current head is 0005 — [0005_train_inference_heartbeat.py:15-16](../../cloud-backend/migrations/versions/0005_train_inference_heartbeat.py)).
  - [ ] `op.create_table("escalations", ...)` with columns per AC1; `JSONB` from `sqlalchemy.dialects.postgresql`; timestamps `sa.TIMESTAMP(timezone=True)`; `sa.CheckConstraint("status IN ('unacknowledged','acknowledged','resolved')", name="ck_escalations_status_valid")`.
  - [ ] `op.create_index("ix_escalations_status", "escalations", ["status"])`, `ix_escalations_alert_code`, `ix_escalations_t_fired`.
  - [ ] `downgrade()` drops indices then table.
  - [ ] Extend [test_migrations.py](../../cloud-backend/tests/integration/test_migrations.py) with a `test_escalations_table_columns` (information_schema assertions) following `test_events_table_columns` pattern; confirm `test_upgrade_head_idempotent` still green.
- [ ] **T2 — escalation upsert on ALERT_RAISED ingest** (AC2)
  - [ ] **READ FIRST (UPDATE file):** [cloud-backend/src/cloud_backend/routes/ingest.py](../../cloud-backend/src/cloud_backend/routes/ingest.py) in full — see Dev Notes §ingest.py for current behaviour. The escalation upsert is added inside the per-event loop, after the `events` INSERT, gated on `ev.event_type == "ALERT_RAISED"`.
  - [ ] Extract `alert_id`, `alert_code`, `confidence_score`, `confidence_basis`, `model_versions` from `ev.payload`; upsert escalations row (`ON CONFLICT (escalation_id) DO NOTHING`).
  - [ ] RED test: ingest an `ALERT_RAISED`, assert one `escalations` row with status `unacknowledged` and copied fields.
- [ ] **T3 — `routes/escalations.py` router** (AC3, AC4, AC5)
  - [ ] New `cloud-backend/src/cloud_backend/routes/escalations.py`: `APIRouter(prefix="/api/v1/escalations", dependencies=[Security(require_api_key)])` (router-level auth — [analytics.py:32](../../cloud-backend/src/cloud_backend/routes/analytics.py)).
  - [ ] `POST /{escalation_id}/acknowledge` (body `AckRequest{operator_id}`) and `POST /{escalation_id}/resolve` (body `ResolveRequest{outcome, action_tags, operator_id}`), Pydantic request models in `cloud-backend/src/cloud_backend/api/escalations.py`.
  - [ ] State-machine guards per AC3/AC4 (404 unknown, 409 resolve-before-ack, 422 bad tag, idempotent re-transition). Validate `action_tags` ⊆ D3 taxonomy.
  - [ ] On success, publish lifecycle update to SSE via existing `publish_alert` ([alerts_sse.py](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)) (AC5).
  - [ ] Register router in [main.py](../../cloud-backend/src/cloud_backend/main.py) (`include_router`).
- [ ] **T4 — CC acknowledge body** (AC6)
  - [ ] [control-centre/src/api/escalations.js:47-49](../../control-centre/src/api/escalations.js): `acknowledgeEscalation(id, operatorId)` → `_post(.../acknowledge, { operator_id: operatorId })`; update caller [FleetContext.jsx:295](../../control-centre/src/context/FleetContext.jsx) to pass `OPERATOR_ID`.
  - [ ] Update `escalations.test.js` for the new body. **Browser-verify** acknowledge + resolve round-trip per control-centre/CLAUDE.md Verification Requirement (loading/error/populated).
- [ ] **T5 — gates** (AC8): `cd cloud-backend && python -m pytest` (unit+integration), `ruff check src/`, `mypy src/`; `cd control-centre && npm run lint && npx vitest run`.
- [ ] **T6 — ADR** (freshness rule): add **ADR-21 "Escalation Lifecycle Persistence"** to [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) documenting the `escalations` table, the ingest-time upsert, and the ack/resolve state machine. Ship in the same commit. (Research confirmed no existing ADR covers escalation audit/lifecycle — [architecture.md ADR-17/18/19/20] cover ledger/telemetry/ingest/SSE only.)

## Dev Notes

### ingest.py — current state (UPDATE file, read fully)
[ingest.py](../../cloud-backend/src/cloud_backend/routes/ingest.py) `POST /api/v1/events` loops over `body.events` (validated `EventEnvelope`), parses `ts_dt` from `ev.timestamp`, upserts a `journeys` row (FK guard), inserts into `events` with `ON CONFLICT ON CONSTRAINT uq_events_journey_type_source_ts DO NOTHING`, then for `INFERENCE_HEARTBEAT` calls `upsert_heartbeat`, and for `ALERT_EVENT_TYPES` fans out via `publish_alert` unless `alert_class_filter.is_filtered`. **What this story changes:** add an escalation upsert for `ALERT_RAISED` after the events INSERT. **What must be preserved:** the existing heartbeat upsert, the kill-switch fan-out filter, the duplicate-handling rowcount logic, and `db.commit()` at the end (single transaction per request).

### Migration pattern (exact)
Head is `0005`. New migration is `0006`, `down_revision="0005"`. Use `sa.TIMESTAMP(timezone=True)` (NOT `sa.DateTime`), `JSONB` from `sqlalchemy.dialects.postgresql`, `sa.CheckConstraint` with single-quote-escaped literals, `op.create_index("ix_...")`. New-table-only → concurrent-read-safe (no `CONCURRENTLY` used in this project). Tests are `@pytest.mark.integration` with `testcontainers` Postgres; idempotency asserted by `test_upgrade_head_idempotent`.

### API + auth pattern (exact)
Router-level `Security(require_api_key)` (validates `X-API-Key` against `get_settings().api_key`, [api/auth.py:11-17](../../cloud-backend/src/cloud_backend/api/auth.py)) — do NOT add per-route auth. Error shape `{"detail": "..."}` per cloud-backend/CLAUDE.md (never raw exception text). No sync DB calls in async handlers — `await db.execute(...)`. Request models go in `cloud-backend/src/cloud_backend/api/` (no `api/v1/` subdir exists — the `/v1` is only in the router prefix).

### CC contract (exact)
`_post(path, body)` sets `Content-Type` + `X-API-Key`, throws on non-ok, returns `{}` on 204 else `json()` ([escalations.js:13-31](../../control-centre/src/api/escalations.js)). `resolveEscalation` already sends `{outcome, action_tags, operator_id}`. `acknowledgeEscalation` currently sends **no body** — this story adds `{operator_id}`. `OPERATOR_ID = import.meta.env.VITE_OPERATOR_ID ?? 'operator-unknown'` ([FleetContext.jsx:17](../../control-centre/src/context/FleetContext.jsx)). The escalation object carries `id` + `status` (`unacknowledged|acknowledged|resolved`), optimistically updated at [FleetContext.jsx:300,322](../../control-centre/src/context/FleetContext.jsx).

### Payload field reference (shipped — source of truth)
`AlertRaisedPayload` ([payloads.py:94-135](../../shared/src/oebb_shared/events/payloads.py)): `alert_id`, `alert_code`, `car_id`, `confidence_score: float|None`, `confidence_basis: Literal["model","sensor","fused"]`, `model_versions: dict[str,str]`. Validator: `sensor`→score None + model_versions empty; `model`→score in [0,1] + ≥1 model; `fused`→≥2 models.

### Testing standards
cloud-backend: `pytest -m unit` (fast) + `pytest -m integration` (Docker/testcontainers); coverage ≥80%. CC: Vitest + browser verification (mandatory for UI changes). Red→green→refactor.

### Project Structure Notes
- Migration: `cloud-backend/migrations/versions/0006_escalations.py` (NOT hand-crafted SQL elsewhere — cloud-backend/CLAUDE.md "What NOT to Touch").
- Router: `cloud-backend/src/cloud_backend/routes/escalations.py`; models: `cloud-backend/src/cloud_backend/api/escalations.py`. (Epic's `src/api/v1/...` path is wrong — no v1 dir.)
- One CC file: `control-centre/src/api/escalations.js` (+ its test).

### References
- [Source: epics.md#Story-E10-S2] (the `escalation_audit` ACs that depend on this lifecycle)
- [Source: 2-5-escalation-detail-acknowledge-resolve.md:29,95] (backend dependency noted + status enum deferred)
- [Source: cloud-backend/migrations/versions/0005_train_inference_heartbeat.py] (migration precedent, head)
- [Source: cloud-backend/src/cloud_backend/routes/ingest.py] (ingest loop to extend)
- [Source: cloud-backend/src/cloud_backend/routes/analytics.py:32] (router + auth pattern)
- [Source: control-centre/src/api/escalations.js] (CC contract)
- [Source: shared/src/oebb_shared/events/payloads.py:94-135] (AlertRaisedPayload)
- Research: workflow `wf_bb727ef4-f6e` (schema-payload-audit, alembic-migration-pattern, api-route-and-analytics-pattern agents)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
