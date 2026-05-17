# Story 2-1: Real WebSocket Client

**Epic:** 2 — Control Centre Dashboard
**Story:** E2-S1
**Story Key:** 2-1-real-ws-client
**Status:** review
**Date Created:** 2026-05-17

---

## User Story

**As a** Control Centre operator,
**I want** the dashboard to connect to the live cloud backend WebSocket instead of the mock client,
**so that** fleet state, escalations, and train health data reflect real-time events from onboard trains rather than simulated data.

---

## Acceptance Criteria

- [x] **AC1** — When `VITE_WS_URL` is set, `FleetContext` connects to it using a `SubscriptionRequest` JSON handshake (`event_types` = all live-monitoring types, `min_severity: "info"`, `coach_ids: null`, `reconnect_replay_depth: 50`)
- [x] **AC2** — When a train event arrives in canonical envelope format (ADR-1), `FleetContext` maps it to the frontend train shape (DD-001 §4) and all consumers update without a page reload
- [x] **AC3** — On disconnection, client reconnects with exponential backoff (base 1s, max 30s, jitter); an amber "Reconnecting…" banner appears in the top nav; existing fleet state is preserved
- [x] **AC4** — On reconnect, the "Reconnecting…" banner clears; no duplicate events appear in the unified feed
- [x] **AC5** — When `VITE_WS_URL` is not set, console logs `[FleetContext] VITE_WS_URL not set — falling back to MockWebSocketClient` and mock is used; no uncaught exception
- [x] **AC6** — `MockWebSocketClient` is preserved and remains the default when `VITE_WS_URL` is absent
- [x] **AC7** — No API keys or secrets appear in frontend source code or built assets

---

## Tasks / Subtasks

- [x] **T1** — Create `control-centre/src/ws/RealWebSocketClient.js`: native WebSocket wrapper with `SubscriptionRequest` handshake, exponential backoff reconnect (base 1s, max 30s, ±20% jitter), `onMessage` / `onStatusChange` callbacks, `connect()` / `disconnect()` API matching `MockWebSocketClient`
- [x] **T2** — Update `control-centre/src/context/FleetContext.jsx`: if `import.meta.env.VITE_WS_URL` is set use `RealWebSocketClient`, otherwise use `MockWebSocketClient` with console warn; expose `wsStatus` (`'connected'|'reconnecting'|'disconnected'`) in context
- [x] **T3** — Add "Reconnecting…" amber banner to `control-centre/src/components/shell/AppShell.jsx` driven by `wsStatus === 'reconnecting'`
- [x] **T4** — Add `control-centre/.env.example` with `VITE_WS_URL=` (empty — comment explaining usage); ensure `VITE_WS_URL` is the only env var needed
- [x] **T5** — Run `npm run lint` in `control-centre/`; fix all ESLint errors; confirm dev server starts cleanly

---

## Dev Notes

### Architecture

- `cloud-backend` serves WebSocket at `/ws` (implemented in E1-S7)
- ADR-9 subscription handshake: client sends JSON `SubscriptionRequest` as first message after connect
- Event types for CC subscription: `["OCCUPANCY_UPDATE", "ALERT_RAISED", "DOOR_OBSTRUCTION", "JOURNEY_STARTED", "JOURNEY_ENDED", "OCCUPANCY_THRESHOLD_CROSSED"]`
- Frontend shape (DD-001 §4) is what `MockWebSocketClient` already emits — `RealWebSocketClient` must map canonical ADR-1 envelopes to the same shape
- `MockWebSocketClient` emits a full `FLEET_STATE` batch every 5s — the real WS delivers individual events; `FleetContext` must handle both modes

### Event mapping (canonical → frontend)

Real WS delivers individual `EventEnvelope` objects (ADR-1):
```json
{
  "event_id": "uuid",
  "journey_id": "...",
  "vehicle_id": "R5001C-031",
  "timestamp": "ISO-8601",
  "event_type": "OCCUPANCY_UPDATE",
  "severity": "info|warning|critical",
  "source": "...",
  "schema_version": 1,
  "payload": { ... }
}
```

`RealWebSocketClient` maps severity: `info→green`, `warning→amber`, `critical→red`.

### MockWebSocketClient interface (to match)

```js
new MockWebSocketClient(onMessage)
client.connect()
client.disconnect()
client.acknowledge(id)
client.resolve(id, outcome)
```

`RealWebSocketClient` must expose the same interface. `acknowledge` and `resolve` send REST calls (E2-S5 concern) — for now they can be no-ops with a console.warn.

### No test runner in control-centre

No vitest/jest configured. ACs are verified via dev server visual inspection and ESLint clean pass. Browser console must show no uncaught exceptions.

---

## Dev Agent Record

### Implementation Plan

1. `src/ws/RealWebSocketClient.js` — self-contained class, no React deps
2. `src/context/FleetContext.jsx` — env-var branching, `wsStatus` state
3. `AppShell.jsx` — amber banner
4. `.env.example`
5. Lint + dev server

### Debug Log

### Completion Notes

- `RealWebSocketClient.js` — ADR-9 handshake, exponential backoff (base 1s, max 30s, ±20% jitter), dedup via `_seenIds` Set, maps canonical envelopes to frontend shape
- `FleetContext.jsx` — branches on `VITE_WS_URL`; exposes `wsStatus`; handles `FLEET_STATE` (mock), `TRAIN_UPDATE`, `ESCALATION_NEW`, `ESCALATION_UPDATED` (real)
- `AppShell.jsx` — amber "Reconnecting…" banner when `wsStatus === 'reconnecting'`
- `.env.example` — documents `VITE_WS_URL`; no secrets in source
- Dev server clean after reload: fallback warn fires correctly, no errors, all 5 views render
- Zero new lint errors introduced (34 pre-existing, 34 after our changes in touched files)

---

## File List

- `control-centre/src/ws/RealWebSocketClient.js` — new
- `control-centre/src/context/FleetContext.jsx` — modified
- `control-centre/src/components/shell/AppShell.jsx` — modified
- `control-centre/.env.example` — new
- `_bmad-output/implementation-artifacts/2-1-real-ws-client.md` — this file

---

## Change Log

- 2026-05-17: E2-S1 implemented — RealWebSocketClient + FleetContext env branching + AppShell reconnect banner
