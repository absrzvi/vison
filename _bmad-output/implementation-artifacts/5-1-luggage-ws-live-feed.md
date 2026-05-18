# Story E5-S1 — Luggage Monitoring Live WebSocket Feed

**Status:** ready-for-dev
**Sprint:** Epic 5
**Story Key:** 5-1-luggage-ws-live-feed

---

## Story

**As a** Control Centre operator,
**I want** the Luggage Monitoring tab and the Luggage Alerts KPI tile to reflect live luggage events arriving over the WebSocket rather than the 7 hardcoded mock events,
**so that** I can see real-time unattended bag alerts and rack saturation events as they are detected onboard, and respond before the situation escalates.

---

## Acceptance Criteria

**AC1:** Given the WebSocket delivers a `LUGGAGE_RACK_SATURATION` event for a vehicle, when `RealWebSocketClient` receives it, then it emits a `LUGGAGE_EVENT` frontend message with shape `{ type: 'LUGGAGE_EVENT', payload: { id, trainId, coachId, state: 'overcrowded', title, detail, confidence, timestamp, stillFrame: null } }`; the event appears in the Luggage Monitoring feed immediately without a page reload.

**AC2:** Given the WebSocket delivers an `UNATTENDED_BAG` event, when `RealWebSocketClient` receives it, then it emits a `LUGGAGE_EVENT` message with `state: 'unattended'`; the event appears in the Luggage Monitoring feed and the unified feed (as `type: 'luggage'` escalation with `status: 'unacknowledged'`).

**AC3:** Given a live `LUGGAGE_EVENT` message arrives, when `FleetContext` processes it, then:
- The event is prepended to a new `luggageEvents` array in context (replacing the static `LUGGAGE_EVENTS` import).
- `luggageEventsToEscalations()` is called on the updated array and the result is merged into `escalations` (replacing the static `LUGGAGE_ESCALATIONS` constant).
- `setLastUpdate(new Date())` is called.

**AC4:** Given `LuggageMonitoring` renders with live context, when `luggageEvents` is empty (no events yet received), then the existing empty-state message "No luggage events received yet." is shown — component does not crash or show mock data.

**AC5:** Given the mock WebSocket (`VITE_WS_URL` not set) is active, when the system runs in dev mode, then `MockWebSocketClient` emits at least 2 `LUGGAGE_EVENT` messages (one `unattended`, one `overcrowded`) so the Luggage tab remains testable offline. The hardcoded `LUGGAGE_EVENTS` import in `LuggageMonitoring.jsx` and `FleetContext.jsx` is replaced — it must not be imported anywhere in non-mock production paths.

**AC6:** Given `RealWebSocketClient` is active, when `LUGGAGE_RACK_SATURATION` or `UNATTENDED_BAG` arrives, then the event is added to the WS `SUBSCRIPTION_REQUEST` `event_types` array so the backend actually delivers these events to the client.

**AC7:** Given a luggage event arrives with an `event_id` the client has already seen (replay on reconnect), when `_trackSeenId` is called, then the duplicate is silently dropped — no duplicate cards in the feed.

---

## Tasks / Subtasks

- [ ] **T1** Extend `RealWebSocketClient.js` — handle `LUGGAGE_RACK_SATURATION` + `UNATTENDED_BAG`
  - [ ] T1.1 Add `'LUGGAGE_RACK_SATURATION'` and `'UNATTENDED_BAG'` to `SUBSCRIPTION_REQUEST.event_types`
  - [ ] T1.2 In `_handleEnvelope`, add handler for `event_type === 'LUGGAGE_RACK_SATURATION'` → emits `LUGGAGE_EVENT` with `state: 'overcrowded'`
  - [ ] T1.3 In `_handleEnvelope`, add handler for `event_type === 'UNATTENDED_BAG'` → emits `LUGGAGE_EVENT` with `state: 'unattended'`
  - [ ] T1.4 Dedup via existing `_trackSeenId` — no new dedup logic needed

- [ ] **T2** Extend `MockWebSocketClient` (websocket.js) — emit `LUGGAGE_EVENT` messages
  - [ ] T2.1 Add 2 `LUGGAGE_EVENT` messages to the initial mock payload (one `unattended`, one `overcrowded`) — keep the mock self-contained, do NOT import from `mock/luggage.js`
  - [ ] T2.2 These events must have `id`, `trainId`, `coachId`, `state`, `title`, `detail`, `confidence`, `timestamp` (ISO-8601), `stillFrame: null`

- [ ] **T3** Update `FleetContext.jsx` — replace static luggage with live state
  - [ ] T3.1 Remove `import { LUGGAGE_EVENTS, luggageEventsToEscalations } from '../mock/luggage'` and the `LUGGAGE_ESCALATIONS` constant
  - [ ] T3.2 Add `luggageEvents` state: `const [luggageEvents, setLuggageEvents] = useState([])`
  - [ ] T3.3 In `onMessage`, add handler for `msg.type === 'LUGGAGE_EVENT'`: prepend to `luggageEvents` with dedup on `id`; call `setLastUpdate(new Date())`
  - [ ] T3.4 Replace `[...msg.payload.escalations, ...LUGGAGE_ESCALATIONS]` in `FLEET_STATE` handler with `[...msg.payload.escalations, ...luggageEventsToEscalations(luggageEvents)]` — import `luggageEventsToEscalations` from `mock/luggage.js` (helper function only, not the static data)
  - [ ] T3.5 Re-derive luggage escalations when `luggageEvents` changes: add a `useEffect` that calls `setEscalations(prev => [...prev.filter(e => e.type !== 'luggage'), ...luggageEventsToEscalations(luggageEvents)])` when `luggageEvents` changes
  - [ ] T3.6 Expose `luggageEvents` in the context value object

- [ ] **T4** Update `LuggageMonitoring.jsx` — consume live context
  - [ ] T4.1 Remove `import { LUGGAGE_EVENTS, ... } from '../../mock/luggage'`
  - [ ] T4.2 Replace `const events = LUGGAGE_EVENTS` with `const { luggageEvents: events } = useFleetData()`
  - [ ] T4.3 Verify empty-state renders when `events.length === 0` (existing guard is already correct)

- [ ] **T5** Tests (Vitest unit — `// @vitest-environment node`)
  - [ ] T5.1 `RealWebSocketClient`: `LUGGAGE_RACK_SATURATION` envelope → emits `LUGGAGE_EVENT` with `state: 'overcrowded'`
  - [ ] T5.2 `RealWebSocketClient`: `UNATTENDED_BAG` envelope → emits `LUGGAGE_EVENT` with `state: 'unattended'`
  - [ ] T5.3 `RealWebSocketClient`: duplicate `event_id` for luggage event is dropped (dedup)
  - [ ] T5.4 `FleetContext` logic: `LUGGAGE_EVENT` message prepends to array and deduplicates on `id`
  - [ ] T5.5 `FleetContext` logic: `luggageEventsToEscalations` called on updated array produces correct escalation shape

---

## Dev Notes

### Architecture — what this story changes

This story replaces the static `LUGGAGE_EVENTS` constant (7 hardcoded events) with a live WS-fed `luggageEvents` array in `FleetContext`. Three files need surgery:

1. **`control-centre/src/ws/RealWebSocketClient.js`** — add two new event_type handlers
2. **`control-centre/src/mock/websocket.js`** — emit LUGGAGE_EVENT in mock mode
3. **`control-centre/src/context/FleetContext.jsx`** — swap static array for live state
4. **`control-centre/src/components/luggage/LuggageMonitoring.jsx`** — read from context

`LuggageFeed.jsx`, `LuggageKpiStrip.jsx`, `LuggageTrainDetail.jsx`, `LuggageMap.jsx` are **NOT touched** — they receive `events` as props from `LuggageMonitoring` and their prop API doesn't change.

### Backend WS event types already defined

`LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` are already in `shared/src/oebb_shared/events/types.py` (EventType StrEnum). The cloud-backend `SUBSCRIPTION_REQUEST` filter in `RealWebSocketClient.js` currently does NOT include them — that's the gap this story fixes.

**`LUGGAGE_RACK_SATURATION` payload** (from `event-payload-schemas.md`):
```json
{
  "car_id": "car-2",
  "rack_id": "car-2-rack-upper-left",
  "fill_pct": 0.95,
  "item_count": 7,
  "confidence": 0.88
}
```

**`UNATTENDED_BAG` payload** (from `event-payload-schemas.md`):
```json
{
  "car_id": "car-3",
  "zone": "seating-mid",
  "track_id": "bag-0042",
  "dwell_s": 180.0,
  "bbox": { "x": 412, "y": 308, "w": 64, "h": 48 },
  "camera_id": "cam-3-02",
  "confidence": 0.91
}
```

### Frontend `LUGGAGE_EVENT` message shape

The `RealWebSocketClient._handleEnvelope` must emit this shape (matches existing `LUGGAGE_EVENTS` object shape minus `duration` and `stillFrame.url` which require Phase 2 storage):

```js
{
  type: 'LUGGAGE_EVENT',
  payload: {
    id: event_id,              // string UUID from envelope
    trainId: vehicle_id,       // from envelope top-level
    coachId: safePayload.car_id ?? null,
    state: 'overcrowded',      // or 'unattended'
    title: /* derived — see below */,
    detail: /* derived — see below */,
    confidence: safePayload.confidence ?? null,
    timestamp: timestamp,      // ISO-8601 UTC string from envelope — NOT formatted
    stillFrame: null,          // Phase 2
  }
}
```

**Title/detail derivation:**

For `LUGGAGE_RACK_SATURATION`:
- `title`: `'Luggage area full — ' + (safePayload.car_id ?? 'unknown coach')`
- `detail`: `'Rack ' + (safePayload.rack_id ?? '') + ' at ' + Math.round((safePayload.fill_pct ?? 0) * 100) + '% capacity. ' + (safePayload.item_count ?? '?') + ' items detected.'`

For `UNATTENDED_BAG`:
- `title`: `'Unattended bag — ' + (safePayload.car_id ?? 'unknown coach') + (safePayload.zone ? ' ' + safePayload.zone : '')`
- `detail`: `'No owner detected for ' + Math.round((safePayload.dwell_s ?? 0) / 60) + ' min. Track: ' + (safePayload.track_id ?? '?') + '.'`

### FleetContext changes in detail

**Current state (lines 4, 14, 76 of FleetContext.jsx):**
```js
import { LUGGAGE_EVENTS, luggageEventsToEscalations } from '../mock/luggage';
const LUGGAGE_ESCALATIONS = luggageEventsToEscalations(LUGGAGE_EVENTS);
// ...in FLEET_STATE handler:
setEscalations([...msg.payload.escalations, ...LUGGAGE_ESCALATIONS]);
```

**Target state:**
```js
import { luggageEventsToEscalations } from '../mock/luggage'; // helper only
// ...
const [luggageEvents, setLuggageEvents] = useState([]);
// ...
// In onMessage, FLEET_STATE handler:
setEscalations([...msg.payload.escalations, ...luggageEventsToEscalations(luggageEventsRef.current)]);

// In onMessage, new LUGGAGE_EVENT handler:
if (msg.type === 'LUGGAGE_EVENT') {
  const { id } = msg.payload ?? {};
  if (!id) return;
  setLuggageEvents(prev => {
    if (prev.some(e => e.id === id)) return prev;
    return [msg.payload, ...prev];
  });
  setLastUpdate(new Date());
}
```

**Problem with `luggageEvents` stale closure in FLEET_STATE handler:**
The `FLEET_STATE` handler inside `onMessage` (itself inside the `useEffect`) cannot read current `luggageEvents` state — it captures the empty array from mount. Use a ref pattern:

```js
const luggageEventsRef = useRef([]);
// sync ref on every change:
useEffect(() => { luggageEventsRef.current = luggageEvents; }, [luggageEvents]);
```

Then in the `FLEET_STATE` handler: `luggageEventsToEscalations(luggageEventsRef.current)`.

**Escalation sync effect (T3.5):** When `luggageEvents` updates (new WS event), escalations must also update to include the new luggage escalation:
```js
useEffect(() => {
  setEscalations(prev => [
    ...prev.filter(e => e.type !== 'luggage'),
    ...luggageEventsToEscalations(luggageEvents),
  ]);
}, [luggageEvents]);
```

### Preserve: `luggageEventsToEscalations` import path

`luggageEventsToEscalations` lives in `control-centre/src/mock/luggage.js` (line 148). It is a pure helper with no side effects — importing it from mock/ is acceptable. Do NOT copy/paste the function; import it. Only the static `LUGGAGE_EVENTS` array must stop being imported.

### Mock WebSocket (websocket.js)

The `MockWebSocketClient` dispatches the initial `FLEET_STATE` message and simulates periodic updates. Add two `LUGGAGE_EVENT` dispatches after the initial FLEET_STATE, with a short delay (e.g. 500ms and 1200ms), so the Luggage tab populates in dev mode:

```js
// In MockWebSocketClient._startSimulation() or equivalent:
setTimeout(() => this._dispatchMessage({
  type: 'LUGGAGE_EVENT',
  payload: {
    id: 'mock-lug-001',
    trainId: 'R5001C-031',
    coachId: 'car-4',
    state: 'unattended',
    title: 'Unattended bag — car-4 seating-mid',
    detail: 'No owner detected for 3 min. Track: bag-0042.',
    confidence: 0.94,
    timestamp: new Date().toISOString(),
    stillFrame: null,
  }
}), 500);
setTimeout(() => this._dispatchMessage({
  type: 'LUGGAGE_EVENT',
  payload: {
    id: 'mock-lug-002',
    trainId: 'R5001C-003',
    coachId: 'car-2',
    state: 'overcrowded',
    title: 'Luggage area full — car-2',
    detail: 'Rack car-2-rack-upper-left at 95% capacity. 7 items detected.',
    confidence: 0.88,
    timestamp: new Date().toISOString(),
    stillFrame: null,
  }
}), 1200);
```

### Timestamps: ISO-8601 going forward

The existing `LUGGAGE_EVENTS` mock uses `timestamp: '11:23'` (HH:MM strings). Live events will carry ISO-8601 UTC timestamps from the WS envelope. `LuggageFeed.jsx` and `LuggageTrainDetail.jsx` currently render `e.timestamp` directly — they will display ISO strings like `2026-05-18T11:23:04Z` unless we format them.

**This story does NOT refactor the timestamp display** (that is E5-S4). For now, the `LUGGAGE_EVENT` payload should store `timestamp` as the raw ISO string from the envelope. The display will look ugly in dev mode until E5-S4. That is acceptable.

### `coachId` naming: `car_id` vs `C1..C8`

The mock data uses `coachId: 'C4'` (OEBB coach label). The backend payload uses `car_id: 'car-4'` (internal inference ID). For this story, store `coachId: safePayload.car_id ?? null` directly — keep the raw value. `LuggageTrainDetail` already handles the display. E5-S2 will align naming if needed.

### What MUST NOT break

- `UnifiedFeed.jsx` — renders escalations from `useFleetData().escalations`. Luggage escalations appear there as `type: 'luggage'`. After this story, live luggage events must still appear in the unified feed. The `FLEET_STATE` handler must continue to seed initial escalations.
- `KpiStrip.jsx` — reads `escalations` for `openEscalations` count. No change needed.
- `LiveMonitoring.jsx` line 46 — reads `luggageKpis` from local `useMemo` on `LUGGAGE_EVENTS`. After this story, this must read from `luggageEvents` from context. **This is in scope for T3/T4.**

### Test environment

Tests run with `// @vitest-environment node` (jsdom not installed). Component render tests are not possible. Test the pure logic:
- `_handleEnvelope` in a class instance (instantiate `RealWebSocketClient`, call `_handleEnvelope` directly, capture emitted messages)
- FleetContext updater functions as pure functions extracted for testing (mirror pattern from E2-S9 `SystemHealth.test.js`)

### File list (expected changes)

| File | Change |
|---|---|
| `control-centre/src/ws/RealWebSocketClient.js` | ADD two event_type handlers + subscription entries |
| `control-centre/src/mock/websocket.js` | ADD two LUGGAGE_EVENT dispatches |
| `control-centre/src/context/FleetContext.jsx` | REPLACE static luggage import with live state |
| `control-centre/src/components/luggage/LuggageMonitoring.jsx` | REPLACE static import with context read |
| `control-centre/src/components/live/LiveMonitoring.jsx` | UPDATE luggageKpis source to use context luggageEvents |
| `control-centre/src/ws/__tests__/RealWebSocketClient.test.js` | NEW — luggage event handler tests |
| `control-centre/src/context/__tests__/FleetContextLuggage.test.js` | NEW — luggage state logic tests |

---

## Dev Agent Record

### Debug Log
_Empty — ready for dev_

### Completion Notes
_Empty — ready for dev_

### File List
_To be filled by dev agent_

### Change Log
_To be filled by dev agent_
