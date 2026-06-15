---
baseline_commit: a7e6a2d
---

# Story 11.3: Profile management + preferences re-key migration

Status: ready-for-dev

<!-- Created 2026-06-15 via bmad-create-story (Amelia). Third story of Epic 11 (Control Centre Admin & Identity).
     Source: _bmad-output/planning-artifacts/epics.md §"Epic 11" → "E11-S3 — Profile management + preferences re-key migration".
     Depends on 11-1 (DONE, JWT foundation: get_current_user, CurrentUser{user_id,username,role}, users table 0009) and
     11-2 (DONE, user_audit table 0010, liveness extractors). Both in _bmad-output/implementation-artifacts/.
     Review tier (A2): FULL adversarial wire-replay — migration on EXISTING data. Permission tier: Tier 3.
     SCOPE IS SMALLER THAN THE EPIC IMPLIED — see "Decisions" D1: 11-1 ALREADY swapped preferences.py to key by
     current_user.user_id and the frontend already uses Bearer auth. The residual work is the SCHEMA re-key migration
     (the table column is still plain TEXT holding the old API-key string; rows read 404 today) + the FK + the Profile
     screen. create-story did not re-scope the epic's intent; it grounded it against what 11-1 actually shipped. -->

## Story

As **a logged-in operator**,
I want **my preferences (critical-alert threshold, staleness threshold) stored against *my* user identity and editable from a dedicated Profile screen**,
so that **my settings follow me regardless of which deployment key was used before — and an operator can only ever read or write their own row, never another user's.**

## Context — why this story exists

E2-S8 shipped `operator_preferences` ([0002_operator_preferences.py](../../cloud-backend/migrations/versions/0002_operator_preferences.py)) with `operator_id` as a **plain `TEXT` primary key**. Before auth existed, the client sent a free-text `operator_id` and the row was effectively keyed by **the shared API-key string** — every "operator" was the same key, so there was never any real per-user preference data.

**11-1 already did half of E11-S3's job.** When 11-1 cut the routers over to JWT, it repointed `preferences.py` to key by `current_user.user_id` ([preferences.py:63,127](../../cloud-backend/src/cloud_backend/routes/preferences.py)) and left a docstring saying *"Existing rows keyed by the old shared API-key string read as 404 → graceful defaults until E11-S3 re-keys/backfills them (Alembic migration). The data migration is E11-S3's job; this story only swaps the identity source."* ([preferences.py:5-9](../../cloud-backend/src/cloud_backend/routes/preferences.py)). So **the identity-source swap the epic describes is already shipped** — the GET/PATCH already use the token's `user_id`. What is **not** done:

1. The **schema is still wrong**: `operator_preferences.operator_id` is a free-floating `TEXT` PK with no relationship to `users`. Nothing stops a stale/garbage key from being inserted, and there is no referential integrity tying a preference row to a real user.
2. The **old rows are dead weight**: any pre-cutover rows are keyed by the defunct API-key string and will never be read again (no token's `user_id` will ever equal that string).
3. There is **no Profile screen** — preferences live in a gear-button modal in the header ([OperatorPreferences.jsx](../../control-centre/src/components/shell/OperatorPreferences.jsx)), not under an authenticated-user profile route.

This story closes all three: a re-key migration (drop the defunct rows, retype/constrain `operator_id` as a real FK to `users`), and a Profile screen route surfacing the existing controls.

## Decisions (locked — review before dev)

> **CREATE-STORY GROUNDING (2026-06-15, Amelia).** The epic text was written before 11-1 shipped. Four facts diverge from the epic and are surfaced here as Decisions rather than silently following the epic (the create-story divergence rule). **D1 and D3 are load-bearing and may warrant a one-line user/pre-flight confirm; D2, D4, D5 are mechanical corrections with an obvious right answer.**

- **D1 — The re-key is a DROP/SEED, not a mapping (epic-endorsed, restated with teeth).**
  The epic already calls this: *"the safe PoC choice is to **drop/seed** preferences against real `user_id`s (there is no real per-user data to preserve — every 'operator' was the same shared key), rather than attempt a fabricated mapping. Document this in the story as a Decision; do not silently migrate."* ([epics.md:2486](../../_bmad-output/planning-artifacts/epics.md)). **Confirmed: the migration DELETEs all pre-existing `operator_preferences` rows** (they are keyed by the dead API-key string; there is no honest mapping from one shared key to N distinct users — any mapping would *invent* per-user data that never existed). New rows are created on-demand by the existing PATCH upsert, now keyed by a real `user_id`. **No data is fabricated.** AC3 pins that the migration does exactly this and nothing more.

- **D2 — Migration number is `0011`, NOT `0010` (epic is stale).**
  The epic names this migration **0010** ([epics.md:2486,2503](../../_bmad-output/planning-artifacts/epics.md)), but **11-2 already shipped `0010_user_audit.py`** ([migrations/versions/0010_user_audit.py](../../cloud-backend/migrations/versions/0010_user_audit.py)). 11-3's migration is **`0011_preferences_rekey_user_id.py`** with `down_revision = "0010"`. (This is the same class of "epic snapshot vs shipped reality" the payload-audit rule guards — caught here for migration numbering.)

- **D3 — How to re-type `operator_id` to a real FK, given the PK type changes (the migration-design decision).**
  Today `operator_id TEXT PRIMARY KEY` ([0002:21](../../cloud-backend/migrations/versions/0002_operator_preferences.py)). Target: `operator_id` is a `UUID` FK → `users.user_id`. The `users.user_id` column is `UUID(as_uuid=False)` ([0009:29](../../cloud-backend/migrations/versions/0009_users.py)). **Because we DROP all existing rows first (D1), the column-type change is unconstrained by data** — the cleanest, lowest-risk shape is:
  1. `DELETE FROM operator_preferences` (drop the defunct rows — D1).
  2. `ALTER COLUMN operator_id TYPE UUID USING operator_id::uuid` — safe *because* the table is now empty (no string→uuid cast of real garbage data can fail).
  3. `ADD CONSTRAINT fk_operator_preferences_user FOREIGN KEY (operator_id) REFERENCES users(user_id) ON DELETE CASCADE`. **`ON DELETE CASCADE`** so deleting a user (11-2 has no hard-delete today, but the FK should be honest) cleans up their preference row; at minimum this prevents an orphan. The PK stays on `operator_id`.
  **Downgrade** drops the FK, `ALTER COLUMN ... TYPE TEXT USING operator_id::text`, restoring the 0002 shape (rows are not restored — they were dropped; downgrade returns the *schema*, consistent with how 0009/0010 downgrades work). **Surface to pre-flight:** if the user prefers a drop-and-recreate-table over an in-place `ALTER`/`DELETE`, that is an alternative — but in-place ALTER on an empty table is more surgical and preserves the two CHECK constraints (`ck_threshold_sec_valid`, `ck_staleness_threshold_sec_valid`) without re-declaring them. **Recommendation: in-place DELETE + ALTER + ADD FK.**
  - **Migration-safety (cloud-backend/CLAUDE.md "Migration safety"):** the only locked table is `operator_preferences` itself (a ~0–few-row PoC table that nothing streams from) — **no lock on `events`/`alerts`** and no concurrent-read hazard on a hot table. The `ALTER COLUMN TYPE` takes an ACCESS EXCLUSIVE lock on `operator_preferences` only, momentarily, on an empty table. Acceptable.

- **D4 — `api_key` / `require_api_key` is NOT fully removed here — the `config:19` comment is stale (11-1 D1 overrode it).**
  `config/__init__.py:17-19` says `api_key` is *"Removed when E11-S3 lands."* That was written by 11-1 **before** 11-1's own Round-1 review carved `POST /api/v1/events` (the machine-to-machine ingest) **back onto `require_api_key`** (11-1 D1: *"unattended machine producer, human JWT wrong model; the ONE documented AC5 exception"*). `require_api_key` is still **live on `routes/ingest.py`** ([routes/ingest.py](../../cloud-backend/src/cloud_backend/routes/ingest.py) imports it). **Decision: do NOT remove `api_key`/`require_api_key`.** This story only removes the *preferences-keying* reason for it (which is now gone). **Action (T5):** correct the two stale comments — `config/__init__.py:17-19` (drop "Removed when E11-S3 lands"; state it stays for the ingest service-token per ADR-23) and `preferences.py:5-9` (the re-key it promised is now done). Removing the service-token entirely is a separate Phase-2 follow-up (proper service identity), not this story.

- **D5 — Profile screen REUSES the existing preference controls; it does NOT rebuild them.**
  `OperatorPreferences.jsx` (the gear-modal, [shell/OperatorPreferences.jsx](../../control-centre/src/components/shell/OperatorPreferences.jsx)) already renders the three `SegmentedControl`s wired to `useFleetData()`'s `updateAlertThreshold`/`updateStalenessThreshold`/`updateUnattendedThreshold`, which already PATCH through the Bearer-authenticated `api/preferences.js`. The Profile screen is a **route** (`/dashboard/profile`) surfacing **the same controls under the authenticated user's identity** (show `username` + `role` from `useAuth()`). **Decision: extract the shared `SegmentedControl` + the three preference rows into a reusable piece both the modal and the Profile route render** (do not duplicate the keyboard-nav logic), OR — if extraction risks regressing the modal's focus-trap — render the existing `OperatorPreferences` body inline on the Profile route. Prefer extraction of just the body; keep the modal's backdrop/focus-trap on the modal only. **Surface at pre-flight only if the user wants the gear-modal removed entirely** (the epic says "Profile screen", not "remove the modal" — keep both unless told otherwise; minimal-functional per the Epic-11 UX plan).
  - **Note — `unattended_threshold_min` is a THIRD preference the backend doesn't persist yet.** The modal has an "Unattended bag alert after" control; FleetContext PATCHes `{unattended_threshold_min}` ([FleetContext.jsx:244](../../control-centre/src/context/FleetContext.jsx)) and reads `prefs.unattended_threshold_min` ([:208](../../control-centre/src/context/FleetContext.jsx)), but **the backend `PreferencesPatch`/`PreferencesOut` models have only `threshold_sec` + `staleness_threshold_sec`** ([preferences.py:35-50](../../cloud-backend/src/cloud_backend/routes/preferences.py)) and the table has no such column. So `unattended_threshold_min` is **client-localStorage-only today** (the PATCH silently ignores the unknown field via Pydantic default-drop; the GET never returns it). **Decision: this story does NOT add `unattended_threshold_min` server persistence** — it is out of E11-S3 scope (the epic lists only "alert threshold, staleness threshold"). The Profile screen may show it (localStorage-backed, as today) but must not claim it persists server-side. Flag it as a known gap, not a regression. Adding it is a clean follow-up (new column + model field).

## Acceptance Criteria

**AC1 — two users have fully independent preferences (the core isolation guarantee)**
Given two distinct logged-in users A (`user_id` U_A) and B (`user_id` U_B), when A `PATCH /api/v1/operators/me/preferences {threshold_sec: 90}` and B `PATCH {threshold_sec: 30}`, then A's `GET` returns `threshold_sec: 90` and B's `GET` returns `threshold_sec: 30` — **A's write never touches B's row and vice versa**. Identity comes **only** from the token's `user_id`; the request body carries no `operator_id` and any client-supplied `operator_id` is ignored (the endpoint has no such body field — Security Test 1).

**AC2 — `operator_preferences` is keyed by a real `user_id` FK; the old TEXT-key shape is gone**
After migration `0011`, `operator_preferences.operator_id` is `UUID` and has a FOREIGN KEY to `users.user_id` (`ON DELETE CASCADE`). Verified by a schema assertion: the column type is `uuid` AND a FK constraint referencing `users(user_id)` exists. A PATCH for a `user_id` that exists in `users` succeeds; the two existing CHECK constraints (`ck_threshold_sec_valid`, `ck_staleness_threshold_sec_valid`) survive the migration (a `threshold_sec=45` PATCH still 422s at the app boundary and the DB CHECK still exists).

**AC3 — migration 0011 applies cleanly + idempotently on a DB containing pre-migration rows; the drop/seed Decision is executed exactly (D1)**
Given a DB at `0010` with at least one pre-migration `operator_preferences` row keyed by an old API-key string (a non-UUID TEXT value), `alembic upgrade head` **DELETEs that row** (D1 — no fabricated mapping), retypes the column, and adds the FK, with NO error from a string→uuid cast (the DELETE precedes the ALTER). The migration is idempotent under the standard downgrade→upgrade re-apply test (mirror 11-1/11-2's strengthened migration test). `down_revision = "0010"`. Downgrade restores the `TEXT` column + drops the FK (rows are not restored — D3).

**AC4 — Profile screen renders, round-trips, and persists across logout/login (browser-verified)**
Given an authenticated session, a Profile screen at `/dashboard/profile` renders loading / error / populated states, shows the user's `username` and `role` (from `useAuth()`), and surfaces the alert-threshold + staleness controls; committing a change PATCHes and the new value is reflected. After logout → login as the same user, the server value is read back (persisted, not just localStorage) — the committed `threshold_sec` survives a fresh session. **Browser-verified** per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) "Verification Requirement": golden path (change a threshold → reload → value persists from server) + one edge (logged-out access blocked OR the PATCH-error toast).

**AC5 — a logged-out user cannot read or write preferences (401)**
Given no token (or an invalid/expired token), `GET` and `PATCH /api/v1/operators/me/preferences` both return `401` (ADR-10 envelope), not a default-filled 200 and not a 500. The Profile route is behind `RequireAuth` (unauthenticated → `/login`), matching the existing dashboard guard.

**AC6 — gates green; no regression to the already-shipped preferences path**
cloud-backend unit + integration (real Postgres, testcontainers) cover AC1–AC3 and AC5 at ≥80%; `ruff` + `mypy --strict` clean on touched `src/`; control-centre `vitest` green for the Profile surface; the existing gear-modal preferences path still works (its tests stay green — D5 must not regress the modal's focus-trap). The full cloud-backend integration suite passes on real Postgres (the migration applies inside the existing Alembic-head fixture without breaking the other modules' `seed_auth_users` path).

## Security Tests (RED-first — write before domain tests, per dev-story DoD)

Write each to fail for the right reason first, then implement:

1. **No client-supplied identity — A cannot write B's row by manipulating the request:** A's token + a body that *attempts* to carry `operator_id: U_B` (or `operator_id` in any form) does NOT write B's row — the field is ignored (not in the model); only `current_user.user_id` keys the upsert. Assert B's row is untouched. (This is AC1's adversarial twin and the epic's named Security Test.)
2. **SQL-safety on the user-id key path:** the `user_id` flows into the parametrized query as a bound param (`:oid`), never string-formatted. A `user_id`-shaped value with SQL metacharacters cannot escape the bind (the column is UUID-typed post-migration, so a non-UUID `sub` 422s/401s before it reaches SQL — pin that a junk `sub` claim does not reach an unparametrized path). Confirm the existing `text(...)` calls keep `:oid` binding.
3. **Logged-out / invalid-token → 401 on both verbs (AC5):** no token, expired token, tampered token → 401 on GET and PATCH — never 200-with-defaults, never 500.

## Integration test (A1 hard gate + A3 real-path seeding)

**`test_preferences_isolation_two_users`** (testcontainers real Postgres) — MUST run and pass before the story flips to `review` ("deferred to CI" is not acceptable; `docker info` to confirm, start it if down). This is the E10-A1 gate.

**A3 — seed via the REAL path:** create two users through the **real `create_user` flow** (the same bcrypt/insert the app uses — reuse 11-2's `create_user`, NOT a raw INSERT of a hand-computed hash), mint a Bearer for each via the real `create_access_token`, then drive **A PATCH 90 → B PATCH 30 → A GET == 90 → B GET == 30 → assert exactly two rows, each FK-valid to its user**. The two users must be real `users` rows so the new FK is satisfied (a raw-insert preference row with a random UUID would now violate the FK — which is itself a useful negative test: `test_preference_fk_rejects_unknown_user`).

Plus **`test_rekey_migration_drops_defunct_rows`** (AC3 — seed a `0010`-era row with a non-UUID TEXT `operator_id`, run `upgrade head`, assert it's gone and the column is UUID+FK) and the **`0010→0011` downgrade→upgrade re-apply test** (AC3 idempotency). Mirror the testcontainers fixture shape across `cloud-backend/tests/integration/` and the `seed_auth_users` idiom in [tests/integration/conftest.py:42](../../cloud-backend/tests/integration/conftest.py).

> **Note the pre-existing integration-test isolation flaky** documented in 11-1/11-2's reviews: `test_ai_quality_rates.py` intermittently fails under multi-module ordering due to `DATABASE_URL`-leaking `pg_url` fixtures — **confirmed not introduced by Epic 11** (task_c97431d4). If it surfaces, do NOT chase it here; verify the 11-3 tests are deterministically green in isolation and note it.

## Tasks / Subtasks

- [ ] **T1 — Alembic `0011_preferences_rekey_user_id`** (AC2, AC3, D1, D2, D3) — new migration `down_revision="0010"`. `upgrade()`: `DELETE FROM operator_preferences` (D1) → `ALTER COLUMN operator_id TYPE UUID USING operator_id::uuid` → `ADD CONSTRAINT fk_operator_preferences_user FOREIGN KEY (operator_id) REFERENCES users(user_id) ON DELETE CASCADE`; preserve the two CHECK constraints (in-place ALTER keeps them — D3). `downgrade()`: drop FK → `ALTER COLUMN operator_id TYPE TEXT USING operator_id::text` (rows not restored). **RED first:** `test_rekey_migration_drops_defunct_rows` + the downgrade→upgrade re-apply test (mirror 11-2's 0010 test).
- [ ] **T2 — Confirm/keep `preferences.py` correct; add the FK-aware negative path** (AC1, AC2, AC5, Security Tests) — `preferences.py` already keys by `current_user.user_id` and binds `:oid` (verify, do NOT rewrite). Confirm a non-UUID/garbage `sub` cannot reach an unparametrized path (Security Test 2) and that GET/PATCH 401 without a token (AC5 — already enforced by the router's `Security(get_current_user)`; pin it). No new endpoint (epic: "key-source swap, not a new endpoint").
- [ ] **T3 — Frontend Profile screen** (AC4, D5) — `src/components/profile/Profile.jsx` (+CSS, `--obb-*` only) at route `/dashboard/profile` behind `RequireAuth`; show `username`/`role` from `useAuth()`; surface the alert-threshold + staleness controls by **extracting the shared `SegmentedControl` + preference-row body** from `OperatorPreferences.jsx` into a reusable component both the modal and Profile render (D5 — do not duplicate keyboard-nav). Add a `/dashboard/profile` `<Route>` in [App.jsx](../../control-centre/src/App.jsx) (mirror the `users` route shape) + a nav entry in [AppShell.jsx](../../control-centre/src/components/shell/AppShell.jsx) (visible to all authenticated users — not admin-gated). vitest for the Profile component states + the extracted control.
- [ ] **T4 — Integration tests + browser verify** (A1 gate, AC4) — `test_preferences_isolation_two_users` (A3 real-seed two users via `create_user`), `test_preference_fk_rejects_unknown_user`, `test_rekey_migration_drops_defunct_rows`, the migration re-apply test — all green on real Postgres (Docker up, run locally). Browser-verify the Profile golden path (change → reload → persists from server) + one edge per AC4. Confirm `ruff`/`mypy --strict`/coverage gates + the gear-modal preferences tests stay green (AC6, D5).
- [ ] **T5 — Docs + stale-comment correction** (D4) — correct `config/__init__.py:17-19` (`api_key` stays for the `POST /api/v1/events` service-token per ADR-23/11-1 D1 — drop "Removed when E11-S3 lands") and `preferences.py:5-9` (the re-key it promised is now done — point at 0011). One-line note in `cloud-backend/CLAUDE.md` recording that `operator_preferences` is now FK'd to `users` (0011) and the drop/seed re-key Decision. **ADR FRESHNESS:** no ADR is contradicted (ADR-23 already anticipated the FK — [0009 docstring:12](../../cloud-backend/migrations/versions/0009_users.py) says *"from E11-S3, the operator_preferences FK"*); confirm no ADR edit needed and record that confirmation.

## Dev Notes

### Architecture patterns & constraints

- **ADR-8:** every route under `/api/v1/`. **ADR-10:** error envelope `{"error","detail","recoverable"}` for 401/422. **ADR-23 (11-1):** the verify seam — `_verify_token` stays pure; the liveness check lives in the extractor. This story adds no auth logic; it inherits both extractors unchanged (preferences is already behind `Security(get_current_user)`).
- **cloud-backend/CLAUDE.md "Migration safety":** every Alembic migration must be safe under concurrent reads — no full-table lock on `events`/`alerts`. 0011 only locks the empty `operator_preferences` table (D3) — compliant.
- **cloud-backend/CLAUDE.md "Review Failure Scenarios":** the migration must be safe; the preferences path must not 500 on a missing row (it 404s → client defaults — preserve that, it's the AC).

### Files being modified (UPDATE) — current state / change / preserve

Per the FULL-FILE-READS rule, each was read completely. Verified current state:

- **[routes/preferences.py](../../cloud-backend/src/cloud_backend/routes/preferences.py)** (146 lines) — *current:* GET (404→client-defaults) + PATCH (upsert) BOTH already key by `current_user.user_id` and bind `:oid`; router is `Security(get_current_user)`; `PreferencesOut`/`PreferencesPatch` have only `threshold_sec` + `staleness_threshold_sec`. *change:* essentially NONE to logic (11-1 already swapped identity) — verify-only, plus fix the stale docstring (T5). *preserve:* the 404→defaults contract (it's an AC of E2-S8 and the frontend relies on it — `api/preferences.js:34` maps 404→defaults), the `:oid` binding, the two threshold validators.
- **[config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py)** (60 lines) — *current:* `api_key` field with a comment claiming E11-S3 removes it. *change:* correct the comment only (D4/T5) — `api_key` STAYS (ingest service-token). *preserve:* the field itself, `require_api_key` importability, the bcrypt floor validator.
- **[migrations/versions/0002_operator_preferences.py](../../cloud-backend/migrations/versions/0002_operator_preferences.py)** — *reference only* (the table shape 0011 re-keys; do NOT edit a shipped migration). 0011 is a NEW file.
- **[control-centre/src/components/shell/OperatorPreferences.jsx](../../control-centre/src/components/shell/OperatorPreferences.jsx)** (188 lines) — *current:* gear-modal with `SegmentedControl` + 3 preference rows wired to `useFleetData()`; focus-trap + Escape-close on the modal. *change:* extract the shared control + preference-row body so Profile reuses it (D5). *preserve:* the modal's backdrop/focus-trap/Escape behavior (keep on the modal); the existing `useFleetData()` wiring; the keyboard-nav semantics of `SegmentedControl`.
- **[control-centre/src/App.jsx](../../control-centre/src/App.jsx)** (55 lines) — *current:* `RequireAuth` + `RequireAdmin` guards; `/dashboard/*` child routes incl. admin-gated `users`. *change:* add a `/dashboard/profile` route behind `RequireAuth` (NOT `RequireAdmin` — every user has a profile). *preserve:* the existing guard/redirect behavior and route order.
- **[control-centre/src/components/shell/AppShell.jsx](../../control-centre/src/components/shell/AppShell.jsx)** — *current:* nav tabs + admin-gated Users tab + the gear button that opens the prefs modal. *change:* add a Profile nav entry (all authenticated users). *preserve:* the gear-button modal trigger (D5 — keep both) and the admin-gating of Users.

### Re-key migration shape (D3 — the load-bearing piece)

```
# 0011_preferences_rekey_user_id.py  (down_revision = "0010")
def upgrade():
    op.execute("DELETE FROM operator_preferences")            # D1 — defunct API-key-keyed rows
    op.alter_column("operator_preferences", "operator_id",
        type_=postgresql.UUID(as_uuid=False),
        postgresql_using="operator_id::uuid")                 # safe: table empty
    op.create_foreign_key(
        "fk_operator_preferences_user", "operator_preferences",
        "users", ["operator_id"], ["user_id"], ondelete="CASCADE")
def downgrade():
    op.drop_constraint("fk_operator_preferences_user", "operator_preferences", type_="foreignkey")
    op.alter_column("operator_preferences", "operator_id",
        type_=sa.Text(), postgresql_using="operator_id::text")
```

Mirror 11-2's 0010 migration test (real downgrade→upgrade re-apply + schema asserts). The `users.user_id` referenced column is `UUID(as_uuid=False)` ([0009:29](../../cloud-backend/migrations/versions/0009_users.py)) — match it exactly so the FK types align.

### CSS tokens (Profile.jsx)

Use only `--obb-*` from [control-centre/src/styles/colors_and_type.css](../../control-centre/src/styles/colors_and_type.css). Verified-present tokens: surfaces `--obb-surface-0..5`; text `--obb-text-on-dark-1..4`; borders `--obb-border-dark`/`--obb-border-bright`; accent `--obb-blue-accent`. Severity ramp (if a save-error/confirm cue is needed): `--obb-sev-critical` (red, #FF3B3B), `--obb-sev-high` (orange), `--obb-sev-medium` (amber), `--obb-sev-advisory` (blue), `--obb-sev-normal` (green). **`--obb-sev-warning` does NOT exist (use `--obb-sev-medium`); `--obb-sev-danger` does NOT exist (use `--obb-sev-critical`).** Reuse `OperatorPreferences.css` patterns for the extracted control rather than inventing new token usage.

### UX ownership (Freya)

The Profile screen is a **new UX surface**. Per the epic's UX-pass plan ([epics.md:2558](../../_bmad-output/planning-artifacts/epics.md)), each E11 story ships a **minimal functional** UI (theme-correct, browser-verified); Freya runs ONE coherent WDS pass over the whole admin/identity shell (login + Users + **Profile** + Alert-Classes + Configuration) at epic close. Do NOT over-design Profile in isolation now — username/role header + the two reused preference controls satisfies AC4; Freya reviews in the browser-verify step.

### Testing standards

- Markers: `@pytest.mark.unit` (no DB) / `@pytest.mark.integration` (testcontainers Postgres). Coverage ≥80%; the isolation + FK paths near-complete.
- `mypy --strict` + `ruff` clean on touched `src/`.
- CC: `vitest` for `src/components/profile/Profile.jsx` states + the extracted control; the existing `OperatorPreferences` tests must stay green (D5 extraction must not regress the modal).
- Mirror 11-1/11-2's strengthened migration test (real downgrade→upgrade, schema assertions) for 0011.

### Previous-story intelligence (11-1, 11-2)

- **11-1** shipped the JWT seam + cut `preferences.py` over to `current_user.user_id` (so this story's "identity swap" is done) and carved `POST /api/v1/events` back to `require_api_key` (D4 — `api_key` survives).
- **11-2** shipped `0010_user_audit`, the liveness extractors, and `tests/integration/conftest.py::seed_auth_users` + `auth_header()` with fixed-UUID synthetic users — **reuse these for the isolation test's two real users** (or create two fresh users via `create_user` per A3; the fixed synthetic UUIDs are operator/admin — for a two-*operator* isolation test, create two real users via the real path so both satisfy the new FK). The liveness check means any token's `sub` must exist + be active in `users`; the new FK reinforces that for preferences.
- **11-2 lesson:** adding a DB dependency rippled across many tests. This story adds **no new auth dependency** (preferences already depends on `get_current_user`/`get_db`), so no comparable ripple — but the **new FK** means any integration test that raw-inserts an `operator_preferences` row with an unknown `operator_id` will now fail. That's intended (the FK is the point); fix such tests to seed a real user first (A3).

### Project Structure Notes

- Backend: `migrations/versions/0011_*.py` (new), `routes/preferences.py` (verify + comment fix only), `config/__init__.py` (comment fix) — matches cloud-backend/CLAUDE.md.
- Frontend: `src/components/profile/Profile.jsx` + `.css` — `profile/` is a NEW component dir (current dirs: admin, alerts, analytics, auth, escalations, health, live, luggage, occupancy, shell, train-detail). Follows `src/components/<feature>/`. The extracted control lands under `shell/` (alongside `OperatorPreferences.jsx`) or a small shared location — keep it next to its current home to minimise churn.

### References

- [Source: epics.md#Epic-11 → E11-S3](../../_bmad-output/planning-artifacts/epics.md) — locked scope/ACs/deliverables (note 0010→0011 + identity-swap-already-done divergences, D1/D2).
- [Source: 11-1-jwt-auth-foundation-login.md](11-1-jwt-auth-foundation-login.md) — JWT foundation; the preferences identity-swap + the ingest `require_api_key` carve-back (D4).
- [Source: 11-2-user-management.md](11-2-user-management.md) — `create_user` (A3 seed), `seed_auth_users`/`auth_header` integration fixtures, the 0010 migration-test shape to mirror.
- [Source: routes/preferences.py](../../cloud-backend/src/cloud_backend/routes/preferences.py) — already keyed by `current_user.user_id`; the 404→defaults contract to preserve.
- [Source: migrations/versions/0002_operator_preferences.py](../../cloud-backend/migrations/versions/0002_operator_preferences.py) — the TEXT-keyed table 0011 re-keys.
- [Source: migrations/versions/0009_users.py](../../cloud-backend/migrations/versions/0009_users.py) — `users.user_id` (UUID, FK target); docstring already names the E11-S3 FK.
- [Source: control-centre/src/components/shell/OperatorPreferences.jsx](../../control-centre/src/components/shell/OperatorPreferences.jsx) — the controls Profile reuses (D5).
- [Source: control-centre/src/context/FleetContext.jsx](../../control-centre/src/context/FleetContext.jsx) — the prefs GET/PATCH wiring + the `unattended_threshold_min` localStorage-only gap (D5 note).

### Permission tier & review tier

- **Permission tier: Tier 3** — DB migration on EXISTING data (`operator_preferences`). **Default permission mode** (project CLAUDE.md: Tier 3 on shared infra — migrations — always default mode regardless of session mode). **Sign-off required in-story before T1.**
- **Review tier: FULL adversarial wire-replay** (A2 — migration on existing data). Code-review must replay the real two-user isolation wire (real `create_user` → real Bearer → cross-user PATCH/GET, NOT synthetic kwargs), adversarially probe the body-supplied-`operator_id` bypass (Security Test 1), and verify the 0011 migration on a DB seeded with a defunct non-UUID row (AC3) — not just an empty-table apply.

## Per-story Failure Scenarios (system-understanding required)

1. **Cross-user preference write via a forged body field (AC1/Security Test 1):** the endpoint takes identity from the token, but a careless refactor that re-introduces an `operator_id` body field (or trusts a header) would let operator A overwrite operator B's threshold by sending B's `user_id`. The review must confirm identity flows **only** from `current_user.user_id` into `:oid`, with no client-supplied path — replaying the real two-user wire, not a single-user happy path.
2. **Re-key migration string→uuid cast failure on real defunct data (AC3/D1):** the table today holds rows keyed by the API-key string (a non-UUID TEXT). If the migration ALTERs the column type *before* deleting those rows, `operator_id::uuid` throws (`invalid input syntax for type uuid`) and the migration fails mid-flight — possibly leaving the table in a half-migrated state on a partial transaction. The DELETE must precede the ALTER (D3); the test must seed a genuine non-UUID row and prove the upgrade succeeds, not run against an empty table that hides the ordering bug.

## Open Questions — for dev pre-flight (none blocking)

1. **D3 migration shape:** in-place `DELETE + ALTER + ADD FK` (recommended) vs drop-and-recreate-table. Recommendation stands unless the user prefers the recreate.
2. **D5 modal vs route:** keep the gear-modal AND add the Profile route (recommended — epic says "Profile screen", not "remove modal"), vs move preferences entirely to Profile and drop the gear modal. Confirm if the user wants the modal retired.
3. **D5 `unattended_threshold_min`:** confirmed OUT of scope for server persistence here (epic lists only alert + staleness). Flag if the user wants it added (clean follow-up: new column + model field).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia)

### Debug Log References

### Completion Notes List

### File List

## Change Log

| # | Change | Rationale |
|---|---|---|
| 1 | create-story grounded the epic against 11-1's shipped reality | Epic was authored pre-11-1. Surfaced 5 Decisions: D1 drop/seed re-key (epic-endorsed); D2 migration is 0011 not 0010 (0010=user_audit, shipped by 11-2); D3 in-place DELETE+ALTER+ADD-FK shape (DELETE before ALTER so string→uuid cast can't fail); D4 `api_key`/`require_api_key` STAYS (11-1 carved ingest back to it — `config:19` "Removed when E11-S3 lands" is stale); D5 Profile reuses the existing gear-modal controls (no rebuild) + `unattended_threshold_min` is localStorage-only and out of scope. Identity-source swap already done by 11-1 → this story is migration + FK + Profile screen, materially lighter than the epic implied. |
