---
baseline_commit: 6a2c8846c3eb2c7cf8b6d44c1b8d502cfe688cdd
---

# Story 10.6: Escalation Lifecycle Persistence (backend)

Status: done

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

**Actor model (2026-06-13 correction):** the PoC has **no on-train conductor and no "Conrad"**, and the Fleet Manager does **not** alert police or stations. The single operator is the **landside Fleet Manager (Claudia)**: their *acknowledge* implies the required action has been taken, and *resolve* records the outcome of that action. This invalidates the shipped `ACTION_TAGS` taxonomy ([EscalationDetail.jsx:8](../../control-centre/src/components/live/EscalationDetail.jsx)), which this story replaces (D3 / AC9).

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
Given the CC `acknowledge` flow, when `acknowledgeEscalation(id)` is called, then the request body includes `{"operator_id": OPERATOR_ID}` (currently it sends no body — [escalations.js:47-49](../../control-centre/src/api/escalations.js)). Resolve already sends `operator_id` ([escalations.js:55-60](../../control-centre/src/api/escalations.js)). (The other CC change in this story is the action-tag replacement — AC9.)

**AC7 — migration safe + idempotent**
Given the migration, then it is a new-table-only migration (safe under concurrent reads, no full-table locks), `down_revision = "0005"`, and `test_upgrade_head_idempotent` passes (applying `upgrade head` twice does not raise). Indices on `status`, `alert_code`, `t_fired`.

**AC8 — coverage + gates**
`cloud-backend` unit + integration tests cover AC2–AC5 at ≥80% coverage; `ruff` + `mypy` clean on touched `src/` files; CC `vitest` green for the `escalations.js` body change and the new `ACTION_TAGS`.

**AC9 — replace stale action-tag taxonomy**
Given the shipped resolve picker, when this story lands, then the `ACTION_TAGS` array ([EscalationDetail.jsx:8-15](../../control-centre/src/components/live/EscalationDetail.jsx)) shows exactly the four landside outcomes (`Resolved remotely`, `Field team dispatched`, `False alarm`, `No action needed`) — the stale `Conrad instructed`/`Police alerted`/`Station notified`/`Passenger assisted`/`No action required`/`Other` are removed; the backend resolve endpoint accepts only the four canonical keys (D3) and maps labels→keys; existing CC tests asserting old tag values are updated; the resolve flow is browser-verified end-to-end with a new tag.

## Decisions (locked — review before dev)

- **D1 — `escalation_id` source = event_id (VERIFIED).** Use the **`ALERT_RAISED` event's envelope `event_id`** as the `escalations` PK. **This is non-negotiable and verified against the live CC:** [RealWebSocketClient.js:172](../../control-centre/src/ws/RealWebSocketClient.js) builds the CC escalation object with `id: event_id`, so the CC calls `POST /api/v1/escalations/{event_id}/acknowledge` ([escalations.js:48](../../control-centre/src/api/escalations.js)). Keying the table on the payload `alert_id` instead would 404 every acknowledge. Store the payload `alert_id` in a separate `alert_id` column so `ALERT_RESOLVED` (which pairs on `alert_id` per the payload docstring) can still be matched. **RED test first:** assert an ingested ALERT_RAISED creates an `escalations` row whose PK equals the event's `event_id`, then assert `acknowledge` with that id returns 200.
- **D2 — `model_versions` shape.** Store the **full `model_versions` dict as JSONB** (lossless), NOT the singular `model_version` string the epic text assumes ([epics.md:2251](../../_bmad-output/planning-artifacts/epics.md)). Shipped `AlertRaisedPayload.model_versions` is `dict[str, str]` ([payloads.py:110](../../shared/src/oebb_shared/events/payloads.py)); reducing to one value is lossy and arbitrary. **This overrides the epic's `model_version` column.**
- **D3 — tag naming + taxonomy (REPLACES stale shipped set — landside-only actor model).** Field name is **`action_tags`** everywhere (the live CC contract already ships `action_tags` — [escalations.js:58](../../control-centre/src/api/escalations.js); the epic's `outcome_tags` is superseded). **The shipped `ACTION_TAGS` ([EscalationDetail.jsx:8-15](../../control-centre/src/components/live/EscalationDetail.jsx): `Passenger assisted / Police alerted / Station notified / Conrad instructed / No action required / Other`) are STALE and must be replaced** — the PoC has no on-train conductor (no "Conrad"), and the Fleet Manager does not alert police or stations. The only actor is the **landside Fleet Manager (Claudia)**, whose acknowledge already implies they have taken the required action; the resolve step records the *outcome* of that action. New PoC taxonomy (4, decisive — no catch-all), canonical key → UI label: `resolved_remotely` → "Resolved remotely"; `field_team_dispatched` → "Field team dispatched"; `false_alarm` → "False alarm"; `no_action_needed` → "No action needed". **Store the canonical key, not the label** — the acknowledge/resolve endpoint maps incoming label → key via a constant dict (single source of truth in `cloud_backend/api/escalations.py`) so re-wording a UI label never re-buckets historical funnel data in 10-2. `422` on any value outside the four. `false_alarm` + `no_action_needed` together are the false-positive signal (feeds deferred E10-S5 FP-rate work). **⚠ PoC default pending ÖBB confirmation; non-blocking for dev.** If ÖBB changes the set, update the UI `ACTION_TAGS` array, this backend enum, and the key-map in lockstep — keys are the contract, labels are display-only.
  - **This story must also update the shipped UI** ([EscalationDetail.jsx:8-15](../../control-centre/src/components/live/EscalationDetail.jsx) `ACTION_TAGS` array + [escalations.test.js:58-59](../../control-centre/src/api/__tests__/escalations.test.js) which asserts the stale `'Passenger assisted'` value) so the picker matches the new taxonomy — see T4.
- **D4 — `alert_class` vs `alert_code`.** The epic calls the funnel dimension `alert_class`; the shipped payload field is `alert_code` ([payloads.py:102](../../shared/src/oebb_shared/events/payloads.py)). Use **`alert_code`** as the column/dimension name throughout (no separate "class" concept exists). 10-2 funnels group by `alert_code`.
- **D5 — `confidence_score` nullable.** `confidence_score` is `None` when `confidence_basis == "sensor"` ([payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py)). Column is NULLABLE; 10-2 aggregations must `NULLIF`/filter nulls.
- **D6 — operator identity.** `operator_id` stays the env-var approximation E2-S5 accepted (`VITE_OPERATOR_ID`, [FleetContext.jsx:17](../../control-centre/src/context/FleetContext.jsx)); real per-operator identity is deferred to Epic 11 (JWT). Audit inherits this limitation — acceptable for PoC.

## Tasks / Subtasks

- [x] **T1 — Alembic migration `0006_escalations.py`** (AC1, AC7)
  - [x] Create `cloud-backend/migrations/versions/0006_escalations.py`, `revision="0006"`, `down_revision="0005"` (current head is 0005 — [0005_train_inference_heartbeat.py:15-16](../../cloud-backend/migrations/versions/0005_train_inference_heartbeat.py)).
  - [x] `op.create_table("escalations", ...)` with columns per AC1; `JSONB` from `sqlalchemy.dialects.postgresql`; timestamps `sa.TIMESTAMP(timezone=True)`; `sa.CheckConstraint("status IN ('unacknowledged','acknowledged','resolved')", name="ck_escalations_status_valid")`. **Refinement:** `escalation_id`/`alert_event_id` are `UUID(as_uuid=False)` (not TEXT) to match `events.event_id` type (uuid) — see Change Log.
  - [x] `op.create_index("ix_escalations_status", "escalations", ["status"])`, `ix_escalations_alert_code`, `ix_escalations_t_fired`.
  - [x] `downgrade()` drops indices then table.
  - [x] Extend [test_migrations.py](../../cloud-backend/tests/integration/test_migrations.py) with a `test_escalations_table_columns` (information_schema assertions) following `test_events_table_columns` pattern; confirm `test_upgrade_head_idempotent` still green. ✅ both pass.
- [x] **T2 — escalation upsert on ALERT_RAISED ingest** (AC2)
  - [x] **READ FIRST (UPDATE file):** [cloud-backend/src/cloud_backend/routes/ingest.py](../../cloud-backend/src/cloud_backend/routes/ingest.py) in full — read; upsert added inside the per-event loop after the `events` INSERT, gated on `ev.event_type == "ALERT_RAISED"`. Preserved heartbeat upsert, kill-switch fan-out, rowcount/commit.
  - [x] Extract `alert_id`, `alert_code`, `confidence_score`, `confidence_basis`, `model_versions` from `ev.payload`; upsert escalations row (`ON CONFLICT (escalation_id) DO NOTHING`).
  - [x] RED→GREEN test: `test_alert_raised_creates_escalation_row` + `_idempotent` pass.
- [x] **T3 — `routes/escalations.py` router** (AC3, AC4, AC5)
  - [x] New `cloud-backend/src/cloud_backend/routes/escalations.py`: `APIRouter(prefix="/api/v1/escalations", dependencies=[Security(require_api_key)])`.
  - [x] `POST /{escalation_id}/acknowledge` (body `AckRequest{operator_id}`) and `POST /{escalation_id}/resolve` (body `ResolveRequest{outcome, action_tags, operator_id}`), request models in `cloud-backend/src/cloud_backend/api/escalations.py`.
  - [x] State-machine guards per AC3/AC4 (404 unknown, 409 resolve-before-ack, 422 bad tag, idempotent re-transition); `action_tags` mapped label→key via `ACTION_TAG_KEYS`.
  - [x] On success, publish `ESCALATION_UPDATED` lifecycle frame to SSE via existing `publish_alert` (AC5).
  - [x] Register router in [main.py](../../cloud-backend/src/cloud_backend/main.py) (`include_router`).
- [x] **T4 — CC acknowledge body + replace stale action tags** (AC6, AC9)
  - [x] [control-centre/src/api/escalations.js:47-49](../../control-centre/src/api/escalations.js): `acknowledgeEscalation(id, operatorId)` → `_post(.../acknowledge, { operator_id: operatorId })`; caller [FleetContext.jsx:295](../../control-centre/src/context/FleetContext.jsx) passes `OPERATOR_ID`.
  - [x] [EscalationDetail.jsx](../../control-centre/src/components/live/EscalationDetail.jsx) — replaced the stale `ACTION_TAGS` array with the D3 set: `Resolved remotely`, `Field team dispatched`, `False alarm`, `No action needed`. Picker + validation unchanged structurally; resolve form behaviour preserved.
  - [x] Resolve POST sends labels; 10-6 resolve endpoint maps label→key via `ACTION_TAG_KEYS` (verified by integration `test_resolve_transitions_to_resolved` asserting `['resolved_remotely']` stored).
  - [x] Updated [escalations.test.js](../../control-centre/src/api/__tests__/escalations.test.js) (ack operator_id body + new tags). **Browser-verified:** dev server serves the new ACTION_TAGS (`Resolved remotely`/`Field team dispatched`/`False alarm`/`No action needed`), stale `Conrad instructed` absent; app renders clean (pre-existing `fetchTrainAlerts` backend-absent errors only). CC vitest 243/243.
- [x] **T5 — gates** (AC8): cloud-backend full suite **142 passed / 0 failed** (was 130; +12 new escalation/migration tests). `ruff check src/` + `mypy src/` clean on all files this story touched (my new `routes/escalations.py` + `api/escalations.py` are 0/0; the escalation upsert added to `ingest.py` introduced no new violations — the 2 pre-existing ingest.py findings + the other src violations predate baseline 6a2c884 and are left per surgical-changes). My test file `test_escalations.py` ruff-clean. CC `vitest` **243 passed**.
- [x] **T6 — ADR** (freshness rule): added **ADR-21 "Escalation Lifecycle Persistence"** to [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) (after ADR-20) — `escalations` table, ingest-time upsert, ack/resolve state machine, actor model + taxonomy, ESCALATION_UPDATED fan-out.

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

## Senior Developer Review (AI) — Round 1

Reviewed 2026-06-13 (claude-opus-4-8[1m]) via 3 adversarial layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor — workflow `wf_e710dd45-3f5`). 25 raw findings → triaged against live HEAD. **Outcome: Changes Requested → RESOLVED.** 3 patches applied (1 Blocker + 2 Med) + verified; 3 deferred (pre-existing/E2-S1 scope); 1 false-positive dismissed; ~15 LOW noise dismissed. No High survived verification. Post-patch: cloud-backend **143 passed**, CC **243 passed**, ruff+mypy clean on touched files.

### Review Findings

**Patch (RESOLVED 2026-06-13):**
- [x] [Review][Patch] **[BLOCKER] ESCALATION_UPDATED SSE frame missing `id` field** [routes/escalations.py `_publish_lifecycle`] — FIXED: frame now includes `id` (= escalation_id) so the CC consumer ([FleetContext.jsx:121](../../control-centre/src/context/FleetContext.jsx)) matches. Test extended (`test_acknowledge_publishes_sse_frame` asserts `frame["id"]`). *(Note: end-to-end convergence also needs E2-S1's WS→SSE client migration — deferred below; the backend frame is now correct regardless of transport.)*
- [x] [Review][Patch] **Transition publishes/logs even on a 0-row UPDATE under concurrency** — FIXED: both acknowledge + resolve capture `result.rowcount` (typed `CursorResult`) and gate `_publish_lifecycle` + log on `== 1`. No redundant SSE frame / duplicate log under a concurrent-transition race.
- [x] [Review][Patch] **Empty-payload ALERT_RAISED → NOT-NULL 500 on escalation insert** — FIXED: ingest skips the escalation upsert with a structured `escalation_skipped_missing_alert_fields` warning when `alert_id`/`alert_code` are absent; event still stored, request returns 202. New test `test_alert_raised_empty_payload_skips_escalation_no_500`.

**Deferred (pre-existing / out of scope — not caused by this change):**
- [x] [Review][Defer] **Duplicate `publish_alert` on duplicate ALERT_RAISED ingest** [routes/ingest.py] — pre-existing ALERT_RAISED SSE fan-out behaviour, untouched by this story; tracked for Epic 9.
- [x] [Review][Defer] **SSE replay omits ESCALATION_UPDATED on reconnect** [routes/alerts_sse.py `_replay_since`] — inherent to ADR-20 (REST reconciles on reconnect; ESCALATION_UPDATED is not DB-persisted). Architectural; document, don't fix here.
- [x] [Review][Defer] **CC still uses WebSocket transport, not SSE** [control-centre/src/ws/RealWebSocketClient.js] — E2-S1 ("Real SSE Client") owns the WS→SSE migration per ADR-20; cross-operator convergence is end-to-end only once that lands.

**Dismissed (false positive / non-actionable):**
- [Review][Dismiss] **AC4 "resolved row + invalid tag → 200"** (Acceptance Auditor, claimed High) — FALSE POSITIVE: tag validation ([escalations.py:98-103](../../cloud-backend/src/cloud_backend/routes/escalations.py)) runs BEFORE the `status == 'acknowledged'` idempotent branch, so a resolved row with an invalid tag returns 422 as specified. Confirmed against live code.
- [Review][Dismiss] ~15 LOW/nit findings affirming correctness (AC1 columns present, D2 round-trip tested, D5 nullable, idempotence covered) or requesting extra tests for already-covered paths.

## Dev Agent Record

### Agent Model Used

Amelia (claude-opus-4-8[1m])

### Debug Log References

- RED→GREEN for all ACs; full cloud-backend suite **142 passed / 0 failed** (130 → 142, +12 new); CC vitest **243 passed**.
- `ruff check src/` + `mypy src/` — my new files (`routes/escalations.py`, `api/escalations.py`) and my test file are 0/0. Pre-existing src violations (ingest.py F401 HTTPException + E501:70; analytics/fleet/error_handlers/preferences) confirmed present at baseline `6a2c884`, left per surgical-changes.
- Browser-verified (Claude Preview): dev server serves the new `ACTION_TAGS`; stale `Conrad instructed` absent; app renders clean.

### Completion Notes List

- **AC1/AC7:** `0006_escalations.py` — new table, indices on status/alert_code/t_fired, idempotent. `escalation_id`/`alert_event_id` typed **UUID** (not the AC's TEXT) to match `events.event_id` (uuid) — see Change Log.
- **AC2:** ingest.py upserts an `escalations` row on `ALERT_RAISED` keyed on `event_id` (the CC's URL id), copying alert_code/confidence/model_versions; `ON CONFLICT DO NOTHING`. Heartbeat upsert + kill-switch fan-out + commit preserved.
- **AC3/AC4/AC5:** `routes/escalations.py` ack/resolve with state-machine guards (404/409/422, idempotent), label→key tag map, `ESCALATION_UPDATED` SSE fan-out via `publish_alert`.
- **AC6/AC9:** CC `acknowledgeEscalation(id, operatorId)` sends operator_id; `ACTION_TAGS` replaced with the 4 landside outcomes. `escalations.test.js` updated; full CC suite green.
- **D3 taxonomy** is the PoC default — **pending ÖBB confirmation** (non-blocking). `false_alarm`+`no_action_needed` = FP signal for E10-S5.
- ADR-21 added.

### File List

- `cloud-backend/migrations/versions/0006_escalations.py` (NEW)
- `cloud-backend/src/cloud_backend/routes/escalations.py` (NEW)
- `cloud-backend/src/cloud_backend/api/escalations.py` (NEW)
- `cloud-backend/src/cloud_backend/routes/ingest.py` (UPDATE — ALERT_RAISED escalation upsert)
- `cloud-backend/src/cloud_backend/main.py` (UPDATE — register escalations router)
- `cloud-backend/tests/integration/test_escalations.py` (NEW)
- `cloud-backend/tests/integration/test_migrations.py` (UPDATE — test_escalations_table_columns)
- `control-centre/src/api/escalations.js` (UPDATE — acknowledge operator_id body)
- `control-centre/src/context/FleetContext.jsx` (UPDATE — pass OPERATOR_ID to acknowledge)
- `control-centre/src/components/live/EscalationDetail.jsx` (UPDATE — ACTION_TAGS taxonomy)
- `control-centre/src/api/__tests__/escalations.test.js` (UPDATE — new body + tags)
- `_bmad-output/planning-artifacts/architecture.md` (UPDATE — ADR-21)

### Change Log

- 2026-06-13: Implemented 10-6. **Deviation from AC1:** `escalation_id` + `alert_event_id` typed `UUID(as_uuid=False)` instead of TEXT, to match the `events.event_id` uuid type and keep the FK type-consistent; the CC sends the id as a string in the URL and Postgres coerces. All other columns per AC1.
- 2026-06-13: Code-review Round 1 (3 adversarial layers). 3 patches applied: (1) ESCALATION_UPDATED SSE frame now carries `id` for CC matching; (2) acknowledge/resolve gate publish+log on `result.rowcount == 1` (concurrent-transition noise); (3) ingest skips escalation upsert + warns on empty-payload ALERT_RAISED (was a NOT-NULL 500). cloud-backend 142→143 (+1 test). 3 deferred to deferred-work.md (duplicate-publish, SSE replay of ESCALATION_UPDATED, CC WS→SSE migration = E2-S1). Status → done.
