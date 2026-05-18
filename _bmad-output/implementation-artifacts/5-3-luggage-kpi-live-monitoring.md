# Story E5-S3 — Luggage KPI Live Monitoring

**Status:** ready-for-dev
**Sprint:** Epic 5
**Story Key:** 5-3-luggage-kpi-live-monitoring

---

## Story

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab to warn me when luggage data is stale, the KPI strip to flag unattended bags only once they exceed a configurable age threshold, and a preference control to tune that threshold,
**so that** I can trust the KPI numbers reflect real operational urgency and avoid alert fatigue from short-duration false alarms.

---

## Acceptance Criteria

**AC1 — Configurable unattended threshold in preferences:** Given the operator opens the Preferences panel, when they see the luggage section, then a new `SegmentedControl` labelled "Unattended bag alert threshold" is shown with options `[1, 2, 5, 10, 15]` (minutes), defaulting to 5 min.

**AC2 — Threshold persisted to backend:** Given the operator selects a new threshold value, when `updateUnattendedThreshold(minutes)` is called, then a `PATCH /api/v1/operators/me/preferences` request is sent with body `{ unattended_threshold_min: <value> }`. On success, the value is persisted to localStorage under key `oebb.cc.unattendedThresholdMinutes`. On failure, state reverts to the previous value and the existing toast "Preference not saved — please retry" is shown.

**AC3 — Server value wins on init:** Given the app loads, when `GET /api/v1/operators/me/preferences` resolves and the response includes `unattended_threshold_min`, then `unattendedThresholdMinutes` in context is updated to the server value and localStorage is synced. If the key is absent from the response, the localStorage value (or default 5) stands.

**AC4 — `getLuggageKPIs` threshold-aware:** Given `getLuggageKPIs(events, thresholdMin)` is called with a threshold, when computing KPIs, then a new `unattendedAlerts` field is returned = count of unattended events where `elapsedMin(event.timestamp) >= thresholdMin`. The existing `unattended` field (raw count) and `totalActive` are unchanged. When `thresholdMin` is not provided, it defaults to `5`.

**AC5 — KPI strip shows threshold-filtered count:** Given `LuggageKpiStrip` receives `kpis` from `LuggageMonitoring`, when `kpis.unattendedAlerts > 0`, then the "Unattended Items" tile is styled red (`lkpi--red`). When `kpis.unattendedAlerts === 0` but `kpis.unattended > 0` (events exist but below threshold), the tile is styled amber (`lkpi--amber`) — indicating "watching". The tile label changes to "Unattended Alerts" and the value displays `kpis.unattendedAlerts`.

**AC6 — Live Monitoring KPI tile unchanged:** Given `LiveMonitoring` passes `luggageAlerts={luggageKpis.totalActive}` to `KpiStrip`, this value must remain `totalActive` (not `unattendedAlerts`) — it reflects all active luggage events, not just threshold-triggered ones. No change to `LiveMonitoring.jsx` or `KpiStrip.jsx`.

**AC7 — Staleness banner on Luggage tab:** Given the Luggage Monitoring tab is visible, when `lastUpdate` exists and `(Date.now() - lastUpdate.getTime()) > stalenessThresholdSeconds * 1000`, then a stale banner is shown at the top of the tab: "Luggage data may be stale — last update over N seconds ago." When `lastUpdate` is within the threshold, the banner is hidden.

**AC8 — `LuggageMonitoring` reads context values:** Given `LuggageMonitoring` renders, when it destructures from `useFleetData()`, then it reads `lastUpdate` and `stalenessThresholdSeconds` (already in context) and `unattendedThresholdMinutes` (new in this story). No new context fields beyond `unattendedThresholdMinutes` and `updateUnattendedThreshold` are required.

---

## Tasks / Subtasks

- [ ] **T1** Add constants to `constants/preferences.js` (AC1, AC3)
  - [ ] T1.1 Add `export const DEFAULT_UNATTENDED_THRESHOLD_MINUTES = 5;`
  - [ ] T1.2 Add `export const UNATTENDED_THRESHOLD_OPTIONS = [1, 2, 5, 10, 15];`
  - [ ] T1.3 Add `export const LS_KEY_UNATTENDED_THRESHOLD = 'oebb.cc.unattendedThresholdMinutes';`

- [ ] **T2** Add `unattendedThresholdMinutes` state to `FleetContext.jsx` (AC2, AC3, AC8)
  - [ ] T2.1 Import `DEFAULT_UNATTENDED_THRESHOLD_MINUTES`, `LS_KEY_UNATTENDED_THRESHOLD` from `../constants/preferences`.
  - [ ] T2.2 Add state: `const [unattendedThresholdMinutes, setUnattendedThresholdMinutes] = useState(() => { const p = parseInt(localStorage.getItem(LS_KEY_UNATTENDED_THRESHOLD), 10); return Number.isFinite(p) ? p : DEFAULT_UNATTENDED_THRESHOLD_MINUTES; });`
  - [ ] T2.3 In the `getPreferences()` effect, handle `prefs.unattended_threshold_min`: `setUnattendedThresholdMinutes(prev => { if (prev !== prefs.unattended_threshold_min) { localStorage.setItem(LS_KEY_UNATTENDED_THRESHOLD, String(prefs.unattended_threshold_min)); return prefs.unattended_threshold_min; } return prev; });` — wrap in `if (prefs.unattended_threshold_min != null)` guard.
  - [ ] T2.4 Add `updateUnattendedThreshold` callback (same optimistic-update + revert pattern as `updateAlertThreshold`): `const updateUnattendedThreshold = useCallback(async (value) => { let prev; setUnattendedThresholdMinutes(p => { prev = p; return value; }); try { await patchPreferences({ unattended_threshold_min: value }); localStorage.setItem(LS_KEY_UNATTENDED_THRESHOLD, String(value)); return null; } catch (err) { setUnattendedThresholdMinutes(prev); return err; } }, []);`
  - [ ] T2.5 Expose `unattendedThresholdMinutes` and `updateUnattendedThreshold` in the context value object.

- [ ] **T3** Update `getLuggageKPIs` in `mock/luggage.js` (AC4)
  - [ ] T3.1 Change signature to `export function getLuggageKPIs(events, thresholdMin = 5)`.
  - [ ] T3.2 Add `unattendedAlerts` to the return: `unattendedAlerts: unattendedEvents.filter(e => (elapsedMin(e.timestamp) ?? 0) >= thresholdMin).length`.
  - [ ] T3.3 All other returned fields (`totalActive`, `unattended`, `overcrowded`, `oversized`, `clearedLastHour`, `longestUnattended`, `longestActive`) remain unchanged.

- [ ] **T4** Update `LuggageMonitoring.jsx` (AC5, AC7, AC8)
  - [ ] T4.1 Destructure `lastUpdate`, `stalenessThresholdSeconds`, `unattendedThresholdMinutes` from `useFleetData()`.
  - [ ] T4.2 Pass `thresholdMin` to `getLuggageKPIs`: `const kpis = useMemo(() => getLuggageKPIs(events, unattendedThresholdMinutes), [events, unattendedThresholdMinutes]);`
  - [ ] T4.3 Compute `isStale`: `const isStale = lastUpdate && (Date.now() - lastUpdate.getTime()) > stalenessThresholdSeconds * 1000;`
  - [ ] T4.4 Render stale banner (same pattern as `LiveMonitoring.jsx`): inside the main `<div className="luggage-monitoring">`, after `<LuggageKpiStrip>`, render: `{isStale && (<div className="luggage-monitoring__stale-banner">Luggage data may be stale — last update over {stalenessThresholdSeconds}s ago. Attempting to reconnect…</div>)}`
  - [ ] T4.5 Add `.luggage-monitoring__stale-banner` CSS to `LuggageMonitoring.css` — copy the pattern from `LiveMonitoring.css` `.live-monitoring__stale-banner`.

- [ ] **T5** Update `LuggageKpiStrip.jsx` (AC5)
  - [ ] T5.1 Change the "Unattended Items" tile to use `kpis.unattendedAlerts` as the value.
  - [ ] T5.2 Change the label to `"Unattended Alerts"`.
  - [ ] T5.3 Update the conditional class: `kpis.unattendedAlerts > 0 ? 'lkpi--red' : kpis.unattended > 0 ? 'lkpi--amber' : ''`.

- [ ] **T6** Update `OperatorPreferences.jsx` (AC1, AC2)
  - [ ] T6.1 Import `UNATTENDED_THRESHOLD_OPTIONS`, `updateUnattendedThreshold` (from context via `useFleetData`), `unattendedThresholdMinutes`.
  - [ ] T6.2 Add `const { ..., unattendedThresholdMinutes, updateUnattendedThreshold } = useFleetData();` to the destructuring.
  - [ ] T6.3 Add `async function handleUnattendedCommit(val) { const err = await updateUnattendedThreshold(val); if (err) showToast('Preference not saved — please retry'); }`.
  - [ ] T6.4 Add a third `SegmentedControl` in the panel body: `<SegmentedControl label="Unattended bag alert threshold" options={UNATTENDED_THRESHOLD_OPTIONS} value={unattendedThresholdMinutes} onCommit={handleUnattendedCommit} formatLabel={(m) => \`${m} min\`} />`

- [ ] **T7** Tests — `// @vitest-environment node` (AC4)
  - [ ] T7.1 `getLuggageKPIs(events, 5)` — unattended event with elapsed ≥ 5 min counts in `unattendedAlerts`.
  - [ ] T7.2 `getLuggageKPIs(events, 5)` — unattended event with elapsed < 5 min does NOT count in `unattendedAlerts`.
  - [ ] T7.3 `getLuggageKPIs(events, 5)` — `unattended` raw count is unchanged regardless of threshold.
  - [ ] T7.4 `getLuggageKPIs(events)` — default threshold (5) applies when not passed.
  - [ ] T7.5 `getLuggageKPIs([])` — returns `unattendedAlerts: 0`.

---

## Security Tests

**UI / client-side security:**
- [ ] No tokens or sensitive data written to localStorage or sessionStorage beyond the three existing preference keys
- [ ] PATCH failure does not expose server error detail to the operator — toast shows generic message only

---

## Dev Notes

### Architecture — what this story changes

Purely a preferences + display layer story. No new WS messages, no new backend endpoints beyond the existing `PATCH /api/v1/operators/me/preferences` (which already accepts arbitrary keys).

**Files to UPDATE:**
1. `control-centre/src/constants/preferences.js` — 3 new exports
2. `control-centre/src/context/FleetContext.jsx` — new state + effect + callback + context value
3. `control-centre/src/mock/luggage.js` — `getLuggageKPIs` signature + `unattendedAlerts` field
4. `control-centre/src/components/luggage/LuggageMonitoring.jsx` — read new context values, stale banner, pass threshold to KPIs
5. `control-centre/src/components/luggage/LuggageMonitoring.css` — stale banner CSS
6. `control-centre/src/components/luggage/LuggageKpiStrip.jsx` — use `unattendedAlerts`, rename tile
7. `control-centre/src/components/shell/OperatorPreferences.jsx` — third SegmentedControl

**Files NOT touched:**
- `LiveMonitoring.jsx` — AC6 explicitly states no change
- `KpiStrip.jsx` — passes `totalActive`, unchanged
- `RealWebSocketClient.js` — no WS changes
- `FleetContext` escalation logic — no change

### `FleetContext.jsx` — exact additions

Add after the `stalenessThresholdSeconds` state declaration (around line 51):

```js
const [unattendedThresholdMinutes, setUnattendedThresholdMinutes] = useState(() => {
  const parsed = parseInt(localStorage.getItem(LS_KEY_UNATTENDED_THRESHOLD), 10);
  return Number.isFinite(parsed) ? parsed : DEFAULT_UNATTENDED_THRESHOLD_MINUTES;
});
```

In the `getPreferences()` effect (around line 177), add after the `serverStaleness` block:

```js
if (prefs.unattended_threshold_min != null) {
  setUnattendedThresholdMinutes(prev => {
    if (prev !== prefs.unattended_threshold_min) {
      localStorage.setItem(LS_KEY_UNATTENDED_THRESHOLD, String(prefs.unattended_threshold_min));
      return prefs.unattended_threshold_min;
    }
    return prev;
  });
}
```

Add after `updateStalenessThreshold` (around line 227):

```js
const updateUnattendedThreshold = useCallback(async (value) => {
  let prevValue;
  setUnattendedThresholdMinutes(prev => { prevValue = prev; return value; });
  try {
    await patchPreferences({ unattended_threshold_min: value });
    localStorage.setItem(LS_KEY_UNATTENDED_THRESHOLD, String(value));
    return null;
  } catch (err) {
    setUnattendedThresholdMinutes(prevValue);
    return err;
  }
}, []);
```

Context value object — add: `unattendedThresholdMinutes, updateUnattendedThreshold,`

### `getLuggageKPIs` — exact change

```js
// BEFORE:
export function getLuggageKPIs(events) {

// AFTER:
export function getLuggageKPIs(events, thresholdMin = 5) {
```

Add to the return object:
```js
unattendedAlerts: unattendedEvents.filter(e => (elapsedMin(e.timestamp) ?? 0) >= thresholdMin).length,
```

Note: `elapsedMin` will be ISO-aware after E5-S2. For this story, the function must work correctly with both HH:MM mock timestamps and ISO live timestamps. Since E5-S2 is a dependency, this is safe.

### Stale banner CSS

Add to `LuggageMonitoring.css`:

```css
.luggage-monitoring__stale-banner {
  background: var(--obb-sev-warning-bg, rgba(232, 160, 32, 0.12));
  border-bottom: 1px solid var(--obb-sev-warning);
  color: var(--obb-sev-warning);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 16px;
  flex-shrink: 0;
}
```

Look up the `.live-monitoring__stale-banner` rule in `LiveMonitoring.css` and use the same CSS custom properties.

### `LuggageKpiStrip.jsx` — exact tile change

```jsx
// BEFORE:
<div className={`lkpi ${kpis.unattended > 0 ? 'lkpi--red' : ''}`}>
  <span className="lkpi__value">{kpis.unattended}</span>
  <span className="lkpi__label">Unattended Items</span>
</div>

// AFTER:
<div className={`lkpi ${kpis.unattendedAlerts > 0 ? 'lkpi--red' : kpis.unattended > 0 ? 'lkpi--amber' : ''}`}>
  <span className="lkpi__value">{kpis.unattendedAlerts}</span>
  <span className="lkpi__label">Unattended Alerts</span>
</div>
```

### `OperatorPreferences.jsx` — exact additions

Import:
```js
import {
  ALERT_THRESHOLD_OPTIONS,
  STALENESS_THRESHOLD_OPTIONS,
  UNATTENDED_THRESHOLD_OPTIONS,
} from '../../constants/preferences';
```

Destructure:
```js
const { alertThresholdSeconds, stalenessThresholdSeconds, updateAlertThreshold, updateStalenessThreshold,
        unattendedThresholdMinutes, updateUnattendedThreshold } = useFleetData();
```

Handler:
```js
async function handleUnattendedCommit(val) {
  const err = await updateUnattendedThreshold(val);
  if (err) showToast('Preference not saved — please retry');
}
```

New SegmentedControl (add in `pref-body` after the staleness control):
```jsx
<SegmentedControl
  label="Unattended bag alert threshold"
  options={UNATTENDED_THRESHOLD_OPTIONS}
  value={unattendedThresholdMinutes}
  onCommit={handleUnattendedCommit}
  formatLabel={(m) => `${m} min`}
/>
```

### What MUST NOT break

- `getLuggageKPIs` called from `LiveMonitoring.jsx` as `getLuggageKPIs(luggageEvents)` with no second arg — default `thresholdMin=5` applies, and `totalActive` is still returned correctly
- `OperatorPreferences` existing two controls must remain unchanged
- 72 existing tests must pass — `getLuggageKPIs` now takes an optional second arg, all existing call sites still work

### Test file location

New test file: `control-centre/src/mock/__tests__/luggage.test.js`

Use `// @vitest-environment node`. Import `getLuggageKPIs`, `elapsedMin` from `../../mock/luggage`. For threshold tests, use mock events with HH:MM timestamps (since E5-S2 is a dependency but tests should work in isolation — use events where `elapsedMin` returns a deterministic value via the `nowTs` parameter):

```js
// Construct a test event where elapsedMin returns exactly 7 min
// Use the ISO path with explicit nowTs:
const ts = '2026-05-19T10:00:00Z';
const now = '2026-05-19T10:07:00Z';
// elapsedMin(ts, now) === 7 — above threshold of 5
```

### File list

| File | Change |
|---|---|
| `control-centre/src/constants/preferences.js` | ADD 3 constants |
| `control-centre/src/context/FleetContext.jsx` | ADD unattendedThresholdMinutes state, effect, callback, context value |
| `control-centre/src/mock/luggage.js` | UPDATE getLuggageKPIs signature + unattendedAlerts field |
| `control-centre/src/components/luggage/LuggageMonitoring.jsx` | ADD lastUpdate/stalenessThresholdSeconds/unattendedThresholdMinutes, stale banner, threshold to getLuggageKPIs |
| `control-centre/src/components/luggage/LuggageMonitoring.css` | ADD stale banner CSS rule |
| `control-centre/src/components/luggage/LuggageKpiStrip.jsx` | UPDATE unattended tile to use unattendedAlerts |
| `control-centre/src/components/shell/OperatorPreferences.jsx` | ADD third SegmentedControl for unattended threshold |
| `control-centre/src/mock/__tests__/luggage.test.js` | NEW — 5 tests for threshold-aware getLuggageKPIs |

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log

### Completion Notes

### File List
