# Story 3.4: Dwell Time — Real Data

Status: review

## Story

As a Control Centre operator,
I want the Dwell Time tab to show real breach counts and dwell durations queried from the event store per selected range,
so that I can make accurate station performance assessments based on actual data rather than multiplied mock values.

## Acceptance Criteria

**AC1 — API call on mount:**
Given the operator navigates to the Dwell Time tab,
When the component mounts,
Then `GET /api/v1/analytics/dwell-time?range=7d` is called; a loading skeleton is shown; on success, the bar chart and scatter plot render with real station data.

**AC2 — No client-side breach multiplier:**
Given the API response includes `breach_count` per station,
When the breach count section renders,
Then it shows the direct server value — no `×1/×2/×4` multiplier is applied client-side; the period label matches the selected range ("this week" / "last 14 days" / "last 30 days").

**AC3 — Date range re-fetch:**
Given the operator changes the date range,
When the new range is selected,
Then `GET /api/v1/analytics/dwell-time?range={new_range}` is fired; the bar chart, scatter plot, breach counts, and correlation insight all update from the new response.

**AC4 — Empty state:**
Given the API returns an empty station array,
When the component renders,
Then the empty state "No dwell data available for this period." is shown for both the bar chart and scatter plot sections.

**AC5 — Regression line computed client-side:**
Given the scatter plot renders,
When it displays,
Then regression line and R² correlation label are computed client-side from the server-provided `{ actual_sec, occupancy_pct }` pairs — the server does not pre-compute R²; the existing `fmtSec` and `linearRegression` functions are preserved unchanged.

**AC6 — Error state:**
Given the API call fails,
When the error is returned,
Then the error state "Dwell data unavailable — retry" with a retry button is shown; the tab bar and date range selector remain functional.

**AC7 — Existing interactions preserved:**
All existing chart interactions are preserved: scheduled tick hover tooltip, scatter dot colours by station, axis tick placement.

## Tasks / Subtasks

- [x] **T1** Add `getDwellTime(range)` to `src/api/analytics.js` (AC1)
  - [x] T1.1 Write failing tests for `getDwellTime` in `analytics.test.js`
  - [x] T1.2 Implement function — `GET /api/v1/analytics/dwell-time?range=...`

- [x] **T2** Refactor `DwellTime.jsx` to fetch real data (AC1–AC7)
  - [x] T2.1 Write failing component tests covering loading, success, empty, error+retry, date range change, no multiplier
  - [x] T2.2 Remove mock imports (`getDwellData`, `DWELL_SCATTER`); add `useEffect` + `getDwellTime`; add loading skeleton and error state
  - [x] T2.3 Map API response (`actual_sec`, `occupancy_pct`) to scatter plot points — replace hardcoded `DWELL_SCATTER`
  - [x] T2.4 Remove `breachScale` multiplier; use `breach_count` directly from API response
  - [x] T2.5 Move regression + correlation constants (`slope`, `intercept`, `r2`, `trendX1/X2/Y1/Y2`) into render/useMemo computed from live data

- [x] **T3** Run full test suite and lint; confirm no regressions

## Dev Notes

### Backend contract

`GET /api/v1/analytics/dwell-time?range={7d|14d|30d}` returns an array:
```json
[
  {
    "station": "Wien Hbf",
    "scheduled_sec": 120.0,
    "actual_sec": 128.4,
    "breach_count": 3,
    "occupancy_pct": 65.2
  }
]
```
- Array is pre-sorted by `actual_sec` DESC (backend `ORDER BY` clause — do not re-sort).
- `occupancy_pct` may be `null` for stations with no occupancy data — scatter plot must skip null points.
- Empty array = no `DWELL_EVENT` records in range; show empty state.

### Shape mismatch: mock vs API

The current mock uses `d.actual` / `d.scheduled` / `d.breaches`. The API returns `actual_sec` / `scheduled_sec` / `breach_count`. Rename field references throughout the component.

### Regression constants — must move inside render

Currently `slope`, `intercept`, `r2`, `trendX1/X2/Y1/Y2`, `correlationLabel`, `dwellPer10` are computed **module-level** from the static `DWELL_SCATTER` constant. After removing the mock, these must be computed inside the component from live scatter data. Safe to use `useMemo([scatterPoints])`.

### Scatter points from API

The mock `DWELL_SCATTER` was a separate hardcoded array. The API's `occupancy_pct` field on each `DwellStationRecord` is the crowding proxy for scatter. Build scatter points as:
```js
const scatterPoints = data
  .filter(d => d.occupancy_pct != null)
  .map(d => ({ crowding: d.occupancy_pct, dwell: d.actual_sec, station: d.station }));
```

`linearRegression` accepts `{ crowding, dwell }` pairs — no change to function signature.

### Loading skeleton

Follow the OccupancyHeatmap skeleton pattern: render a `dwell-time__skeleton` div while `loading === true`. The existing CSS file already has a `.dwell-time` root class — add `.dwell-time__skeleton` if not present (copy the `occ-heatmap__skeleton` approach: a single fixed-height shimmer block).

### State shape

Use the same `{ data, loading, error }` + `retryCount` pattern from E3-S2 and E3-S3:
```js
const [state, setState] = useState({ data: null, loading: true, error: false });
const [retryCount, setRetryCount] = useState(0);
```
`useEffect([dateRange, retryCount])` → call `getDwellTime(dateRange)`.

### API function pattern

Add to `src/api/analytics.js` immediately after `getOccupancyHeatmap`:
```js
export function getDwellTime(range = '7d') {
  return _get(`/api/v1/analytics/dwell-time?range=${encodeURIComponent(range)}`);
}
```

### fmtSec preserved unchanged (AC5)

`fmtSec` is referenced in the bar chart for actual, scheduled, and excess values. Do not alter its signature or logic.

### `delayColor` preserved unchanged

`delayColor(actual, scheduled)` uses raw second values — after renaming to `d.actual_sec` / `d.scheduled_sec` call sites must pass the renamed fields but the function body is unchanged.

### Period label mapping (AC2)

```js
const PERIOD_LABEL = { '7d': 'this week', '14d': 'last 14 days', '30d': 'last 30 days' };
```
Use `PERIOD_LABEL[dateRange]` wherever `breachPeriodLabel` was previously set by the mock's `getDwellData`.

### Existing patterns (from E3-S3 / OccupancyHeatmap)

- ESLint `react-hooks/set-state-in-effect` fires on synchronous `setState` inside effects — suppress with inline disable on the single offending line (pre-existing pattern throughout the codebase).
- `retryCount` increment re-triggers the fetch effect; do not call `setState` twice in the same effect.

## Dev Agent Record

### Pre-Flight
- Assumptions: backend `GET /api/v1/analytics/dwell-time` is live (E3-S1 done). `occupancy_pct` doubles as scatter crowding proxy. Array pre-sorted by backend. `fmtSec` / `linearRegression` / `delayColor` unchanged.
- Open Questions: None.
- Simplicity Check: 2 source files changed (analytics.js + DwellTime.jsx), 2 test files extended/added.
- Surgical-Change Test: analytics.js (T1), DwellTime.jsx (T2), analytics.test.js (T1), DwellTime.test.jsx (T2).

### Debug Log
- `renderToStaticMarkup` (SSR) does not run `useEffect`, so API-call-on-mount tests were converted to mock contract tests — same approach used throughout the heatmap test suite.
- ESLint `react-hooks/set-state-in-effect` fires on synchronous `setState({ loading: true })` at top of effect. Suppressed with inline disable on that line (pre-existing pattern in ExceptionWorkflow, OccupancyHeatmap, SystemHealth).
- Two stale `eslint-disable-next-line` directives removed (rules-of-hooks, exhaustive-deps — not needed on the final implementation).

### Completion Notes
- Added `getDwellTime(range)` to `src/api/analytics.js` — 3-line addition following `getOccupancyHeatmap` pattern.
- Rewrote `DwellTime.jsx`: removed `getDwellData`/`DWELL_SCATTER` mock imports; added `useEffect` fetch with loading/error/success states; loading skeleton with `data-testid`; error state with retry button.
- Scatter points now derived from API `occupancy_pct` field — null records filtered out; no separate hardcoded array.
- Regression constants (`slope`, `intercept`, `r2`, trend line endpoints, `correlationLabel`, `dwellPer10`) moved from module-level into `useMemo([scatterPoints])` — computed from live data.
- `breach_count` used directly from API response — `breachScale` multiplier removed; `PERIOD_LABEL` map replaces `breachPeriodLabel` from mock.
- `fmtSec`, `delayColor`, `linearRegression`, `STATION_COLORS` all preserved unchanged.
- 173/173 tests pass (25 new); no new lint errors in changed files.

## File List

- `control-centre/src/api/analytics.js`
- `control-centre/src/api/__tests__/analytics.test.js`
- `control-centre/src/components/analytics/DwellTime.jsx`
- `control-centre/src/components/analytics/__tests__/DwellTime.test.jsx`

## Change Log

- 2026-05-19: Story created — dwell time wired to real backend API
- 2026-05-19: Implemented — getDwellTime API function, DwellTime.jsx real data wiring, 25 new tests; 173/173 pass
