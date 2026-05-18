# Story 3.5: AI Detection Quality — Real Data

Status: done

## Story

As a Control Centre operator,
I want the AI Detection Quality tab to show real per-week detection counts and per-train uptime computed from the inference event log,
so that I can assess actual AI performance rather than viewing deterministic baked constants.

## Acceptance Criteria

**AC1 — API call on mount:**
Given the operator navigates to the AI Detection Quality tab,
When the component mounts,
Then `GET /api/v1/analytics/detection-quality?range=7d` is called; a loading skeleton is shown for the KPI strip, bar chart, and uptime list; results replace skeletons on success.

**AC2 — fp_rate null state:**
Given the API returns `fp_rate: null` (both `total_events` and `total_fp` are zero),
When the KPI strip renders,
Then the FP rate tile shows "—" and "(no data)" label — not "0%" or "0.0%"; this matches the existing prototype null-state logic.

**AC3 — Bar chart from daily_bars:**
Given the `daily_bars` array in the API response,
When the detection chart renders for `range=7d`,
Then bars are labelled Mon–Sun from the actual dates in the response; for `range=14d` or `range=30d` bars are weekly aggregates labelled W1, W2, etc.; `maxBar` is floored at 1 to prevent divide-by-zero.

**AC4 — Per-train uptime list:**
Given the `per_train_uptime` array in the response,
When the uptime list renders,
Then trains are sorted ascending by uptime (lowest first); the uptime bar maps 70–100% to full bar width; the 85% warning threshold line is shown; colours: green ≥85% · amber 70–84% · red <70%.

**AC5 — Date range re-fetch:**
Given the operator changes the date range,
When the new range is selected,
Then `GET /api/v1/analytics/detection-quality?range={new_range}` is fired; KPI strip, chart, and uptime list all update; no `Math.random()` or baked constants remain in the component.

**AC6 — Error state:**
Given the API call fails,
When the error is returned,
Then "Detection quality data unavailable — retry" is shown with a retry button.

**AC7 — Tooltip from API data:**
Bar hover tooltip content is derived from the API response `daily_bars` rows — not from local mock constants.

**AC8 — useMemo preserved:**
`useMemo([dateRange])` memoisation is preserved for chart and uptime computations.

## Tasks / Subtasks

- [x] **T1** Add `getDetectionQuality(range)` to `src/api/analytics.js` (AC1)
  - [x] T1.1 Write failing tests for `getDetectionQuality` in `analytics.test.js`
  - [x] T1.2 Implement function — `GET /api/v1/analytics/detection-quality?range=...`

- [x] **T2** Refactor `AIDetection.jsx` to fetch real data (AC1–AC8)
  - [x] T2.1 Write failing component tests in `AIDetection.test.jsx`
  - [x] T2.2 Remove mock imports (`getDetectionTrend`, `getInferenceUptime`, `DETECTION_SUMMARY`); add `useEffect` + `getDetectionQuality`; add loading skeleton and error state
  - [x] T2.3 Map `kpi` fields from API response to summary display (totalEvents, fpRate, avgConfidence, fleetUptime)
  - [x] T2.4 Map `daily_bars` to bar chart — derive day labels from `date` field for 7d, weekly W1/W2/etc. for 14d/30d
  - [x] T2.5 Map `per_train_uptime` to uptime list — sort ascending by `uptime_pct`, apply existing colour thresholds
  - [x] T2.6 Ensure `computeFpRate` is removed (logic moves to server); use `kpi.fp_rate` directly

- [x] **T3** Run full test suite and lint; confirm no regressions

### Review Findings

- [x] [Review][Patch] Fleet uptime KPI colour regression — healthy branch uses `--obb-sev-critical` instead of `--obb-sev-normal` [AIDetection.jsx:115]
- [x] [Review][Patch] `avg_confidence ?? '—'` renders "—%" — null suffix not suppressed; same bug on `fleet_uptime_pct ?? '—'` [AIDetection.jsx:117,122]
- [x] [Review][Patch] `aggregateBars` partial-week label for 30d — W5 gets 2 days but renders identically to W1's 7 days; no normalisation or visual indicator [AIDetection.jsx:aggregateBars]
- [x] [Review][Patch] No null guard on `kpi`/`daily_bars`/`per_train_uptime` fields — 200 OK with malformed body crashes component; error branch only catches rejected promise [AIDetection.jsx]
- [x] [Review][Defer] Missing CSS classes (`analytics-retry-btn`, `ai-detection__skeleton`, `ai-detection--error`) — deferred, pre-existing pattern across E3-S2/S3/S4 [AIDetection.jsx]
- [x] [Review][Defer] Race condition on rapid dateRange change (no AbortController) — deferred, pre-existing across all analytics components [AIDetection.jsx]
- [x] [Review][Defer] `fp_count`/`total_events` null coercion in aggregation — deferred, Pydantic backend validates int [AIDetection.jsx:aggregateBars]
- [x] [Review][Defer] `barPct` no upper clamp (>100% not capped) — deferred, pre-existing pattern in uptime bar [AIDetection.jsx]

## Dev Notes

### Backend contract

`GET /api/v1/analytics/detection-quality?range={7d|14d|30d}` returns:

```json
{
  "kpi": {
    "total_events": 142,
    "fp_rate": 3.5,
    "avg_confidence": 91.2,
    "fleet_uptime_pct": 93.1
  },
  "daily_bars": [
    { "date": "2026-05-12", "total_events": 18, "fp_count": 1 }
  ],
  "per_train_uptime": [
    { "train_id": "4024-001", "uptime_pct": 88.5 }
  ]
}
```

- `fp_rate` is `null` when `total_events == 0` AND `total_fp == 0` — display "—" and "(no data)" label.
- `avg_confidence` may be `null` if no inference results exist.
- `fleet_uptime_pct` may be `null` if no journey data.
- `per_train_uptime` does **not** include `incidents` count — the uptime list row must drop the "N incidents" badge from the mock UI (or show nothing). The backend `PerTrainUptime` Pydantic model only has `train_id` and `uptime_pct`.
- `daily_bars` only has `total_events` and `fp_count` — no per-type breakdown (unattended/overcrowded/oversized). The stacked bar chart by detection type cannot be re-created from real data. The chart must switch to a simpler total-events bar + FP bar.

### Shape mismatch: mock vs API — critical differences

| Mock field | API field | Notes |
|---|---|---|
| `d.unattended`, `d.overcrowded`, `d.oversized` | none | API has no per-type split in `daily_bars` |
| `d.falsePositive` | `d.fp_count` | rename |
| `d.day` (label string) | `d.date` (ISO date string "2026-05-12") | derive label from date |
| `DETECTION_SUMMARY.avgConfidence` | `kpi.avg_confidence` | |
| `DETECTION_SUMMARY.uptimeFleet` | `kpi.fleet_uptime_pct` | |
| `t.train` | `t.train_id` | |
| `t.uptime` | `t.uptime_pct` | |
| `t.incidents` | not in API | drop the incidents badge or hide if missing |

### Bar chart simplification (no per-type breakdown)

The mock chart used a stacked bar (unattended/overcrowded/oversized). Since `daily_bars` only provides `total_events` and `fp_count`, simplify to a two-segment bar:

- Primary bar = `total_events` (use `TYPE_COLOR.unattended` or a neutral colour)
- FP sub-bar below = `fp_count` (existing `TYPE_COLOR.falsePositive`)

Remove the three-colour legend; replace with a simpler note. Keep the `fp_count > 0 && <div class="detection-bar-col__fp">{fp_count} FP</div>` pattern.

### Day label derivation

For `range=7d`: `daily_bars` contains 7 entries with ISO dates. Derive Mon/Tue/etc. from the `date` field:
```js
const DAY_ABBR = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
const label = DAY_ABBR[new Date(d.date + 'T00:00:00').getDay()];
```
Use `d.date + 'T00:00:00'` to avoid UTC offset shifting the date by one day.

For `range=14d` or `range=30d`: group `daily_bars` into ISO weeks and label W1, W2, etc.:
```js
// Group by week index
const weeks = [];
daily_bars.forEach((bar, i) => {
  const weekIdx = Math.floor(i / 7);
  if (!weeks[weekIdx]) weeks[weekIdx] = { label: `W${weekIdx + 1}`, total_events: 0, fp_count: 0 };
  weeks[weekIdx].total_events += bar.total_events;
  weeks[weekIdx].fp_count += bar.fp_count;
});
```

### computeFpRate removal

The existing `computeFpRate(trend)` function computes FP rate client-side from mock data. After this story, `kpi.fp_rate` comes from the server. Remove `computeFpRate` entirely. Use `kpi.fp_rate` directly:
```js
const fpRate = data.kpi.fp_rate; // null | float
```
The existing null-branch render (shows "—" and "(no data)") remains unchanged — it already handles `null`.

### State shape — same pattern as E3-S2/S3/S4

```js
const [state, setState] = useState({ data: null, loading: true, error: false });
const [retryCount, setRetryCount] = useState(0);
// useEffect([dateRange, retryCount]) → call getDetectionQuality(dateRange)
```
ESLint `react-hooks/set-state-in-effect` fires on synchronous `setState({ loading: true })` at top of effect — suppress with inline disable (pre-existing pattern in DwellTime, OccupancyHeatmap).

### API function pattern

Add to `src/api/analytics.js` immediately after `getDwellTime`:
```js
export function getDetectionQuality(range = '7d') {
  return _get(`/api/v1/analytics/detection-quality?range=${encodeURIComponent(range)}`);
}
```

### Loading skeleton

Add a `ai-detection__skeleton` div (same pattern as `dwell-time__skeleton`, `occ-heatmap__skeleton`). Render it when `loading === true`. Include `data-testid="ai-detection-skeleton"`.

### useMemo computation targets

The existing `trend` and `sortedUptime` are computed with `useMemo([dateRange])`. After this change, they depend on `state.data` instead of the mock call:
```js
const bars = useMemo(() => {
  if (!state.data) return [];
  if (dateRange === '7d') return state.data.daily_bars.map(d => ({ ...d, day: DAY_ABBR[new Date(d.date + 'T00:00:00').getDay()] }));
  // aggregate to weekly
  ...
}, [state.data, dateRange]);

const sortedUptime = useMemo(() => {
  if (!state.data) return [];
  return [...state.data.per_train_uptime].sort((a, b) => a.uptime_pct - b.uptime_pct);
}, [state.data]);
```

### Uptime row — field rename

`t.train` → `t.train_id`; `t.uptime` → `t.uptime_pct`. The bar width calculation:
```js
const barPct = ((t.uptime_pct - UPTIME_BASELINE) / UPTIME_RANGE) * 100;
```
Colour thresholds stay identical (≥85 green, ≥70 amber, <70 red). The incidents badge (`t.incidents`) must be removed — `per_train_uptime` has no `incidents` field.

### Colour thresholds (existing, preserved)

```js
const color = t.uptime_pct >= 85
  ? 'var(--obb-sev-normal)'
  : t.uptime_pct >= 70
    ? 'var(--obb-sev-medium)'
    : 'var(--obb-sev-critical)';
```

### Existing functions to preserve

- `TYPE_COLOR` — keep for FP bar colour (`TYPE_COLOR.falsePositive`)
- `UPTIME_BASELINE` / `UPTIME_RANGE` constants — unchanged
- Uptime axis labels (70% / 85% / 100%) and threshold line — unchanged
- `handleBarEnter` / tooltip pattern — rewrite to use `bar.total_events`, `bar.fp_count`; drop unattended/overcrowded/oversized fields

### Test approach (from DwellTime.test.jsx pattern)

Use `renderToStaticMarkup` (SSR) + `vi.mock('../../../api/analytics')`:
- Loading: `getDetectionQuality.mockReturnValue(new Promise(() => {}))` → assert `data-testid="ai-detection-skeleton"`
- API contract: `getDetectionQuality.mockResolvedValueOnce({...})` → resolved value test
- FP null state: unit test that `null` fp_rate renders "—" / "(no data)"
- Weekly aggregation: unit test the week-grouping logic
- Day label derivation: unit test `new Date(d.date + 'T00:00:00').getDay()` for known dates
- Uptime sort: unit test `.sort((a,b) => a.uptime_pct - b.uptime_pct)`
- Error message string: constant assertion

### Deferred (do not implement)

- AbortController for stale fetch on rapid range change — deferred, pre-existing across all analytics components.
- Per-type breakdown (unattended/overcrowded/oversized) in bar chart — not available from backend `daily_bars`.

## Previous Story Intelligence

From E3-S4 (DwellTime) and E3-S3 (OccupancyHeatmap):

- `renderToStaticMarkup` (SSR) does not run `useEffect` — keep all API-call-on-mount tests as mock contract tests.
- ESLint `react-hooks/set-state-in-effect` fires on synchronous `setState({ loading: true })` at top of effect — suppress with `// eslint-disable-next-line react-hooks/set-state-in-effect` on that line.
- State pattern `{ data, loading, error }` + `retryCount` is the established standard — do not invent alternatives.
- Never use `// eslint-disable` directives unless needed for a specific known rule; remove any stale ones after implementation.
- Loading skeleton uses a single fixed-height shimmer block with a `data-testid` attribute.
- Empty state: single early-return block; return message literal must match exactly as stated in the AC.

## File List

- `control-centre/src/api/analytics.js` (UPDATE — add `getDetectionQuality`)
- `control-centre/src/api/__tests__/analytics.test.js` (UPDATE — add tests for `getDetectionQuality`)
- `control-centre/src/components/analytics/AIDetection.jsx` (UPDATE — real data wiring)
- `control-centre/src/components/analytics/__tests__/AIDetection.test.jsx` (NEW — test suite)

## Dev Agent Record

### Pre-Flight
- Assumptions: backend `GET /api/v1/analytics/detection-quality` live (E3-S1 done). `daily_bars` has `total_events` + `fp_count` only — no per-type split. `per_train_uptime` has `train_id` + `uptime_pct` only.
- Open Questions: None.
- Simplicity Check: 2 source files changed, 2 test files changed/created.

### Debug Log
- Day-label test data had wrong weekday comments (2026-05-12 is Tue not Mon) — corrected test fixtures.
- ESLint `react-hooks/set-state-in-effect` suppressed with inline disable on synchronous `setState` at top of effect — pre-existing pattern.
- `computeFpRate` removed — server returns `kpi.fp_rate` as `null | float` directly.
- `incidents` badge dropped from uptime rows — `PerTrainUptime` has no incidents field.
- Bar chart simplified to single-colour total-events bar + FP count below — API does not provide per-type split.

### Completion Notes
- Added `getDetectionQuality(range)` to `src/api/analytics.js` — 3-line addition after `getDwellTime`.
- Rewrote `AIDetection.jsx`: removed all mock imports; `useEffect` fetch with loading skeleton / error state / success; `data-testid="ai-detection-skeleton"`.
- KPI strip reads `kpi.total_events`, `kpi.fp_rate`, `kpi.avg_confidence`, `kpi.fleet_uptime_pct` from API.
- `aggregateBars()` helper: day labels derived via `d.date + 'T00:00:00'` for 7d; W1/W2/etc. weekly aggregation for 14d/30d.
- Uptime list uses `t.train_id` / `t.uptime_pct`; sorted ascending; incidents badge removed.
- 35 new tests; 208/208 total pass; no new lint errors in changed files.

## Change Log

- 2026-05-19: Story created — AI detection quality wired to real backend API
- 2026-05-19: Implemented — getDetectionQuality API function, AIDetection.jsx real data wiring, 35 new tests; 208/208 pass
