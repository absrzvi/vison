---
baseline_commit: 68c89e4
---

# Story 11.5: Configuration surface — mutable confidence thresholds (admin)

Status: ready-for-dev

## Story

As an **admin**,
I want the per-class confidence thresholds and the degraded-banner floor (today hardcoded, read-only) to be **editable and persisted**,
so that calibration values can change **without a code redeploy** and the change is owned/audited by a real admin user.

## Context & Scope (READ FIRST — the epic text is partly stale)

This is the **final Epic-11 story**. Three facts ground it against the shipped reality; the epic (`epics.md:2532`) was written before E11-S1..S4 landed:

1. **The new migration is `0012`, NOT `0011`.** The epic says "Alembic 0011 if a table is added" — but **0011 already shipped** (E11-S3 prefs re-key). The Alembic head is `0011` (chain `…0009→0010→0011`). The new migration **MUST be `0012` with `down_revision = "0011"`**. (Stale-numbering caught at create-story per the PAYLOAD-AUDIT/ADR-FRESHNESS rules.)

2. **Operator preference is DONE — do NOT rebuild it.** The per-operator alert threshold (`threshold_sec`) + staleness threshold are fully shipped in `preferences.py`, persisted in `operator_preferences` (re-keyed to a `users.user_id` FK by E11-S3's 0011), and surfaced on the Profile screen. E11-S5 touches **none** of this. Its only job is the **admin-facing confidence-threshold config surface**.

3. **CRITICAL — there is NO per-class confidence "gate".** The epic's AC1 says the thresholds are "used by the live confidence gate … drive an alert through". **They are not.** Research of the full consumer graph found:
   - `DEFAULT_CONFIDENCE_THRESHOLDS` (per-class dict) is consumed **only for display** — `GET /api/v1/config/confidence-thresholds` echoes it, and the frontend `UnifiedFeed.jsx` passes `per_class` to `<ConfidenceChip>` (a per-alert trust-signal chip). **Nothing suppresses or flags an alert based on a per-class threshold.**
   - `DEGRADED_BANNER_FLOOR` (the scalar) **is** a real backend gate: `health.py:53` computes `rolling-1h mean(confidence_score) < DEGRADED_BANNER_FLOOR` → the `ai_quality_degraded` flag on `GET /api/v1/health` (drives the non-dismissible degraded banner, UX-DR17).

   **Decision D1 (user-locked):** persist + admin-PATCH the **existing** values only; **do NOT invent a new per-class suppression gate**. Re-point the two existing consumers (config GET, degraded-banner gate) to read the persisted store. AC1's "drive an alert through, verified end-to-end" is satisfied against the **degraded floor** (the one real gate); per-class edits are verified through the GET → ConfidenceChip display path. No alert-suppression behaviour is added or changed.

## Acceptance Criteria

1. **Degraded floor mutable + live (the end-to-end gate).** An admin PATCHes `degraded_banner_floor` to a new value; the persisted value is read by the `ai_quality_degraded` computation on the **next** evaluation (after the 30s `_DegradedCache` TTL or an explicit invalidate). Verified end-to-end on real Postgres: seed model-basis `ALERT_RAISED` rows whose rolling-1h mean sits **between** the old and new floor, PATCH the floor across that mean, and assert the `ai_quality_degraded` flag flips accordingly — NOT merely re-GET the config.
2. **Per-class thresholds mutable + read back.** An admin PATCHes a per-class threshold (e.g. `unattended_bag` 0.75→0.80); `GET /api/v1/config/confidence-thresholds` returns the new value (read from the persisted store), so the frontend ConfidenceChip display reflects it. (No suppression behaviour — display only, per D1.)
3. **Admin-only mutation; read stays as-is.** Operator token on the PATCH endpoint → **403** (never 500). The **read** `GET /api/v1/config/confidence-thresholds` keeps its current exposure (`get_current_user` — any authenticated user), matching the shipped read-only contract that `UnifiedFeed.jsx` depends on.
4. **Migration 0012 applies cleanly + idempotently + seeds defaults (behaviour unchanged until edited).** A new `confidence_thresholds` KV table (Alembic **0012**, `down_revision="0011"`) is seeded at migration time with the current `# CALIBRATE` defaults (the 5 per-class values + the floor). An **empty/unseeded** store falls back to the hardcoded `DEFAULT_CONFIDENCE_THRESHOLDS`/`DEGRADED_BANNER_FLOOR` (fail-safe). Downgrade drops the table. `alembic upgrade head` is idempotent and a `downgrade→upgrade` re-applies.
5. **Invalid values rejected at the boundary (fail-safe, never fail-open).** A PATCH with a value outside `0.0–1.0`, `NaN`/`Inf`, or a non-numeric → **422** with the ADR-10 envelope, and **nothing is persisted**. A malformed/missing stored value must fall back to the hardcoded default — it must **never** disable the gate or the chip ("fail to the safe default, not to no-gating").
6. **Config screen renders 3 states + edit round-trips.** New admin-only `Configuration.jsx` screen (route behind `RequireAdmin`, admin-gated nav) renders loading/error/populated, lists the per-class thresholds + the floor, and an edit round-trips (PATCH → refetch → new value shown). Browser-verified per control-centre/CLAUDE.md (golden path + one edge: operator nav-gate/route-bounce + an invalid-value rejection).

## Security Tests (RED-first — write these before any other test)

- **ST1 — operator cannot mutate (403).** A valid **operator** JWT on `PATCH …/confidence-thresholds` (and the floor) → 403, distinct from the 401 a no-token request gets. Asserts on the real `require_role("admin")` gate, not a mock.
- **ST2 — out-of-range / NaN / Inf rejected at the boundary (422), nothing persisted.** Parametrize `1.5`, `-0.1`, `NaN`, `Infinity`, `"abc"` → 422 ADR-10 envelope; assert the store row is unchanged after each.
- **ST3 — a malformed stored value fails SAFE, not open.** If the persisted value is missing/NULL/un-parseable, the gate and the GET fall back to the hardcoded default (the gate keeps gating; the chip keeps rendering) — it must NOT silently become "no floor" / "threshold 0.0 = everything passes". (Unit test: stub the store to return a bad row, assert the read returns the hardcoded default.)
- **ST4 — read exposure unchanged.** The GET stays reachable by an operator token (the shipped `UnifiedFeed.jsx` contract); only the PATCH is admin-gated. Assert operator GET → 200.

## Tasks / Subtasks

- [ ] **T1 — Persistence store + migration 0012** (AC4, D1) — NEW `cloud-backend/migrations/versions/0012_confidence_thresholds.py` (`revision="0012"`, `down_revision="0011"`). Create a KV table `confidence_thresholds` mirroring the `alert_class_state` idiom (new-table-only, safe under concurrent reads — see 0004):
  - Columns: `config_key TEXT PRIMARY KEY`, `value DOUBLE PRECISION NOT NULL`, `updated_by TEXT NULL`, `updated_at TIMESTAMP(timezone=True) NULL`, plus a `CHECK (value >= 0.0 AND value <= 1.0)` constraint (defence-in-depth alongside the app-layer 422 — assert it via the catalog, NOT only via a 422 that never reaches the DB).
  - **Seed** the 5 per-class keys (`per_class:unattended_bag`=0.75, `per_class:door_obstruction`=0.85, `per_class:accessibility_detected`=0.70, `per_class:slip_fall`=0.75, `per_class:luggage_rack_saturation`=0.70) + `degraded_banner_floor`=0.60 inside the migration `upgrade()` (an `op.bulk_insert` of the current `# CALIBRATE` defaults) so behaviour is unchanged on first deploy. Downgrade drops the table.
  - Keep the key shape explicit (e.g. `per_class:<code>` rows + one `degraded_banner_floor` row) so per-class and the scalar live in one table.
- [ ] **T2 — Store reader with fail-safe + cache** (AC1, AC2, AC4, AC5/ST3, D1) — In `cloud-backend/src/cloud_backend/config/confidence_thresholds.py`: keep `DEFAULT_CONFIDENCE_THRESHOLDS` + `DEGRADED_BANNER_FLOOR` as the **hardcoded fail-safe defaults** (do not delete — they're the ST3 fallback). Add an async store reader (e.g. `async def load_thresholds(db) -> dict` returning `{"per_class": {...}, "degraded_banner_floor": float}`) that reads the table and, **per missing/un-parseable key, substitutes the hardcoded default** (never returns a bad/None value to a gate). **Mirror the `fanout_filter.py` cache pattern** (TTL + `asyncio.Lock` + double-check-inside-lock + a generation counter + `invalidate()`), since both `health.py` and `config.py` currently capture the values at module import — a per-evaluation read through this cache is required (module-level capture won't see edits). Update the docstring (the current "Mutability is deferred to Epic 11 — changing a threshold requires a code deploy" is now stale — D3 freshness).
- [ ] **T3 — Repoint the two consumers + add the admin PATCH** (AC1, AC2, AC3, ST1, ST4, D1) — 
  - `routes/health.py`: `_DegradedCache.get` reads the floor from the store reader (T2) instead of the imported `DEGRADED_BANNER_FLOOR` constant. (Keep its own 30s `ai_quality_degraded` cache — that caches the *computed flag*; the floor read should reflect edits within the store TTL. Acceptable eventual-consistency for config, like the kill-switch's 60s — document it.)
  - `routes/config.py`: the GET reads `per_class` + floor from the store reader (T2), still behind `Security(get_current_user)` (ST4 — read exposure unchanged). Add the **admin PATCH** `PATCH /api/v1/config/confidence-thresholds` behind `Security(require_role("admin"))` (mirror the E11-S4 kill-switch auth pattern). Body: a partial map of `{per_class: {...}}` and/or `{degraded_banner_floor: float}`; validate every value `0.0–1.0` + finite (reject NaN/Inf) via a Pydantic validator → 422 ADR-10 on violation, nothing written. On success upsert the KV rows (`updated_by = current_user.username`, `updated_at = NOW()`), call the store reader's `invalidate()`, return the new full config. **Actor = `current_user.username`** (mirror E11-S4 — never a body field). NOTE: the GET and PATCH share a prefix but different auth — keep the GET on the existing router and mount the PATCH with the admin dep (a per-route `Security(require_role("admin"))`), OR split into a `/api/v1/admin/config` router for the PATCH. Either is fine; state which and keep the GET path stable for `UnifiedFeed.jsx`.
- [ ] **T4 — Frontend admin Configuration screen** (AC6, D2) — NEW `control-centre/src/api/config.js` (write-capable client mirroring `api/users.js`/`api/alertClasses.js` `_send` helper: `authHeaders`+`handle401`+`(await res.json())?.detail?.detail`+`err.status`; `listThresholds()` → GET, `patchThresholds(patch)` → PATCH). **Do NOT modify** the existing read-only `api/confidenceThresholds.js` (session-cached, consumed by `UnifiedFeed.jsx` — leave its contract intact). NEW `control-centre/src/components/admin/Configuration.jsx` + `Configuration.css` mirroring `AlertClasses.jsx` (3 states with `data-testid="configuration-loading|error|screen"`, `useCallback(load)` + `runAction`-then-refetch, a per-row editable threshold with a save action, `actionError` surface; an inline 0.0–1.0 numeric input or a constrained control). `--obb-*` tokens only (NO hex). Route in `App.jsx` behind `RequireAdmin`+`ErrorBoundary` (mirror the `alert-classes` route); admin-gated nav in `AppShell.jsx` (`data-testid="nav-configuration"`). vitest `Configuration.test.jsx` mirroring `AlertClasses.test.jsx` (3 states + edit round-trip + a 422/error surface).
- [ ] **T5 — Integration test (A1 hard gate, real producer seeding) + docs freshness** (AC1, AC4, ST1-ST3, D3) — 
  - NEW `cloud-backend/tests/integration/test_confidence_config.py` on real Postgres (testcontainers + Alembic head, mirror `test_killswitch_auth_swap.py`'s fixtures; seed users via `seed_auth_users`/real `create_access_token` — A3). The A1 end-to-end test: ingest model-basis `ALERT_RAISED` rows via the **real `POST /api/v1/events` path** (NOT raw INSERTs — A3) so their mean sits between the seeded floor and a new floor; admin-PATCH the floor across that mean; invalidate/wait the cache; assert the `ai_quality_degraded` flag on `GET /api/v1/health` flips. Plus: 0012 idempotent + downgrade→upgrade re-apply (mirror `test_migrations.py`); operator PATCH → 403 (ST1); out-of-range/NaN → 422, store unchanged (ST2); CHECK constraint present via catalog (AC4). **Run + pass on real Postgres before flipping to review** (Docker required; if down, start it — `docker info`).
  - Docs freshness (D3, no ADR decision contradicted — same "planned terminal state arriving" pattern as E11-S4): (a) fix the `confidence_thresholds.py` docstring (deferred→realised); (b) add an `cloud-backend/CLAUDE.md` note (thresholds now persisted + admin-PATCH, store reader + fail-safe); (c) mark **PRD Open Question 12** (`prd.md`) RESOLVED (per-operator = user-scoped E11-S3; per-class/floor = admin-scoped E11-S5; neither is an env var); (d) add an E11-S5 freshness line to the E10-S1 story note + UX-DR17 (the floor is now persisted; default behaviour unchanged until edited). No `shared/` change, no new EventType.

## Dev Notes

### Files being modified (full-file reads done at create-story per the FULL-FILE-READS rule)

- **`cloud-backend/src/cloud_backend/config/confidence_thresholds.py`** (17 lines) — *current:* module-level `DEFAULT_CONFIDENCE_THRESHOLDS: dict[str,float]` (5 `# CALIBRATE` per-class values) + `DEGRADED_BANNER_FLOOR: float = 0.60`; docstring says "Mutability is deferred to Epic 11 — changing a threshold requires a code deploy." *change:* keep both constants as the **fail-safe defaults**; add an async store reader + cache (T2); fix the docstring. *preserve:* the default values themselves (they seed 0012 and are the ST3 fallback).
- **`cloud-backend/src/cloud_backend/routes/config.py`** (20 lines) — *current:* `router = APIRouter(prefix="/api/v1/config", dependencies=[Security(get_current_user)])`; one GET `confidence_thresholds()` that echoes `dict(DEFAULT_CONFIDENCE_THRESHOLDS)` + `DEGRADED_BANNER_FLOOR`. *change:* GET reads from the store reader; add the admin-gated PATCH. *preserve:* the GET path `/api/v1/config/confidence-thresholds`, its response shape `{"per_class": {...}, "degraded_banner_floor": float}`, and its `get_current_user` (operator-readable) exposure — `UnifiedFeed.jsx` depends on all three.
- **`cloud-backend/src/cloud_backend/routes/health.py`** (`_DegradedCache`, lines 18-58) — *current:* imports `DEGRADED_BANNER_FLOOR` at module level; `get()` runs `SELECT AVG((payload->>'confidence_score')::float) … WHERE event_type='ALERT_RAISED' AND timestamp > NOW()-INTERVAL '1 hour' AND (payload->>'confidence_basis')='model'`, then `self._value = mean is not None and float(mean) < DEGRADED_BANNER_FLOOR`; 30s in-process flag cache with an `asyncio.Lock` + double-check. *change:* read the floor from the store reader instead of the import. *preserve:* the 30s flag cache, the lock/double-check (R3 clou-3/4 concurrency fix), the SQL, and the `mean is not None` guard (empty window → not degraded).
- **`control-centre/src/App.jsx`** — add `configuration` route behind `RequireAdmin`+`ErrorBoundary` (mirror `alert-classes` at :53). **`control-centre/src/components/shell/AppShell.jsx`** — add the admin-gated nav entry (mirror `nav-alert-classes` at :81-83).

### Reference patterns (mirror verbatim — established + reviewed)

- **Auth (admin mutation):** E11-S4 `routes/admin_alert_classes.py` — `Security(require_role("admin"))`, actor = `current_user.username` (never a body field), per-route `current: CurrentUser = Security(require_role("admin"))` to read the actor. `require_role`/`get_current_user` live in `api/auth.py` (401 no-token, 403 under-privileged, never 500 — incl. the `assert_user_active` DBAPIError→401 guard for malformed `sub`).
- **Cache + invalidate:** `services/fanout_filter.py` `AlertClassFilter` — TTL + `asyncio.Lock` + double-check-inside-lock + `_generation` counter + `invalidate()`; admin write calls `invalidate()` after commit. The store reader (T2) mirrors this.
- **Migration:** `0004_alert_class_state.py` (new-table-only, safe-under-concurrent-reads, empty→default) for shape; `0011_preferences_rekey_user_id.py` for the in-migration data op + logging idiom + the one-transaction/atomic note. New = **`0012`**, `down_revision="0011"`.
- **Frontend admin screen:** `components/admin/AlertClasses.jsx` (+ `.css`, + `__tests__/AlertClasses.test.jsx`) and `api/alertClasses.js` — the exact 3-state + `runAction`-refetch + `_send` shapes to copy. Existing read-only `api/confidenceThresholds.js` is the GET consumed by `UnifiedFeed.jsx` — **leave it untouched**; the new admin screen gets its own write client `api/config.js`.

### CSS tokens (control-centre — `--obb-*` only, NO hex; from `src/styles/colors_and_type.css`)

Severity ramp: `--obb-sev-critical` (red, errors), `--obb-sev-high` (orange), `--obb-sev-medium` (amber, warnings — **NOT** `--obb-sev-warning`, which does not exist), `--obb-sev-advisory` (blue, info), `--obb-sev-normal` (green, ok). **`--obb-sev-danger` does not exist — use `--obb-sev-critical`.** Surfaces `--obb-surface-0..5`; text `--obb-text-on-dark-1..4`; borders `--obb-border-dark`/`--obb-border-bright`; accent `--obb-blue-accent`/`--obb-blue-dim`; `--font-mono`, `--font-size-sm`. Mirror `AlertClasses.css` class-for-class.

### Previous-story intelligence (E11-S4, just DONE — commits da163f9 + 68c89e4)

- The kill-switch auth swap is the **direct precedent** for T3's admin PATCH: same `require_role("admin")` gate, same actor-from-`current_user.username` (no body actor), same per-route `Security` to obtain `current`. Reuse it verbatim.
- **E11-S4 review caught a `require_role` double-evaluation** (router-level + per-route each build a distinct `_checker` → the liveness SELECT runs twice; tracked E11S4-R1-DoubleAuth, deferred as a project-wide pattern matching `users.py`). For 11-5: if you put the GET (operator-readable) and PATCH (admin) on the **same** router, do NOT put a router-level admin dep (it would break the operator-readable GET) — gate the PATCH per-route only. This is cleaner here than the kill-switch (whose whole router is admin).
- **E11-S4 review convergence lesson:** the Blind + Acceptance layers both caught a misleading test comment (DB-row vs token-claim actor). Keep test comments precise about *which* identity a value is.
- **A1 integration gate is non-negotiable and Docker-flaky on this box:** E11-S4's integration run was blocked ~26 min by Docker not starting (engine service needs elevation). Start Docker early (`docker info`; if down, launch Docker Desktop and poll) so the gate can run before review — do NOT flip to review on unit/RTL coverage alone.

### Consumer graph (why AC1 rides the floor, not a per-class gate)

| Value | Read at | How used | Mutability impact |
|---|---|---|---|
| `DEGRADED_BANNER_FLOOR` | `health.py:53` `mean < floor` | **Real gate** → `ai_quality_degraded` flag (UX-DR17 banner) | AC1 end-to-end target: drive alerts, flip the flag |
| `DEFAULT_CONFIDENCE_THRESHOLDS` (per_class) | `config.py` GET → `UnifiedFeed.jsx` → `<ConfidenceChip>` | **Display only** (per-alert trust chip) | AC2: edit → GET reflects → chip display changes |
| (per-class suppression gate) | — | **DOES NOT EXIST** | Out of scope (D1 — do NOT add) |

### Project Structure Notes

- Tier: **Tier 3** (migration 0012 on the schema). Default permission mode. Review tier per the A2 rule: a migration + an admin-auth mutation → lean **FULL adversarial wire-replay** (auth + migration are both named FULL triggers), though the surface is small. State the tier at review.
- No `shared/` change, no new `EventType`, no Conrad/Hailo/video path. The PATCH is landside-local config (like user-management) — not a cross-service event.

### References

- [Source: epics.md#E11-S5](../planning-artifacts/epics.md) lines 2532-2554 (note the stale "0011" + the "live gate" framing corrected here)
- [Source: architecture.md#ADR-23](../planning-artifacts/architecture.md) (auth seam + the E11-S4 addendum the PATCH mirrors)
- [Source: prd.md] FR38/FR40/FR42, NFR3, UX-DR17, Open Question 12 (→ mark RESOLVED in T5)
- [Source: confidence_thresholds.py](../../cloud-backend/src/cloud_backend/config/confidence_thresholds.py), [config.py](../../cloud-backend/src/cloud_backend/routes/config.py), [health.py](../../cloud-backend/src/cloud_backend/routes/health.py), [fanout_filter.py](../../cloud-backend/src/cloud_backend/services/fanout_filter.py)
- [Source: 0011 migration](../../cloud-backend/migrations/versions/0011_preferences_rekey_user_id.py), [0004 migration](../../cloud-backend/migrations/versions/0004_alert_class_state.py)
- [Source: AlertClasses.jsx](../../control-centre/src/components/admin/AlertClasses.jsx), [api/alertClasses.js](../../control-centre/src/api/alertClasses.js), [api/confidenceThresholds.js](../../control-centre/src/api/confidenceThresholds.js), [UnifiedFeed.jsx](../../control-centre/src/components/live/UnifiedFeed.jsx)

## Dev Agent Record

### Agent Model Used

_TBD by dev-story_

### Debug Log References

### Completion Notes List

### File List

### Change Log

| # | Change | Rationale |
|---|---|---|
| 1 | create-story (Amelia) → ready-for-dev | Final Epic-11 story. 4 Explore subagents mapped the full consumer graph + shipped reality. Surfaced 3 grounded findings: (a) migration is **0012** not the epic's stale "0011" (0011 = E11-S3 prefs re-key); (b) operator preference is DONE — out of scope; (c) **no per-class confidence gate exists** — per-class thresholds are display-only (ConfidenceChip), the only real backend gate is `DEGRADED_BANNER_FLOOR`. D1 (user-locked): persist + admin-PATCH existing values only, no new suppression gate; AC1 rides the degraded floor. ADR-FRESHNESS: no ADR decision contradicted (planned terminal state, like E11-S4) — freshness notes only. Tier 3, FULL review, A1 integration gate (drive alerts → flip the flag, real producer seeding). |

## Open Questions / Pre-Flight Confirmations (non-blocking — resolve at dev Pre-Flight)

1. **PATCH endpoint placement** — same router as the GET (PATCH gated per-route admin, GET stays operator-readable at the router level) vs. a dedicated `/api/v1/admin/config` router for the PATCH. Recommend **same router, per-route admin dep on PATCH only** (keeps the GET path stable for `UnifiedFeed.jsx`, avoids a router-level admin dep that would break the operator-readable GET). Confirm at Pre-Flight.
2. **Frontend edit control** — an inline numeric `0.0–1.0` input + Save per row vs. a constrained stepper/segmented control. Recommend a simple numeric input with client-side `0–1` bounds + the server 422 as the real guard (mirrors the Users password-min pattern). Confirm.
3. **Floor edit propagation latency** — the floor read flows through the store-reader TTL (mirroring fanout's 60s) AND `_DegradedCache`'s 30s flag cache. Net worst-case propagation ≈ store-TTL + 30s. Acceptable eventual-consistency for config (the integration test should `invalidate()` both, or wait, to assert deterministically). Confirm the TTL value (recommend matching fanout's 60s, or shorter for config since edits are rare/manual).
