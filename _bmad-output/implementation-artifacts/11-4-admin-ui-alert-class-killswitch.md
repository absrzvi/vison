---
baseline_commit: 2dac6cc
---

# Story 11.4: Admin UI for kill-switch (X-Admin-Key → JWT role swap)

Status: ready-for-dev

<!-- Created 2026-06-15 via bmad-create-story (Amelia). Fourth story of Epic 11 (Control Centre Admin & Identity).
     Source: _bmad-output/planning-artifacts/epics.md §"Epic 11" → "E11-S4 — Admin UI for kill-switch (X-Admin-Key → JWT swap)".
     Depends on 11-1 (DONE — JWT foundation: get_current_user, require_role, CurrentUser{user_id,username,role}) and
     11-2 (DONE — admin Users screen + the require_role("admin") router pattern + RequireAdmin frontend guard).
     11-3 (DONE) is the PARALLEL sibling (S3∥S4) — its extracted SegmentedControl is unrelated to this story; what 11-3
     established that IS reused here: the admin-screen UI pattern, the AuthContext role gate, the testcontainers A1 idiom.
     Review tier (A2): FULL adversarial wire-replay — AUTH SWAP on a LIVE kill-switch. Permission tier: Tier 3.
     GROUNDED against shipped code (2026-06-15, Amelia + 2 Explore subagents read every UPDATE file completely):
       - The auth swap is a genuinely SINGLE clean swap point (router-level dependency, admin_alert_classes.py:45).
       - ONE load-bearing Decision: actor source. RESOLVED (user) → current_user.username; AdminActionBody.actor_name REMOVED.
       - NO migration, NO shared-schema change (PAYLOAD AUDIT: AlertClassStatePayload stays as-shipped; only the VALUE source changes).
       - NO existing frontend kill-switch caller (E10-S1 shipped backend only) → AlertClasses.jsx + api/alertClasses.js are NEW. -->

## Story

As **an admin**,
I want **to disable and re-enable an alert class from a Control Centre settings screen, authenticated by my own admin role rather than a shared admin key and curl**,
so that **the E10-S1 kill-switch is operated through the UI with role-based auth, every toggle is attributed to the real admin who made it (not a client-supplied string), and the shared `X-Admin-Key` secret is retired from this surface.**

## Context — why this story exists

E10-S1 shipped the alert-class kill-switch **backend-only**: a `POST /api/v1/admin/alert-classes/{alert_code}/{disable|enable}` pair plus a `GET` list, all gated behind a shared `X-Admin-Key` header ([admin_alert_classes.py:43-46](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)). It was operated by Nomad on-call via `curl` per the E10-S3 SOP — the epic explicitly deferred a UI and real auth to Epic 11 ([epics.md:2227-2233](../../_bmad-output/planning-artifacts/epics.md)).

11-1 then shipped self-contained JWT (`get_current_user`, `require_role`, `CurrentUser{user_id, username, role}`) and 11-2 shipped the first admin screen (Users) behind `require_role("admin")` + a `RequireAdmin` frontend guard. **Everything 11-4 needs already exists.** This story closes the loop on the kill-switch:

1. **Backend:** swap the router's auth dependency from `Security(require_admin_key)` to `Security(require_role("admin"))` — the single clean swap point confirmed against live code ([admin_alert_classes.py:45](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)). The fan-out filter behaviour ([fanout_filter.py](../../cloud-backend/src/cloud_backend/services/fanout_filter.py)) is **untouched** — only the gate changes. Source the audit `actor_name` from `current_user.username` instead of the request body (D1). Retire `X-Admin-Key`/`CC_ADMIN_KEY` from this router.
2. **Frontend:** a NEW admin-only "Alert Classes" screen ([AlertClasses.jsx](../../control-centre/src/components/admin/AlertClasses.jsx)) — list from the existing `GET`, per-class disable/enable toggle calling the existing POSTs, gated on `role === 'admin'` exactly like the Users screen. No frontend caller exists today (confirmed — E10-S1 shipped no UI).

This is an **auth swap on a live kill-switch** — the FULL review tier exists because the failure mode (kill-switch silently stops filtering, or an operator can disable a safety alert class) is operationally serious. The behaviour the swap must preserve end-to-end is E10-S1's: a new alert of a disabled class is suppressed from REST + SSE fan-out; in-flight escalations stay visible.

## Decisions (locked — review before dev)

> **CREATE-STORY GROUNDING (2026-06-15, Amelia).** The epic text for E11-S4 is accurate and current (it post-dates E10-S1 and was verified against live code in the 2026-06-14 planning pass). Only ONE decision is load-bearing — the actor source — and it has been **resolved by the user**. The rest are mechanical confirmations with an obvious right answer, recorded so a reviewer doesn't re-litigate.

- **D1 — Actor source: `current_user.username`, and `AdminActionBody.actor_name` is REMOVED. ✅ RESOLVED (user, 2026-06-15).**
  Today the audit actor comes from a request **body** field: `AdminActionBody(actor_name: str = Field(min_length=1))` ([admin_alert_classes.py:49-50](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)), used at three sites — the `alert_class_state.disabled_by`/`enabled_by` upsert ([:132,167](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)), the `_persist_audit_event` envelope ([:138,173](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)), and the structured log ([:146,181](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)). The epic is explicit: *"keep the audit-event plumbing intact — `actor_name` now comes from `current_user`, not a body field"* ([epics.md:2512](../../_bmad-output/planning-artifacts/epics.md)) and AC3: *"now with `actor = current_user.user_id` (no more body-supplied `actor_name`)"* ([epics.md:2518](../../_bmad-output/planning-artifacts/epics.md)).
  **Decision: persist `current_user.username`** (e.g. `"claudia"`), not the UUID. Rationale: `disabled_by`/`enabled_by` are **display columns** the new AlertClasses UI surfaces via the GET; a raw UUID reads poorly there and would force a username join. The username matches the curl-era display semantics and reads naturally in the audit trail; the kill-switch envelope is a domain event a human reads (unlike `user_audit`, which keys by `user_id`). **`AdminActionBody` is deleted** — the POST body is now empty; identity comes only from the token. (The epic AC text says `user_id`; the user has overridden to `username` for display legibility — recorded here so the reviewer treats `username` as the locked choice, not a deviation to flag.)
  - **No shared-schema change (PAYLOAD AUDIT — rule satisfied):** `AlertClassStatePayload.actor_name` is a required `_NonEmptyStr` ([payloads.py:543-548](../../shared/src/oebb_shared/events/payloads.py)). We keep the field; only its **value source** changes (body → token). `current_user.username` is non-empty (unique, NOT NULL in `users` — [0009](../../cloud-backend/migrations/versions/0009_users.py)) so the `_NonEmptyStr` constraint holds. **No `shared/` edit, no contract test, no migration.** This is the create-story PAYLOAD-AUDIT check run and cleared.

- **D2 — The auth swap is router-level, but the handlers MUST capture `current_user` (per-route `Security`) to read the actor. ✅ Confirmed.**
  Today: `dependencies=[Security(require_admin_key)]` at the router ([admin_alert_classes.py:43-46](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)) — a router-level gate that returns nothing to the handler. To source `actor_name = current_user.username`, the two POST handlers need the `CurrentUser` **object**, so they take a per-route `current: CurrentUser = Security(require_role("admin"))` parameter — the exact canonical pattern from [users.py:126,184,249](../../cloud-backend/src/cloud_backend/routes/users.py). The GET (`list_alert_classes`) does not need the actor, so it can rely on a **router-level** `dependencies=[Security(require_role("admin"))]`. **Shape: keep the router-level dependency `[Security(require_role("admin"))]` for blanket coverage AND add the per-route `current: CurrentUser = Security(require_role("admin"))` to the two POSTs** (FastAPI dedupes the dependency — it runs once; this is exactly how `users.py` does it). Delete `require_admin_key`, `_admin_header`, and the `import secrets` / `APIKeyHeader` it needed.

- **D3 — `cc_admin_key` Setting is deprecated, not deleted; `CC_ADMIN_KEY` no longer gates this router. ✅ Confirmed.**
  `config/__init__.py:24-27` already carries the comment *"E11-S4 swaps this for JWT role"*. After this story nothing reads `cc_admin_key` (it was only read by `require_admin_key`, which is deleted). **Decision: remove the `cc_admin_key` field from `Settings`** (it has no remaining reader; leaving a dead fail-closed knob is misleading) AND drop `CC_ADMIN_KEY` from `.env.example` if present. Grep-confirm zero readers before removing. (Contrast D4 of 11-3: `api_key` STAYS because `require_api_key` is still live on ingest; `cc_admin_key` has NO surviving reader, so it goes. This is the symmetric-but-opposite call and the difference must be stated so a reviewer doesn't "consistency"-flag it.)
  - **ADR FRESHNESS check (rule satisfied):** searched `architecture.md` — ADR-23 (self-contained JWT) is the relevant ADR; it already anticipates the `require_role` swap and the X-Admin-Key retirement (E10-S1's `cc_admin_key` was always documented as the temporary seam). **No ADR is contradicted** by retiring `cc_admin_key` — it's the planned terminal state. Confirm no ADR edit needed and record that confirmation (T5). The E10-S1 SOP that documents the `curl` + `X-Admin-Key` path **does** become stale → see D5.

- **D4 — Frontend is a clean mirror of the Users screen; no existing caller. ✅ Confirmed.**
  Grep of `control-centre/src` for any kill-switch/alert-class caller found only two **comment** references in unrelated AI-quality code — **zero production callers**. So `AlertClasses.jsx`, `AlertClasses.css`, `api/alertClasses.js`, and the test are all NEW, mirroring [Users.jsx](../../control-centre/src/components/admin/Users.jsx) / [api/users.js](../../control-centre/src/api/users.js) / [Users.test.jsx](../../control-centre/src/components/admin/__tests__/Users.test.jsx) structurally. Route + nav mirror the admin-gated Users route ([App.jsx:51](../../control-centre/src/App.jsx)) and nav entry ([AppShell.jsx:78-80](../../control-centre/src/components/shell/AppShell.jsx)). The API client reuses the shared `authHeaders` Bearer helper ([authFetch.js](../../control-centre/src/lib/auth/authFetch.js)) exactly as `api/users.js` does.

- **D5 — The E10-S3 SOP's `curl`/`X-Admin-Key` operating instructions go stale; flag a docs follow-up (do NOT rewrite the SOP here). ✅ Confirmed.**
  The critical-alert SOP and routing matrix under `_bmad-output/operational-procedures/` document operating the kill-switch via `curl` with `X-Admin-Key`. After this story that path 401s. **This story does not own rewriting the operational SOPs** (out of code scope, and the SOP rewrite is an ÖBB-facing artifact Freya/Mary own at epic close). **Action (T5):** add a one-line tracked follow-up in `deferred-work.md` ("E10-S3 SOP kill-switch operation: curl+X-Admin-Key → UI/JWT; rewrite at Epic-11 close") so the stale instruction is known/scoped, not a surprise to a pilot reviewer.

## Acceptance Criteria

**AC1 — kill-switch behaviour preserved end-to-end through the new auth path (the core guarantee)**
An admin (valid `admin`-role Bearer token) toggles an alert class to `disabled` via the UI → `POST /api/v1/admin/alert-classes/{alert_code}/disable`. A **new** `ALERT_RAISED` event of that `alert_code` raised *after* the disable is **suppressed from REST + SSE fan-out** (the [fanout_filter.alert_class_filter](../../cloud-backend/src/cloud_backend/services/fanout_filter.py) drops it, `t_raised > disabled_at`), while an in-flight escalation raised *before* the disable stays visible. Re-enabling restores fan-out for subsequent alerts. **The E10-S1 behaviour is unchanged — only the auth gate changed.** The `alert_class_filter.invalidate()` cache-bust still fires on every toggle ([admin_alert_classes.py:142,177](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)).

**AC2 — operator is forbidden; admin is allowed; no token is unauthorized (the auth swap)**
A valid **`operator`**-role token on any of the three endpoints (`disable`, `enable`, GET) → **403** (`{"error":"FORBIDDEN",...}` — the `require_role` shape, [auth.py:180-196](../../cloud-backend/src/cloud_backend/api/auth.py)). A valid **`admin`**-role token → 200. **No token / invalid / expired / tampered token → 401** (never 500 — the JWT-edge-case rule, cloud-backend/CLAUDE.md). The UI toggle is **not rendered** for operators (the nav entry and the route are `role === 'admin'`-gated, mirroring Users).

**AC3 — audit trail unbroken across the swap; actor is now `current_user.username` (D1)**
Every toggle still writes all three audit artifacts ([admin_alert_classes.py:125-148,160-184](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)): the `alert_class_state` row (`disabled_by`/`enabled_by`), the `ALERT_CLASS_DISABLED`/`ALERT_CLASS_REENABLED` event envelope, and the structured log — but `actor_name` is now `current_user.username`, **never a body-supplied value** (`AdminActionBody` is deleted; the POST body is empty). Verified by: an integration toggle with an admin token whose username is known asserts `alert_class_state.disabled_by == <that username>` AND the persisted `ALERT_CLASS_DISABLED` event's `payload.actor_name == <that username>`. A POST that *attempts* to send `{"actor_name": "spoofed"}` in the body has that field **ignored** (no model field accepts it; the actor is still the token's username).

**AC4 — `X-Admin-Key`/`CC_ADMIN_KEY` is no longer accepted on this router (old curl path dies)**
A request to any of the three endpoints carrying **only** the old `X-Admin-Key` header (no Bearer token) → **401** (the old curl path 401s — it's now an unauthenticated request to a JWT-gated route). `cc_admin_key` has zero readers after this story (grep-verified) and the `Settings.cc_admin_key` field is removed (D3). `require_admin_key`, `_admin_header`, and the now-unused `secrets`/`APIKeyHeader` imports are deleted from the router file.

**AC5 — Alert Classes admin screen renders loading/error/populated; toggle round-trips (browser-verified)**
A NEW `/dashboard/alert-classes` screen behind `RequireAdmin` ([App.jsx](../../control-centre/src/App.jsx)) renders the three required states (loading / error / populated — control-centre/CLAUDE.md), lists alert classes from `GET /api/v1/admin/alert-classes` with current state + `disabled_by`/`disabled_at`, and a per-class disable/enable toggle that POSTs (empty body) and refetches so the UI reflects server truth (the Users-screen mutation pattern — [Users.jsx:101-109](../../control-centre/src/components/admin/Users.jsx)). **Browser-verified** per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md): golden path (admin logs in → sees Alert Classes nav → toggles a class → state flips and persists on refetch) + one edge (operator login → no Alert Classes nav, direct `/dashboard/alert-classes` → bounced to `/dashboard/live` by `RequireAdmin`).

**AC6 — gates green; no regression to the fan-out or the existing admin screens**
cloud-backend unit + integration (real Postgres, testcontainers) cover AC1–AC4 at ≥80%; `ruff` + `mypy --strict` clean on touched `src/`; control-centre `vitest` green for the AlertClasses surface; the existing kill-switch **fan-out filter tests stay green** (the swap must not regress E10-S1's suppression behaviour); the existing Users/Profile admin screens still work. The full cloud-backend integration suite passes on real Postgres.

## Security Tests (RED-first — write before domain tests, per dev-story DoD)

Write each to fail for the right reason first, then implement:

1. **Operator cannot disable/enable an alert class (403):** an `operator`-role token on `POST .../disable`, `POST .../enable`, and `GET` → 403 on all three. (The epic's named Security Test; mirror [test_user_management_security.py](../../cloud-backend/tests/unit/test_user_management_security.py)'s `test_operator_forbidden_on_every_admin_endpoint`.)
2. **Old `X-Admin-Key`, no Bearer → 401 (AC4):** a request with the retired `X-Admin-Key` header set but **no** `Authorization: Bearer` → 401 (authentication, not authorization, fails — there is no token). Confirms the curl path is dead and the swap didn't accidentally leave a dual-auth backdoor.
3. **Authentication alone is insufficient — admin role required (AC2):** a *valid authenticated* operator token (auth succeeds, role check fails) → 403, distinct from the 401 no-token case. Pin that the 403 is the role gate, not a token problem.
4. **No body-supplied actor can override the token identity (AC3/D1):** an admin token + a POST body `{"actor_name": "spoofed"}` (or any actor field) does NOT set the audit actor to `"spoofed"` — the persisted `disabled_by` and the envelope `payload.actor_name` are the **token's** username. (This is D1's adversarial twin — the integrity reason the swap exists.)

## Integration test (A1 hard gate + A3 real-path seeding)

**`test_killswitch_auth_swap_admin_toggle`** (testcontainers real Postgres) — MUST run and pass before the story flips to `review` ("deferred to CI" is not acceptable; `docker info` to confirm, start it if down). This is the E10-A1 gate.

**A3 — seed via the REAL path; create users via `create_user` + mint real Bearer tokens (Amelia).** Create one **admin** and one **operator** through the real `create_user` flow (reuse 11-2's `create_user` / [tests/integration/conftest.py](../../cloud-backend/tests/integration/conftest.py) `seed_auth_users` + `auth_header` — both already provide a fixed-UUID admin + operator with real tokens; either reuse those or create fresh via `create_user`), then drive:
- **admin token → `POST .../disable`** → assert 200, assert the `alert_class_state` row state is `disabled` AND `disabled_by == admin.username` (AC3 actor-source), assert an `ALERT_CLASS_DISABLED` event row exists with `payload.actor_name == admin.username`;
- **then raise a new `ALERT_RAISED` of that `alert_code` via the real ingest path** and assert the fan-out filter suppresses it (AC1 — the E10-S1 behaviour preserved); mirror the existing [test_killswitch_fanout.py](../../cloud-backend/tests/integration/test_killswitch_fanout.py) seed idiom but drive the toggle through the **JWT** path, not `X-Admin-Key`;
- **operator token → `POST .../disable`** → assert 403, assert NO state change.

> **Note the pre-existing integration-test isolation flaky** documented in 11-1/11-2/11-3 reviews: `test_ai_quality_rates.py` intermittently fails under multi-module ordering due to `DATABASE_URL`-leaking `pg_url` fixtures — **confirmed not introduced by Epic 11** (task_c97431d4). If it surfaces, do NOT chase it here; verify the 11-4 tests are deterministically green in isolation and note it.

## Tasks / Subtasks

- [ ] **T1 — Backend auth swap on `admin_alert_classes.py`** (AC1, AC2, AC3, AC4, D1, D2) — In [routes/admin_alert_classes.py](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py):
  - Delete `require_admin_key` (:32-40), `_admin_header` (:29), and the now-unused `import secrets` (:12) and `from fastapi.security import APIKeyHeader` (:17).
  - Router: replace `dependencies=[Security(require_admin_key)]` with `dependencies=[Security(require_role("admin"))]` (:43-46). Import `require_role` and `CurrentUser` from `..api.auth`.
  - Delete `AdminActionBody` (:49-50). Both POST handlers: drop the `body: AdminActionBody` param, add `current: CurrentUser = Security(require_role("admin"))` (per-route, so the handler gets the user — D2; FastAPI dedupes vs the router-level dep). The POST body is now empty.
  - Replace all five `body.actor_name` references (:132, :138, :146, :167, :173, :181) with `current.username`. Logic, `alert_class_filter.invalidate()`, the audit envelope, and the structured log are **otherwise unchanged** (surgical — the fan-out path is not touched).
  - **RED first:** Security Tests 1-4 + the AC3 actor-source assertion fail before the swap, pass after.
- [ ] **T2 — Deprecate `cc_admin_key`** (AC4, D3) — In [config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py): **grep-confirm zero readers** of `cc_admin_key` across `src/` first, then remove the `cc_admin_key` field (:24-27). Remove `CC_ADMIN_KEY` from `.env.example` if present. Confirm no other module imports `require_admin_key` (grep `src/` + `tests/`).
- [ ] **T3 — Frontend: API client `src/api/alertClasses.js`** (AC5, D4) — NEW file mirroring [api/users.js](../../control-centre/src/api/users.js): `listAlertClasses()` → `GET /api/v1/admin/alert-classes`; `disableAlertClass(alertCode)` → `POST /api/v1/admin/alert-classes/{alertCode}/disable` (empty body); `enableAlertClass(alertCode)` → `.../enable`. Reuse the shared `authHeaders` Bearer helper from [lib/auth/authFetch.js](../../control-centre/src/lib/auth/authFetch.js) and the `import.meta.env.VITE_API_URL ?? ''` base; map errors via the `(await res.json())?.detail?.detail` pattern with `err.status` attached, exactly as `api/users.js`.
- [ ] **T4 — Frontend: AlertClasses screen + route + nav** (AC2, AC5, D4) — NEW [src/components/admin/AlertClasses.jsx](../../control-centre/src/components/admin/AlertClasses.jsx) + `AlertClasses.css` (`--obb-*` only) mirroring [Users.jsx](../../control-centre/src/components/admin/Users.jsx): loading/error/populated states (`data-testid="alert-classes-loading|error|screen"`), list each class with state + `disabled_by`/`disabled_at`, a per-class disable/enable toggle that calls the API then **refetches** (`load()` after success — server-truth pattern, no optimistic update), `actionError` surfacing on mutation failure. Add the route to [App.jsx](../../control-centre/src/App.jsx) behind `RequireAdmin` mirroring the `users` route ([:51](../../control-centre/src/App.jsx)). Add the admin-gated nav entry in [AppShell.jsx](../../control-centre/src/components/shell/AppShell.jsx) (`{role === 'admin' && <NavLink to="/dashboard/alert-classes" ... data-testid="nav-alert-classes">Alert Classes</NavLink>}`, mirroring [:78-80](../../control-centre/src/components/shell/AppShell.jsx)). vitest [src/components/admin/__tests__/AlertClasses.test.jsx](../../control-centre/src/components/admin/__tests__/AlertClasses.test.jsx) mirroring [Users.test.jsx](../../control-centre/src/components/admin/__tests__/Users.test.jsx) (`@vitest-environment jsdom`, mock `../../../api/alertClasses`, three-state + toggle-refetch + error tests).
- [ ] **T5 — Tests, docs, tracked follow-ups** (A1 gate, AC6, D3, D5) — Update [tests/unit/test_admin_alert_classes.py](../../cloud-backend/tests/unit/test_admin_alert_classes.py) (9 tests use `X-Admin-Key` → swap to Bearer tokens; the two `cc_admin_key`-default/no-baked-key tests are now obsolete → delete or repoint to the JWT fail-closed posture) and [tests/integration/test_killswitch_fanout.py](../../cloud-backend/tests/integration/test_killswitch_fanout.py) (drive the toggle via JWT, not `X-Admin-Key`). Add `test_killswitch_auth_swap_admin_toggle` (A1 gate, real path). Confirm `ruff`/`mypy --strict`/coverage gates + the fan-out filter tests stay green. **Docs:** ADR-FRESHNESS — confirm no ADR contradicted (ADR-23 already anticipates this; record the confirmation). Update `cloud-backend/CLAUDE.md` Auth note: `admin/alert-classes` is now `require_role("admin")`, `cc_admin_key` retired. Add the **tracked follow-up** in `deferred-work.md`: "E10-S3 SOP kill-switch operation curl+X-Admin-Key → UI/JWT; rewrite at Epic-11 close" (D5).

## Dev Notes

### Architecture patterns & constraints

- **ADR-8:** every route under `/api/v1/`. **ADR-10:** error envelope `{"error","detail","recoverable"}` for 401/403 (the `require_role` 403 already emits this — [auth.py:180-196](../../cloud-backend/src/cloud_backend/api/auth.py)). **ADR-23 (11-1):** the verify seam — `_verify_token` stays pure; the liveness check lives in the extractor. This story adds **no auth logic** — it consumes `require_role("admin")` exactly as `users.py` does. It does NOT touch `api/auth.py`.
- **cloud-backend/CLAUDE.md "Auth":** *"Role-gate a route with `Security(require_role("admin"))` — not by checking the role inside the body."* — this story is the literal application of that rule to the kill-switch router. *"The legacy `X-API-Key` (`require_api_key`) is … kept importable until E11-S3/S4"* — note `require_api_key` (ingest) is a DIFFERENT key from `cc_admin_key` (kill-switch); this story retires `cc_admin_key` only. `require_api_key`/`api_key` STAYS (ingest, per 11-3 D4).
- **cloud-backend/CLAUDE.md "Review Failure Scenarios":** JWT edge cases (expired/tampered/missing-role) must return 401/403, never 500 — already guaranteed by `require_role`/`get_current_user`; the new tests pin it on this router.
- **No migration, no shared-schema change** (D1 PAYLOAD-AUDIT + D3 ADR-FRESHNESS both run and cleared). This keeps the blast radius to two backend files + the frontend.

### Files being modified (UPDATE) — current state / change / preserve

Per the FULL-FILE-READS rule, each was read completely (the backend router in full above; the frontend mirrors via the Users/Profile precedent read in 11-3). Verified current state:

- **[routes/admin_alert_classes.py](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)** (211 lines) — *current:* router-gated by `Security(require_admin_key)` (:45); `require_admin_key` checks `X-Admin-Key` vs `cc_admin_key` with `secrets.compare_digest`, fail-closed 401 (:32-40); `AdminActionBody.actor_name` is a body field (:49-50) used at 5 sites; two POSTs upsert `alert_class_state` + `_persist_audit_event` (envelope) + structured log + `alert_class_filter.invalidate()`; GET lists classes. *change:* swap the gate to `require_role("admin")` (router-level) + add per-route `current: CurrentUser` to the POSTs; delete `require_admin_key`/`_admin_header`/`AdminActionBody` + their imports; `body.actor_name` → `current.username` (5 sites). *preserve:* the `alert_class_state` upsert SQL, `_persist_audit_event` envelope shape, `alert_class_filter.invalidate()`, the GET response shape, the structured-log keys — **the fan-out behaviour and the audit transport are untouched.**
- **[config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py)** — *current:* `cc_admin_key: str = ""` fail-closed field (:24-27) with the "E11-S4 swaps this" comment; `api_key` field (:16-23, STAYS — ingest). *change:* remove `cc_admin_key` (zero readers after T1). *preserve:* `api_key` and `require_api_key` (ingest service-token — 11-3 D4); the bcrypt floor validator; every other Setting.
- **[control-centre/src/App.jsx](../../control-centre/src/App.jsx)** (58 lines) — *current:* `RequireAuth`/`RequireAdmin` guards; admin-gated `users` route (:51), `profile` route (:52, RequireAuth only). *change:* add an `alert-classes` route behind `RequireAdmin` mirroring the `users` line exactly. *preserve:* guard/redirect behaviour and route order.
- **[control-centre/src/components/shell/AppShell.jsx](../../control-centre/src/components/shell/AppShell.jsx)** (98 lines) — *current:* admin-gated Users nav (`{role === 'admin' && <NavLink to="/dashboard/users" ...>}`, :78-80) + Profile nav (:81). *change:* add an Alert Classes nav entry alongside Users (same `role === 'admin'` gate). *preserve:* the gear-button modal trigger, the admin-gating of Users, the Profile nav.
- **[tests/unit/test_admin_alert_classes.py](../../cloud-backend/tests/unit/test_admin_alert_classes.py)** — *current:* 9 tests, all auth via `X-Admin-Key`; two pin the `cc_admin_key` default/no-baked-key posture. *change:* swap header auth → Bearer; the two `cc_admin_key`-specific tests become obsolete (the field is gone) → delete or repoint to JWT fail-closed; the `actor_name`-from-body tests become `actor_name`-from-token. *preserve:* the disable/enable upsert + envelope-emit + log assertions (now with token-sourced actor) + the GET-shape test.
- **[tests/integration/test_killswitch_fanout.py](../../cloud-backend/tests/integration/test_killswitch_fanout.py)** — *current:* real-PG fan-out suppression tests; toggles via `X-Admin-Key`. *change:* drive the toggle via a real admin Bearer token. *preserve:* the fan-out suppression assertions (the E10-S1 behaviour AC1 guards).

### The auth swap shape (D1/D2 — the load-bearing piece)

```python
# admin_alert_classes.py — after the swap
from ..api.auth import CurrentUser, require_role   # replaces secrets/APIKeyHeader + require_admin_key

router = APIRouter(
    prefix="/api/v1/admin/alert-classes",
    dependencies=[Security(require_role("admin"))],      # was Security(require_admin_key)
)
# AdminActionBody DELETED — POST body is now empty.

@router.post("/{alert_code}/disable")
async def disable_alert_class(
    alert_code: str,
    request: Request,
    current: CurrentUser = Security(require_role("admin")),   # per-route: handler needs the actor (D2)
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    source_ip = _client_ip(request)
    # ... upsert alert_class_state with :actor = current.username (was body.actor_name)
    # ... _persist_audit_event(..., actor_name=current.username, ...)
    # ... log.info("admin.alert_class_disabled", actor_name=current.username, ...)
    # ... alert_class_filter.invalidate()  # UNCHANGED
```

Mirror [users.py:33-36,126](../../cloud-backend/src/cloud_backend/routes/users.py) — the router-level dep gives blanket coverage (incl. the GET), the per-route dep gives the POST handlers the `CurrentUser`. FastAPI runs `require_role("admin")` once per request despite appearing twice (dependency dedup).

### CSS tokens (AlertClasses.jsx)

Use only `--obb-*` from [control-centre/src/styles/colors_and_type.css](../../control-centre/src/styles/colors_and_type.css). The Users screen ([Users.css](../../control-centre/src/components/admin/Users.css)) uses: surfaces `--obb-surface-1..4`, text `--obb-text-on-dark-1`/`-3`, borders `--obb-border-dark`/`-bright`, accent `--obb-blue-accent`/`--obb-blue-dim`, and `--obb-sev-critical` for a destructive cue. For the disabled-state cue on a class row, the severity ramp is: `--obb-sev-critical` (red, #FF3B3B), `--obb-sev-high` (orange), `--obb-sev-medium` (amber), `--obb-sev-advisory` (blue), `--obb-sev-normal` (green, healthy/enabled). **`--obb-sev-warning` does NOT exist (use `--obb-sev-medium`); `--obb-sev-danger` does NOT exist (use `--obb-sev-critical`).** Reuse `Users.css` patterns rather than inventing new token usage.

### UX ownership (Freya)

The Alert Classes screen is a **new UX surface**. Per the epic's UX-pass plan ([epics.md:2558](../../_bmad-output/planning-artifacts/epics.md)), each E11 story ships a **minimal functional** UI (theme-correct, browser-verified); Freya runs ONE coherent WDS pass over the whole admin/identity shell (login + Users + Profile + **Alert Classes** + Configuration) at epic close. Do NOT over-design in isolation now — a state-listing table with disable/enable toggles + loading/error/populated states satisfies AC5; Freya reviews in the browser-verify step.

### Testing standards

- Markers: `@pytest.mark.unit` (no DB) / `@pytest.mark.integration` (testcontainers Postgres). Coverage ≥80%.
- `mypy --strict` + `ruff` clean on touched `src/`.
- CC: `vitest` for `AlertClasses.jsx` states + toggle-refetch + error; the existing Users/Profile tests must stay green.
- The existing **fan-out filter tests** are the regression guard for AC1 — they must stay green after the auth swap (the swap is orthogonal to the filter, but FULL review exists to prove it).

### Previous-story intelligence (11-1, 11-2, 11-3)

- **11-1** shipped `get_current_user`, `require_role`, `CurrentUser{user_id, username, role}` ([auth.py](../../cloud-backend/src/cloud_backend/api/auth.py)) — this story consumes them unchanged. The `username` claim is present on the token (11-3 verified it in the browser: showed "claudia").
- **11-2** shipped the canonical admin pattern: `routes/users.py` router-level `dependencies=[Security(require_role("admin"))]` + per-route `current: CurrentUser = Security(require_role("admin"))`, audit via `actor_user_id=current.user_id`, and the frontend Users screen + `RequireAdmin` guard + `api/users.js`. **Mirror users.py for the backend, Users.jsx for the frontend.** Its security tests ([test_user_management_security.py](../../cloud-backend/tests/unit/test_user_management_security.py)) are the template for Security Tests 1-3.
- **11-3** (parallel sibling) shipped the Profile admin route + confirmed the `useAuth()` `role`/`username` exposure and the `RequireAdmin`/`RequireAuth` route shapes this story reuses. Its `actor`-from-token pattern (preferences keyed by `current_user.user_id`, body identity ignored) is the same integrity principle as D1 here.
- **Audit-transport asymmetry (intentional — do NOT "consistency"-flag):** `users.py` audits to the local `user_audit` table keyed by `user_id` (landside-local account events); `admin_alert_classes.py` audits via the **shared event envelope** (`ALERT_CLASS_DISABLED`/`REENABLED`) because a kill-switch toggle is a visible **domain** event. This story KEEPS the envelope transport — only the `actor_name` source changes. (11-2 D1 locked this asymmetry; cloud-backend/CLAUDE.md records it.)

### Project Structure Notes

- Backend: `routes/admin_alert_classes.py` (swap), `config/__init__.py` (remove `cc_admin_key`) — matches cloud-backend/CLAUDE.md. **No new file, no migration.**
- Frontend: `src/components/admin/AlertClasses.jsx` + `.css` + `__tests__/AlertClasses.test.jsx` (NEW, alongside the existing `admin/Users.jsx`), `src/api/alertClasses.js` (NEW, alongside `api/users.js`). Modify `App.jsx` + `AppShell.jsx`. Follows `src/components/<feature>/` + `src/api/<feature>.js`.

### References

- [Source: epics.md#Epic-11 → E11-S4](../../_bmad-output/planning-artifacts/epics.md) — locked scope/ACs/deliverables; the single-swap-point + actor-from-current_user direction.
- [Source: 11-1-jwt-auth-foundation-login.md](11-1-jwt-auth-foundation-login.md) — JWT foundation: `get_current_user`, `require_role`, `CurrentUser`.
- [Source: 11-2-user-management.md](11-2-user-management.md) — the canonical `require_role("admin")` router pattern, audit-via-current_user, Users screen + `RequireAdmin` + `api/users.js`, the security-test template.
- [Source: 11-3-profile-management-prefs-rekey.md](11-3-profile-management-prefs-rekey.md) — sibling S3∥S4; confirmed `useAuth()` role/username + the admin route/guard shapes; the actor-from-token integrity principle.
- [Source: routes/admin_alert_classes.py](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py) — the swap target (router dep, `AdminActionBody`, the 5 `actor_name` sites, the audit plumbing to preserve).
- [Source: api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py) — `require_role`/`get_current_user`/`CurrentUser` consumed unchanged.
- [Source: routes/users.py](../../cloud-backend/src/cloud_backend/routes/users.py) — the canonical pattern to mirror (router-level + per-route `require_role`, actor from `current`).
- [Source: services/fanout_filter.py](../../cloud-backend/src/cloud_backend/services/fanout_filter.py) — the kill-switch filter (AC1 behaviour to preserve; auth swap does NOT touch it).
- [Source: shared/src/oebb_shared/events/payloads.py](../../shared/src/oebb_shared/events/payloads.py) — `AlertClassStatePayload.actor_name` (`_NonEmptyStr`; unchanged — PAYLOAD AUDIT cleared).
- [Source: config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py) — `cc_admin_key` (removed) vs `api_key` (kept — ingest, 11-3 D4).
- [Source: control-centre/src/components/admin/Users.jsx](../../control-centre/src/components/admin/Users.jsx) + [api/users.js](../../control-centre/src/api/users.js) + [__tests__/Users.test.jsx](../../control-centre/src/components/admin/__tests__/Users.test.jsx) — the frontend mirror.
- [Source: control-centre/src/App.jsx](../../control-centre/src/App.jsx) + [shell/AppShell.jsx](../../control-centre/src/components/shell/AppShell.jsx) — route + nav admin-gating to mirror.
- [Source: control-centre/src/context/AuthContext.jsx](../../control-centre/src/context/AuthContext.jsx) — `useAuth()` → `{ role, username, ... }`.
- [Source: tests/integration/test_killswitch_fanout.py](../../cloud-backend/tests/integration/test_killswitch_fanout.py) + [tests/unit/test_admin_alert_classes.py](../../cloud-backend/tests/unit/test_admin_alert_classes.py) — tests to repoint from `X-Admin-Key` to JWT.

### Permission tier & review tier

- **Permission tier: Tier 3** — auth swap on a LIVE kill-switch (shared-infra security boundary). **Default permission mode** (project CLAUDE.md: Tier 3 on shared infra — auth/CI/migrations — always default mode regardless of session mode). **Sign-off required in-story before T1.**
- **Review tier: FULL adversarial wire-replay** (A2 — auth swap). Code-review must replay the real auth wire: a real `admin` Bearer toggles a class and the fan-out filter actually suppresses a subsequently-ingested alert of that class (not a synthetic state poke); a real `operator` token 403s; the old `X-Admin-Key`-only request 401s; and a body-supplied `actor_name` is provably ignored (the persisted actor is the token's username). Confirm the fan-out filter behaviour is byte-for-byte unchanged by the swap.

## Per-story Failure Scenarios (system-understanding required)

1. **Kill-switch silently stops filtering after the swap (AC1):** the swap changes the *gate* on the toggle endpoints, not the filter. But a careless refactor that drops the `alert_class_filter.invalidate()` call (or reorders it before the `db.commit()`) would leave the in-process `_disabled` cache stale → a freshly-disabled class keeps fanning out until the cache TTL expires, defeating the toggle the admin just made. The review must replay the **real** wire: admin toggles disable → ingest a NEW alert of that class → assert it is suppressed *now*, not after a cache expiry. (The `invalidate()` at [:142,177](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py) is load-bearing and must survive the swap untouched.)
2. **Operator escalates to kill-switch operator via the dropped body field (AC2/AC3/D1):** the old endpoint trusted a body `actor_name`; if the swap leaves any body-supplied actor path (or attaches `require_role` only at the router and reads an un-validated body in the handler), an authenticated operator — or an admin impersonating another admin — could forge the audit actor, or worse, a non-admin could reach the endpoint if the role gate is mis-wired (router dep present but a handler accidentally overrides it with `get_current_user` instead of `require_role`). The review must confirm: (a) operator → 403 on all three endpoints, and (b) the audit actor is provably `current_user.username` with no body path, replaying a spoof-attempt body.

## Open Questions — ✅ RESOLVED

1. **Actor source (D1):** ✅ **`current_user.username`** (user, 2026-06-15) — display-legible in `disabled_by`/the AlertClasses UI; `AdminActionBody.actor_name` removed; no shared-schema change.

> No residual blocker. Tier-3 sign-off before T1 still required (auth swap on a live kill-switch, default permission mode).

## Dev Agent Record

### Agent Model Used

_TBD by dev-story_

### Debug Log References

### Completion Notes List

### File List
