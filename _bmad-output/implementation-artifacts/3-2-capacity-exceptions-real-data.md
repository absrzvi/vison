# Story 3.2: Capacity Exceptions — Real Data & Date Range

Status: ready-for-dev

## Story

As a Control Centre operator,
I want the Capacity Exceptions tab to show real historical exception records from the backend and let me switch between 7-, 14-, and 30-day windows,
so that I can investigate capacity patterns based on actual data stored in PostgreSQL.

## Acceptance Criteria

**AC1 — API call on mount:**
Given the Analytics panel opens on the Capacity Exceptions tab,
When the component mounts,
Then `GET /api/v1/analytics/exceptions?range=7d` is called (default range); a loading skeleton is shown while the request is in flight; results replace the skeleton on success; the mock `getExceptionsForRange()` import is removed.

**AC2 — Route grouping and severity sort:**
Given the response contains exception records,
When the list renders,
Then exceptions are grouped by route (route group header + count badge); within each group, records are sorted red-first; the coach occupancy chart uses the server-provided `coach_peaks` array — not the client-side `coachPeaks()` derivation from `timeline`.

**AC3 — Date range re-fetch:**
Given the operator changes the date range control (7d / 14d / 30d),
When a new range is selected,
Then the request is re-fired with the new `?range=` parameter; the list and detail panel update; the previously selected exception is deselected.

**AC4 — Date range selector stays as 3-option toggle:**
Given the date range selector renders,
When the operator views it,
Then it remains the existing 3-option toggle (7d / 14d / 30d) — NOT a full calendar date picker; the `from/to` query-param API extension is deferred to a future story.

**AC5 — Review queue action calls backend:**
Given the operator clicks "Add to capacity review queue" on an unreviewed exception, completes the modal (note + priority) and confirms,
When confirmed,
Then `POST /api/v1/analytics/exceptions/{id}/review` is called with `{ note, priority }` and `X-API-Key`; on success the exception status updates to `in_review` and the action strip shows "Queued · Priority: {X}" with the `queued_at` timestamp returned from the server.

**AC6 — Dismiss calls backend:**
Given the operator clicks "No action required",
When confirmed,
Then `POST /api/v1/analytics/exceptions/{id}/dismiss` is called; on success the exception moves to the dismissed section.

**AC7 — Reopen calls backend:**
Given the operator clicks "Reopen" on a dismissed exception,
When clicked,
Then `POST /api/v1/analytics/exceptions/{id}/reopen` is called; on success the exception status reverts to `unreviewed`.

**AC8 — Export CSV:**
Given the operator clicks "Export CSV" while on the Exceptions tab,
When clicked,
Then `GET /api/v1/capacity-review-queue/export?format=csv` is called; the browser downloads `capacity-review-{YYYY-MM-DD}.csv` with columns: `exception_id`, `route`, `train_id`, `departure_date`, `priority`, `note`, `queued_by`, `queued_at`, `status`; dismissed exceptions are excluded; if the queue is empty the download proceeds with header row only.

**AC9 — Error states:**
Given the `GET /api/v1/analytics/exceptions` call fails,
When the error is returned,
Then the exceptions area shows "Exception data unavailable – retry" with a retry button; no crash; the tab bar and date range selector remain functional.

**AC10 — Conrad flag deep-link:**
Given the `conradFlag` field on an exception record is non-null,
When the detail panel renders,
Then "View Conrad's full flag ↗" link is present and points to `{VITE_CONDUCTOR_APP_URL}/flags/{flag_id}`; if `VITE_CONDUCTOR_APP_URL` is absent or empty the link is hidden entirely.

**AC11 — New backend endpoints:**
Given the review/dismiss/reopen/export actions,
Then the following backend endpoints are implemented in `cloud-backend`:
- `POST /api/v1/analytics/exceptions/{id}/review` → 200 `{ status: "in_review", queued_at: "<ISO-8601>" }`
- `POST /api/v1/analytics/exceptions/{id}/dismiss` → 200 `{ status: "dismissed" }`
- `POST /api/v1/analytics/exceptions/{id}/reopen` → 200 `{ status: "unreviewed" }`
- `GET /api/v1/capacity-review-queue/export?format=csv` → 200 `text/csv`
All require `X-API-Key`; writes update `capacity_review_queue` table.

**AC12 — Summary strip uses server data:**
Given the API response,
When the summary strip renders,
Then `services operated` count, date range label, and from/to dates come from backend metadata (or are derived from the selected range on the client); no values are sourced from `EXCEPTION_DATE_RANGES` mock.

## Tasks / Subtasks

- [ ] **T1** Create `src/api/analytics.js` — API client module (AC1, AC5, AC6, AC7, AC8)
  - [ ] T1.1 Copy `_get` / `_post` / `_timeoutSignal` helpers from `escalations.js` — same pattern, same `VITE_API_URL` / `VITE_API_KEY` env vars
  - [ ] T1.2 `export function getCapacityExceptions(range = '7d')` → `_get('/api/v1/analytics/exceptions?range=' + encodeURIComponent(range))`
  - [ ] T1.3 `export function reviewException(id, note, priority)` → `_post('/api/v1/analytics/exceptions/${id}/review', { note, priority })`
  - [ ] T1.4 `export function dismissException(id)` → `_post('/api/v1/analytics/exceptions/${id}/dismiss')`
  - [ ] T1.5 `export function reopenException(id)` → `_post('/api/v1/analytics/exceptions/${id}/reopen')`
  - [ ] T1.6 `export function exportCapacityReviewCsv(dateStr)` → `_get('/api/v1/capacity-review-queue/export?format=csv')` and trigger browser download with filename `capacity-review-${dateStr}.csv`

- [ ] **T2** Refactor `ExceptionWorkflow.jsx` — replace mock with real API (AC1, AC2, AC3, AC9, AC10, AC12)
  - [ ] T2.1 Remove imports from `../../mock/analytics` (`EXCEPTION_DATE`, `EXCEPTION_DATE_RANGES`, `getExceptionsForRange`)
  - [ ] T2.2 Add `useState` for `exceptions`, `loading`, `error` (the component **currently does not define `useState` for `exceptions`** — it uses `setExceptions` without declaring it; this is a pre-existing bug that this story fixes)
  - [ ] T2.3 Add `useEffect([dateRange])` that calls `getCapacityExceptions(dateRange)` and sets `loading` / `exceptions` / `error`; add cleanup / abort on unmount
  - [ ] T2.4 Replace `coachPeaks(exception)` client-side derivation with server-provided `coach_peaks` array from `ExceptionRecord`; see field mapping in Dev Notes
  - [ ] T2.5 Replace `exception.weeklyPeak` reference with `exception.trend` (server field name); keep `WeeklyTrendChart` rendering logic unchanged
  - [ ] T2.6 Replace hardcoded summary strip values (`rangeInfo.servicesOperated`, `rangeInfo.from`, `rangeInfo.to`) with computed values — derive `from`/`to` client-side from selected range and today's date; `servicesOperated` becomes total unique `journey_id` values or is omitted if backend doesn't return it (do NOT fabricate)
  - [ ] T2.7 Replace `handleDismiss` / `handleReopen` / `handleReviewConfirm` local state mutations with API calls + optimistic update pattern
  - [ ] T2.8 Render loading skeleton (3 placeholder cards, matches existing CSS) while `loading === true`
  - [ ] T2.9 Render error state with retry button when `error !== null`
  - [ ] T2.10 Wire Conrad flag deep-link: `{VITE_CONDUCTOR_APP_URL}/flags/{conradFlag.flag_id}` — hidden when env var absent; use `import.meta.env.VITE_CONDUCTOR_APP_URL`

- [ ] **T3** Update `Analytics.jsx` — wire export button to real API (AC8)
  - [ ] T3.1 Replace `mockExportCsv(tab, range)` for the exceptions tab with `exportCapacityReviewCsv(dateStr)` from `analytics.js`; keep `mockExportCsv` for the other 3 tabs (occupancy / dwell / AI) — those are wired in E3-S3/S4/S5
  - [ ] T3.2 Pass `dateRange` to `ExceptionWorkflow` as before (no change)

- [ ] **T4** Backend — new action endpoints (AC5, AC6, AC7, AC11)
  - [ ] T4.1 Add Alembic migration creating `capacity_review_queue` table (schema in Dev Notes)
  - [ ] T4.2 Create `cloud-backend/src/cloud_backend/routes/capacity_review.py` with router `prefix="/api/v1/analytics/exceptions"` and `dependencies=[Security(require_api_key)]`
  - [ ] T4.3 `POST /{id}/review` — inserts row into `capacity_review_queue`; returns `{ status: "in_review", queued_at: "<ISO-8601>" }`; `queued_by` extracted from the validated API key (operator_id from `require_api_key`)
  - [ ] T4.4 `POST /{id}/dismiss` — upserts `status = 'dismissed'` in `capacity_review_queue`; returns `{ status: "dismissed" }`
  - [ ] T4.5 `POST /{id}/reopen` — updates `status = 'unreviewed'` (delete or soft-delete the queue row); returns `{ status: "unreviewed" }`
  - [ ] T4.6 Mount `capacity_review_router` in `main.py`

- [ ] **T5** Backend — CSV export endpoint (AC8, AC11)
  - [ ] T5.1 Add `GET /api/v1/capacity-review-queue/export` route in `capacity_review.py`; accepts `?format=csv`
  - [ ] T5.2 Query `capacity_review_queue JOIN events ON exception_id` for columns: `exception_id`, `route`, `train_id`, `departure_date`, `priority`, `note`, `queued_by`, `queued_at`, `status`; exclude `status = 'dismissed'`
  - [ ] T5.3 Return `StreamingResponse` with `media_type="text/csv"` and `Content-Disposition: attachment; filename=capacity-review-{YYYY-MM-DD}.csv`

- [ ] **T6** Write Vitest unit tests for `analytics.js` API client (AC1, AC5, AC6, AC7, AC8)
  - [ ] T6.1 `src/api/__tests__/analytics.test.js` — follow existing pattern in `escalations.test.js` / `health.test.js`
  - [ ] T6.2 Test `getCapacityExceptions('7d')` — GETs correct URL, returns parsed JSON
  - [ ] T6.3 Test `reviewException(id, note, priority)` — POSTs correct body, returns response
  - [ ] T6.4 Test `dismissException(id)` / `reopenException(id)` — correct paths
  - [ ] T6.5 Test error propagation: non-2xx throws `Error` with `.status`

- [ ] **T7** Write backend unit/integration tests (AC5, AC6, AC7, AC8, AC11)
  - [ ] T7.1 `tests/unit/test_capacity_review_security.py` — unauthenticated 401, wrong key 401 for all 4 new endpoints
  - [ ] T7.2 `tests/integration/test_capacity_review.py` — testcontainers Postgres; seed exception in `events` table; POST review → assert row in `capacity_review_queue` with correct fields; POST dismiss → assert status updated; POST reopen → assert status reverted; GET export → assert CSV headers + row content

- [ ] **T8** Run lint and tests
  - [ ] T8.1 `npm run lint` in `control-centre/` — no new errors
  - [ ] T8.2 `npm run test` in `control-centre/` — all existing + new Vitest tests pass
  - [ ] T8.3 `python -m pytest tests/unit/test_capacity_review_security.py tests/integration/test_capacity_review.py -q` in `cloud-backend/` — all pass
  - [ ] T8.4 `python -m ruff check src/` + `python -m mypy src/` in `cloud-backend/` — clean

## Security Tests

**API endpoint security:**
- [ ] `test_unauthenticated_review` — no key → 401 for `POST /api/v1/analytics/exceptions/{id}/review`
- [ ] `test_unauthenticated_dismiss` — no key → 401 for `POST /api/v1/analytics/exceptions/{id}/dismiss`
- [ ] `test_unauthenticated_reopen` — no key → 401 for `POST /api/v1/analytics/exceptions/{id}/reopen`
- [ ] `test_unauthenticated_export` — no key → 401 for `GET /api/v1/capacity-review-queue/export`
- [ ] `test_wrong_key_review` — wrong key → 401

**UI / client-side security:**
- [ ] `X-API-Key` is sourced from `VITE_API_KEY` env var only — never hardcoded or stored in localStorage
- [ ] Error states in `ExceptionWorkflow` display generic user-facing messages — no raw server error detail or status codes exposed in the UI
- [ ] `exportCapacityReviewCsv` result is written to a `Blob` URL and immediately revoked — no sensitive data persists in memory beyond the download

**OEBB-specific:**
- [ ] No raw CCTV stream URL appears in any exceptions API response or rendered UI
- [ ] `priority` value in `reviewException` body is validated client-side to `['Low', 'Medium', 'High']` before POST — no arbitrary string injection

## Dev Notes

### Critical Pre-Existing Bug to Fix

`ExceptionWorkflow.jsx` calls `setExceptions()` (in `handleDismiss`, `handleReopen`, `handleReviewConfirm`) but **never declares `const [exceptions, setExceptions] = useState(...)`**. The component currently reads `exceptions` from `useMemo(() => getExceptionsForRange(dateRange), [dateRange])`, which is read-only. This is why action state changes don't persist in the current UI. This story fixes this by:
1. Replacing the `useMemo` with `useState([])`
2. Loading data via `useEffect` from the real API
3. Wiring all mutation handlers to API calls + local state updates (optimistic)

### Field Mapping: Mock → Server

The server (`ExceptionRecord` from `cloud_backend/api/analytics.py`) uses these field names — **different from the mock**:

| Mock field | Server field | Notes |
|---|---|---|
| `id` | `exception_id` | Use `exception_id` as React key and for API calls |
| `trainId` | `train_id` | camelCase → snake_case |
| `weeklyPeak` | `trend` | Array of 7 floats |
| `timeline` | _(not in server response)_ | Remove `coachPeaks()` derivation; use `coach_peaks` directly |
| `coaches` | _(derived)_ | Not in server; derive from `coach_peaks.map(cp => cp.coach_id)` if needed for display |
| `peakOccupancy` | _(derived)_ | Compute `Math.max(...coach_peaks.map(cp => cp.peak_pct))` client-side |
| `conradFlag.time` | `conradFlag.note` / `flag_id` | Server: `{ flag_id, note }` — no `time` field |
| `severity` | `severity` | Same values: `critical` / `warning` / `info` — note server uses these, not `red` / `amber` |
| `status` | `status` | Same values: `unreviewed` / `in_review` / `dismissed` |
| `trendDirection` | _(not in server)_ | Not returned by server; remove trend badge or hide if absent |
| `trendWeeks` | _(not in server)_ | Same as above |
| `departure` | `departure` | Same |
| `route` | `route` | Same |
| `date` | `date` | Same — ISO date string `YYYY-MM-DD` |

**Severity mapping:** Server returns `critical` / `warning` / `info` (not `red` / `amber`). Update CSS class derivation:
```javascript
// Before (mock): exc.severity === 'red'
// After (server): exc.severity === 'critical'
const sevClass = exc.severity === 'critical' ? 'red' : exc.severity === 'warning' ? 'amber' : 'info';
```
All existing CSS classes (`exc-card--red`, `exc-sev-dot--red`, `badge--red`) remain unchanged — only the class-derivation logic changes.

### Coach Occupancy Chart — Refactor

The existing `coachPeaks(exception)` function derives peak occupancy from `exception.timeline` (a mock-only field not returned by the server). Replace with server data:

```javascript
// NEW: use server-provided coach_peaks array directly
function CoachOccupancyChart({ coachPeaks }) {
  // coachPeaks: [{ coach_id: "C1", peak_pct: 94.0 }, ...]
  if (!coachPeaks || !coachPeaks.length) return null;
  return (
    <div className="exc-coach-chart">
      <div className="exc-chart-title">Peak occupancy by coach</div>
      <div className="exc-coach-bars">
        {coachPeaks.map(({ coach_id, peak_pct }) => {
          const color = coachColor(peak_pct, peak_pct >= 85);
          return (
            <div key={coach_id} className="exc-coach-row">
              <span className="exc-coach-row__label">{coach_id}</span>
              <div className="exc-coach-row__track">
                <div className="exc-coach-row__threshold" aria-hidden="true" />
                <div className="exc-coach-row__bar" style={{ width: `${peak_pct}%`, background: color }} />
              </div>
              <span className="exc-coach-row__pct" style={{ color: peak_pct >= 85 ? color : 'var(--obb-text-on-dark-4)' }}>
                {peak_pct}%
              </span>
              {peak_pct >= 85 && <span className="exc-coach-row__flag" style={{ color }}>▲</span>}
            </div>
          );
        })}
      </div>
      {/* Keep existing axis markup unchanged */}
    </div>
  );
}
```
Call as: `<CoachOccupancyChart coachPeaks={selectedExc.coach_peaks} />`

### API Client Pattern

Follow `escalations.js` exactly — same helpers, same module-level constants:

```javascript
// src/api/analytics.js
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';
const FETCH_TIMEOUT_MS = 10_000;

function _timeoutSignal(ms) { /* copy from escalations.js */ }
async function _get(path) { /* copy from escalations.js */ }
async function _post(path, body) { /* copy from escalations.js */ }

export function getCapacityExceptions(range = '7d') {
  return _get(`/api/v1/analytics/exceptions?range=${encodeURIComponent(range)}`);
}

export function reviewException(id, note, priority) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/review`, { note, priority });
}

export function dismissException(id) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/dismiss`);
}

export function reopenException(id) {
  return _post(`/api/v1/analytics/exceptions/${encodeURIComponent(id)}/reopen`);
}

export async function exportCapacityReviewCsv() {
  const dateStr = new Date().toISOString().slice(0, 10);
  const res = await fetch(`${API_BASE}/api/v1/capacity-review-queue/export?format=csv`, {
    headers: { 'X-API-Key': API_KEY },
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `capacity-review-${dateStr}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
```

### useEffect Pattern for Data Fetching

```javascript
// In ExceptionWorkflow.jsx
const [exceptions, setExceptions] = useState([]);
const [loading, setLoading] = useState(true);
const [error, setError] = useState(null);

useEffect(() => {
  let cancelled = false;
  setLoading(true);
  setError(null);
  setSelectedId(null);

  getCapacityExceptions(dateRange)
    .then(data => { if (!cancelled) { setExceptions(data); setLoading(false); } })
    .catch(err => { if (!cancelled) { setError(err); setLoading(false); } });

  return () => { cancelled = true; };
}, [dateRange]);
```

### Loading Skeleton

Use 3 placeholder cards. The existing `exc-card` CSS already supports this — add a `exc-card--skeleton` modifier with pulse animation, or use the existing `skeleton` class from the design system. If no skeleton class exists, add one following the existing pattern in `src/index.css`:
```css
/* In ExceptionWorkflow.css or index.css */
.exc-card--skeleton {
  background: var(--obb-surface-2);
  animation: pulse 1.4s ease-in-out infinite;
  pointer-events: none;
  height: 72px;
  border-radius: 6px;
}
@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }
```

### Backend: Capacity Review Queue Table

```sql
CREATE TABLE capacity_review_queue (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exception_id   TEXT NOT NULL,
  route          TEXT NOT NULL,
  train_id       TEXT NOT NULL,
  departure_date DATE NOT NULL,
  priority       TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high')),
  note           TEXT,
  queued_by      TEXT NOT NULL,
  queued_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status         TEXT NOT NULL DEFAULT 'in_review'
                 CHECK (status IN ('in_review', 'dismissed', 'unreviewed'))
);
```

Migration file: `cloud-backend/migrations/versions/XXXX_add_capacity_review_queue.py`

### Backend: Route Handler Pattern

Follow `cloud-backend/src/cloud_backend/routes/analytics.py` exactly:
- Router prefix + `dependencies=[Security(require_api_key)]`
- `async def` handlers with `db: AsyncSession = Depends(get_db)`
- `text("""...""")` SQL via SQLAlchemy async
- Pydantic response models in `cloud-backend/src/cloud_backend/api/capacity_review.py` (new file)

For the `queued_by` field: `require_api_key` in `cloud-backend/src/cloud_backend/api/auth.py` returns the operator_id from the API key lookup — check how it's used in existing routes (the dependency validates the key and the operator_id is extractable).

### Summary Strip — Deferred Fields

The mock `EXCEPTION_DATE_RANGES` provided `servicesOperated`, `from`, and `to`. The server does **not** return these as metadata. Handle as follows:
- `from` / `to`: Compute client-side from selected range and `new Date()` — no server call needed
- `servicesOperated`: **Remove from summary strip** — do not fabricate. The backend does not count operated services; fabricating this number would mislead operators.

### Scope Deferral: Full Calendar Date Picker

The epic AC specifies a full calendar date picker with `from/to` params. This is deferred because:
1. The current backend only accepts `range=7d|14d|30d` (E3-S1)
2. Changing the backend requires an additive API change to accept arbitrary date ranges
3. The existing 3-option toggle satisfies PoC operator needs

Document this in the story completion notes. Create a deferred item in `deferred-work.md`.

### Existing Files Modified (READ before touching)

**`ExceptionWorkflow.jsx`** (lines 1–3 imports, lines ~215–220 data load, lines ~255–275 mutation handlers):
- Currently: `const exceptions = useMemo(() => getExceptionsForRange(dateRange), [dateRange])` — read-only, no `setExceptions` declaration
- After: `useState([])` + `useEffect` with API call
- Preserve: All rendering logic, all CSS classes, modal, `ReviewModal` component, `groupByRoute`, `ExceptionCard`, chart components (adapt props only)

**`Analytics.jsx`** (line ~55 export function, line ~90 render):
- Currently: `mockExportCsv(tab, range)` called for all tabs
- After: Branch on `tab === 'exceptions'` → call `exportCapacityReviewCsv()` from `analytics.js`; keep `mockExportCsv` for other tabs unchanged

### Testing Pattern (Vitest)

Follow `src/api/__tests__/escalations.test.js` exactly:
```javascript
// src/api/__tests__/analytics.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getCapacityExceptions, reviewException } from '../analytics';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function okResponse(body = {}) {
  return { ok: true, json: () => Promise.resolve(body) };
}
```

### Backend Testing Pattern

Follow `cloud-backend/tests/integration/test_analytics_endpoints.py` exactly:
- `pg_url` module-scoped fixture with `PostgresContainer("postgres:16-alpine")`
- Per-test `client` fixture with `app.dependency_overrides[get_db]`
- Seed the `capacity_review_queue` and `events` tables in `_seed()`
- Mark with `@pytest.mark.integration`

### References

- Epic 3 story spec: `_bmad-output/planning-artifacts/epics.md` §E3-S2
- Server response models: `cloud-backend/src/cloud_backend/api/analytics.py`
- Server route: `cloud-backend/src/cloud_backend/routes/analytics.py`
- Route pattern: `cloud-backend/src/cloud_backend/routes/analytics.py` (follow this exactly)
- Auth dependency: `cloud-backend/src/cloud_backend/api/auth.py`
- API client pattern: `control-centre/src/api/escalations.js`
- Test pattern (Vitest): `control-centre/src/api/__tests__/escalations.test.js`
- Test pattern (backend): `cloud-backend/tests/integration/test_analytics_endpoints.py`
- DB schema: `cloud-backend/tests/integration/test_postgres_schema.py`
- CLAUDE.md (frontend): `control-centre/CLAUDE.md`
- CLAUDE.md (backend): `cloud-backend/CLAUDE.md`
- Deferred work log: `_bmad-output/implementation-artifacts/deferred-work.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
