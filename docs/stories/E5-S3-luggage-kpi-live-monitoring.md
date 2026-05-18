# Story E5-S3 — Luggage KPI Live Monitoring

**Status:** review
**Sprint:** Epic 5
**Story Key:** 5-3-luggage-kpi-live-monitoring

---

## Story

As a control-centre operator,
I want the Luggage Monitoring tab to show a staleness warning when no luggage events have arrived recently, the KPI strip to flag unattended bags only once they exceed a configurable age threshold, and the Live Monitoring KPI tile to reflect the correct luggage alert count,
so that I have accurate, trustworthy situational awareness and can tune alert sensitivity to my operational context.

---

## Acceptance Criteria

**AC1 — Unattended threshold preference persisted**
Given an operator opens the Preferences panel,
When they select a new unattended bag age threshold (1, 2, 5, 10, or 15 minutes),
Then the value is PATCHed to `PATCH /api/v1/operators/me/preferences` with body `{ unattended_threshold_min: N }`, stored in localStorage under key `oebb.cc.unattendedThresholdMinutes`, and the UI reflects the new value immediately (optimistic update).

**AC2 — Server value wins on load**
Given the app initialises,
When `GET /api/v1/operators/me/preferences` returns `unattended_threshold_min`,
Then `unattendedThresholdMinutes` in FleetContext is set to the server value and localStorage is updated accordingly.

**AC3 — PATCH failure reverts**
Given an operator selects a new unattended threshold,
When the PATCH call fails (network error or 4xx/5xx),
Then the previous value is restored in state and localStorage, and a toast "Preference not saved — please retry" appears in the panel.

**AC4 — getLuggageKPIs threshold-aware**
Given a set of unattended bag events each with an ISO timestamp,
When `getLuggageKPIs(events, thresholdMin)` is called,
Then:
- `unattended` = all events with `state === 'unattended'` (raw count, unchanged)
- `unattendedAlerts` = events with `state === 'unattended'` AND `elapsedMin(timestamp) >= thresholdMin` (alert-worthy subset)
- `totalActive` includes all active events regardless of threshold (unchanged semantics — used by the Live Monitoring KPI tile for total count)

**AC5 — LuggageKpiStrip reflects threshold**
Given `unattendedAlerts` is present in the kpis object,
When the LuggageKpiStrip renders,
Then:
- The "Unattended Items" tile value displays `kpis.unattendedAlerts` (not raw `unattended`)
- The tile is styled `lkpi--red` only when `kpis.unattendedAlerts > 0`
- The tile label reads "Unattended Alerts" to distinguish from the raw count

**AC6 — Live Monitoring KPI tile unaffected**
Given luggage events are present,
When the Live Monitoring KpiStrip renders,
Then `luggageAlerts` prop passed to it continues to equal `luggageKpis.totalActive` (all active events, threshold-agnostic), so the tile count does not change from current behaviour.

**AC7 — Luggage tab staleness banner**
Given the operator is on the Luggage Monitoring tab,
When no `LUGGAGE_EVENT` WS message has been received for longer than `stalenessThresholdSeconds` (from FleetContext),
Then a stale banner appears: "Luggage data may be stale — last event over N minutes ago."
When a new LUGGAGE_EVENT arrives,
Then the banner disappears.

**AC8 — Luggage tab no banner when fresh**
Given a LUGGAGE_EVENT arrived within `stalenessThresholdSeconds`,
When the Luggage Monitoring tab renders,
Then no stale banner is visible.

**AC9 — localStorage fallback on cold start**
Given the preferences API is unreachable on app start,
When the app initialises,
Then `unattendedThresholdMinutes` falls back to the localStorage value if present, else `DEFAULT_UNATTENDED_THRESHOLD_MINUTES` (5).

**AC10 — Preferences panel renders new control**
Given the operator opens the Preferences panel,
Then a "Unattended bag alert after" segmented control is visible with options [1, 2, 5, 10, 15] minutes and the current value selected.

---

## Tasks / Subtasks

- [x] T1 — Add `unattendedThresholdMinutes` constants (AC1, AC2, AC9)
  - [x] T1.1 — In `control-centre/src/constants/preferences.js` add:
    - `DEFAULT_UNATTENDED_THRESHOLD_MINUTES = 5`
    - `UNATTENDED_THRESHOLD_OPTIONS = [1, 2, 5, 10, 15]`
    - `LS_KEY_UNATTENDED_THRESHOLD = 'oebb.cc.unattendedThresholdMinutes'`

- [x] T2 — Wire `unattendedThresholdMinutes` into FleetContext (AC1, AC2, AC3, AC9)
  - [x] T2.1 — Import new constants in `FleetContext.jsx`
  - [x] T2.2 — Add state initialised from localStorage with `DEFAULT_UNATTENDED_THRESHOLD_MINUTES` fallback
  - [x] T2.3 — In the `getPreferences()` effect, read `prefs.unattended_threshold_min` and reconcile state + localStorage (same pattern as `alertThresholdSeconds`)
  - [x] T2.4 — Add `updateUnattendedThreshold` callback (optimistic update → PATCH `{ unattended_threshold_min: value }` → revert on error), same pattern as `updateAlertThreshold`
  - [x] T2.5 — Expose `unattendedThresholdMinutes` and `updateUnattendedThreshold` on the context value object

- [x] T3 — Extend `getLuggageKPIs` with threshold param (AC4)
  - [x] T3.1 — In `control-centre/src/mock/luggage.js`, change signature to `getLuggageKPIs(events, thresholdMin = 5)`
  - [x] T3.2 — Compute `unattendedAlerts` = unattended events where `elapsedMin(e.timestamp) >= thresholdMin`
  - [x] T3.3 — Add `unattendedAlerts` to the returned object; keep `unattended` (raw count) and `totalActive` unchanged

- [x] T4 — Update LuggageKpiStrip (AC5)
  - [x] T4.1 — Change the "Unattended Items" tile to display `kpis.unattendedAlerts ?? kpis.unattended` (graceful fallback)
  - [x] T4.2 — Change tile label to "Unattended Alerts"
  - [x] T4.3 — Apply `lkpi--red` only when `kpis.unattendedAlerts > 0`

- [x] T5 — Pass threshold to getLuggageKPIs call sites (AC4, AC5, AC6)
  - [x] T5.1 — In `LuggageMonitoring.jsx`, read `unattendedThresholdMinutes` from `useFleetData()` and pass as second arg to `getLuggageKPIs(events, unattendedThresholdMinutes)`
  - [x] T5.2 — In `LiveMonitoring.jsx`, `getLuggageKPIs(luggageEvents)` — leave as-is (no threshold, uses default 5, `totalActive` is threshold-agnostic so AC6 holds)

- [x] T6 — Staleness banner on Luggage tab (AC7, AC8)
  - [x] T6.1 — In `LuggageMonitoring.jsx`, read `lastUpdate` and `stalenessThresholdSeconds` from `useFleetData()`
  - [x] T6.2 — Derive `isLuggageStale`: `lastUpdate && (Date.now() - lastUpdate.getTime()) > stalenessThresholdSeconds * 1000`
    - Note: `lastUpdate` is set on every LUGGAGE_EVENT and FLEET_STATE in FleetContext, so this is a reasonable proxy. If the team later wants a luggage-specific last-event timestamp, that is out of scope for this story.
  - [x] T6.3 — Render stale banner above `LuggageKpiStrip` when `isLuggageStale` is true, with text: "Luggage data may be stale — last update over N minutes ago." where N = `Math.round(stalenessThresholdSeconds / 60)`
  - [x] T6.4 — Add `.luggage-monitoring__stale-banner` CSS class in `LuggageMonitoring.css` using `--color-amber` custom property (mirrors `.live-monitoring__stale-banner`)

- [x] T7 — Add unattended threshold control to OperatorPreferences panel (AC1, AC3, AC10)
  - [x] T7.1 — In `OperatorPreferences.jsx`, destructure `unattendedThresholdMinutes` and `updateUnattendedThreshold` from `useFleetData()`
  - [x] T7.2 — Import `UNATTENDED_THRESHOLD_OPTIONS` from constants
  - [x] T7.3 — Add a `SegmentedControl` row below the existing two controls, label "Unattended bag alert after", options `UNATTENDED_THRESHOLD_OPTIONS`, `formatLabel` = `(n) => \`${n} min\``
  - [x] T7.4 — Add `handleUnattendedCommit` async handler that calls `updateUnattendedThreshold(val)` and shows toast on error (same pattern as existing handlers)

- [x] T8 — Pure logic tests (AC4)
  - [x] T8.1 — In `control-centre/src/mock/luggage.test.js` (create if absent), add `// @vitest-environment node`
  - [x] T8.2 — Test: events with `elapsedMin < thresholdMin` → `unattendedAlerts === 0`
  - [x] T8.3 — Test: events with `elapsedMin >= thresholdMin` → counted in `unattendedAlerts`
  - [x] T8.4 — Test: `totalActive` is unchanged by threshold (all active states counted)
  - [x] T8.5 — Test: `unattended` raw count is unchanged by threshold

---

## Security Tests

None required for this story — no new API surfaces, no user input leaves the client beyond an integer preference already validated server-side. Existing PATCH validation on `unattended_threshold_min` is the backend's responsibility.

---

## Dev Notes

### File inventory — what changes

| File | Change |
|---|---|
| `control-centre/src/constants/preferences.js` | Add 3 new exports |
| `control-centre/src/context/FleetContext.jsx` | Add state, effect reconcile, `updateUnattendedThreshold` callback, expose on context |
| `control-centre/src/mock/luggage.js` | `getLuggageKPIs` new `thresholdMin` param, add `unattendedAlerts` to return |
| `control-centre/src/components/luggage/LuggageKpiStrip.jsx` | Use `unattendedAlerts`, update label |
| `control-centre/src/components/luggage/LuggageMonitoring.jsx` | Pass threshold to `getLuggageKPIs`, read `lastUpdate`+`stalenessThresholdSeconds`, render stale banner |
| `control-centre/src/components/luggage/LuggageMonitoring.css` | Add `.luggage-monitoring__stale-banner` |
| `control-centre/src/components/shell/OperatorPreferences.jsx` | Add third `SegmentedControl` row |
| `control-centre/src/mock/luggage.test.js` | New test file |

### What must NOT change

- `LiveMonitoring.jsx` line `luggageAlerts={luggageKpis.totalActive}` — do not touch (AC6).
- `applyLuggageEvent`, `luggageEventsToEscalations`, `getLuggageSummaryByTrain` — no changes.
- WS message handling in `FleetContext.jsx` — no new message types, no changes to `LUGGAGE_EVENT` handler.
- `elapsedMin` function — already handles ISO timestamps after E5-S2; do not regress.

### FleetContext pattern — exact mirror for new preference

Current pattern for `alertThresholdSeconds` (lines 44–47, 185–203, 208–219 in `FleetContext.jsx`):

```js
// 1. State init from localStorage
const [alertThresholdSeconds, setAlertThresholdSeconds] = useState(() => {
  const parsed = parseInt(localStorage.getItem(LS_KEY_ALERT_THRESHOLD), 10);
  return Number.isFinite(parsed) ? parsed : DEFAULT_ALERT_THRESHOLD_SECONDS;
});

// 2. Reconcile from server (getPreferences effect)
const serverThreshold = prefs.threshold_sec;
setAlertThresholdSeconds(prev => {
  if (prev !== serverThreshold) {
    localStorage.setItem(LS_KEY_ALERT_THRESHOLD, String(serverThreshold));
    return serverThreshold;
  }
  return prev;
});

// 3. Update callback
const updateAlertThreshold = useCallback(async (value) => {
  let prevValue;
  setAlertThresholdSeconds(prev => { prevValue = prev; return value; });
  try {
    await patchPreferences({ threshold_sec: value });
    localStorage.setItem(LS_KEY_ALERT_THRESHOLD, String(value));
    return null;
  } catch (err) {
    setAlertThresholdSeconds(prevValue);
    return err;
  }
}, []);
```

Replicate exactly for `unattendedThresholdMinutes`:
- State var: `unattendedThresholdMinutes` / setter `setUnattendedThresholdMinutes`
- LS key: `LS_KEY_UNATTENDED_THRESHOLD`
- Default: `DEFAULT_UNATTENDED_THRESHOLD_MINUTES`
- Server key from prefs: `prefs.unattended_threshold_min`
- PATCH body: `{ unattended_threshold_min: value }`
- Callback name: `updateUnattendedThreshold`

### getLuggageKPIs — exact diff

Current signature: `export function getLuggageKPIs(events)`
New signature: `export function getLuggageKPIs(events, thresholdMin = 5)`

Add after `const unattendedEvents = active.filter(...)`:
```js
const unattendedAlerts = unattendedEvents.filter(
  e => elapsedMin(e.timestamp) >= thresholdMin
);
```

Add to returned object:
```js
unattendedAlerts: unattendedAlerts.length,
```

All other fields (`totalActive`, `unattended`, `overcrowded`, `oversized`, `clearedLastHour`, `longestUnattended`, `longestActive`) remain unchanged.

### elapsedMin note

After E5-S2, `elapsedMin` supports ISO 8601 timestamps. The mock `refStr = '11:35'` fallback is only hit when `nowTs` is null and `timestamp` is an old `HH:MM` string. Live WS events carry ISO timestamps and `elapsedMin` will compute from `Date.now()` in the E5-S2 fix. Do not alter `elapsedMin` in this story.

### Stale banner in LuggageMonitoring

`lastUpdate` in FleetContext is set on every `LUGGAGE_EVENT` and `FLEET_STATE` message (lines 99 and 109 in `FleetContext.jsx`). Using it as the luggage-specific staleness proxy is acceptable for this story — a dedicated `luggageLastUpdate` timestamp is a future improvement.

Derive in component render (not a useMemo — simple boolean):
```js
const { luggageEvents: events, lastUpdate, stalenessThresholdSeconds, unattendedThresholdMinutes } = useFleetData();
const isLuggageStale = lastUpdate != null && (Date.now() - lastUpdate.getTime()) > stalenessThresholdSeconds * 1000;
```

Banner markup (place before `<LuggageKpiStrip />`):
```jsx
{isLuggageStale && (
  <div className="luggage-monitoring__stale-banner">
    Luggage data may be stale — last update over {Math.round(stalenessThresholdSeconds / 60)} minutes ago.
  </div>
)}
```

CSS in `LuggageMonitoring.css`:
```css
.luggage-monitoring__stale-banner {
  padding: 0.5rem 1rem;
  background: var(--color-amber-subtle, rgba(232, 160, 32, 0.12));
  color: var(--color-amber, #E8A020);
  border-left: 3px solid var(--color-amber, #E8A020);
  font-size: 0.8125rem;
  margin-bottom: 0.75rem;
}
```

Use CSS custom properties — no hardcoded hex in the rule. The fallback values shown are only for browsers without the vars defined.

### LuggageKpiStrip tile change

Current:
```jsx
<div className={`lkpi ${kpis.unattended > 0 ? 'lkpi--red' : ''}`}>
  <span className="lkpi__value">{kpis.unattended}</span>
  <span className="lkpi__label">Unattended Items</span>
</div>
```

New:
```jsx
<div className={`lkpi ${(kpis.unattendedAlerts ?? kpis.unattended) > 0 ? 'lkpi--red' : ''}`}>
  <span className="lkpi__value">{kpis.unattendedAlerts ?? kpis.unattended}</span>
  <span className="lkpi__label">Unattended Alerts</span>
</div>
```

The `?? kpis.unattended` fallback guards against rendering regressions if `getLuggageKPIs` is called without the threshold param anywhere (should not happen after T5, but defensive).

### OperatorPreferences — new control placement

Add below the `stalenessThreshold` `SegmentedControl`:
```jsx
<SegmentedControl
  label="Unattended bag alert after"
  options={UNATTENDED_THRESHOLD_OPTIONS}
  value={unattendedThresholdMinutes}
  onCommit={handleUnattendedCommit}
  formatLabel={(n) => `${n} min`}
/>
```

Handler:
```js
async function handleUnattendedCommit(val) {
  const err = await updateUnattendedThreshold(val);
  if (err) showToast('Preference not saved — please retry');
}
```

### Test file location and pattern

Tests for `getLuggageKPIs` go in `control-centre/src/mock/luggage.test.js`.
No jsdom. Use `// @vitest-environment node` at the top.
Import from relative path: `import { getLuggageKPIs } from './luggage.js'`

Minimal fixture:
```js
// @vitest-environment node
import { describe, it, expect } from 'vitest';
import { getLuggageKPIs } from './luggage.js';

// ISO timestamp helper — N minutes ago from a fixed reference
function minutesAgo(n) {
  return new Date(Date.now() - n * 60 * 1000).toISOString();
}

const makeEvent = (state, minsAgo) => ({
  id: `t-${minsAgo}`,
  trainId: 'R5001C-031',
  coachId: 'C1',
  state,
  timestamp: minutesAgo(minsAgo),
  confidence: 90,
});
```

Note: `elapsedMin` uses `Date.now()` for ISO strings (post-E5-S2 behaviour), so `minutesAgo` fixtures will produce accurate elapsed values in tests.

---

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Debug Log
_empty_

### Completion Notes
All 8 tasks complete. Added `unattendedThresholdMinutes` as a new preference mirroring the `alertThresholdSeconds` pattern exactly (localStorage init → server reconcile → optimistic PATCH with revert). `getLuggageKPIs` extended with `thresholdMin` param — `unattendedAlerts` is the alert-worthy subset; `unattended` and `totalActive` semantics unchanged. `LuggageKpiStrip` tile relabelled "Unattended Alerts" and reads `unattendedAlerts` with graceful `?? kpis.unattended` fallback. Staleness banner in `LuggageMonitoring` derives from existing `lastUpdate` + `stalenessThresholdSeconds`. `OperatorPreferences` gains third `SegmentedControl` with [1,2,5,10,15] min options. 5 Vitest unit tests pass (node env, ISO timestamp fixtures).

### File List
- `control-centre/src/constants/preferences.js`
- `control-centre/src/context/FleetContext.jsx`
- `control-centre/src/mock/luggage.js`
- `control-centre/src/mock/luggage.test.js`
- `control-centre/src/components/luggage/LuggageKpiStrip.jsx`
- `control-centre/src/components/luggage/LuggageMonitoring.jsx`
- `control-centre/src/components/luggage/LuggageMonitoring.css`
- `control-centre/src/components/shell/OperatorPreferences.jsx`
