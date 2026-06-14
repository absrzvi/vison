---
baseline_commit: 4384535
---

# Story 11.1: JWT Auth Foundation + Login Flow

Status: ready-for-dev

<!-- Created 2026-06-14 via bmad-create-story (Amelia). First story of Epic 11 (Control Centre Admin & Identity).
     Source: _bmad-output/planning-artifacts/epics.md §"Epic 11" → "E11-S1 — JWT auth foundation + login flow".
     Epic breakdown (commit 4384535) verified the auth seam against live code first (epic-10-retro prerequisite).
     This story's shape is LOCKED by the breakdown — create-story added the grounding the breakdown deferred
     (the staged-cutover pre-flight against main.py) but did not re-scope.
     Review tier (A2): FULL adversarial wire-replay — auth + migration. Permission tier: Tier 3. -->

## Story

As **the cloud-backend (serving Control Centre operators and admins)**,
I want **to issue and verify my own JWTs against a local credential store, with role-claim-based authorization behind a single `get_current_user` dependency**,
so that **every protected route knows *who* is calling and with *what role*, operator actions become real-identity-attributable (replacing the shared `X-API-Key` and the `VITE_OPERATOR_ID` approximation), and an external IdP can be swapped in later without touching those routes**.

## Context — why this story exists

Today the cloud-backend has **no user identity**. Authentication is two flat shared-key schemes:
- `require_api_key` ([cloud-backend/src/cloud_backend/api/auth.py:11](../../cloud-backend/src/cloud_backend/api/auth.py)) — one shared `X-API-Key` matched against `Settings.api_key`, on **14 routers**.
- `require_admin_key` ([admin_alert_classes.py:32](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)) — `X-Admin-Key` against `Settings.cc_admin_key`, fail-closed via `secrets.compare_digest`, on the kill-switch router (the E11-S4 swap point, **not** this story).

`operator_id` is a free-text body field the client sends ([control-centre/src/api/escalations.js:48](../../control-centre/src/api/escalations.js)); the server never verifies it. `operator_preferences` rows are keyed by the **API-key string itself** ([preferences.py:60](../../cloud-backend/src/cloud_backend/routes/preferences.py): `WHERE operator_id = :oid`, `:oid = api_key`) — the re-key migration is E11-S3, not here.

**ADR-7** ([architecture.md:568](../../_bmad-output/planning-artifacts/architecture.md)) already mandates the upgrade path this story begins: *"OAuth2/OIDC with ÖBB identity provider at fleet rollout. Architecture must not assume API key is permanent — no hardcoded key logic in business layer."* **ADR-22's GDPR note** ([architecture.md:712](../../_bmad-output/planning-artifacts/architecture.md)) and **10-6's D6** ([10-6-escalation-lifecycle-persistence.md:68](10-6-escalation-lifecycle-persistence.md)) both explicitly defer real operator identity to "Epic 11 (JWT)" — **this story is that promised replacement.**

The `cloud-backend/CLAUDE.md` "Auth" section *already describes* `get_current_user`/JWT/role-in-route — but it **does not exist in code** (grep: zero matches). That description is **aspirational**; this story makes it real and the doc honest (AC8).

**Decision (PoC, locked by the breakdown): self-contained JWT.** cloud-backend issues + verifies its own HS256 tokens against a local `users` table (passlib/bcrypt). **No external IdP.** Keycloak / ÖBB-OIDC SSO is Phase 2, out of scope. The cost of deferring SSO is contained **only if** token *verification* is decoupled from *issuance* — that decoupling is **AC4**, the load-bearing seam contract.

## Decisions (locked — review before dev)

- **D1 — ADRs live in `architecture.md`, not separate files.** The breakdown's deliverable path `_bmad-output/architecture-artifacts/ADR-23-...md` was a guess and is **WRONG**. ADRs are `#### ADR-NN` sections inside [architecture.md](../../_bmad-output/planning-artifacts/architecture.md); the current head is **ADR-22** ([architecture.md:701](../../_bmad-output/planning-artifacts/architecture.md)). **ADR-23 is authored as a new section in `architecture.md`** (T7). Per the ADR-FRESHNESS rule, also update **ADR-7** (add "E11-S1 realizes the OIDC upgrade path's first half — self-contained JWT; see ADR-23") and **ADR-22's line 712 note** ("Epic 11 replaces with JWT identity" → "replaced by JWT identity in E11-S1, see ADR-23").

- **D2 — Staged cutover is 15 per-file edits, not one switch in `main.py` (PRE-FLIGHT VERIFIED).** [main.py](../../cloud-backend/src/cloud_backend/main.py) mounts routers with bare `app.include_router(...)`; the auth dependency is attached **inside each router file** as `APIRouter(..., dependencies=[Security(require_api_key)])`. There is **no central auth middleware to flip.** So the AC5 cutover edits **14 router files + 1 per-route decorator** ([health.py:77](../../cloud-backend/src/cloud_backend/routes/health.py) attaches auth on the `/api/v1/health` route directly). This is surgical but spread out — the AC5 parametrized integration test is what proves none was missed. **Decision: accept the per-file cutover** (matching the shipped pattern) rather than refactor to central middleware in this story (that refactor would be a larger, riskier change touching every router's signature — out of scope; note as a possible Epic-9 hardening item).

- **D3 — Infra health probes stay OPEN.** [health.py](../../cloud-backend/src/cloud_backend/routes/health.py) has `/health/live` and `/health/ready` (k8s / load-balancer probes, **unauthenticated by design** — see [health.py:82-83](../../cloud-backend/src/cloud_backend/routes/health.py) comment) **and** the auth-gated `/api/v1/health` summary ([health.py:77](../../cloud-backend/src/cloud_backend/routes/health.py)). The cutover **must auth-gate `/api/v1/health` only** and leave the two infra probes open. AC5's parametrized test must assert the probes still return 200 **without** a token (negative coverage — proving we didn't over-gate).

- **D4 — `require_api_key` stays alive in parallel through the cutover, then is removed at the END of this story.** Sequencing within the story: ship the JWT machinery + login + frontend FIRST (so a working token exists), THEN cut the 14 routers over in one reviewed pass (T6). At no point is a protected surface left unauthenticated. After cutover, `require_api_key` and `Settings.api_key` are dead for routing — but **do NOT delete `Settings.api_key` yet**: `require_admin_key`/`cc_admin_key` is a separate scheme removed in E11-S4, and `operator_preferences` is still api-key-keyed until E11-S3. Leave `api_key` in `Settings` with a `# DEAD after E11-S1 cutover; removed when E11-S3 re-keys preferences` comment. **Mention as cleanup, do not delete** (Karpathy surgical rule).

- **D5 — HS256 symmetric secret for PoC; seam is RS256/JWKS-ready.** `jwt_algorithm` defaults `HS256` with a symmetric `jwt_secret`. The verification code path reads algorithm + key from config so an RS256 public key / JWKS URL drops in without touching `get_current_user`'s callers. AC4 is the assertion that this holds. Do **not** build JWKS fetching now (speculative — Phase 2); just don't hardcode `HS256`/the secret into the verify call.

- **D6 — No refresh tokens for PoC.** Single short-TTL access token (`jwt_access_ttl_minutes`, default 60). On expiry the frontend redirects to `/login` (AC6). Refresh-token rotation is explicitly out of scope (epic "Out of scope"). Keep `exp` enforcement strict.

- **D7 — `sub` claim = `user_id` (uuid), not username.** Username can change; `user_id` is the stable identity used for `operator_preferences` FK (E11-S3) and audit attribution. `get_current_user` loads `{user_id (from sub), username, role}` — username/role come from claims, no DB hit required on every request for the PoC (the token is the source of truth for the request). **Exception:** AC re E11-S2 `is_active` mid-session revocation is **NOT** in this story — S1 trusts a validly-signed unexpired token; the active-check-on-verify is an **E11-S2** AC. Note this boundary so the dev doesn't gold-plate.

- **D8 — live-stream auth: token cannot ride an HTTP header (LOAD-BEARING — verified against live client).** The Control Centre's live transport is a **raw browser `WebSocket` to `/ws`** ([RealWebSocketClient.js:1-11](../../control-centre/src/ws/RealWebSocketClient.js)), NOT EventSource — and the backend also exposes an SSE route `/api/v1/alerts/stream` ([alerts_sse.py](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py), ADR-20). **Neither browser `WebSocket` nor `EventSource` can set an `Authorization` header.** So the `X-API-Key`→`Bearer` swap (AC6) does **not** mechanically apply to the live stream — gating it on `get_current_user` (which reads the `Authorization` header) would **break the live alert feed**, the dashboard's core function (regression-disaster). **Decision:** the live-stream token rides in the **first-message subscription handshake** — the client already sends `SUBSCRIPTION_REQUEST` as the first WS message ([RealWebSocketClient.js:13-27](../../control-centre/src/ws/RealWebSocketClient.js)); add the token to it, and the `/ws` handler validates it via a **`get_current_user`-equivalent that accepts the token from the handshake payload instead of the header** (same verification core, different extraction — preserves the AC4 seam: one verify function, two extractors). For the SSE route, use a `?token=` query param validated by the same core. **Do NOT pass the token in the URL of the WS unless the handshake path is infeasible** (URL tokens leak to logs). **Flag to the user if the `/ws` handler's current auth (confirm whether `/ws` is even `require_api_key`-gated today — it is NOT in the 14-router list) needs its own cutover task.** This Decision converts the buried Dev-Note risk into an explicit, testable path.

## Acceptance Criteria

**AC1 — login issues a signed JWT; bad creds 401**
Given a `users` row with a bcrypt-hashed password, when `POST /api/v1/auth/login` is called with `{"username","password"}` matching, then a `200` returns `{"access_token","token_type":"bearer"}` where the JWT carries claims `sub` (= `user_id`), `role`, `iss` (= `jwt_issuer`), `exp`. Invalid username OR wrong password returns `401` with the ADR-10 envelope `{"error":"UNAUTHORIZED","detail":"...","recoverable":false}` and **no token**. The 401 body and timing must be **identical** for unknown-user vs wrong-password (no user-enumeration — see Security Tests).

**AC2 — `get_current_user` resolves a valid token; rejects bad tokens 401, never 500**
Given a protected route depending on `get_current_user`, when called with `Authorization: Bearer <valid token>`, then the dependency resolves to `CurrentUser{user_id, username, role}` and the route runs. When called with a **missing**, **malformed**, **expired**, **tampered-signature**, or **wrong-issuer** token, the response is `401` with the ADR-10 envelope — **never 500** (mirrors the JWT-edge-case scenario in [cloud-backend/CLAUDE.md](../../cloud-backend/CLAUDE.md) "Review Failure Scenarios").

**AC3 — `require_role` enforces role**
Given `require_role("admin")` on a route, when called with a valid `operator` token → `403` (ADR-10 envelope); with a valid `admin` token → `200`. `require_role` is a dependency factory composing on top of `get_current_user` (role read from the claim, not re-fetched).

**AC4 — seam contract: verification decoupled from issuance (OIDC-swap guarantee)**
Given the auth module, then: (a) token **verification** is isolated in `get_current_user`; (b) `jwt_issuer`, `jwt_algorithm`, and the signing/verifying key are read from `Settings`, **not** hardcoded at the call site; (c) a documented test (`test_seam_oidc_swap`) demonstrates that pointing verification at a **second issuer/algorithm** (e.g. a different `iss` + key via settings override) verifies a token minted by that issuer **without editing any of the 14 protected routers or their route functions**. Violation of (a)–(c) is an **AC FAIL**. (This is the guarantee that Keycloak/ÖBB-OIDC is a contained Phase-2 swap, not a rewrite.)

**AC5 — every protected surface requires a token after cutover; infra probes + login stay open**
Given the protected surfaces previously behind `require_api_key` (see Dev Notes for the exact inventory — **15 routers + the `/api/v1/health` per-route gate; note `capacity_review` is TWO routers**), when each is called with **no token** or an **invalid token**, then `401` — proven by a **single parametrized integration test** (`test_all_protected_routes_require_token`) enumerating every protected prefix. The same test asserts the **open** surfaces return non-401 **without** a token (D3): `/health/live`, `/health/ready`, and `POST /api/v1/auth/login` (the login endpoint MUST stay unauthenticated — chicken-and-egg; gating it would make login impossible). After cutover, **no router still references `require_api_key`** for routing (grep assertion). The live `/ws` stream auth is handled separately per **D8** (handshake token), not by this header-based gate.

**AC6 — frontend login + token store + 401 interceptor**
Given the Control Centre SPA, when an unauthenticated user loads any route, they are redirected to `/login`. When they submit valid creds, the token is stored (in-memory + `sessionStorage`), the `Authorization: Bearer <token>` header is sent on all API calls (replacing the `VITE_API_KEY` `X-API-Key` header — see the 25 `src/api/*.js` files in Dev Notes), and they land on the dashboard. When **any** API call returns `401`, the token is cleared and the user is redirected to `/login`. Logout clears the token and returns to `/login`. **Browser-verified** per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) "Verification Requirement" — golden path + at least one edge state (bad creds error, expired-token→redirect).

**AC7 — fail-closed on unset secret**
Given `jwt_secret` empty/unset, then login cannot mint a usable token AND no token verifies (every protected route 401s) — the same fail-closed posture as `cc_admin_key` ([admin_alert_classes.py:34-35](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)). No token is ever accepted under an empty secret (no `alg:none` bypass — see Security Tests).

**AC8 — ADR-23 authored; CLAUDE.md corrected; ADR-7/ADR-22 updated**
Given this story lands, then: ADR-23 (self-contained JWT for PoC + the verification-seam contract + OIDC/Keycloak Phase-2 swap-in) exists as a `#### ADR-23` section in [architecture.md](../../_bmad-output/planning-artifacts/architecture.md); ADR-7 and ADR-22's line-712 note are updated to point at it (D1); the `cloud-backend/CLAUDE.md` "Auth" section describes the now-real `get_current_user`/`require_role`/login flow (no longer aspirational).

**AC9 — migration safe + idempotent; gates green**
Given migration `0009_users.py`, then it is a new-table-only migration (safe under concurrent reads, no full-table locks), `down_revision = "0008"`, and `test_upgrade_head_idempotent` passes (applying `upgrade head` twice does not raise). `cloud-backend` unit + integration tests cover AC1–AC5/AC7 at ≥80% coverage; `ruff` + `mypy --strict` clean on touched `src/` files; CC `vitest` green for the new auth/login surface and the `X-API-Key`→`Bearer` swap.

## Security Tests (RED-first — write these before domain tests, per dev-story DoD)

Write each to fail for the right reason first, then implement:

1. **Expired token → 401** (not 500): mint a token with `exp` in the past; assert 401 + ADR-10 envelope.
2. **Tampered signature → 401**: take a valid token, mutate one signature byte; assert 401.
3. **`alg:none` / algorithm-confusion → 401**: craft a token with `{"alg":"none"}` and no signature; assert 401 (PyJWT must be called with an explicit `algorithms=[settings.jwt_algorithm]` allow-list — never accept `none`, never let an HS-signed token verify against an RS public key or vice-versa).
4. **Wrong-issuer token → 401**: mint with a different `iss`; assert 401 (verify must enforce `issuer=settings.jwt_issuer`).
5. **Operator token on admin route → 403** (not 401, not 500): valid `operator` token on a `require_role("admin")` route.
6. **Missing role claim → 401/403, not 500**: token with no `role` claim must be rejected cleanly, not crash `require_role`.
7. **Login brute-force / user-enumeration → uniform 401**: unknown username and wrong-password-for-known-user return byte-identical bodies; assert no timing oracle (bcrypt-verify a dummy hash even on unknown user so the code path duration doesn't leak existence).
8. **Empty `jwt_secret` fails closed** (AC7): with secret unset, a previously-valid token does not verify AND login yields no usable token.

## Integration test (A1 hard gate + A3 real-producer seeding)

**`test_auth_flow_end_to_end`** (testcontainers real Postgres) — MUST run and pass before the story flips to `review`. "Deferred to CI" is **not acceptable** (Docker runs locally; `docker info` to confirm, start it if down). This is the E10-A1 gate; auth is the canonical test/prod-divergence risk (epic-10-retro §Key Insights: *"An auth regression that only shows against a real token store is precisely the test/prod-divergence species this epic was burned by"*).

**A3 — seed via the REAL path:** the test user MUST be created through the **actual user-creation code path** (the same hashing function the app uses — call the real `create_user`/bcrypt helper, or hit a real creation entry point), **NOT** a raw `INSERT` of a hand-computed hash. A test that raw-inserts a hash can pass while the real hashing/verify pairing is broken (the 10-5 `_seed_parent` / 10-4 real-`update_pis` lesson). Then drive end-to-end: **create user (real hash) → `POST /auth/login` → get Bearer → call a protected route 200 → tamper the token → 401**. Mirror the established integration-test shape (testcontainers fixture used across `cloud-backend/tests/integration/`).

`test_all_protected_routes_require_token` (AC5) and `test_seam_oidc_swap` (AC4) are also integration-tier and run under the same gate.

## Tasks / Subtasks

- [ ] **T1 — Dependencies + Settings** (AC1, AC4, AC7, D5, D6)
  - [ ] Add `pyjwt` and `passlib[bcrypt]` to `cloud-backend/pyproject.toml` (pin versions; verify latest stable via Context7 before pinning — see Dev Notes "Latest tech").
  - [ ] Add to `Settings` ([config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py)): `jwt_secret: str = ""` (env `JWT_SECRET`, fail-closed empty default — comment it like `cc_admin_key`), `jwt_issuer: str = "oebb-cloud-backend"`, `jwt_algorithm: str = "HS256"`, `jwt_access_ttl_minutes: int = 60`. Add all four to `.env.example` if one exists for this package.
- [ ] **T2 — Alembic 0009 users table** (AC9, D7)
  - [ ] `cloud-backend/migrations/versions/0009_users.py`, `revision="0009"`, `down_revision="0008"` (current head — [0008_escalation_seconds_to_departure.py](../../cloud-backend/migrations/versions/0008_escalation_seconds_to_departure.py)). Mirror the [0006_escalations.py](../../cloud-backend/migrations/versions/0006_escalations.py) shape.
  - [ ] Columns: `user_id` (`UUID(as_uuid=False)`, PK), `username` (Text, unique, NOT NULL), `password_hash` (Text, NOT NULL), `role` (Text, NOT NULL, `CheckConstraint("role IN ('admin','operator')", name="ck_users_role_valid")`), `is_active` (Boolean, NOT NULL, server_default `true`), `created_at`/`updated_at` (TIMESTAMPTZ, NOT NULL, server_default `now()`). Unique index on `username`.
  - [ ] New-table-only (safe under concurrent reads). `test_upgrade_head_idempotent` must still pass.
- [ ] **T3 — auth module: verification seam + token mint** (AC1–AC4, AC7, D5, D7)
  - [ ] Extend [api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py): `CurrentUser` pydantic model `{user_id, username, role}`; `hash_password`/`verify_password` (passlib bcrypt); `create_access_token(user) -> str` (claims `sub`,`role`,`iss`,`exp`); `get_current_user(creds = Security(HTTPBearer(auto_error=False))) -> CurrentUser` (decode with explicit `algorithms=[settings.jwt_algorithm]`, `issuer=settings.jwt_issuer`, `options={"require":["exp","sub","role"]}` → 401 on any `PyJWTError`/missing claim, **never 500**); `require_role(*roles)` factory → 403 on role mismatch.
  - [ ] **Seam discipline (AC4):** `get_current_user` reads algorithm/issuer/key from `Settings` only; the 14 routers depend on `get_current_user`/`require_role`, never on JWT internals.
- [ ] **T4 — routes/auth.py: login + me** (AC1, AC2, Security Test 7)
  - [ ] `POST /api/v1/auth/login` (unauthenticated): look up user by username; **always** run `verify_password` (against a dummy hash if user absent — uniform timing, Security Test 7); on match + `is_active` mint token; else 401 ADR-10. Mount in [main.py](../../cloud-backend/src/cloud_backend/main.py).
  - [ ] `GET /api/v1/auth/me` (`Depends(get_current_user)`) → returns `CurrentUser`.
- [ ] **T5 — frontend login + token store + interceptor** (AC6) — *UX: see Freya note in Dev Notes*
  - [ ] `control-centre/src/components/auth/Login.jsx` + CSS (use `--obb-*` tokens — see Dev Notes token list); `/login` route in the router.
  - [ ] Token store (`src/lib/auth/tokenStore.js`): in-memory + `sessionStorage`; `getToken/setToken/clearToken`.
  - [ ] Central fetch wrapper / interceptor: attach `Authorization: Bearer <token>`; on `401` clear token + redirect `/login`. **Replace the `X-API-Key: VITE_API_KEY` header** across the 25 `src/api/*.js` files (Dev Notes lists them) — prefer routing them through one shared helper if not already.
  - [ ] Route guard: unauthenticated → `/login`; logout control clears token.
- [ ] **T6 — staged cutover of 14 routers + /api/v1/health** (AC5, D2, D3, D4) — *do AFTER T3–T5 are green*
  - [ ] In each of the 14 router files, swap `dependencies=[Security(require_api_key)]` → `dependencies=[Security(get_current_user)]` (router list in Dev Notes). For [health.py:77](../../cloud-backend/src/cloud_backend/routes/health.py), swap the per-route `dependencies=[Security(require_api_key)]` on `/api/v1/health` only.
  - [ ] **Leave `/health/live` and `/health/ready` OPEN** (D3).
  - [ ] **Do NOT delete** `require_api_key`/`Settings.api_key` (D4) — add the dead-code comment; cleanup deferred to E11-S3.
  - [ ] Update [tests/unit/test_rest_api.py](../../cloud-backend/tests/unit/test_rest_api.py) and any test using `_HEADERS = {"X-API-Key": ...}` to use a Bearer token (these will break on cutover — that's expected; fix them in the same pass).
- [ ] **T7 — ADR-23 + ADR-7/ADR-22 updates + CLAUDE.md** (AC8, D1)
  - [ ] Author `#### ADR-23: Self-Contained JWT Authentication (2026-06-14)` in [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) after ADR-22: decision (self-contained HS256 JWT, local users table, bcrypt), the **verification-seam contract** (AC4), and the OIDC/Keycloak Phase-2 swap-in (cite ADR-6/ADR-7 upgrade-path language).
  - [ ] Update ADR-7 ([architecture.md:568](../../_bmad-output/planning-artifacts/architecture.md)) and ADR-22's line-712 note (D1).
  - [ ] Rewrite the `cloud-backend/CLAUDE.md` "Auth" line to match shipped reality (`get_current_user` real; `Authorization: Bearer`; `require_role` in route).
- [ ] **T8 — Security Tests (RED-first) + integration tests** (Security Tests §, Integration test §, AC9)
  - [ ] Write the 8 Security Tests first (RED), then `test_auth_flow_end_to_end` (A3 real-seed), `test_all_protected_routes_require_token` (AC5), `test_seam_oidc_swap` (AC4).
  - [ ] **Run integration tests on real Postgres and watch them pass BEFORE flipping to review** (A1 hard gate). If Docker truly unavailable after a real attempt, HALT and tell the user — do not flip to review on unit coverage alone.
  - [ ] Browser-verify the login flow (AC6) — golden path + bad-creds + expired-token→redirect.

## Dev Notes

### Architecture patterns & constraints

- **ADR-7** ([architecture.md:568](../../_bmad-output/planning-artifacts/architecture.md)): *"Architecture must not assume API key is permanent — no hardcoded key logic in business layer."* ADR-23 realizes the first half of its OIDC upgrade path. **ADR-8**: every route stays under `/api/v1/`. **ADR-10**: error envelope `{"error","detail","recoverable"}` — reuse for all 401/403.
- **Fail-closed posture** is the shipped idiom: copy the `cc_admin_key` empty-default rejection ([admin_alert_classes.py:34-35](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py)) for `jwt_secret` (AC7).
- **cloud-backend/CLAUDE.md "Review Failure Scenarios"** already names the JWT edge cases (expired / tampered / missing-role → 401/403 not 500) — Security Tests 1,2,6 are the discharge of that scenario.

### Files being modified (UPDATE) — current state / change / preserve

Per the FULL-FILE-READS rule, read each completely before coding. Summary of what's already verified:

- **[api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py)** (18 lines) — *current:* only `require_api_key` (X-API-Key vs `Settings.api_key`). *change:* ADD `CurrentUser`, password hash/verify, `create_access_token`, `get_current_user`, `require_role`. *preserve:* keep `require_api_key` callable through the cutover (D4).
- **[config/__init__.py](../../cloud-backend/src/cloud_backend/config/__init__.py)** (22 lines) — *current:* `api_key`, `cc_admin_key` (fail-closed), db/log/host/port. *change:* ADD 4 jwt_* fields. *preserve:* `api_key`/`cc_admin_key` untouched (other schemes still live).
- **[main.py](../../cloud-backend/src/cloud_backend/main.py)** (59 lines) — *current:* mounts 15 routers via bare `include_router`; auth is per-router, no central middleware (D2). *change:* mount the new `auth_router`. *preserve:* mount order / exception handler / startup log.
- **[routes/health.py](../../cloud-backend/src/cloud_backend/routes/health.py)** — *current:* open `/health/live`,`/health/ready` + auth-gated `/api/v1/health` ([:77](../../cloud-backend/src/cloud_backend/routes/health.py)). *change:* swap the gate on `/api/v1/health` ONLY. *preserve:* probes stay open (D3).
- **[tests/unit/test_rest_api.py](../../cloud-backend/tests/unit/test_rest_api.py)** — *current:* `_HEADERS={"X-API-Key": get_settings().api_key}`, `TestClient`, dependency-override mock-db pattern. *change:* Bearer token. *preserve:* the mock-db override pattern (reuse it).

### The protected surfaces (AC5 parametrized test — exact, verified list)

**15 routers** with `dependencies=[Security(require_api_key)]` (swap whole router) — note `capacity_review.py` defines **TWO** routers under different prefixes (verified [capacity_review.py:42,48](../../cloud-backend/src/cloud_backend/routes/capacity_review.py)):
1. `analytics` → `/api/v1/analytics`
2. `capacity_review` _exceptions → `/api/v1/analytics/exceptions`
3. `capacity_review` _export → `/api/v1/capacity-review-queue`
4. `fleet` → `/api/v1/fleet`
5. `alerts_sse` → `/api/v1/alerts`
6. `config` → `/api/v1/config`
7. `ai_pipeline` → `/api/v1/health/...` (confirm exact subpath in [ai_pipeline.py:14](../../cloud-backend/src/cloud_backend/routes/ai_pipeline.py))
8. `ai_quality` → `/api/v1/ai-quality`
9. `maintenance` → confirm prefix in [maintenance.py:17](../../cloud-backend/src/cloud_backend/routes/maintenance.py)
10. `preferences` → `/api/v1/operators/me`
11. `escalations` → `/api/v1/escalations`
12. `escalations_audit` → `/api/v1/escalations-audit`
13. `kpi` → `/api/v1/kpi`
14. `ingest` → `/api/v1/events`

Plus **the standalone per-route gate** `GET /api/v1/health` ([health.py:77](../../cloud-backend/src/cloud_backend/routes/health.py)) — swap that decorator only.

**Open — assert NON-401 without a token:** `/health/live`, `/health/ready` (D3 infra probes), `POST /api/v1/auth/login` (D4/chicken-and-egg).

**SEPARATE — `/ws` live stream:** confirm whether the `/ws` WebSocket endpoint is auth-gated today (it is **not** in the `require_api_key` router list). Its auth is the **D8 handshake-token** path, NOT this header gate. If `/ws` is currently open, adding handshake-token validation is in-scope for AC6's "live stream carries identity"; if that expands scope materially, raise it with the user.

*(When writing the test, hit a real path on each prefix — a 401 on the router's `dependencies` fires before routing, so any path under the prefix works.)*

### Frontend — the X-API-Key → Bearer swap

25 `control-centre/src/api/*.js` + related files currently read `VITE_API_KEY` and send `X-API-Key` (e.g. [escalations.js:2,18,36](../../control-centre/src/api/escalations.js), [preferences.js:7,30,49](../../control-centre/src/api/preferences.js)). Route them through one shared fetch helper that injects `Authorization: Bearer` + the 401 interceptor, rather than editing 25 header literals in place where a helper already exists. SSE (`src/ws/RealWebSocketClient.js`) also needs the token — EventSource can't set headers, so pass the token as a query param or use the fetch-based SSE path; **flag this to the user if the SSE client can't carry a Bearer header cleanly** (possible Decision at dev time).

### CSS tokens (Login.jsx)

Use only `--obb-*` from [control-centre/src/styles/colors_and_type.css](../../control-centre/src/styles/colors_and_type.css). Surfaces: `--obb-surface-0..5`; text `--obb-text-on-dark-1..4`; error state `--obb-sev-critical` (red) for bad-creds; borders `--obb-border-dark/bright`; accent `--obb-blue-accent`. **`--obb-sev-warning` does NOT exist (use `--obb-sev-medium`); `--obb-sev-danger` does NOT exist (use `--obb-sev-critical`).**

### UX ownership (Freya)

The login screen is a **new UX surface**. Per project CLAUDE.md, UX is Freya's. For this story a **minimal functional login** (username/password, error state, submit, ÖBB dark-ops theme via `--obb-*`) satisfies AC6. If a polished design pass is wanted before dev, invoke Freya for a login-screen spec; otherwise the dev implements the minimal version and Freya reviews in the browser-verification step.

### Latest tech (verify before pinning — T1)

Confirm current stable versions + any security notes via Context7 before pinning: **PyJWT** (decode allow-list API: `jwt.decode(token, key, algorithms=[...], issuer=..., options={"require":[...]})` — the `algorithms` allow-list is the `alg:none` defense), **passlib[bcrypt]** (bcrypt 72-byte truncation caveat; `CryptContext(schemes=["bcrypt"])`). Do not accept `algorithms` defaulting — always pass an explicit allow-list (Security Test 3).

### Testing standards

- Markers: `@pytest.mark.unit` (no DB) and `@pytest.mark.integration` (testcontainers Postgres). Coverage gate ≥80% (cloud-backend), this story's security-critical paths should be near-complete.
- `mypy --strict` + `ruff` clean on touched `src/`.
- CC: `vitest` for token store / interceptor / Login; Playwright **four paths** (happy, auth-failure, validation/error, edge) per dev-story DoD.

### Project Structure Notes

- Backend layout matches [cloud-backend/CLAUDE.md](../../cloud-backend/CLAUDE.md): routes in `routes/` (handlers only), models in `api/`, all env vars in `config.py`, migrations autogenerated then reviewed. `auth.py` correctly lives in `api/` (cross-cutting), `routes/auth.py` holds the login/me handlers.
- Frontend: `src/components/auth/`, `src/lib/auth/` follow the `src/components/<feature>/` + `src/lib/<area>/` conventions ([control-centre/CLAUDE.md](../../control-centre/CLAUDE.md)).
- No variances from unified structure detected.

### References

- [Source: epics.md#Epic-11 → E11-S1](../../_bmad-output/planning-artifacts/epics.md) — locked scope/ACs/deliverables.
- [Source: architecture.md#ADR-7](../../_bmad-output/planning-artifacts/architecture.md) — cloud-backend auth + OIDC upgrade path (extended by ADR-23).
- [Source: architecture.md#ADR-6](../../_bmad-output/planning-artifacts/architecture.md) — JWT Phase-2 trigger language.
- [Source: architecture.md#ADR-22:712](../../_bmad-output/planning-artifacts/architecture.md) — "Epic 11 replaces with JWT identity" (update target).
- [Source: 10-6-escalation-lifecycle-persistence.md#D6](10-6-escalation-lifecycle-persistence.md) — operator identity deferred to Epic 11 (this story).
- [Source: cloud-backend/api/auth.py](../../cloud-backend/src/cloud_backend/api/auth.py), [admin_alert_classes.py:32-40](../../cloud-backend/src/cloud_backend/routes/admin_alert_classes.py) — shipped auth + fail-closed idiom.
- [Source: 0006_escalations.py](../../cloud-backend/migrations/versions/0006_escalations.py) — migration shape for 0009.
- [Source: epic-10-retro-2026-06-14.md#A1/A2/A3](epic-10-retro-2026-06-14.md) — review gates wired into this story.

### Permission tier & review tier

- **Permission tier: Tier 3** — new dependency, DB migration (0009), and auth on shared infrastructure. **Default permission mode** (per project CLAUDE.md: Tier 3 on shared infra — auth, migrations — always default mode, regardless of session mode). **Sign-off recorded here.**
- **Review tier: FULL adversarial wire-replay** (A2 — auth + migration). The code-review must replay the real login→Bearer→protected-route wire, not synthetic kwargs.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
