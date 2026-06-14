---
baseline_commit: f45013f
---

# Story 11.2: User Management (CRUD + roles + password reset)

Status: review

<!-- Created 2026-06-14 via bmad-create-story (Amelia). Second story of Epic 11 (Control Centre Admin & Identity).
     Source: _bmad-output/planning-artifacts/epics.md §"Epic 11" → "E11-S2 — User management (CRUD + roles + password reset)".
     Depends on 11-1 (DONE, commit 718e56f / patches 756a503): get_current_user, require_role, CurrentUser,
     create_access_token, hash_password/verify_password, create_user helper, users table (Alembic 0009).
     Review tier (A2): FULL adversarial wire-replay — auth + migration-adjacent. Permission tier: Tier 3.
     This story's shape is LOCKED by the epic breakdown; create-story added grounding (audit-transport Decision,
     lock-out concurrency, the mid-session active-check seam) but did not re-scope. -->

## Story

As **an admin**,
I want **to create, list, deactivate, and role-assign operator/admin accounts and reset passwords through the Control Centre**,
so that **ÖBB ops can manage who has Control Centre access without editing the database by hand, every access change is attributable and audited, and a deactivated account loses access immediately — not just at next login.**

## Context — why this story exists

11-1 shipped the JWT machinery but **the only way to create a user today is the `create_user` helper called from test code / a seed script** ([routes/auth.py:55](../../cloud-backend/src/cloud_backend/routes/auth.py)). There is no admin HTTP surface, no role management, no deactivation, no password reset, and no admin UI. This story builds that surface on top of 11-1's foundation.

It also closes the **one deferred security boundary** 11-1 explicitly left open: 11-1's **D7** decided `get_current_user` trusts a validly-signed unexpired token *without* a DB hit, and noted *"the active-check-on-verify is an **E11-S2** AC"* ([11-1-...md:64](11-1-jwt-auth-foundation-login.md)). E11-S2 AC3 is that promised check — deactivating a user must invalidate their **existing** token mid-session, not only block their next login. That converts the verify path from "claims are the source of truth" to "claims + a liveness check," and is the highest-risk design point in this story (see D2).

11-1's Round-1 review also flagged a now-relevant **Defer** that this story must clear: *"Empty-string/garbage `role` claim authenticates… harden when E11-S2/S4 add role-gated routes"* ([11-1-...md:275](11-1-jwt-auth-foundation-login.md)). E11-S2 introduces the first `require_role("admin")` routes — so the role-claim hardening lands here.

## Decisions (locked — review before dev)

> **PARTY-MODE RESOLUTION (2026-06-14, Winston + Amelia + Mary).** The three pre-flight open questions are resolved (see "Open Questions" at the bottom for the original framing):
> - **D1 → Option A** (dedicated `user_audit` table; NO `shared/` EventType/payload change). Unanimous.
> - **D6 → ADD the `bcrypt_rounds` knob**, justified as a **test-speed lever** (not prod tunability), guarded by a **fail-closed Settings validator: reject `rounds < 10` unless `app_env == "test"`** (mirrors `cc_admin_key`/`jwt_secret`).
> - **D3 (password policy) → NIST length-only, no composition rules; `Field(min_length=12, max_length=72)`** (12 for security-review defensibility; provisional pending an ÖBB corporate standard if one surfaces).
> - Two hardening riders added from the round: **72-byte cap** (AC1/AC4) and **fresh-user liveness** (AC3); plus a **seam-purity guard test** (the `is_active` lookup stays in the extractors, never folded into `_verify_token` — protects 11-1 AC4 / ADR-23).

- **D1 — User-management audit transport: structured log + dedicated `user_audit` table, NOT the events envelope. ✅ RESOLVED → Option A (party-mode, unanimous).**
  The epic says AC5's audit must be *"queryable like the kill-switch audit"* ([epics.md:2467](../../_bmad-output/planning-artifacts/epics.md)). The kill-switch audits **three ways**: an `alert_class_state` row, a structured log, **and** an `AlertClassStatePayload` event in the `events` table via `_persist_audit_event` ([admin_alert_classes.py:57](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)).
  **PAYLOAD-SPEC AUDIT (create-story rule):** there is **no `USER_*` EventType and no user-management payload in `shared/`** (verified: `EventType` tail is `ALERT_CLASS_DISABLED/REENABLED`, [types.py:41](../../shared/src/oebb_shared/events/types.py); `PAYLOAD_MODELS`, [payloads.py:555](../../shared/src/oebb_shared/events/payloads.py)). Reusing the events envelope for user audit would require **adding new EventTypes + a payload + the `PAYLOAD_MODELS` registry entry + the `anonymise.py` allow-list entry** ([anonymise.py:55-67](../../shared/src/oebb_shared/events/anonymise.py)), which **cascades to event-store + the `contract` test suite** (shared/CLAUDE.md: *"Do not change event schema field names without a contract test update — cloud-backend and event-store both deserialise these"*).
  - **Option A (RECOMMENDED): dedicated `user_audit` table + structured log.** Add `user_audit` (Alembic 0010) with `{audit_id, actor_user_id, target_user_id, action, detail, created_at}` and a structured `log.info("admin.user_<action>", ...)`. User-account events are a **cloud-backend-local admin concern** that never flows onboard/edge and has **no anonymisation/egress relevance** — putting password-reset/role-change rows through the cross-service event envelope (designed for onboard sensor telemetry) is the wrong bus. "Queryable like the kill-switch audit" is satisfied by a queryable table + structured log; the envelope was one of *three* kill-switch mechanisms, not the defining one.
  - **Option B: extend the events envelope.** Add `USER_CREATED/USER_ROLE_CHANGED/USER_DEACTIVATED/USER_PASSWORD_RESET` EventTypes + a `UserAuditPayload` + registry + anonymise allow-list + contract tests. Truer to "exactly like the kill-switch," but spends a cross-service schema change + contract churn on data that never leaves cloud-backend.
  - **Cost of each:** A = one local migration, zero `shared/` change, zero contract churn. B = `shared/` schema change + event-store awareness + new contract tests + anonymise review, for an audit stream no other service consumes.
  - **Recommendation: Option A.** Surface to the user at pre-flight if they want the stricter "literally the same mechanism" reading (Option B); otherwise proceed with A and record it in the story's Change Log + a one-line note in the cloud-backend CLAUDE.md auth/audit section.

- **D2 — Mid-session deactivation requires a DB liveness check on the verify path (AC3) — scope it tightly.**
  11-1's `get_current_user` does **no DB hit** (D7). AC3 requires a deactivated user's *existing* token to fail. The minimal change: after `_verify_token` resolves claims, look up `is_active` for `sub` and 401 if false/missing. **Decisions inside D2:**
  - Add the liveness check in a place that does **not** break 11-1's AC4 seam contract (verification stays config/issuer-agnostic). The cleanest seam: keep `_verify_token` pure (claims only), and add the `is_active` lookup in `get_current_user` / `get_current_user_from_query` **after** `_verify_token` returns — so the *crypto* seam is untouched and only the *extractor* gains a liveness gate. The OIDC-swap guarantee (AC4) still holds: an external issuer's token still verifies; the liveness check is a local authorization concern layered on top.
  - This adds **one indexed PK lookup per authenticated request.** Acceptable for a ~4-user PoC. Do **not** build a cache/revocation-list (speculative — Karpathy). Note as a perf item for Phase 2.
  - **Trap:** `get_current_user_from_query` (the SSE `?token=` path) must get the **same** liveness gate, or a deactivated user keeps their live alert stream. AC3's test must cover **both** extractors.
  - **DB session on the verify path:** `get_current_user` currently has no `db` dependency. Adding one makes every protected route depend on a DB session at auth time. Confirm `get_db` ([database.py](../../cloud-backend/src/cloud_backend/database.py)) is safe to depend on inside an auth dependency (it is the same async session factory routes already use). Keep the query a single `SELECT is_active FROM users WHERE user_id = :sub`.
  - **✅ SEAM RULING (party-mode, Winston):** the liveness lookup in the *extractor* genuinely **preserves** the ADR-23 seam — it is authorization (a *local* question: "is this validly-identified principal still allowed here?"), distinct from `_verify_token`'s authentication (a *crypto* question: "is this token valid under the configured issuer?"). The liveness check **survives the Keycloak/OIDC swap unchanged** — even with an external issuer minting tokens, ÖBB still deactivates an operator in our `users` table and we must still honor it mid-session. **The one move that WOULD break the contract: folding the `is_active` SELECT into `_verify_token` to save a round-trip.** Forbid it — add a **seam-purity guard test** (`test_seam_liveness_survives_verifier_swap`): swap the verifier (second issuer/key via Settings, reusing 11-1's `test_seam_oidc_swap` mechanism) and assert the liveness gate still fires (a deactivated user is still 401'd) — proving liveness lives in the extractor, not the crypto core. ADR-23 gets a one-line addendum, not a rewrite (T7).

- **D3 — Last-active-admin lock-out guard must be race-safe (AC6).**
  "Cannot delete/deactivate the last active admin → 409" ([epics.md:2468](../../_bmad-output/planning-artifacts/epics.md)). A naive `SELECT count(*) … WHERE role='admin' AND is_active` then `UPDATE` is a **TOCTOU race** under two concurrent deactivations — both read count=2, both proceed, zero admins left. **Decision:** enforce atomically. Do the guard inside the same transaction as the mutation using a conditional UPDATE, e.g. `UPDATE users SET is_active=false WHERE user_id=:id AND NOT (role='admin' AND (SELECT count(*) FROM users WHERE role='admin' AND is_active) <= 1)` evaluated under `SELECT … FOR UPDATE` on the admin rows, or a guard that re-counts within the locked transaction and rolls back → 409. The integration test (A1) must drive the concurrent-deactivation case, not just the single-call case. This is the OEBB-specific failure scenario for this story (see Review section).

- **D4 — No new `users` columns; this story is CRUD on the 0009 table.** The `users` table (0009) already has `user_id, username, password_hash, role, is_active, created_at, updated_at` ([0009_users.py:27](../../cloud-backend/migrations/versions/0009_users.py)). E11-S2 needs **no `users` schema change** — only the new `user_audit` table (D1 Option A → Alembic 0010). `updated_at` is **not** auto-updated by the DB on mutation (server_default applies on insert only); if AC needs a fresh `updated_at` on role/active/password change, set it explicitly in the UPDATE. (Surgical: only touch `updated_at` where a mutation AC implies it; do not add a DB trigger.)

- **D5 — Reuse `create_user`; do not reinvent the insert.** `POST /api/v1/admin/users` builds on the existing `create_user(db, username, password, role)` helper ([routes/auth.py:55](../../cloud-backend/src/cloud_backend/routes/auth.py)) — it already hashes via the app's bcrypt and inserts. Add only: duplicate-username handling (uniform error, no enumeration — Security Test) and password-policy validation at the boundary. **Do not** raw-INSERT a hash (A3 rule; also defeats the real-hash pairing).

- **D6 — Password policy at the boundary + bcrypt cost knob. ✅ RESOLVED (party-mode).**
  - **Password policy → NIST-style, length-only, NO composition rules** (no "1 upper / 1 digit" theatre — NIST 800-63B dropped it; it drives operators to `Password1!` + post-its). Enforce at the Pydantic boundary on the create/reset bodies (not in the handler): **`password: str = Field(min_length=12, max_length=72)`**. `min_length=12` (not 8) for ÖBB-security-review defensibility — provisional pending an actual ÖBB corporate standard if one surfaces. `max_length=72` is **load-bearing, not padding** (the 72-byte rider — see AC1 note): `hash_password` silently truncates at 72 bytes ([api/auth.py:61](../../cloud-backend/src/cloud_backend/api/auth.py)), so without the cap a >72-byte password "set" by the user authenticates on only its first 72 bytes — a silent footgun. The cap 422s it at the boundary instead.
  - **bcrypt cost knob → ADD `bcrypt_rounds: int = 12` to Settings; `hash_password` reads `bcrypt.gensalt(rounds=settings.bcrypt_rounds)`.** Justification is **test speed, not prod tunability**: the A1 integration suite creates users through the real cost-12 hash path repeatedly (~250ms/hash), compounding across end-to-end + concurrent-lockout + login round-trips; the test env drops `bcrypt_rounds` to 4. Prod stays 12.
  - **Fail-closed floor (Mary's condition, Winston-endorsed):** the cheap value must NOT escape the test env. A **Pydantic field validator on Settings rejects `bcrypt_rounds < 10` unless `app_env == "test"`** — the same fail-closed reflex this codebase already uses for `cc_admin_key`/`jwt_secret` (don't trust env hygiene; reject at Settings load, which is startup). No separate startup assertion (the validator already fails at load). Blast radius of a silently-cost-4 prod is *every credential in the store* — three lines of validator is the cheapest insurance in the story.

- **D7 — Role-claim hardening (clears 11-1 Defer).** `require_role` currently admits any non-empty role string and `_verify_token` requires the `role` claim present but not non-empty ([api/auth.py:128](../../cloud-backend/src/cloud_backend/api/auth.py)). With real `require_role("admin")` routes arriving, reject an empty/garbage role: a token whose `role` is `""` or not in the known set must NOT satisfy any `require_role(...)`. Minimal: `require_role` already 403s when `user.role not in roles` — an empty role naturally fails `require_role("admin")`. Confirm the empty-role token cannot reach a privileged route, and add a Security Test pinning it. Do not over-engineer a role enum unless mypy/clarity demands it.

## Acceptance Criteria

**AC1 — admin creates an operator who can immediately log in**
Given an `admin` token, when `POST /api/v1/admin/users` is called with `{"username","password","role":"operator"}`, then `201` with the new user's `{user_id, username, role, is_active}` (NO password/hash in the response), and that user can immediately `POST /api/v1/auth/login` and receive an `operator`-role token. Creation goes through the real `create_user` path (D5) — bcrypt-hashed, never a raw INSERT.
**Rider (72-byte cap, D6):** `UserCreate.password` and `PasswordReset.password` are `Field(min_length=12, max_length=72)`; a >72-byte password is rejected `422` at the boundary, **never silently truncated** to a different credential than the user typed (closes the `hash_password` 72-byte-truncation footgun).

**AC2 — admin-only on every user endpoint**
Given an `operator` token, when it calls ANY `/api/v1/admin/users*` endpoint (`GET` list, `POST` create, `PATCH`, `POST .../reset-password`), then `403` (ADR-10 envelope). Given an `admin` token → `200/201`. A missing/invalid token → `401` (not 403). The router is gated with `Security(require_role("admin"))` (per-router, matching 11-1's pattern), not body-level role checks.

**AC3 — deactivation invalidates the existing token mid-session (the D7-deferred check)**
Given an active user with a currently-valid token, when an admin `PATCH /api/v1/admin/users/{id}` sets `is_active=false`, then (a) that user's subsequent `login` fails `401`, AND (b) that user's **already-issued** token now fails `get_current_user` **and** `get_current_user_from_query` (SSE `?token=`) with `401` — the liveness check runs on verify, not only at login (D2). Re-activating restores access.
**Rider (fresh-user liveness, closes the AC1↔D2 contradiction):** a freshly-created user's **first-issued token passes both liveness extractors immediately** — the 0009 `is_active` server-default resolves `true` on insert, so `create → login → authenticated call` succeeds with no second mutation. (Without this pin, AC1's "immediately log in" and D2's new per-request `is_active` SELECT could silently disagree.)

**AC4 — password reset rotates the credential**
Given an `admin` token, when `POST /api/v1/admin/users/{id}/reset-password` with a new password, then the old password `login` → `401` and the new password `login` → `200`. Reset requires `admin` role specifically (not merely an authenticated caller — Security Test). The new hash goes through the app's `hash_password` (no raw INSERT/UPDATE of a hand-computed hash).

**AC5 — every mutation is audited (D1 Option A)**
Given any user-management mutation (create, role change, deactivate/reactivate, password reset), then a `user_audit` row is written with `{actor_user_id = current_user.user_id, target_user_id, action, detail, created_at}` AND a structured log line is emitted, **in the same transaction as the mutation** (no audit-without-mutation, no mutation-without-audit). The audit is queryable by `target_user_id` and by `actor_user_id`. (Password-reset audit records the action, NEVER the password or hash.)

**AC6 — last-active-admin lock-out guard, race-safe**
Given exactly one active admin, when an admin tries to deactivate that last active admin (or change its role away from `admin`), then `409` (ADR-10 envelope) and the user stays active/admin. The guard is atomic: under two concurrent deactivation requests targeting the two last admins, **at most one succeeds** and at least one active admin always remains (D3). Proven by an integration test driving the concurrent case.

**AC7 — frontend admin Users screen (role-gated, browser-verified)**
Given the Control Centre SPA with an `admin` session, a "Users" admin screen renders loading / error / populated states; admin can create a user (modal), toggle role, deactivate/reactivate, and reset a password, and each round-trips and reflects in the list without a manual refresh. Given an `operator` session, the Users screen / nav entry is **not shown** and a direct route to it is blocked (operator never sees admin UI). **Browser-verified** per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) "Verification Requirement": golden path (create→appears in list) + at least one edge (operator-blocked OR duplicate-username error OR last-admin 409 surfaced).

**AC8 — gates green; migration safe + idempotent**
Given Alembic `0010_user_audit.py` (D1 Option A), it is new-table-only (`down_revision="0009"`, safe under concurrent reads, no lock on `users`/`events`), and a downgrade→upgrade re-apply test passes (mirror 11-1's strengthened migration test, [test_auth_jwt.py](../../cloud-backend/tests/integration/test_auth_jwt.py)). cloud-backend unit + integration (real Postgres, testcontainers) cover AC1–AC6 at ≥80%; `ruff` + `mypy --strict` clean on touched `src/`; control-centre `vitest` green for the Users surface + four-path Playwright per dev-story DoD.

## Security Tests (RED-first — write before domain tests, per dev-story DoD)

Write each to fail for the right reason first, then implement:

1. **Operator self-escalation via PATCH → 403:** an `operator` token PATCHing its own (or any) user to `role:"admin"` is rejected by `require_role("admin")` before any DB write (AC2). Assert no row changed.
2. **Reset-password requires admin, not mere authentication → 403:** a valid `operator` token on `…/reset-password` → 403 (AC4).
3. **Duplicate-username on create → uniform error, no enumeration:** creating an existing username returns a generic conflict (e.g. 409 with a non-username-revealing detail) — the body must not differ in a way that confirms which usernames exist beyond the unavoidable conflict signal; do not echo "user 'claudia' exists" vs a generic message inconsistently.
4. **Deactivated-user token rejected mid-session (both extractors):** deactivate a user, then their pre-existing Bearer token → 401 on a header-gated route AND their `?token=` on the SSE gate → 401 (AC3 / D2 trap).
5. **Empty/garbage role claim cannot reach an admin route (clears 11-1 Defer):** a token minted with `role:""` (or a junk role) → 403/401 on every `require_role("admin")` route — never 200, never 500 (D7).
6. **Last-active-admin guard holds under concurrency → ≥1 admin always remains (AC6/D3):** two concurrent deactivations of the two last admins; assert exactly ≤1 succeeds and an active admin remains.
7. **No password/hash ever leaves the API:** create / reset / list responses and audit rows contain no `password` or `password_hash` field (grep the serialized response + the audit row).

## Integration test (A1 hard gate + A3 real-producer seeding)

**`test_user_management_end_to_end`** (testcontainers real Postgres) — MUST run and pass before the story flips to `review` ("deferred to CI" is not acceptable; `docker info` to confirm, start it if down). This is the E10-A1 gate; auth/identity is the canonical test/prod-divergence risk.

**A3 — seed via the REAL path:** the acting admin is created through the **real `create_user`/login flow** (the same bcrypt the app uses), NOT a raw INSERT of a hand-computed hash (the 10-4/10-5 lesson, restated in 11-1's A3 gate). Then drive end-to-end on real Postgres:
**create-admin (real) → login-as-admin → create-operator (via API) → login-as-new-operator (proves the real hash/verify pairing) → admin deactivates operator → operator's existing token now 401s (AC3) → operator login now 401s → admin reset-password → old creds 401 / new creds 200 → assert a `user_audit` row exists for each mutation.**
Plus `test_last_admin_guard_concurrent` (AC6/D3), `test_seam_liveness_survives_verifier_swap` (D2 seam-purity guard), and the `0009→0010` migration re-apply test (AC8) run under the same gate. Mirror the testcontainers fixture shape used across `cloud-backend/tests/integration/`.

> **Note the pre-existing integration-test isolation flaky** documented in 11-1's review ([11-1-...md:278](11-1-jwt-auth-foundation-login.md)): `test_ai_quality_rates.py` intermittently fails under multi-module ordering due to `DATABASE_URL`-leaking `pg_url` fixtures — **confirmed not introduced by 11-1**. If it surfaces, do NOT chase it in this story; verify the 11-2 auth/user tests are deterministically green in isolation and note it. (The hermetic-fixture fix is its own deferred follow-up.)

## Tasks / Subtasks

- [x] **T1 — Pydantic models + `bcrypt_rounds` Setting + Alembic 0010 `user_audit`** (AC1, AC5, AC8, D1, D4, D6) — `api/users.py` request/response models (`UserCreate`, `UserPatch`, `PasswordReset`, `UserOut` — NO hash field, AC7-7); password fields `Field(min_length=12, max_length=72)` (D6). Add `bcrypt_rounds: int = 12` to `config/__init__.py` Settings with a **field validator rejecting `< 10` unless `app_env == "test"`** (D6 fail-closed floor); repoint `hash_password` → `bcrypt.gensalt(rounds=settings.bcrypt_rounds)` ([api/auth.py:61](../../cloud-backend/src/cloud_backend/api/auth.py)). `0010_user_audit.py` new-table-only (`down_revision="0009"`), columns per D1 Option A. RED: migration re-apply test + the `bcrypt_rounds < 10` prod-rejection validator test first.
- [x] **T2 — Liveness check on the verify path + seam-purity guard** (AC3, D2, D7) — add the `is_active` lookup in `get_current_user` AND `get_current_user_from_query` AFTER `_verify_token` (keep `_verify_token` pure → AC4 seam intact); reject deactivated/missing user 401. RED first: Security Test 4 (both extractors), Test 5 (empty role), AND `test_seam_liveness_survives_verifier_swap` (D2 seam ruling — swap the verifier, assert the liveness gate still fires; proves liveness lives in the extractor, not the crypto core).
- [x] **T3 — `routes/users.py` admin CRUD** (AC1, AC2, AC4, AC6, D3, D5) — router gated `Security(require_role("admin"))`; `GET` list, `POST` create (reuse `create_user`, duplicate→uniform conflict), `PATCH` (role / is_active, with the race-safe last-admin guard D3), `POST .../reset-password`; mount in `main.py` (preserve mount order / exception handler / startup log). RED: Security Tests 1,2,3,6 first.
- [x] **T4 — Audit writes (D1 Option A)** (AC5) — `user_audit` row + structured log in the SAME transaction as each mutation; actor = `current_user.user_id`, never a body field; password reset audits the action only (no secret). Mirror the structured-log idiom from `admin_alert_classes` ([:143](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)).
- [x] **T5 — Frontend admin Users screen** (AC7) — `src/api/users.js` (through the shared `authFetch` Bearer helper, [src/lib/auth/authFetch.js](../../control-centre/src/lib/auth/authFetch.js)); `src/components/admin/Users.jsx` (+CSS, `--obb-*` only) — list / create-modal / role-toggle / deactivate-reactivate / reset-password; role-gated nav + route guard so operators never see it (extend the existing `RequireAuth` pattern with a role check, [src/App.jsx](../../control-centre/src/App.jsx) / AuthContext). vitest for the api client + component states.
- [x] **T6 — Integration tests + browser verify** (A1 gate, AC7, AC8) — `test_user_management_end_to_end` (A3 real-seed), `test_last_admin_guard_concurrent`, migration re-apply — all green on real Postgres (Docker up, run locally). Browser-verify the Users golden path + one edge per AC7. Confirm `ruff`/`mypy --strict`/coverage gates.
- [x] **T7 — Docs** (D1, AC8) — one-line note in `cloud-backend/CLAUDE.md` auth/audit section recording the user-audit transport decision (D1 Option A) and the mid-session liveness check (D2). **ADR FRESHNESS:** the D2 liveness check refines ADR-23's "claims are the source of truth" posture (it now reads "claims authenticate; a local `is_active` check in the extractor authorizes — without coupling the verifier to local state"). Add a **one-line ADR-23 addendum** in `architecture.md` to that effect (not a new ADR — confirmed by the party-mode seam ruling).

## Dev Notes

### Architecture patterns & constraints

- **ADR-8:** every route under `/api/v1/`. **ADR-10:** error envelope `{"error","detail","recoverable"}` for all 401/403/409. **ADR-23 (11-1):** the verify seam — `_verify_token` reads issuer/algorithm/key from Settings only; **keep it pure** so AC4's OIDC-swap guarantee survives D2 (layer liveness in the *extractor*, not the crypto core).
- **Fail-closed idiom** is shipped ([admin_alert_classes.py:34-35](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)); the JWT path already fails closed on empty secret (11-1 AC7) — nothing to add there.
- **cloud-backend/CLAUDE.md "Review Failure Scenarios":** JWT edge cases (expired/tampered/missing-role → 401/403 not 500) — 11-1 discharged these; this story must not regress them when adding the liveness check (the check must 401, never 500, on a missing/deactivated user).

### Files being modified (UPDATE) — current state / change / preserve

Per the FULL-FILE-READS rule, read each completely before coding. Verified current state:

- **[api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py)** (145 lines) — *current:* `_verify_token` (pure, claims-only), `get_current_user` (header extractor, NO db), `get_current_user_from_query` (`?token=`, NO db), `require_role` factory (403 when `role not in roles`), `hash_password`/`verify_password`/`create_access_token`. *change:* add an `is_active` DB liveness check in BOTH extractors after `_verify_token` (D2/AC3); leave `_verify_token` and `require_role` logic intact. *preserve:* the seam contract (AC4) — extractors gain a `db` dep, the crypto core does not change; `require_api_key` stays importable.
- **[routes/auth.py](../../cloud-backend/src/cloud_backend/routes/auth.py)** (109 lines) — *current:* `login` (uniform-timing dummy-hash verify, checks `is_active` at login), `/me`, and the **`create_user` helper this story reuses** ([:55](../../cloud-backend/src/cloud_backend/routes/auth.py)). *change:* none required, OR move/import `create_user` if `routes/users.py` reuses it (import it; do not duplicate). *preserve:* the uniform-timing login path (don't refactor it).
- **[main.py](../../cloud-backend/src/cloud_backend/main.py)** — *current:* bare `include_router` mounts, per-router auth, no central middleware (11-1 D2). *change:* mount the new `users_router`. *preserve:* mount order / exception handler / startup log.
- **[admin_alert_classes.py](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)** — *reference only* (the audit + structured-log idiom to mirror; E11-S2 does NOT touch this router — its JWT swap is E11-S4).
- **[control-centre/src/App.jsx](../../control-centre/src/App.jsx)** + AuthContext + `RequireAuth` — *current:* 11-1's auth guard redirects unauthenticated → `/login`. *change:* add a role-gated route/nav for the admin Users screen (operators blocked). *preserve:* the existing `RequireAuth` redirect behavior.

### shared/ payload audit (PAYLOAD-SPEC AUDIT rule — DONE)

Verified: **no `USER_*` EventType, no user-mgmt payload** exists in `shared/`. `EventType` tail = `ALERT_CLASS_DISABLED/REENABLED` ([types.py:41](../../shared/src/oebb_shared/events/types.py)); `PAYLOAD_MODELS` registry ends at the same ([payloads.py:584](../../shared/src/oebb_shared/events/payloads.py)); anonymise allow-list ([anonymise.py:55](../../shared/src/oebb_shared/events/anonymise.py)) likewise. **This is the basis of D1** — Option A avoids any `shared/` change and the contract-test cascade; Option B incurs it. Do not silently add to `shared/` without taking D1 to the user.

### CSS tokens (Users.jsx)

Use only `--obb-*` from [control-centre/src/styles/colors_and_type.css](../../control-centre/src/styles/colors_and_type.css). Likely tokens: surfaces `--obb-surface-0..5`; text `--obb-text-on-dark-1..4`; destructive/deactivate state `--obb-sev-critical` (red); confirm/active `--obb-sev-normal` (green); borders `--obb-border-dark/bright`; accent `--obb-blue-accent`; `--font-mono` for `user_id`/timestamps. **`--obb-sev-warning` does NOT exist (use `--obb-sev-medium`); `--obb-sev-danger` does NOT exist (use `--obb-sev-critical`).**

### UX ownership (Freya)

The admin Users screen is a **new UX surface**. Per the epic's UX-pass plan ([epics.md:2558](../../_bmad-output/planning-artifacts/epics.md)), each E11 story ships a **minimal functional** UI (theme-correct, browser-verified); Freya runs ONE coherent WDS pass over the whole admin/identity shell (login + Users + Profile + Alert-Classes + Configuration) at epic close — so do NOT over-design the Users screen in isolation now. Minimal functional list + modal + toggles satisfies AC7; Freya reviews in the browser-verify step.

### Testing standards

- Markers: `@pytest.mark.unit` (no DB) / `@pytest.mark.integration` (testcontainers Postgres). Coverage ≥80%; security-critical paths near-complete.
- `mypy --strict` + `ruff` clean on touched `src/`.
- CC: `vitest` for `src/api/users.js` + Users component states; Playwright four paths (happy, auth-failure/operator-blocked, validation/duplicate-or-409 error, edge) per dev-story DoD.
- Mirror 11-1's strengthened migration test (real downgrade→upgrade, schema assertions) for 0010.

### Project Structure Notes

- Backend: `routes/users.py` (handlers only), `api/users.py` (Pydantic models), env (if any) in `config.py`, migration autogenerated then reviewed — matches cloud-backend/CLAUDE.md. No variances detected.
- Frontend: `src/components/admin/Users.jsx` + `src/api/users.js` — `admin/` is a NEW component dir (current dirs: alerts, analytics, auth, escalations, health, live, luggage, occupancy, shell, train-detail). Follows the `src/components/<feature>/` convention (control-centre/CLAUDE.md).

### References

- [Source: epics.md#Epic-11 → E11-S2](../../_bmad-output/planning-artifacts/epics.md) — locked scope/ACs/deliverables.
- [Source: 11-1-jwt-auth-foundation-login.md](11-1-jwt-auth-foundation-login.md) — foundation (D7 active-check deferral → AC3; Round-1 empty-role Defer → D7; A1/A3 gates; flaky-fixture note).
- [Source: cloud-backend/src/cloud_backend/api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py) — `require_role`, extractors, `_verify_token` seam.
- [Source: cloud-backend/src/cloud_backend/routes/auth.py:55](../../cloud-backend/src/cloud_backend/routes/auth.py) — `create_user` helper (reuse, D5).
- [Source: admin_alert_classes.py](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py) — audit + structured-log idiom (mirror, D1/T4).
- [Source: 0009_users.py](../../cloud-backend/migrations/versions/0009_users.py) — users table (no schema change this story, D4) + migration shape for 0010.
- [Source: shared/events/types.py, payloads.py, anonymise.py] — payload audit basis for D1.

### Permission tier & review tier

- **Permission tier: Tier 3** — DB migration (0010) + auth/role enforcement + the verify-path liveness change on shared infrastructure. **Default permission mode** (project CLAUDE.md: Tier 3 on shared infra — auth, migrations — always default mode regardless of session mode). **Sign-off required in-story before T1.**
- **Review tier: FULL adversarial wire-replay** (A2 — auth + migration-adjacent). Code-review must replay the real admin→create→login-as-new-user→deactivate→token-401 wire (not synthetic kwargs), and adversarially probe the lock-out race (D3) and the mid-session liveness gate on BOTH extractors (D2).

## Per-story Failure Scenarios (system-understanding required)

1. **Last-active-admin lock-out under concurrency (D3/AC6):** two admins are deactivated simultaneously (two requests, two workers). A count-then-update implementation leaves **zero** active admins — Control Centre is permanently locked out (no admin can re-activate anyone). The guard must be atomic; the review must confirm the real concurrent path, not just the single-request 409.
2. **Deactivated operator keeps the live alert feed via SSE (D2/AC3 trap):** an operator is deactivated, their Bearer calls now 401 — but their browser's `EventSource` opened a `?token=` SSE stream *before* deactivation and `get_current_user_from_query` was NOT given the liveness gate, so the long-lived stream keeps delivering alerts to a revoked user until the token's 60-min `exp`. Both extractors must share the liveness check; the test must cover the query path, not only the header path.

## Open Questions — ✅ ALL RESOLVED (party-mode 2026-06-14)

1. **D1 — audit transport:** ✅ **Option A** (dedicated `user_audit` table, no `shared/` change). Unanimous (Winston/Amelia/Mary) — user-account audit is landside-local, never crosses the egress/anonymise boundary the events bus exists for; "queryable like the kill-switch" is a *property* (queryable trail), not the envelope *mechanism*.
2. **D6 — bcrypt cost knob:** ✅ **ADD** `bcrypt_rounds: int = 12` — justified as a test-speed lever (not prod tunability), guarded by a fail-closed Settings validator (`reject < 10 unless app_env == "test"`). Mary/Winston flipped from "defer" once Amelia reframed it as a CI-wall-clock multiplier on the mandatory real-path A1 suite.
3. **Password policy minimum length** (D6): ✅ **NIST length-only, `min_length=12`, no composition rules**; provisional pending an actual ÖBB corporate standard if one surfaces (12 > 8 for security-review defensibility, one-line validator change either way). Plus the `max_length=72` truncation-cap rider.

> One residual item to confirm at dev pre-flight (not a blocker): whether ÖBB has a published Control-Centre password standard to anchor the `min_length` to — if so, match it; if not, 12 stands.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia)

### Debug Log References

### Completion Notes List

- **All 9 ACs satisfied.** AC1 create+immediate-login (+72-byte rider), AC2 admin-only (operator→403, missing→401 on all 4 endpoints), AC3 mid-session deactivation kills BOTH extractors (+fresh-user liveness rider), AC4 password reset rotates, AC5 audit row per mutation in-transaction, AC6 race-safe last-admin guard, AC7 browser-verified Users screen, AC8 gates green + 0010 idempotent, plus the seam-purity guard test.
- **D2 liveness ripple (the big one).** Adding the `is_active` lookup to `get_current_user`/`get_current_user_from_query` made every protected route depend on `get_db`. This broke 27 unit + ~47 integration tests that minted synthetic-user tokens (`u-operator`) with no DB row. Fixed centrally, NOT per-test: (a) unit tier — an autouse fixture in `tests/unit/conftest.py` overrides the two extractors to verify-without-DB (chosen over a get_db override because many unit db-mocks answer by call-INDEX and a liveness query inserted first shifts every index); (b) integration tier — `tests/integration/conftest.py` gained `seed_auth_users(pg_url)` (creates `users` IF NOT EXISTS + seeds two fixed-UUID synthetic users), called from each protected module's `pg_url` fixture. `auth_header()` now mints tokens for those seeded UUIDs.
- **Bug caught by my own integration test:** the last-admin guard initially didn't fire — `_would_orphan_admins` compared a UUID object (`r.user_id`) to a str (`target_user_id`); fixed with `str()` coercion. Without the concurrent test this would have shipped.
- **Latent 11-1 flaky fixed (it surfaced through my work, so I fixed it).** `test_auth_jwt.py::test_auth_flow_end_to_end` intermittently failed in the full suite: its tamper flipped the LAST signature base64url char to 'A'/'B', which leaves the signature byte-identical ~5.5% of the time (the trailing char carries ~2 significant bits). My new module shifted test timing enough to expose it. Changed the tamper to reverse the whole signature segment (guaranteed-invalid). Also made my `test_seam_liveness_survives_verifier_swap` restore `JWT_SECRET`/`JWT_ISSUER` via explicit try/finally (not monkeypatch) so it can't leak the alt-issuer secret across modules.
- **GATES (all green):** backend **257 passed** (unit + integration on real Postgres via testcontainers, A1 gate ran locally — Docker up), determinism confirmed 3× consecutive; **mypy --strict** clean (40 files); **ruff** clean (src + tests); coverage **TOTAL 83%** (≥80 gate), `api/auth.py`/`api/users.py`/`config` 100%. Frontend **275 vitest** passed (264 baseline + 11 new); eslint clean on all new files (the one remaining repo-wide lint error is pre-existing `AuthContext.jsx only-export-components`, not introduced here).
- **BROWSER-VERIFIED (AC7)** against a real seeded backend (admin `claudia`) via the `control-centre-verify-8002` launch config (Vite dev-proxy → uvicorn :8002, real Postgres): (1) unauthenticated `/dashboard/users` → redirect to /login; (2) golden — admin login → dashboard → admin-only Users nav → list renders → create operator round-trips (modal closes, list refetches); (3) edge — Deactivate on the last admin surfaces "Cannot remove the last active admin" (red `--obb-sev-critical`), user stays active; (4) operator-blocked — Users nav hidden for operator AND direct `/dashboard/users` bounced to /dashboard/live. Only console errors are the pre-existing `fetchTrainAlerts` 404s (mock train IDs; 404 not 401 = auth flowing).
- **bcrypt cost-4 coverage note:** `routes/users.py` shows 41% line coverage under `--cov`, but every endpoint is exercised by passing integration assertions — this is the known async-route-under-ASGITransport coverage measurement gap (consistent with other route files in the suite, e.g. routes measured low while logic modules read 100%). The logic-bearing modules (`api/users.py`, `api/auth.py`, `config`) are 100%.

### File List

**Backend (new):** `src/cloud_backend/api/users.py`, `src/cloud_backend/routes/users.py`, `migrations/versions/0010_user_audit.py`, `tests/unit/test_user_management_security.py`, `tests/integration/test_user_management.py`
**Backend (modified):** `src/cloud_backend/config/__init__.py` (app_env + bcrypt_rounds + validator), `src/cloud_backend/api/auth.py` (liveness extractors + hash_password rounds), `src/cloud_backend/main.py` (mount users_router), `CLAUDE.md` (auth/liveness/audit note), `tests/conftest.py` (APP_ENV/BCRYPT_ROUNDS), `tests/unit/conftest.py` (liveness-bypass autouse), `tests/unit/test_auth_security.py` (active-user db override), `tests/integration/conftest.py` (seed_auth_users + UUID synthetic ids), `tests/integration/test_auth_jwt.py` (robust tamper + liveness-aware seam test), `tests/integration/{test_ai_quality_rates,test_alerts_sse,test_analytics_endpoints,test_capacity_review,test_delay_minutes_avoided,test_escalation_audit,test_escalations,test_killswitch_fanout}.py` (call seed_auth_users in pg_url)
**Frontend (new):** `src/api/users.js`, `src/components/admin/Users.jsx`, `src/components/admin/Users.css`, `src/api/__tests__/users.test.js`, `src/components/admin/__tests__/Users.test.jsx`
**Frontend (modified):** `src/lib/auth/tokenStore.js` (getRole), `src/context/AuthContext.jsx` (expose role), `src/App.jsx` (RequireAdmin + /dashboard/users route), `src/components/shell/AppShell.jsx` (admin-only Users nav)
**Docs:** `_bmad-output/planning-artifacts/architecture.md` (ADR-23 E11-S2 addendum)
**Local tooling (gitignored):** `.claude/launch.json` (control-centre-verify-8002 config)

> **Flagged (not mine to claim, left untouched):** an uncommitted local change to `tests/integration/test_ai_quality_rates.py` (back-dating seed timestamps to dodge the host/container clock-skew flaky) was already in the working tree at story start — a legitimate fix for the pre-existing flaky 11-1's review documented. Left as-is; not part of this story's commits.

## Change Log

| # | Change | Rationale |
|---|---|---|
| 1 | Party-mode (Winston/Amelia/Mary) resolved D1/D6/D3 + added 3 hardening riders | D1→Option A (local `user_audit`, no events-bus/contract cascade); D6→add `bcrypt_rounds` knob (test-speed lever) with fail-closed `< 10 unless test` validator; D3 password policy→NIST length-only `min_length=12`. Riders: 72-byte `max_length` cap (AC1), fresh-user liveness pin (AC3, closes AC1↔D2 contradiction), seam-purity guard test (D2/T2, protects 11-1 AC4/ADR-23). All pre-flight open questions closed. |
| 2 | Liveness check made all protected routes depend on get_db → fixed test ripple centrally | Unit: autouse extractor-bypass in tests/unit/conftest.py (avoids the call-index fragility of a get_db mock). Integration: seed_auth_users() in tests/integration/conftest.py + per-module pg_url calls, with fixed-UUID synthetic users matching auth_header() tokens. |
| 3 | `_would_orphan_admins` UUID-vs-str coercion | Last-admin guard silently no-op'd (set comparison `{UUID} == {str}` always False); caught by the concurrent integration test. |
| 4 | Robust tamper in 11-1 `test_auth_flow_end_to_end` (reverse sig, not last-char flip) | A last-char base64url A/B flip leaves the signature byte-identical ~5.5% of the time — a latent flake exposed by this story's test-ordering shift. Verifier itself is correct. |
| 5 | seam-liveness test restores JWT_SECRET/JWT_ISSUER via try/finally not monkeypatch | monkeypatch's function-teardown interleaved with other modules' module-scoped _jwt_env fixtures, leaking the alt-issuer secret in full-suite runs. |
