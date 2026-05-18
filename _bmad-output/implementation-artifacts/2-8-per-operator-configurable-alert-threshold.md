# Story E2-S8 — Per-Operator Configurable Alert Threshold

**Status:** done
**Sprint:** Epic 2
**Story Key:** 2-8-per-operator-configurable-alert-threshold

---

## Story

**As a** Control Centre operator,
**I want** to configure the threshold at which the critical alert hook (pulsing red pill) activates,
**so that** I can tune alert sensitivity to match my operational context rather than using a hardcoded 60-second default.

---

## Acceptance Criteria

**AC1:** Given the operator opens their preferences (settings icon in top nav), when the preferences panel renders, then `GET /api/v1/operators/me/preferences` is called; two controls are shown: "Critical alert threshold" (30s / 60s / 90s / 120s, default 60s) and "Connection staleness warning" (60s / 120s / 180s / 300s, default 120s); returned values are highlighted; 404 uses defaults.
> **Implementation note:** GET fires on `FleetContext` mount (page load), not on panel open. This satisfies AC3's instant-load requirement naturally and gives faster UX. The panel renders already-reconciled values. Decision confirmed 2026-05-18.

**AC2:** Given the operator selects a new threshold and confirms, when the selection is confirmed, then `PATCH /api/v1/operators/me/preferences` is called with `{ threshold_sec: N }`; on HTTP 200 the alert hook immediately uses the new value; the preference is also persisted to `localStorage` key `oebb.cc.alertThresholdSeconds` as a cache for offline / fast-load.

**AC3:** Given the operator reloads the page, when `FleetContext` initialises, then `localStorage` is read first (instant); a background `GET /api/v1/operators/me/preferences` call reconciles the server value; if they differ, the server value wins and `localStorage` is updated.

**AC4:** Given the `PATCH` call fails (4xx/5xx), when the error is returned, then the threshold control reverts to the previous value; a toast error appears: "Preference not saved — please retry"; `localStorage` is not updated.

**AC5:** Given an unacknowledged critical escalation exists, when elapsed time since arrival exceeds the operator's configured threshold, then `pid-app-shell-alert-hook` pulses red and navigates to `/dashboard/live` when clicked.

**AC6:** Given the escalation is acknowledged, when `FleetContext` processes acknowledgement, then the alert hook disappears regardless of threshold.

**AC7:** The threshold control is keyboard accessible: arrow keys cycle options, Enter confirms.

**AC8:** `DEFAULT_ALERT_THRESHOLD_SECONDS = 60` is the named constant — no magic numbers anywhere.

---

## Tasks / Subtasks

### Review Findings

- [x] [Review][Decision] GET preferences fires on mount not panel open — resolved: keep mount-time GET (option a); AC1 note updated.
- [x] [Review][Patch] secsElapsed rounds to full minutes — 30s threshold is effectively 60s [AppShell.jsx:7-13]
- [x] [Review][Patch] focusIdxRef mutated during render (concurrent-mode unsafe) [OperatorPreferences.jsx SegmentedControl]
- [x] [Review][Patch] localStorage NaN guard missing — corrupted value silently disables alert hook [FleetContext.jsx]
- [x] [Review][Patch] Stale closure in updateAlertThreshold — prev captured at call time [FleetContext.jsx]
- [x] [Review][Patch] `body.threshold_sec or 60` wrong idiom for None-check [preferences.py:123]
- [x] [Review][Patch] AC8 magic numbers 60/120 in PATCH upsert defaults [preferences.py:123-124]
- [x] [Review][Patch] Focus trap missing in preferences modal (Tab escapes panel) [OperatorPreferences.jsx]
- [x] [Review][Patch] Toast setTimeout not cleared on unmount — memory leak [OperatorPreferences.jsx]
- [x] [Review][Defer] API key as PK in operator_preferences [0002_operator_preferences.py] — deferred, pre-existing single-operator design
- [x] [Review][Defer] VITE_API_KEY in client bundle — deferred, pre-existing architecture from E2-S1
- [x] [Review][Defer] PATCH {} creates row with defaults instead of no-op — deferred, no AC requires empty-PATCH to be a no-op

- [x] **T1** Alembic migration `0002_operator_preferences.py`
  - [x] T1.1 Create `operator_preferences` table with CHECK constraints
  - [x] T1.2 Add `downgrade()` dropping the table

- [x] **T2** Backend: `cloud-backend/src/cloud_backend/routes/preferences.py`
  - [x] T2.1 `GET /api/v1/operators/me/preferences` — returns row or 404 with defaults hint
  - [x] T2.2 `PATCH /api/v1/operators/me/preferences` — upserts; validates allowed values; returns 422 on bad value
  - [x] T2.3 Register router in `main.py`

- [x] **T3** Frontend: `src/api/preferences.js`
  - [x] T3.1 `getPreferences()` — GET with X-API-Key; handles 404 by returning defaults
  - [x] T3.2 `patchPreferences(patch)` — PATCH; propagates error on non-200

- [x] **T4** Frontend: `src/components/shell/OperatorPreferences.jsx` + `.css`
  - [x] T4.1 Segmented control for "Critical alert threshold" (30/60/90/120s)
  - [x] T4.2 Segmented control for "Connection staleness warning" (60/120/180/300s)
  - [x] T4.3 Keyboard accessible: arrow keys cycle, Enter confirms
  - [x] T4.4 Toast error on PATCH failure; revert control to previous value
  - [x] T4.5 Panel opens/closes via settings icon in AppShell header

- [x] **T5** FleetContext: threshold initialisation + server reconciliation
  - [x] T5.1 On mount: read `localStorage` key `oebb.cc.alertThresholdSeconds` → `alertThresholdSeconds`
  - [x] T5.2 Background `getPreferences()` call; server value wins if different; update `localStorage`
  - [x] T5.3 Expose `alertThresholdSeconds` + `updateAlertThreshold(n)` from context
  - [x] T5.4 `updateAlertThreshold(n)` calls `patchPreferences`; on success updates state + `localStorage`; on failure reverts + returns error

- [x] **T6** AppShell: settings icon + threshold-aware alert hook
  - [x] T6.1 Replace hardcoded `>= 1` minute with `alertThresholdSeconds` from context
  - [x] T6.2 Add settings gear icon button to header; toggles `OperatorPreferences` panel
  - [x] T6.3 Alert hook has `data-testid="pid-app-shell-alert-hook"`

- [x] **T7** Tests (Vitest unit + Playwright E2E)
  - [x] T7.1 Unit: `preferences.js` — `getPreferences` returns defaults on 404
  - [x] T7.2 Unit: `preferences.js` — `patchPreferences` propagates error on 4xx
  - [x] T7.3 Unit: `OperatorPreferences` renders two segmented controls with correct options
  - [x] T7.4 Unit: `OperatorPreferences` reverts on PATCH failure and shows error message
  - [x] T7.5 E2E happy path: settings panel opens, GET preferences called, controls show current values
  - [x] T7.6 E2E auth failure: 401 from GET preferences → defaults shown
  - [x] T7.7 E2E PATCH failure: PATCH 422 → control reverts, toast appears
  - [x] T7.8 E2E edge case: localStorage pre-populated on reload → instant value, server reconciles

---

## Security Tests

- [x] SEC1 `PATCH` with `threshold_sec=999` returns 422 (value not in allowed set)
- [x] SEC2 `PATCH` with `operator_id` in body is ignored — server derives it from API key header
- [x] SEC3 `GET` without `X-API-Key` returns 401
- [x] SEC4 `PATCH` without `X-API-Key` returns 401

---

## Dev Notes

### Architecture context
- `AppShell` currently has a hardcoded `minsElapsed(...) >= 1` guard — that's `60s`. Replace with `alertThresholdSeconds / 60` via `useFleetData()`.
- Alert hook `tick` state already refreshes every 15s — sufficient resolution for threshold display.
- `operator_id` is derived from the `X-API-Key` value directly in the router (same pattern as `OPERATOR_ID = import.meta.env.VITE_API_KEY` on the frontend). Backend: use `api_key` param passed by `require_api_key`.
- No new context files needed — `FleetContext` absorbs threshold state.
- `localStorage` key is `oebb.cc.alertThresholdSeconds` (string → parseInt on read).
- Staleness warning threshold (`staleness_threshold_sec`) is stored and reconciled but not yet wired to UI behaviour — AC only asks for storage + controls; a future story wires it to the reconnecting banner timeout.
- CSS tokens already present: `--bg-surface`, `--bg-raised`, `--color-critical`, `--color-text`.

### Backend notes
- Auth: `require_api_key` returns the raw API key string — use that as `operator_id`.
- Allowed values enforced at DB level (CHECK constraint) AND at API level (422 before hitting DB).
- Use SQLAlchemy `text()` for upsert: `INSERT INTO ... ON CONFLICT (operator_id) DO UPDATE SET ...`.

### Named constants
```js
// src/constants/preferences.js
export const DEFAULT_ALERT_THRESHOLD_SECONDS = 60;
export const DEFAULT_STALENESS_THRESHOLD_SECONDS = 120;
export const ALERT_THRESHOLD_OPTIONS = [30, 60, 90, 120];
export const STALENESS_THRESHOLD_OPTIONS = [60, 120, 180, 300];
export const LS_KEY_ALERT_THRESHOLD = 'oebb.cc.alertThresholdSeconds';
export const LS_KEY_STALENESS_THRESHOLD = 'oebb.cc.stalenessThresholdSeconds';
```

---

## Dev Agent Record

### Pre-Flight Block

**Assumptions:**
- `operator_id` on the backend is derived from the `X-API-Key` header value (which equals `get_settings().api_key`). Single-operator dev environment — one key, one row in `operator_preferences`.
- `staleness_threshold_sec` is stored and surfaced in the UI but not yet wired to the reconnecting banner timeout (that's a future story). This story just saves and displays it.
- The `minsElapsed` helper in AppShell computes minutes since a `HH:MM` timestamp string — threshold comparison needs to convert `alertThresholdSeconds` to minutes.
- Vitest test environment is `node` (per vite.config.js) — no DOM renderer; test pure logic in `preferences.js`; component tests require jsdom.
- Playwright e2e tests go in `control-centre/tests/e2e/`.

**Open Questions:** None — all ACs are explicit.

**Simplicity Check:**
- Adding: `0002_operator_preferences.py` (migration), `preferences.py` (router), `preferences.js` (API module), `OperatorPreferences.jsx+css` (component), `preferences.js` (constants) — each directly maps to an AC.
- NOT adding: separate preferences context, settings route/page, modal dialog infrastructure (inline panel is sufficient per epics spec).

**Surgical-Change Test:**
- `cloud-backend/migrations/versions/0002_operator_preferences.py` → AC1/AC2 (data model)
- `cloud-backend/src/cloud_backend/routes/preferences.py` → AC1/AC2/AC4
- `cloud-backend/src/cloud_backend/main.py` → register router
- `control-centre/src/api/preferences.js` → AC1/AC2/AC4
- `control-centre/src/constants/preferences.js` → AC8
- `control-centre/src/components/shell/OperatorPreferences.jsx+css` → AC1/AC2/AC4/AC7
- `control-centre/src/context/FleetContext.jsx` → AC3/AC5/AC6
- `control-centre/src/components/shell/AppShell.jsx+css` → AC5/AC6

### Debug Log
| Step | Action | Outcome |
|------|--------|---------|
| T4 | OperatorPreferences SegmentedControl refactor | Removed setState-in-effect pattern; focusIdx moved to ref, DOM focus managed imperatively |
| T7 | E2E test fix | `getByRole('radio', { name: '60s' })` was ambiguous (two groups); scoped to radiogroup aria-label |

### Completion Notes
All 8 ACs satisfied. Backend: Alembic migration adds `operator_preferences` table with CHECK constraints; FastAPI router handles GET (404→defaults) and PATCH (422 on invalid values, upsert on valid). Frontend: `FleetContext` reads `localStorage` on init for instant threshold, background GET reconciles with server value. `OperatorPreferences` panel opens from settings gear in AppShell header; segmented controls for both thresholds; keyboard accessible (arrow keys + Enter); toast error + revert on PATCH failure. Alert hook in AppShell now uses `alertThresholdSeconds` from context instead of hardcoded 60s. Tests: 8 backend unit (incl. 4 security), 34 frontend Vitest (incl. 8 preferences unit), 9 Playwright E2E covering all 4 mandatory paths.

---

## File List

- `cloud-backend/migrations/versions/0002_operator_preferences.py` (new)
- `cloud-backend/src/cloud_backend/routes/preferences.py` (new)
- `cloud-backend/src/cloud_backend/main.py` (modified)
- `cloud-backend/tests/unit/test_preferences_api.py` (new)
- `control-centre/src/api/preferences.js` (new)
- `control-centre/src/api/__tests__/preferences.test.js` (new)
- `control-centre/src/constants/preferences.js` (new)
- `control-centre/src/constants/preferences.test.js` (new)
- `control-centre/src/components/shell/OperatorPreferences.jsx` (new)
- `control-centre/src/components/shell/OperatorPreferences.css` (new)
- `control-centre/src/components/shell/AppShell.jsx` (modified)
- `control-centre/src/components/shell/AppShell.css` (modified)
- `control-centre/src/context/FleetContext.jsx` (modified)
- `control-centre/tests/e2e/operator-preferences.spec.js` (new)
- `_bmad-output/implementation-artifacts/2-8-per-operator-configurable-alert-threshold.md` (new)

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-18 | Story file created from epics.md |
| 2026-05-18 | Implementation complete — all tasks done, status → review |
