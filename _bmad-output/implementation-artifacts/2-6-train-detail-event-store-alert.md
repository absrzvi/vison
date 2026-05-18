# Story E2-S6 — Train Detail Event-Store Alert Integration

**Status:** done
**Sprint:** Epic 2
**Story Key:** 2-6-train-detail-event-store-alert

---

## Story

**As a** Control Centre operator,
**I want** the Train Detail panel's Active Alerts list to show first-class alert events from the event-store rather than being derived inline from coach occupancy flags,
**so that** alerts are accurate, carry full context (type, timestamp, confidence, camera), and don't disappear when occupancy data refreshes.

---

## Acceptance Criteria

**AC1:** Given a train detail panel opens for train ID `{id}`, when the panel mounts, then a `GET /api/v1/trains/{id}/alerts?status=active` request is sent; the response populates the `td-alerts-list` with alert events in the canonical shape: `{ alert_id, type, coach_id, title, confidence, camera_id, raised_at, status }`.

**AC2:** Given the API returns an empty array, when the alerts list renders, then an empty state message "No active alerts for this train" is shown; the `td-alerts-list` does not render a list.

**AC3:** Given an alert is resolved via the WebSocket stream while the panel is open, when the `ALERT_RESOLVED` event arrives in `FleetContext`, then the resolved alert is removed from the `td-alerts-list` within one render cycle — no stale resolved alerts remain visible.

**AC4:** Given a new `ALERT_RAISED` event arrives for the open train, when `FleetContext` processes it, then the new alert is prepended to the `td-alerts-list` without requiring a panel close/reopen.

**AC5:** Given the `GET /api/v1/trains/{id}/alerts` call fails, when the error is returned, then the error envelope (ADR-10) is logged; the alerts section shows "Alert data unavailable" with a retry button; the rest of the Train Detail panel remains functional.

**AC6:** The inline derivation of alerts from `coach.hasAlert` is removed from `TrainDetail.jsx` — no fallback to the prototype shortcut.

**AC7:** Coach cell tap still filters the alerts list to the selected coach (existing behaviour preserved).

---

## Tasks / Subtasks

- [x] **T1** Add `getTrainAlerts(trainId)` to `src/api/escalations.js`
  - [x] T1.1 `GET /api/v1/trains/{id}/alerts?status=active` with X-API-Key header
  - [x] T1.2 Use existing `_timeoutSignal` and API_BASE/API_KEY pattern
  - [x] T1.3 Return parsed JSON array or throw on non-2xx

- [x] **T2** Add `ALERT_RAISED` / `ALERT_RESOLVED` handlers to `FleetContext.jsx`
  - [x] T2.1 Add `trainAlerts` state: `{ [trainId]: alert[] }` plain object for React state compat
  - [x] T2.2 Handle `ALERT_RAISED`: prepend to matching train's alert list (dedup by alert_id)
  - [x] T2.3 Handle `ALERT_RESOLVED`: filter out resolved alert by `alert_id`
  - [x] T2.4 Expose `trainAlerts`, `fetchTrainAlerts(trainId)`, `trainAlertsLoading`, `trainAlertsError` via context

- [x] **T3** Update `TrainDetail.jsx`
  - [x] T3.1 On mount / trainId change: call `fetchTrainAlerts(train.id)` from context
  - [x] T3.2 Remove `activeAlerts` inline derivation from `escalations` prop
  - [x] T3.3 Render `td-alerts-list` from `trainAlerts[train.id]` (context state)
  - [x] T3.4 Show loading state while fetch in flight
  - [x] T3.5 Show "Alert data unavailable" + retry button on error (AC5)
  - [x] T3.6 Show "No active alerts for this train" on empty array (AC2)
  - [x] T3.7 Preserve coach-cell tap filter behaviour (AC7 — no existing filter; trivially satisfied)

- [x] **T4** Write Vitest unit tests for `getTrainAlerts`
  - [x] T4.1 Success: returns parsed array
  - [x] T4.2 Non-2xx: throws with status
  - [x] T4.3 Network error: propagates

### Review Findings (2026-05-18)

#### Patches
- [x] [Review][Patch] **Alert rows are non-interactive `<div>` — click to open EscalationDetail removed** [`TrainDetail.jsx`] — restored as `<button>` with onClick; falls back to cursor:default if no matching escalation found by alert_id
- [x] [Review][Patch] **Stale REST response overwrites WS state — in-flight GET clobbers ALERT_RAISED/RESOLVED** [`FleetContext.jsx` `fetchTrainAlerts`] — fixed with per-trainId generation counter in `fetchGenRef`; stale responses discarded
- [x] [Review][Patch] **Blank flash on first render — no branch matches when `activeAlerts=null, loading=false, error=null`** [`TrainDetail.jsx`] — `alertsLoading` now also true when `activeAlerts === null` (not yet fetched)
- [x] [Review][Patch] **`selectedEscId` not reset on train switch** [`TrainDetail.jsx`] — render-phase ref comparison clears selectedEscId when train.id changes
- [x] [Review][Patch] **WS ALERT_RAISED/RESOLVED payload not guarded — missing fields create `undefined` key in `trainAlerts`** [`FleetContext.jsx` L81-94] — destructures `train_id`/`alert_id` with guard before setState
- [x] [Review][Patch] **WS ALERT_RAISED creates entries for trains never fetched — partial list shown as authoritative** [`FleetContext.jsx` L81-87] — only updates if `train_id in prev` (train already fetched)

#### Deferred
- [x] [Review][Defer] **AC5: ADR-10 error envelope not parsed — raw Error logged, not body JSON** [`FleetContext.jsx`] — backend endpoint doesn't exist yet; revisit when backend is live and error contract is defined
- [x] [Review][Defer] **`td-alerts-list` testid on `<section>` always present — AC2 "list not rendered" is semantic** — section with heading always exists; only the `<p>` list items are absent; acceptable for PoC
- [x] [Review][Defer] **CSS modifier uses `a.type` not severity — styling will differ from escalation rows** [`TrainDetail.jsx`] — alert shape has no severity field; type-based CSS is correct for the new shape; pre-existing CSS classes don't apply
- [x] [Review][Defer] **`trainAlerts` never pruned — memory growth in long operator sessions** [`FleetContext.jsx`] — PoC; add LRU eviction in a follow-up hardening story
- [x] [Review][Defer] **`API_KEY` in browser bundle** [`escalations.js`] — pre-existing, covered by ADR-6/7 Keycloak path
- [x] [Review][Defer] **`_get` res.json() throws on non-JSON 200 (e.g. proxy HTML error page)** [`escalations.js`] — pre-existing pattern from `_post`; add content-type guard in a hardening pass
- [x] [Review][Defer] **`confidence` `%` suffix assumes 0-100 scale — backend contract not yet locked** [`TrainDetail.jsx`] — revisit when API contract is finalised
- [x] [Review][Defer] **WS ALERT_RAISED payload prepended as-is — may lack canonical shape fields** [`FleetContext.jsx`] — WS contract not yet defined; revisit when backend WS events are specced

---

## Dev Notes

### Architecture context
- `FleetContext` is the single source of truth. `TrainDetail` must not fetch directly — call `fetchTrainAlerts` exposed by context.
- Existing `escalations.js` pattern: `_post(path, body)` helper + `_timeoutSignal`. Add a `_get(path)` helper using the same pattern.
- `trainAlerts` in context is `Map<trainId, alert[]>`. Keep it as a plain object `{ [trainId]: alert[] }` for React state compatibility (Maps don't trigger re-renders).
- `ALERT_RAISED` and `ALERT_RESOLVED` are new WS message types — add handlers in the `onMessage` callback in FleetContext's `useEffect`. These may not be sent by the mock WS client; that is fine — the fetch covers the initial load.
- ADR-10 error envelope: `console.error('[TrainDetail]', err)` is sufficient for PoC logging.
- No global toast — local error state inside the alerts section only.
- `fetchTrainAlerts` should set per-trainId loading + error state so the rest of the panel stays functional.

### Alert canonical shape
```js
{ alert_id, type, coach_id, title, confidence, camera_id, raised_at, status }
```

### Backend endpoint
`GET /api/v1/trains/{id}/alerts?status=active` — may not exist yet in the backend; the fetch will fail and AC5 covers the error path. The mock WS client does not need to be changed for this story.

### Coach filter
Current `TrainDetail` has no coach tap filter wired (the `coach-cell` has `cursor: default`). AC7 says preserve existing behaviour — since there is no existing filter behaviour, no change is required here.

### Security
- `X-API-Key` from `VITE_API_KEY` env var — same pattern as `escalations.js`.
- No new env vars needed.

---

## Dev Agent Record

### Pre-Flight Block

**Assumptions:**
- `_get` helper follows the same pattern as `_post` in `escalations.js`
- `trainAlerts` state stored as plain object `{ [trainId]: alert[] }` (not Map) for React state
- `fetchTrainAlerts` is the context-exposed trigger; `TrainDetail` calls it on mount
- No mock WS changes needed — fetch covers initial load; ALERT_RAISED/ALERT_RESOLVED handled when they arrive
- Coach cell filter: no existing behaviour to preserve (cursor: default, no onClick) — AC7 is satisfied trivially

**Open Questions:** None

**Simplicity Check:**
- `_get` helper in escalations.js — needed for GET requests
- `getTrainAlerts(id)` export — needed for AC1
- `trainAlerts`, `trainAlertsLoading`, `trainAlertsError` state in FleetContext — needed for AC1/AC5
- `fetchTrainAlerts` callback in context — needed to keep fetch out of TrainDetail
- `ALERT_RAISED`/`ALERT_RESOLVED` handlers in FleetContext — needed for AC3/AC4
- TrainDetail: remove inline derivation, render from context state — AC6

NOT adding: retry timer, pagination, per-coach alert counts on coach cells

**Surgical-Change Test:**
| File | AC |
|---|---|
| `src/api/escalations.js` | AC1 |
| `src/context/FleetContext.jsx` | AC1, AC3, AC4 |
| `src/components/train-detail/TrainDetail.jsx` | AC1–AC7 |
| `src/api/__tests__/escalations.test.js` | T4 |

### Debug Log

### Completion Notes

- Added `_get` helper + `getTrainAlerts(trainId)` to `escalations.js` — GETs `/api/v1/trains/{id}/alerts?status=active` with X-API-Key, timeout, encodeURIComponent.
- `FleetContext`: added `trainAlerts`/`trainAlertsLoading`/`trainAlertsError` state, `fetchTrainAlerts` callback, `ALERT_RAISED`/`ALERT_RESOLVED` WS handlers (dedup on RAISED, filter on RESOLVED). All exposed via context.
- `TrainDetail`: removed inline `activeAlerts` derivation from `escalations` prop; now renders from `trainAlerts[train.id]`; shows loading, error+retry, and empty state. `useEffect` triggers `fetchTrainAlerts` on mount and trainId change.
- 9/9 Vitest tests pass (3 new for getTrainAlerts).

---

## File List

- `src/api/escalations.js` (modified)
- `src/context/FleetContext.jsx` (modified)
- `src/components/train-detail/TrainDetail.jsx` (modified)
- `src/api/__tests__/escalations.test.js` (modified)

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-17 | Story created |
| 2026-05-18 | Implementation complete — all ACs satisfied, 9/9 tests passing, status → review |
