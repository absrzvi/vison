# Story E5-S2 — Luggage Monitoring Live UI

**Status:** ready-for-dev
**Sprint:** Epic 5
**Story Key:** 5-2-luggage-monitoring-live-ui

---

## Story

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab to display a loading state while waiting for the first WS events, show live event cards with correctly formatted timestamps and elapsed time, surface per-coach status in the train detail grid from live `coachId` values, and allow me to filter events by type without the filter resetting on new arrivals,
**so that** I can monitor live luggage alerts without confusion from broken timestamps, incorrect coach attribution, or disorienting filter resets.

---

## Acceptance Criteria

**AC1 — Loading skeleton:** Given `luggageEvents` is empty AND the WS connection is not yet established (`!wsReady`), when the Luggage Monitoring tab is rendered, then a skeleton placeholder is shown instead of the empty-state message "No luggage events received yet." The empty-state message is only shown once `wsReady` is true and `luggageEvents.length === 0`.

**AC2 — ISO timestamp display:** Given a live luggage event arrives with an ISO-8601 timestamp (e.g. `2026-05-18T11:23:04Z`), when the event is rendered in `LuggageFeed` and `LuggageTrainDetail`, then the timestamp is displayed as `HH:MM` in local time (e.g. `11:23`) — not as a raw ISO string. The `elapsedMin` function must compute elapsed time correctly from ISO timestamps (not only from HH:MM strings).

**AC3 — Elapsed time from ISO timestamps:** Given a live event with an ISO timestamp, when `elapsedMin(event.timestamp)` is called, then it returns the correct elapsed minutes based on `Date.now()` as the reference (not the hardcoded `"11:35"` mock anchor). Mock events that use HH:MM timestamps must continue to work (backwards compatible). The threshold classes `luggage-item__elapsed--warn` (≥15 min) and `luggage-item__elapsed--crit` (≥25 min) must fire correctly for live events.

**AC4 — KPI strip correct for live events:** Given live events arrive with ISO timestamps, when `getLuggageKPIs(events)` is called, then `longestUnattended` and `longestActive` return correct elapsed minute strings (e.g. `"4 min"`) based on real wall-clock time rather than always returning `"0 min"`.

**AC5 — Coach grid correct for live events:** Given `LuggageMonitoring` receives live events where `coachId` is already normalised to OEBB format (e.g. `C4`) by `RealWebSocketClient.normaliseCoachId`, when the operator drills into a train, then the coach grid in `LuggageTrainDetail` correctly highlights that coach's cell. No additional normalisation is needed in the UI layer — this AC verifies end-to-end correctness of the E5-S1 normalisation patch.

**AC5b — `getLuggageSummaryByTrain` groups by normalised coachId:** Given live events with `coachId: "C4"` arrive, when `getLuggageSummaryByTrain(events)` is called and the train detail opens, the per-coach grid shows the correct coach highlighted — not "no events" for that cell.

**AC6 — Filter persistence on new arrivals:** Given an operator has set a type filter (e.g. `Unattended`) in `LuggageFeed`, when a new luggage event arrives via WS and `luggageEvents` updates, then the selected filter is NOT reset — the operator's filter selection persists across re-renders.

**AC7 — Confidence displayed as percentage:** Given a live event has `confidence: 0.94` (decimal 0–1 from the WS payload), when rendered in `LuggageFeed`, then the confidence badge shows `94%` (not `0.94%`). The existing mock events use integer percentages (e.g. `94`) — the render path must handle both decimal (0–1) and integer (0–100) formats.

**AC8 — `wsReady` exposed from context:** Given `FleetContext` already tracks `wsReady`, when `LuggageMonitoring` reads from context, then it can access `wsReady` to gate the loading skeleton (AC1). No new context state is needed — `wsReady` is already in context value.

---

## Tasks / Subtasks

- [ ] **T1** Fix `elapsedMin` and timestamp display for ISO timestamps (AC2, AC3, AC4)
  - [ ] T1.1 Update `elapsedMin(timestamp, nowTs)` in `mock/luggage.js` to detect ISO-8601 strings (contains `T` or `-`) and compute elapsed from `Date.now()` instead of parsing as `HH:MM`. HH:MM strings continue to use the existing mock anchor `"11:35"`.
  - [ ] T1.2 Add `formatTimestamp(ts)` helper in `mock/luggage.js` that returns `HH:MM` from ISO strings (via `new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' })`) and passes through HH:MM strings unchanged.
  - [ ] T1.3 In `LuggageFeed.jsx`, replace `{ev.timestamp}` usage in elapsed display with `elapsedMin(ev.timestamp)` (already done) — verify no raw ISO appears in rendered output. Replace any timestamp display text with `formatTimestamp(ev.timestamp)`.
  - [ ] T1.4 In `LuggageTrainDetail.jsx`, replace `{ev.timestamp}` in the event row time column with `formatTimestamp(ev.timestamp)`. Import `formatTimestamp` from `../../mock/luggage`.
  - [ ] T1.5 Update `getLuggageKPIs` — it calls `elapsedMin` internally; once T1.1 is done, KPI strip automatically computes correct elapsed for live events (no further changes needed — verify in tests).

- [ ] **T2** Loading skeleton for Luggage tab (AC1, AC8)
  - [ ] T2.1 In `LuggageMonitoring.jsx`, destructure `wsReady` from `useFleetData()`.
  - [ ] T2.2 Create `LuggageMonitoringSkeleton` component in `LuggageMonitoring.jsx` (inline, not a separate file) — renders a skeleton KPI strip (6 shimmer blocks matching `LuggageKpiStrip` layout) and 3 skeleton feed items below.
  - [ ] T2.3 Render logic: `if (!wsReady) return <LuggageMonitoringSkeleton />` (before the `events.length === 0` empty-state check). Once `wsReady && events.length === 0` → show empty-state message. Once `wsReady && events.length > 0` → show normal UI.
  - [ ] T2.4 Skeleton uses existing `.skeleton-pulse` CSS class (already in `index.css`) — no new CSS variables.

- [ ] **T3** Confidence decimal normalisation (AC7)
  - [ ] T3.1 In `LuggageFeed.jsx`, update the confidence display: `{Math.round(ev.confidence > 1 ? ev.confidence : ev.confidence * 100)}%`. Apply the same to `confClass` input: `confClass(ev.confidence > 1 ? ev.confidence : ev.confidence * 100)`.
  - [ ] T3.2 Verify `confClass` thresholds still work correctly for both integer (e.g. `94`) and decimal (e.g. `0.94`) inputs after normalisation.

- [ ] **T4** Verify end-to-end coach grid correctness (AC5, AC5b)
  - [ ] T4.1 No code change needed — `normaliseCoachId` in `RealWebSocketClient` already converts `car-4` → `C4`. Verify in tests that `getLuggageSummaryByTrain` with `coachId: 'C4'` maps correctly to the `allCoachIds` array (`['C1','C2',...,'C8']`) used in `LuggageMonitoring`.
  - [ ] T4.2 Add test: `getLuggageSummaryByTrain` with a live-shaped event (`coachId: 'C4'`) produces a map entry that matches the allCoachIds array key — so the coach grid cell highlights correctly.

- [ ] **T5** Tests (Vitest, `// @vitest-environment node`)
  - [ ] T5.1 `elapsedMin` with ISO timestamp returns a positive integer (> 0) based on `Date.now()`.
  - [ ] T5.2 `elapsedMin` with HH:MM string continues to use `"11:35"` anchor — backwards compatible.
  - [ ] T5.3 `formatTimestamp` with ISO string returns `HH:MM` format string.
  - [ ] T5.4 `formatTimestamp` with HH:MM string passes through unchanged.
  - [ ] T5.5 `getLuggageKPIs` with live ISO-timestamped events returns a positive `longestUnattended` value (not `null`, not `"0 min"`).
  - [ ] T5.6 Confidence normalisation: `Math.round(0.94 > 1 ? 0.94 : 0.94 * 100)` === `94`; `Math.round(94 > 1 ? 94 : 94 * 100)` === `94`.
  - [ ] T5.7 `getLuggageSummaryByTrain` with `coachId: 'C4'` produces a map key matching the `allCoachIds` `'C4'` entry.

---

## Security Tests

**UI / client-side security:**
- [ ] No tokens or sensitive data written to localStorage or sessionStorage
- [ ] Error states display generic messages — no internal API detail exposed

**OEBB-specific:**
- [ ] Luggage event confidence values from WS are clamped/normalised before display — no raw `NaN` or negative values rendered

---

## Dev Notes

### Architecture — what this story changes

This story fixes display-layer issues introduced by E5-S1 switching from static mock data (HH:MM timestamps, integer confidence) to live WS data (ISO timestamps, decimal confidence). No new WS messages, no new context state, no new API calls.

**Files to UPDATE:**
1. `control-centre/src/mock/luggage.js` — `elapsedMin`, `getLuggageKPIs`, add `formatTimestamp` export
2. `control-centre/src/components/luggage/LuggageMonitoring.jsx` — add `wsReady`, skeleton, gate empty-state
3. `control-centre/src/components/luggage/LuggageFeed.jsx` — `formatTimestamp` for timestamp display, confidence normalisation
4. `control-centre/src/components/luggage/LuggageTrainDetail.jsx` — `formatTimestamp` for event row time column

**Files NOT touched:**
- `FleetContext.jsx` — already correct after E5-S1 patches
- `RealWebSocketClient.js` — `normaliseCoachId` already correct
- `LuggageKpiStrip.jsx` — gets correct values once `getLuggageKPIs` is fixed
- Any CSS file — skeleton uses existing `.skeleton-pulse`

### Current state of `elapsedMin` (must understand before changing)

```js
// control-centre/src/mock/luggage.js — current implementation
function toMinutes(ts) {
  if (!ts) return null;
  const [h, m] = ts.split(':').map(Number);
  return h * 60 + m;
}

export function elapsedMin(timestamp, nowTs = null) {
  const refStr = nowTs ?? '11:35'; // mock "now" anchored to scenario time
  const ref = toMinutes(refStr);
  const t = toMinutes(timestamp);
  if (ref == null || t == null) return null;
  return Math.max(0, ref - t);
}
```

**Problem:** When `timestamp` is `"2026-05-18T11:23:04Z"`, `toMinutes` splits on `:` and gets `["2026-05-18T11", "23", "04Z"]` → `h = NaN`, returns `null`. So `elapsed` is null and the elapsed badge never renders.

**Fix strategy:** Detect ISO strings and use `Date.now()`:
```js
export function elapsedMin(timestamp, nowTs = null) {
  if (!timestamp) return null;
  // ISO-8601 detection: contains 'T' (standard) or matches YYYY-MM-DD
  const isIso = typeof timestamp === 'string' && (timestamp.includes('T') || /^\d{4}-/.test(timestamp));
  if (isIso) {
    const t = new Date(timestamp).getTime();
    if (isNaN(t)) return null;
    const now = nowTs ? new Date(nowTs).getTime() : Date.now();
    return Math.max(0, Math.round((now - t) / 60000));
  }
  // Legacy HH:MM path — unchanged, uses '11:35' mock anchor
  const refStr = nowTs ?? '11:35';
  const ref = toMinutes(refStr);
  const t2 = toMinutes(timestamp);
  if (ref == null || t2 == null) return null;
  return Math.max(0, ref - t2);
}
```

### `formatTimestamp` — new export

```js
export function formatTimestamp(ts) {
  if (!ts) return '--:--';
  const isIso = typeof ts === 'string' && (ts.includes('T') || /^\d{4}-/.test(ts));
  if (isIso) {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '--:--';
    return d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
  }
  return ts; // already HH:MM
}
```

**Import** this in `LuggageFeed.jsx` and `LuggageTrainDetail.jsx`:
```js
import { LUGGAGE_STATES, NEXT_STATION, elapsedMin, formatTimestamp } from '../../mock/luggage';
```

### `LuggageFeed.jsx` — timestamp display location

Currently line 84 in the event row renders `{ev.timestamp}` — this is inside `renderCard`. There is **no** direct `{ev.timestamp}` output visible at present because the feed card doesn't show a raw timestamp — it only shows `elapsed`. But `LuggageTrainDetail.jsx` line 84 renders `{ev.timestamp}` directly in `.luggage-train-detail__event-time`.

`LuggageFeed.jsx` uses `elapsedMin(ev.timestamp)` for the elapsed badge — this will be fixed by T1.1 automatically. No further timestamp changes needed in `LuggageFeed.jsx` itself (only confidence normalisation in T3).

### Confidence value shapes

**Mock events** (`LUGGAGE_EVENTS` in `mock/luggage.js`): `confidence: 94` (integer, 0–100)
**Live WS events** (from `RealWebSocketClient`): `confidence: safePayload.confidence ?? null` where backend sends decimal `0.94`

Current `confClass` function:
```js
const confClass = (pct) => {
  if (pct == null) return '';
  if (pct >= 85) return 'luggage-item__confidence--high';
  if (pct >= 70) return 'luggage-item__confidence--med';
  return 'luggage-item__confidence--low';
};
```

Fix for both display and class — normalise to 0–100 range first:
```js
const normaliseConf = (c) => c == null ? null : (c <= 1 ? Math.round(c * 100) : Math.round(c));
```

Then use `normaliseConf(ev.confidence)` for both the display value and `confClass` input.

### Skeleton design

Pattern from E2-S7 (loading skeletons story). Use `.skeleton-pulse` CSS class already defined in `index.css`. Example from `KpiStripSkeleton`:

```jsx
function LuggageMonitoringSkeleton() {
  return (
    <div className="luggage-monitoring luggage-monitoring--loading">
      <div className="luggage-kpi-strip luggage-kpi-strip--skeleton">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="lkpi">
            <div className="skeleton-pulse" style={{ width: 48, height: 28, borderRadius: 4 }} />
            <div className="skeleton-pulse" style={{ width: 80, height: 11, borderRadius: 3, marginTop: 4 }} />
          </div>
        ))}
      </div>
      <div className="luggage-monitoring__body">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="skeleton-pulse" style={{ height: 64, margin: '6px 16px', borderRadius: 6 }} />
        ))}
      </div>
    </div>
  );
}
```

### `wsReady` in context

Already available in `FleetContext` value (added in E2-S7). `LuggageMonitoring` does not currently destructure it but `useFleetData()` exposes it:
```js
const { luggageEvents: events, wsReady } = useFleetData();
```

### Filter persistence on new arrivals (AC6)

`LuggageFeed`'s `typeFilter` state is local to the component and lives in `useState('all')`. Since `luggageEvents` changing causes `LuggageMonitoring` to re-render but **not** remount `LuggageFeed` (it's the same component instance in the same conditional branch), the filter state is preserved automatically. **No code change needed for AC6** — this is a verification AC. Include in tests by checking that the filter state is not reset when the parent passes new events (pure logic test: same component instance means same state).

The potential trap: if `LuggageMonitoring` switches between `<LuggageTrainDetail>` and `<LuggageFeed>` (when `selectedTrainId` changes), that does unmount/remount `LuggageFeed`. This is expected behaviour (user navigated away). AC6 only applies when new events arrive without the user switching views.

### What MUST NOT break

- **Mock events** (`LUGGAGE_EVENTS` static array) still use HH:MM timestamps — `elapsedMin` and `formatTimestamp` must handle them with the old anchor logic
- **`getLuggageKPIs`** calls `elapsedMin` internally — after fix, KPIs will correctly reflect real elapsed for live events
- **`luggageEventsToEscalations`** does not use timestamps — not affected
- **`LuggageKpiStrip`** receives computed KPI strings — no change needed there
- **72 existing tests must continue passing** — no regressions

### Test environment

`// @vitest-environment node` — no jsdom. All tests must be pure function tests. Use the pattern from `FleetContextLuggage.test.js` and `SystemHealth.test.js`: import the production functions and test them directly. No component render tests.

For `elapsedMin` with live ISO timestamps, use `Date.now()` as the reference — in tests, provide a fixed `nowTs` ISO string to get deterministic output:
```js
// test:
const ts = new Date(Date.now() - 5 * 60 * 1000).toISOString(); // 5 minutes ago
expect(elapsedMin(ts)).toBeGreaterThanOrEqual(4); // allow 1 min tolerance
// OR pass explicit nowTs:
const event_ts = '2026-05-19T10:00:00Z';
const now_ts   = '2026-05-19T10:05:00Z';
expect(elapsedMin(event_ts, now_ts)).toBe(5);
```

### File list (expected changes)

| File | Change |
|---|---|
| `control-centre/src/mock/luggage.js` | UPDATE `elapsedMin` for ISO support; ADD `formatTimestamp` export |
| `control-centre/src/components/luggage/LuggageMonitoring.jsx` | ADD `wsReady`, skeleton, gate empty-state |
| `control-centre/src/components/luggage/LuggageFeed.jsx` | ADD confidence normalisation; import `formatTimestamp` |
| `control-centre/src/components/luggage/LuggageTrainDetail.jsx` | ADD `formatTimestamp` for event time column |
| `control-centre/src/mock/__tests__/luggage.test.js` | NEW — unit tests for `elapsedMin`, `formatTimestamp`, `getLuggageKPIs`, `getLuggageSummaryByTrain` |

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log

### Completion Notes

### File List
