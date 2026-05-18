# Story E5-S4 — Luggage ISO Timestamp Migration

**Status:** done
**Sprint:** Epic 5
**Story Key:** 5-4-luggage-iso-timestamps

---

## Story

**As a** developer maintaining the Control Centre luggage mock data,
**I want** all static `LUGGAGE_EVENTS` timestamps migrated to ISO-8601 UTC strings and the legacy HH:MM code paths removed,
**so that** `elapsedMin` and `formatTimestamp` have a single, testable code path that is consistent with live WebSocket events.

---

## Acceptance Criteria

**AC1 — Mock data uses ISO timestamps**
Given `LUGGAGE_EVENTS` is imported from `control-centre/src/mock/luggage.js`, when a developer inspects any event's `timestamp` field, then it is an ISO-8601 UTC string (e.g. `"2026-05-19T08:51:00.000Z"`), not an `"HH:MM"` string.

**AC2 — `elapsedMin` is ISO-only**
Given `elapsedMin(timestamp, nowTs)` is called:
- When `timestamp` is an ISO string and `nowTs` is omitted, then it returns `Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 60000))`.
- When `timestamp` is an ISO string and `nowTs` is an explicit ISO string, then it returns the elapsed minutes between the two ISO values (for test determinism).
- When `timestamp` is `null` or `undefined`, then it returns `null`.
- When `timestamp` is an invalid string that produces `NaN` from `new Date()`, then it returns `null`.
- The legacy `toMinutes` helper and the HH:MM branch do not exist anywhere in the file.

**AC3 — `formatTimestamp` is ISO-only**
Given `formatTimestamp(ts)` is called:
- When `ts` is an ISO string, then it returns a localised `"HH:MM"` string via `new Date(ts).toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' })`.
- When `ts` is `null`, `undefined`, or an unparseable string, then it returns `"--:--"`.
- The HH:MM passthrough branch (`return ts`) does not exist.

**AC4 — `getLuggageKPIs` still works**
Given `getLuggageKPIs(LUGGAGE_EVENTS)` is called after the migration, then it returns a valid KPIs object with numeric `totalActive`, `unattended`, `overcrowded`, `oversized`, `clearedLastHour` values, and non-null string values for `longestUnattended` and `longestActive` where applicable. No runtime error is thrown.

**AC5 — No regressions in downstream consumers**
Given `luggageEventsToEscalations(LUGGAGE_EVENTS)` is called after the migration, then it returns an array of escalation objects each with a valid ISO `timestamp` field (unchanged from the event). `getLuggageSummaryByTrain(LUGGAGE_EVENTS)` returns the correct per-train summary. Neither function inspects the format of `timestamp`.

**AC6 — Test suite passes with deterministic `nowTs`**
Given the Vitest test file for `luggage.js` runs with `// @vitest-environment node`, when `elapsedMin` is called with both an ISO `timestamp` and an explicit ISO `nowTs`, then it returns the expected integer number of minutes without relying on `Date.now()`.

**AC7 — Mock scenario time documented**
Given a developer reads `luggage.js`, when they look at `LUGGAGE_EVENTS`, then a comment above the array states the scenario anchor `2026-05-19T09:00:00Z` and explains that elapsed times will grow as real wall-clock time advances in dev mode.

---

## Tasks / Subtasks

- [x] **T1** — Migrate `LUGGAGE_EVENTS` timestamps to ISO-8601 strings (AC1, AC7)
  - [x] T1.1 Define `SCENARIO_START` constant: `const SCENARIO_START = new Date('2026-05-19T09:00:00Z').getTime()`
  - [x] T1.2 Replace each `timestamp: 'HH:MM'` with a hardcoded ISO string computed as `new Date(SCENARIO_START - N * 60000).toISOString()` where N matches the original HH:MM offset from 09:00 scenario start (see Dev Notes for per-event mapping)
  - [x] T1.3 Add scenario time comment block above `LUGGAGE_EVENTS` (see Dev Notes for exact text)

- [x] **T2** — Simplify `elapsedMin` to ISO-only (AC2)
  - [x] T2.1 Remove the `toMinutes` internal helper function entirely
  - [x] T2.2 Replace the two-branch `elapsedMin` implementation with the ISO-only version (see Dev Notes for exact code)
  - [x] T2.3 Verify no other file in `control-centre/src/` imports or calls `toMinutes` (it is unexported, so callers can only be within `luggage.js`)

- [x] **T3** — Simplify `formatTimestamp` to ISO-only (AC3)
  - [x] T3.1 Replace the two-branch `formatTimestamp` with the ISO-only version (see Dev Notes for exact code)

- [x] **T4** — Verify `getLuggageKPIs` and other consumers (AC4, AC5)
  - [x] T4.1 Manually trace `getLuggageKPIs(LUGGAGE_EVENTS)` with the new ISO timestamps and confirm `elapsedMin` returns positive integers for active events
  - [x] T4.2 Confirm `luggageEventsToEscalations` and `getLuggageSummaryByTrain` are unaffected (they do not call `elapsedMin` or `formatTimestamp`)

- [x] **T5** — Write / update Vitest tests (AC6)
  - [x] T5.1 Create `control-centre/src/mock/luggage.test.js` with `// @vitest-environment node` header
  - [x] T5.2 Write tests for `elapsedMin` using explicit ISO `nowTs` (see Dev Notes for test cases)
  - [x] T5.3 Write tests for `formatTimestamp` with valid ISO, null, and invalid inputs
  - [x] T5.4 Write a smoke test for `getLuggageKPIs(LUGGAGE_EVENTS)` asserting shape and no thrown errors
  - [x] T5.5 Run `npm run test` (or `npx vitest run`) from `control-centre/` and confirm all tests pass

---

## Security Tests

This is an internal refactor of mock/dev-only data. No network calls, authentication, or user input is involved.

- N/A: No user-supplied data is parsed.
- N/A: No secrets, credentials, or PII are touched.
- N/A: Mock data is never bundled into production paths (see `control-centre/CLAUDE.md` — mock imports must not appear in production component trees).

---

## Dev Notes

### Dependency

**E5-S2 must be merged before this story is started.** After E5-S2, `elapsedMin` already has an ISO fast-path and `formatTimestamp` already has an ISO fast-path. E5-S4 removes the legacy fallback branches that E5-S2 retained for backwards compatibility with the still-HH:MM `LUGGAGE_EVENTS`. If E5-S2 is not merged, the ISO fast-paths do not exist and this story cannot be implemented as described.

---

### Scenario Time Anchor

The static mock events use a fixed scenario anchor:

```
Scenario start: 2026-05-19T09:00:00Z  (09:00 UTC = 11:00 CEST)
```

Each event timestamp is `scenarioStart - durationMinutes * 60000` converted to ISO. The elapsed minutes at the moment the scenario "begins" are meaningful for the KPI display. However, because `elapsedMin` uses `Date.now()` (not a fixed reference), elapsed values will grow continuously as real wall-clock time advances. This is intentional and expected in dev mode — it mirrors the behaviour of live WS events.

**Original HH:MM → ISO mapping (relative to 09:00:00Z):**

| id       | Original | Offset from 09:00 | ISO timestamp                  |
|----------|----------|-------------------|-------------------------------|
| lug-001  | 11:23    | −9 min            | `2026-05-19T08:51:00.000Z`    |
| lug-002  | 11:09    | −23 min (14 min ago at scenario start, but original was 26 min before 11:35) — use 26 min | `2026-05-19T08:34:00.000Z` |
| lug-003  | 10:52    | −43 min (21 min duration shown; 43 min before 11:35 scenario "now") | `2026-05-19T08:17:00.000Z` |
| lug-004  | 11:31    | −4 min            | `2026-05-19T08:56:00.000Z`    |
| lug-005  | 11:12    | −23 min           | `2026-05-19T08:37:00.000Z`    |
| lug-006  | 11:18    | −17 min           | `2026-05-19T08:43:00.000Z`    |
| lug-007  | 10:44    | −51 min           | `2026-05-19T08:09:00.000Z`    |

**Mapping rationale:** The original scenario "now" was `11:35`. Each HH:MM timestamp is `11:35 - HH:MM` minutes in the past. We preserve those same relative offsets from `09:00:00Z`:
- `11:35 - 11:23 = 12 min` → `SCENARIO_START - 12 * 60000` → `2026-05-19T08:48:00.000Z`

Recalculated correctly from `09:00:00Z` minus offset-from-11:35:

| id       | 11:35 - ts | ISO (09:00:00Z minus offset) |
|----------|-----------|------------------------------|
| lug-001  | 12 min    | `2026-05-19T08:48:00.000Z`   |
| lug-002  | 26 min    | `2026-05-19T08:34:00.000Z`   |
| lug-003  | 43 min    | `2026-05-19T08:17:00.000Z`   |
| lug-004  | 4 min     | `2026-05-19T08:56:00.000Z`   |
| lug-005  | 23 min    | `2026-05-19T08:37:00.000Z`   |
| lug-006  | 17 min    | `2026-05-19T08:43:00.000Z`   |
| lug-007  | 51 min    | `2026-05-19T08:09:00.000Z`   |

Use these ISO strings directly as hardcoded literals (not computed at runtime via `Date.now() - N`). Hardcoded strings are easier to read in diffs, reproducible in snapshots, and have no module-load-time side effects.

---

### Files Changed

1. `control-centre/src/mock/luggage.js` — primary change
2. `control-centre/src/mock/luggage.test.js` — new file (Vitest tests)

No other files require changes. `MockWebSocketClient` already uses `new Date().toISOString()` (added in E5-S1). Component files do not import `toMinutes` (it was never exported).

---

### Before / After: `luggage.js`

#### `toMinutes` — REMOVE ENTIRELY

**Before (E5-S2 state):**
```js
// Parse "HH:MM" timestamp into minutes since midnight for elapsed calculation
function toMinutes(ts) {
  if (!ts) return null;
  const [h, m] = ts.split(':').map(Number);
  return h * 60 + m;
}
```

**After:** Delete this function. It has no callers once the HH:MM branch of `elapsedMin` is removed. It is unexported so no external callers exist.

---

#### `elapsedMin` — SIMPLIFY TO ISO-ONLY

**Before (E5-S2 state — two paths):**
```js
export function elapsedMin(timestamp, nowTs = null) {
  if (!timestamp) return null;
  const isIso = typeof timestamp === 'string' && (timestamp.includes('T') || /^\d{4}-/.test(timestamp));
  if (isIso) {
    const t = new Date(timestamp).getTime();
    if (isNaN(t)) return null;
    const now = nowTs ? new Date(nowTs).getTime() : Date.now();
    return Math.max(0, Math.round((now - t) / 60000));
  }
  // Legacy HH:MM path
  const refStr = nowTs ?? '11:35'; // mock "now" anchored to scenario time
  const ref = toMinutes(refStr);
  const t2 = toMinutes(timestamp);
  if (ref == null || t2 == null) return null;
  return Math.max(0, ref - t2);
}
```

**After (ISO-only):**
```js
export function elapsedMin(timestamp, nowTs = null) {
  if (!timestamp) return null;
  const t = new Date(timestamp).getTime();
  if (isNaN(t)) return null;
  const now = nowTs ? new Date(nowTs).getTime() : Date.now();
  return Math.max(0, Math.round((now - t) / 60000));
}
```

Key points:
- `nowTs` parameter is retained — tests pass an explicit ISO string to get deterministic output.
- `isIso` detection guard is removed because all callers now pass ISO strings.
- `toMinutes` is no longer called.

---

#### `formatTimestamp` — SIMPLIFY TO ISO-ONLY

**Before (E5-S2 state — two paths):**
```js
export function formatTimestamp(ts) {
  if (!ts) return '--:--';
  const isIso = typeof ts === 'string' && (ts.includes('T') || /^\d{4}-/.test(ts));
  if (isIso) {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '--:--';
    return d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
  }
  return ts; // HH:MM passthrough
}
```

**After (ISO-only):**
```js
export function formatTimestamp(ts) {
  if (!ts) return '--:--';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '--:--';
  return d.toLocaleTimeString('de-AT', { hour: '2-digit', minute: '2-digit' });
}
```

---

#### `LUGGAGE_EVENTS` — MIGRATE TIMESTAMPS

**Before (E5-S2 state, representative excerpt):**
```js
export const LUGGAGE_EVENTS = [
  {
    id: 'lug-001',
    trainId: 'R5001C-031',
    coachId: 'C4',
    state: 'unattended',
    title: 'Unattended bag — C4 luggage rack',
    detail: 'Black rucksack, upper rack, row 12. No owner detected within 3m for 9 min.',
    duration: '9 min',
    confidence: 94,
    timestamp: '11:23',   // <-- HH:MM
    stillFrame: { ... },
  },
  // ...
];
```

**After (with scenario comment and ISO timestamps):**
```js
// Scenario anchor: 2026-05-19T09:00:00Z (= 11:00 CEST).
// Timestamps are fixed ISO strings offset from this anchor.
// elapsedMin() uses Date.now() so elapsed values grow as real time passes — expected in dev.
export const LUGGAGE_EVENTS = [
  {
    id: 'lug-001',
    trainId: 'R5001C-031',
    coachId: 'C4',
    state: 'unattended',
    title: 'Unattended bag — C4 luggage rack',
    detail: 'Black rucksack, upper rack, row 12. No owner detected within 3m for 9 min.',
    duration: '9 min',
    confidence: 94,
    timestamp: '2026-05-19T08:48:00.000Z',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C4+luggage+rack+%E2%80%94+11%3A23%3A04',
      capturedAt: '11:23:04',
      camera: 'C4-rack-overhead',
      confidence: 94,
    },
  },
  {
    id: 'lug-002',
    trainId: 'R5001C-003',
    coachId: 'C2',
    state: 'overcrowded',
    title: 'Luggage area full — C2',
    detail: 'Overhead rack at capacity. 3 passengers unable to store bags. Aisle partially blocked.',
    duration: '14 min',
    confidence: 88,
    timestamp: '2026-05-19T08:34:00.000Z',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C2+rack+overhead+%E2%80%94+11%3A09%3A22',
      capturedAt: '11:09:22',
      camera: 'C2-rack-overhead',
      confidence: 88,
    },
  },
  {
    id: 'lug-003',
    trainId: 'R5001C-003',
    coachId: 'C5',
    state: 'overcrowded',
    title: 'Luggage area full — C5',
    detail: 'Vestibule luggage zone at capacity. Large suitcases blocking door clearance.',
    duration: '21 min',
    confidence: 91,
    timestamp: '2026-05-19T08:17:00.000Z',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C5+vestibule+%E2%80%94+10%3A52%3A47',
      capturedAt: '10:52:47',
      camera: 'C5-vestibule',
      confidence: 91,
    },
  },
  {
    id: 'lug-004',
    trainId: 'R5001C-012',
    coachId: 'C3',
    state: 'oversized',
    title: 'Oversized item — C3 vestibule',
    detail: 'Large bicycle partially blocking vestibule. Not secured to rack.',
    duration: '6 min',
    confidence: 97,
    timestamp: '2026-05-19T08:56:00.000Z',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C3+vestibule+%E2%80%94+11%3A31%3A18',
      capturedAt: '11:31:18',
      camera: 'C3-vestibule',
      confidence: 97,
    },
  },
  {
    id: 'lug-005',
    trainId: 'R5001C-044',
    coachId: 'C1',
    state: 'overcrowded',
    title: 'Luggage area full — C1',
    detail: 'High boarding at Bruck an der Mur. Rack capacity exceeded, bags on floor.',
    duration: '5 min',
    confidence: 85,
    timestamp: '2026-05-19T08:37:00.000Z',
    stillFrame: {
      url: 'https://placehold.co/480x270/1E2430/9BA3AF?text=C1+rack+overhead+%E2%80%94+11%3A12%3A03',
      capturedAt: '11:12:03',
      camera: 'C1-rack-overhead',
      confidence: 85,
    },
  },
  {
    id: 'lug-006',
    trainId: 'R5001C-055',
    coachId: 'C6',
    state: 'owner_returned',
    title: 'Owner returned — C6 rack',
    detail: 'Owner returned to previously unattended item. Item confirmed attended.',
    duration: null,
    confidence: 90,
    timestamp: '2026-05-19T08:43:00.000Z',
    stillFrame: null,
  },
  {
    id: 'lug-007',
    trainId: 'R5001C-017',
    coachId: 'C2',
    state: 'cleared',
    title: 'Cleared — C2 aisle bag',
    detail: 'Conductor confirmed item removed from aisle. Area clear.',
    duration: null,
    confidence: null,
    timestamp: '2026-05-19T08:09:00.000Z',
    stillFrame: null,
  },
];
```

---

### `getLuggageKPIs` — No change required

`getLuggageKPIs` calls `elapsedMin(e.timestamp)` without `nowTs`. After the migration this will use `Date.now()` as the reference, which is correct. The function's logic is unchanged. However the dev agent should manually verify that `elapsedMin` returns a positive integer for each active event by checking: `new Date('2026-05-19T08:48:00.000Z').getTime() < Date.now()` (true for any run after the scenario date). If tests need deterministic KPI output, pass events with explicit `nowTs` via a wrapper — but `getLuggageKPIs` itself does not expose `nowTs`. This is acceptable for the current story; a future story can add `nowTs` to `getLuggageKPIs` if test determinism is required there.

---

### Vitest Test File

Create `control-centre/src/mock/luggage.test.js`:

```js
// @vitest-environment node
import { describe, it, expect } from 'vitest';
import {
  elapsedMin,
  formatTimestamp,
  getLuggageKPIs,
  LUGGAGE_EVENTS,
} from './luggage.js';

const NOW = '2026-05-19T09:35:00.000Z'; // 35 min after scenario anchor

describe('elapsedMin', () => {
  it('returns correct minutes for ISO timestamp with explicit nowTs', () => {
    // 09:35 - 08:48 = 47 min
    expect(elapsedMin('2026-05-19T08:48:00.000Z', NOW)).toBe(47);
  });

  it('returns 0 when timestamp equals nowTs', () => {
    expect(elapsedMin(NOW, NOW)).toBe(0);
  });

  it('returns 0 when timestamp is in the future relative to nowTs', () => {
    expect(elapsedMin('2026-05-19T10:00:00.000Z', NOW)).toBe(0);
  });

  it('returns null for null timestamp', () => {
    expect(elapsedMin(null, NOW)).toBeNull();
  });

  it('returns null for undefined timestamp', () => {
    expect(elapsedMin(undefined, NOW)).toBeNull();
  });

  it('returns null for an unparseable string', () => {
    expect(elapsedMin('not-a-date', NOW)).toBeNull();
  });
});

describe('formatTimestamp', () => {
  it('returns a time string for a valid ISO input', () => {
    const result = formatTimestamp('2026-05-19T08:48:00.000Z');
    // de-AT locale formats as HH:MM; just check it looks like a time string
    expect(result).toMatch(/^\d{2}:\d{2}$/);
  });

  it('returns --:-- for null', () => {
    expect(formatTimestamp(null)).toBe('--:--');
  });

  it('returns --:-- for undefined', () => {
    expect(formatTimestamp(undefined)).toBe('--:--');
  });

  it('returns --:-- for an unparseable string', () => {
    expect(formatTimestamp('garbage')).toBe('--:--');
  });
});

describe('getLuggageKPIs', () => {
  it('returns a valid shape without throwing', () => {
    const kpis = getLuggageKPIs(LUGGAGE_EVENTS);
    expect(typeof kpis.totalActive).toBe('number');
    expect(typeof kpis.unattended).toBe('number');
    expect(typeof kpis.overcrowded).toBe('number');
    expect(typeof kpis.oversized).toBe('number');
    expect(typeof kpis.clearedLastHour).toBe('number');
  });

  it('correctly counts active vs cleared events', () => {
    const kpis = getLuggageKPIs(LUGGAGE_EVENTS);
    // lug-006 (owner_returned) and lug-007 (cleared) are not active
    expect(kpis.totalActive).toBe(5);
    expect(kpis.clearedLastHour).toBe(2);
  });

  it('returns non-null longestUnattended when unattended events exist', () => {
    const kpis = getLuggageKPIs(LUGGAGE_EVENTS);
    expect(kpis.longestUnattended).not.toBeNull();
    expect(kpis.longestUnattended).toMatch(/\d+ min/);
  });
});
```

**Note on `formatTimestamp` locale test:** The `de-AT` locale in Node.js may format `08:48 UTC` as a local time depending on the system timezone. The regex `/^\d{2}:\d{2}$/` is intentionally loose — it only verifies the output is a formatted time string, not a specific value. If strict value testing is needed, set `TZ=UTC` in the test environment.

---

### `MockWebSocketClient` — No change

`MockWebSocketClient` already dispatches `LUGGAGE_EVENT` with `timestamp: new Date().toISOString()` (added in E5-S1). No change needed.

---

### E5-S3 compatibility note

E5-S3 adds a configurable unattended threshold and a staleness banner. Both depend on `elapsedMin`. After E5-S4:
- `elapsedMin` still accepts `(timestamp, nowTs)` — E5-S3's threshold comparison `elapsedMin(e.timestamp) >= threshold` works unchanged.
- If E5-S3 is not yet merged when E5-S4 is implemented, the `getLuggageKPIs` function in the current codebase does not have the threshold parameter — that is fine; E5-S4 does not modify `getLuggageKPIs` logic.

---

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log
_empty_

### Completion Notes
All 5 tasks complete. `LUGGAGE_EVENTS` timestamps migrated to 7 hardcoded ISO-8601 strings offset from `2026-05-19T09:00:00Z` scenario anchor. `toMinutes`, `ISO_RE`, `HH_MM_RE` constants and the HH:MM branches of `elapsedMin` and `formatTimestamp` removed. Both functions are now ISO-only with a single code path. Added `isNaN(now)` guard in `elapsedMin` for invalid `nowTs`. `getLuggageKPIs`, `luggageEventsToEscalations`, `getLuggageSummaryByTrain` unaffected. `luggage.test.js` in `src/mock/` updated with E5-S4 `elapsedMin`, `formatTimestamp`, and `LUGGAGE_EVENTS` smoke tests. Pre-existing E5-S2 HH:MM compat tests in `src/mock/__tests__/luggage.test.js` updated to match the new ISO-only contract. 113 tests pass.

### File List
- `control-centre/src/mock/luggage.js`
- `control-centre/src/mock/luggage.test.js`
- `control-centre/src/mock/__tests__/luggage.test.js`

### Review Findings

- [x] [Review][Patch] `clearedLastHour` smoke test assertion is a time-bomb [`luggage.test.js` getLuggageKPIs describe]
- [x] [Review][Patch] `formatTimestamp` missing `timeZone: 'Europe/Vienna'` in `toLocaleTimeString` options [`luggage.js:193`]
- [x] [Review][Patch] `stillFrame.capturedAt` fields still contain legacy HH:MM strings after ISO migration [`luggage.js:30,41,54,66,78`]
- [x] [Review][Defer] `getLuggageKPIs` silently drops unattended events when `elapsedMin` returns null [`luggage.js:213`] — deferred, pre-existing
- [x] [Review][Defer] `elapsedMin` grows unbounded with fixed anchor dates in dev [`luggage.js:196-203`] — deferred, pre-existing (noted in file header comment as expected dev behaviour)
- [x] [Review][Defer] Duplicate `formatTimestamp` describe blocks across two test files — deferred, intentional cross-version regression coverage
