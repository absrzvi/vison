# Story E2-S5 — Escalation Detail Acknowledge / Resolve API Wiring

**Status:** done  
**Sprint:** Epic 2  
**Story Key:** 2-5-escalation-detail-acknowledge-resolve

---

## Story

**As a** Control Centre operator,
**I want** the Acknowledge and Resolve actions in the Escalation Detail panel to POST to the backend API,
**so that** my actions are persisted, visible to other operators, and logged against the escalation record.

---

## Acceptance Criteria

**AC1:** Given an escalation with status `unacknowledged` is open in EscalationDetail, when the operator clicks "Acknowledge", then a `POST /api/v1/escalations/{id}/acknowledge` request is sent with the `X-API-Key` header; on HTTP 200 the escalation status updates to `acknowledged` in `FleetContext`; the Acknowledge button is replaced by the Resolve form.

**AC2:** Given an escalation with status `acknowledged` is open, when the operator enters outcome text (≤200 chars) + selects at least one action tag and clicks "Resolve", then a `POST /api/v1/escalations/{id}/resolve` request is sent with body `{"outcome": "<text>", "action_tags": ["<tag>", ...], "operator_id": "<from session>"}` and `X-API-Key` header; on HTTP 200 the escalation status updates to `resolved` in `FleetContext`.

**AC3:** Given the API returns HTTP 4xx or 5xx, when the request fails, then the action button re-enables; a toast error message appears: "Action failed — please try again"; the escalation status does NOT change in the UI.

**AC4:** Given two operators have the same escalation open simultaneously, when Operator A acknowledges it, then Operator B's open panel updates the status pill to `acknowledged` within 5 seconds via the next WebSocket tick; no stale UI state persists.

**AC5:** Given the Resolve form requires outcome text, when the operator attempts to submit with an empty outcome field, then the submit button remains disabled and a "Outcome required" inline validation message appears below the textarea.

**And** the backend REST endpoints `POST /api/v1/escalations/{id}/acknowledge` and `POST /api/v1/escalations/{id}/resolve` must exist (backend story dependency noted).  
**And** all API calls use `fetch` with `X-API-Key` header (httpx is Python-side; JS uses native fetch).

---

## Tasks / Subtasks

- [x] **T1** Create `src/api/escalations.js`
  - [x] T1.1 `acknowledgeEscalation(id)` — POST with X-API-Key, returns parsed JSON or throws
  - [x] T1.2 `resolveEscalation(id, outcome, actionTags, operatorId)` — POST with body + X-API-Key
  - [x] T1.3 Handle non-2xx responses by throwing an Error with status code

- [x] **T2** Update `FleetContext.jsx`
  - [x] T2.1 Import `acknowledgeEscalation` + `resolveEscalation` from `src/api/escalations.js`
  - [x] T2.2 Replace `acknowledge` callback: call API, on success dispatch `ESCALATION_UPDATED` patch
  - [x] T2.3 Replace `resolve` callback: call API with outcome + tags + operatorId, on success dispatch patch
  - [x] T2.4 Expose per-escalation pending/error state via context (Map keyed by id)
  - [x] T2.5 `ESCALATION_UPDATED` WebSocket handler already handles status sync (AC4 — no change needed)

- [x] **T3** Update `EscalationDetail.jsx`
  - [x] T3.1 Fix `useRef` missing from React import
  - [x] T3.2 Read `escalationPending` / `escalationError` from `useFleetData()` context
  - [x] T3.3 Show spinner / disable button while pending
  - [x] T3.4 Show inline toast error "Action failed — please try again" on error, clear on next action
  - [x] T3.5 AC5 inline validation: "Outcome required" below textarea when submit attempted with empty outcome

- [x] **T4** Fix callers to pass `action_tags` through
  - [x] T4.1 `UnifiedFeed.jsx` — `onResolve` passes `tags` arg to parent
  - [x] T4.2 `TrainDetail.jsx` — `onResolve` passes `tags` arg to parent

- [x] **T5** Remove stubs from `RealWebSocketClient.js`
  - [x] T5.1 Delete `acknowledge()` and `resolve()` no-op methods

- [x] **T6** Write Vitest unit tests for `src/api/escalations.js`
  - [x] T6.1 Test successful acknowledge (200 response)
  - [x] T6.2 Test successful resolve (200 response)
  - [x] T6.3 Test non-2xx throws with status
  - [x] T6.4 Test network error propagates

### Review Findings (2026-05-17)

#### Decision-Needed
- [x] [Review][Decision] **VITE_API_KEY in public browser bundle** — deferred; Keycloak evaluation in progress; OAuth2/OIDC upgrade path per ADR-6/7 covers this at fleet rollout
- [x] [Review][Decision] **`operator_id` from env var vs. "from session"** — deferred; PoC approximation acceptable; real per-operator identity comes from Keycloak session at rollout

#### Patches
- [x] [Review][Patch] **`encodeURIComponent(id)` missing in URL paths** [`src/api/escalations.js:21,26`]
- [x] [Review][Patch] **Submit button disabled by `isPending` not `!canSubmit` — violates AC5** [`src/components/live/EscalationDetail.jsx:241`] — disable on `isPending || !canSubmit`
- [x] [Review][Patch] **No validation message when zero tags selected** [`src/components/live/EscalationDetail.jsx`] — add inline message parallel to "Outcome required"
- [x] [Review][Patch] **`handleResolve` clears form before awaiting response — data loss on retry** [`src/components/live/EscalationDetail.jsx:68-76`] — form now clears via `useEffect` watching `escalation.status` change
- [x] [Review][Patch] **Stale-closure: REST success can overwrite a later WS `resolved` state** [`src/context/FleetContext.jsx:90-92,107-109`] — optimistic update now guards on predecessor status
- [x] [Review][Patch] **`ESCALATION_UPDATED` WS tick clears `pending` action state for in-flight request** [`src/context/FleetContext.jsx:57-62`] — only clears on `TERMINAL_STATUSES` (acknowledged/resolved)
- [x] [Review][Patch] **No fetch timeout — hung request locks button indefinitely** [`src/api/escalations.js:5`] — `AbortSignal.timeout(10000)` added
- [x] [Review][Patch] **Error toast sticky with no dismissal/auto-clear** [`src/components/live/EscalationDetail.jsx:202-206`] — clears on escalation switch; re-attempting action overwrites error state
- [x] [Review][Patch] **`res.json()` throws on 204 No Content — false failure toast** [`src/api/escalations.js:18`] — guarded with `res.status === 204` check
- [x] [Review][Patch] **Pending state not cancelled on unmount / escalation switch — stale toast on re-open** [`src/context/FleetContext.jsx:98-100`] — render-phase reset on escalation id change clears all state; TERMINAL_STATUSES guard prevents stale WS clear

#### Deferred (pre-existing)
- [x] [Review][Defer] **`computeElapsed` midnight wrapping produces wrong elapsed times** [`src/components/live/EscalationDetail.jsx:31-47`] — pre-existing, not touched in this story
- [x] [Review][Defer] **`LUGGAGE_ESCALATIONS` re-appended on every FLEET_STATE — potential duplicates on reconnect** [`src/context/FleetContext.jsx:49`] — pre-existing mock pattern
- [x] [Review][Defer] **`OPERATOR_ID` defaults to `'operator-unknown'` silently** [`src/context/FleetContext.jsx:8`] — PoC design, ADR-6/7 OAuth2 upgrade path
- [x] [Review][Defer] **ESC closes modal discarding typed resolve outcome silently** — pre-existing UX pattern
- [x] [Review][Defer] **Vitest `afterEach(vi.restoreAllMocks)` doesn't restore `stubGlobal`** [`src/api/__tests__/escalations.test.js`] — tests pass; cosmetic test hygiene
- [x] [Review][Defer] **`environment: node` in vite test config — jsdom needed when React component tests added** [`vite.config.js`] — only API module tested here
- [x] [Review][Defer] **No prop-types guard for `onResolve`/`onAcknowledge` vs context coupling** — pre-existing pattern, no prop-types in codebase

---

## Dev Notes

### Architecture context
- `FleetContext` owns all escalation state; components never fetch directly
- `ESCALATION_UPDATED` WS message is already handled in `FleetContext.onMessage` — AC4 (cross-operator sync) is satisfied automatically when the backend broadcasts the state change
- `VITE_API_URL` = base REST URL; `VITE_API_KEY` = `X-API-Key` value; `VITE_OPERATOR_ID` = operator session identifier (PoC env-var approach)
- No global toast system exists — use local error state in `EscalationDetail`
- `action_tags` is already threaded through `EscalationDetail.handleResolve(id, outcome, tags)` signature; fix is in callers that currently drop the third arg

### Known pre-existing bug
`EscalationDetail.jsx` line 1 imports `{ useState, useEffect }` but uses `useRef` at line 65 — this is a runtime error. Fix as part of T3.1.

### Security
- `X-API-Key` value read from `import.meta.env.VITE_API_KEY` — never hardcoded
- `operator_id` from `import.meta.env.VITE_OPERATOR_ID` — PoC only; OAuth2 upgrade path in fleet rollout (ADR-6/7)

---

## Dev Agent Record

### Pre-Flight Block (2026-05-17)
**Assumptions:**
- VITE_API_URL, VITE_API_KEY, VITE_OPERATOR_ID env vars used for PoC REST auth
- action_tags already flows from EscalationDetail → callers need to pass it up
- No global toast: local error state in EscalationDetail
- useRef bug (missing import) pre-exists and is fixed here

**Open Questions:** None

**Simplicity Check:** 1 new file (escalations.js), 5 surgical edits. No new abstractions.

**Surgical-Change Test:**
| File | AC |
|---|---|
| src/api/escalations.js (new) | AC1, AC2 |
| src/context/FleetContext.jsx | AC1, AC2, AC4 |
| src/components/live/EscalationDetail.jsx | AC1–AC5 |
| src/components/live/UnifiedFeed.jsx | AC2 |
| src/components/train-detail/TrainDetail.jsx | AC2 |
| src/ws/RealWebSocketClient.js | AC1 (remove stubs) |

### Debug Log

- `useRef` missing from EscalationDetail import was a pre-existing runtime bug — fixed in T3.1.
- `react-refresh/only-export-components` lint error in FleetContext.jsx is pre-existing (file exports both component + hook); not introduced by this story.
- All 6 Vitest unit tests pass. Vitest + vite config updated.

### Completion Notes

- Created `src/api/escalations.js` — `acknowledgeEscalation(id)` and `resolveEscalation(id, outcome, actionTags, operatorId)` using native `fetch` with `X-API-Key` header from `VITE_API_KEY`.
- `FleetContext` `acknowledge`/`resolve` are now async REST calls; expose `escalationActionState` map (pending/Error per id) to consumers.
- `EscalationDetail` reads `escalationActionState` from context: buttons disable while pending, show "Acknowledging…"/"Submitting…" labels, error toast on failure (AC3), inline "Outcome required" validation (AC5).
- AC4 (cross-operator sync): handled automatically — existing `ESCALATION_UPDATED` WebSocket handler already patches escalation status in context.
- `UnifiedFeed` and `TrainDetail` callers now forward `tags` as third arg to `onResolve`.
- `RealWebSocketClient` stubs removed.
- 6/6 Vitest tests pass.

---

## File List

- `src/api/escalations.js` (new)
- `src/context/FleetContext.jsx` (modified)
- `src/components/live/EscalationDetail.jsx` (modified)
- `src/components/live/UnifiedFeed.jsx` (modified)
- `src/components/train-detail/TrainDetail.jsx` (modified)
- `src/ws/RealWebSocketClient.js` (modified)
- `src/api/__tests__/escalations.test.js` (new)

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-17 | Story created and implemented — all ACs satisfied, 6/6 tests passing |
