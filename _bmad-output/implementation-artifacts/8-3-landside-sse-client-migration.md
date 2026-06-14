---
baseline_commit: 2e2f5a4
---

# Story 8.3: Landside Live Client — WebSocket → SSE Migration (RealSseClient)

Status: ready-for-dev

<!-- Created 2026-06-14 via bmad-create-story (Amelia). Fixes the pre-existing landside live-transport
     mismatch surfaced 2026-06-14 during Epic-11 story 11-1 planning (11-1 Decision D8) and already
     recorded in architecture.md:642 + :1749. This story implements the post-ADR-20 rewrite of E2-S1
     (epics.md:517-551) that was NEVER built: story 2-1 shipped the WebSocket client (done 2026-05-17)
     BEFORE ADR-20 (2026-05-30) rewrote the epic to SSE, and nobody reconciled the divergence.
     Filed under Epic 8 (UI Hardening — the FleetContext epic) because Epic 2 is `done` and key 2-1 is taken.
     Review tier: FULL adversarial wire-replay (A2 — cross-container contract: SSE wire shape + frontend client).
     Permission tier: Tier 2 (local file edits only; no migration, no shell, no new backend route). -->

## Story

As **a Control Centre operator**,
I want **the dashboard's live client to consume the cloud-backend SSE stream (`GET /api/v1/alerts/stream`) instead of a dead WebSocket client pointed at a non-existent `/ws` endpoint**,
so that **fleet escalations and luggage events render in real time from the actually-shipped landside backend (ADR-20), the architecture violation at the client layer is closed, and Epic-11 story 11-1 has a real SSE client to attach the JWT `?token=` param to**.

## Context — why this story exists

The landside live-event path has a **transport mismatch** between the shipped frontend client and the shipped backend. Verified against live code (commit `2e2f5a4`):

- **Backend reality (correct, per ADR-20):** the cloud-backend's ONLY landside live-push route is **SSE** — `GET /api/v1/alerts/stream`, `media_type="text/event-stream"`, gated by `require_api_key`, reconnect via the `Last-Event-ID` **header**, server-side allow-list `ALERT_EVENT_TYPES`. See [alerts_sse.py:19-28,160-173](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py). **There is NO WebSocket endpoint anywhere in `cloud-backend/`** (grep `websocket`/`/ws` → zero matches).
- **Frontend reality (wrong):** the production live client is `RealWebSocketClient`, which does `new WebSocket(import.meta.env.VITE_WS_URL)` to a `/ws` endpoint ([RealWebSocketClient.js:2,88,102](../../control-centre/src/ws/RealWebSocketClient.js)) and sends an ADR-9-style `SUBSCRIPTION_REQUEST` JSON as its first message ([RealWebSocketClient.js:13-27](../../control-centre/src/ws/RealWebSocketClient.js)) — that is the **onboard event-store** WS handshake (ADR-9, intra-CCU), not the landside SSE contract.
- **`RealWebSocketClient` is DEAD in production.** `FleetContext.makeClient` selects it only when `VITE_WS_URL` is set ([FleetContext.jsx:24-31](../../control-centre/src/context/FleetContext.jsx)); the shipped [.env](../../control-centre/.env) and [.env.example](../../control-centre/.env.example) both leave `VITE_WS_URL=` **empty** → only `MockWebSocketClient` ever runs. There is no real `/ws` backend for it to talk to. The 2026-06-14 sprint note on 10-5 confirms the live mock seam is "`VITE_WS_URL`-unset→MockWebSocketClient".

**Root cause:** story [2-1-real-ws-client.md](2-1-real-ws-client.md) (done **2026-05-17**) built the WebSocket client for the pre-SSE design. **ADR-20** (**2026-05-30**, [architecture.md:616](../../_bmad-output/planning-artifacts/architecture.md)) then switched landside transport to SSE and **rewrote E2-S1** ([epics.md:517-551](../../_bmad-output/planning-artifacts/epics.md)) to specify a `RealSseClient` consuming `/api/v1/alerts/stream` with the WS client deleted — **but that rewrite was never implemented.** The shipped code still carries the dead WS client. ADR-20 itself records the open defect: *"❌ `control-centre/src/ws/RealWebSocketClient.js` still uses `new WebSocket(wsUrl)` — must be replaced with an `EventSource`-based client"* ([architecture.md:642](../../_bmad-output/planning-artifacts/architecture.md)); [architecture.md:1749](../../_bmad-output/planning-artifacts/architecture.md) names the intended replacement `RealSseClient`.

**Why now / coordination with 11-1:** Epic-11 story [11-1](11-1-jwt-auth-foundation-login.md) (JWT auth) **Decision D8** flagged this exact mismatch as out of its scope and handed the client-wiring to "whoever fixes the transport mismatch" — this story. D8 requires that the eventual SSE client carry the JWT in a **`?token=<jwt>` query param**, because a browser `EventSource` **cannot set an `Authorization` header**. 11-1 is `ready-for-dev` but **not yet built**; this story builds the SSE client **now** against the current `require_api_key` gate, structured so 11-1 adds `?token=` as a one-line change.

## Decisions (locked — review before dev)

- **D1 — SSE is the correct landside transport. Confirmed, not assumed.** ADR-20 ratifies it; the backend ships only the SSE route; the WS client has no backend and is mock-gated-out in production. This story does NOT add or restore any WebSocket path on the landside. ADR-9 stays the **onboard** event-store contract (intra-CCU) and is untouched.

- **D2 — Clean delete of `RealWebSocketClient.js`, NOT a deprecation stub (overrides epics.md:547).** The rewritten E2-S1 (epics.md:547) called for deleting the WS file "with a stub re-export that logs a one-time deprecation warning." That stub was speculative: the ONLY importer of `RealWebSocketClient` is `FleetContext.jsx` ([grep confirms](../../control-centre/src/context/FleetContext.jsx:3)) plus its own test file — and this story repoints `FleetContext` to `RealSseClient`. A deprecation stub would protect importers that do not exist (Karpathy: no speculative flexibility). **Decision: delete `RealWebSocketClient.js` and its test outright** after porting; no stub. (User-confirmed 2026-06-14.)

- **D3 — Build now against `require_api_key`; structure URL-building so 11-1 adds `?token=` in one line (sequencing, user-confirmed).** 11-1 is not in dev (only doc commits exist). This story ships the SSE client today against the shipped `require_api_key` gate. The SSE URL is assembled in **one `_buildUrl()` method** that today appends only the configured API key param (if cross-origin requires it — see D6); when 11-1 lands it adds `&token=${jwt}` at that single site. Do NOT import a token store or stub JWT plumbing now (it does not exist yet; 11-1 owns its shape) — just isolate URL construction so the future edit is one line. Cross-ref: [11-1 Decision D8](11-1-jwt-auth-foundation-login.md).

- **D4 — Preserve ALL event-normalisation logic from `RealWebSocketClient` — port, don't rewrite.** The WS client's envelope→frontend-message mapping is load-bearing and already review-hardened (stories 2-1, 5-1..5-4, 10-1, 10-6). It MUST be carried into `RealSseClient` byte-for-byte in behaviour: `normaliseCoachId` (`car-4`→`C4`), `SEVERITY_MAP` (`info/warning/critical`→`green/amber/red`), `_handleEnvelope` dispatch for every event type, dedup via the capped `_seenIds`/`_seenIdsQueue` Set (cap `SEEN_IDS_MAX = 1000`, oldest-evicted), `formatTimestamp` (de-AT locale), and the reconnect backoff constants. See "Preserve" inventory in Dev Notes. Losing or subtly changing any of these is an **AC FAIL** (regression).

- **D5 — `MockWebSocketClient` stays; the dev-fallback seam moves from `VITE_WS_URL` to `VITE_SSE_URL`.** Per epics.md:543-547, the real SSE client is selected when `VITE_SSE_URL` is set; absent it, `FleetContext` logs `[FleetContext] VITE_SSE_URL not set — falling back to MockWebSocketClient` and uses the mock. **The env var is renamed `VITE_WS_URL` → `VITE_SSE_URL`** (the WS name is now a misnomer; nothing real reads `VITE_WS_URL` after this story). `MockWebSocketClient`'s own class name keeps its legacy "WebSocket" misnomer to minimise churn — add a one-line source comment noting it now backs an SSE seam (epics.md:519).

- **D6 — Auth-on-the-wire today: same-origin assumption, `withCredentials` off, no key in URL unless cross-origin.** The shipped deploy serves the SPA from the cloud-backend / same-origin reverse proxy (control-centre/CLAUDE.md: "served by the cloud-backend or a reverse proxy"). On same-origin, the browser presents the session/cookie context and **no `X-API-Key` needs to ride the SSE URL** — matching how the shipped REST `src/api/*.js` calls already authenticate. **Do not put `VITE_API_KEY` in the SSE query string** (AC: "no API keys or secrets appear in built assets" — a key in the EventSource URL leaks to access logs and the bundle). If a future cross-origin deploy needs it, that is the same single `_buildUrl()` site D3 isolates. For this story: open `new EventSource(url)` with no credential param; rely on same-origin. Note this explicitly in the client source.

- **D7 — `EventSource` native reconnect + `Last-Event-ID` is the browser's job; do NOT hand-roll a reconnect socket loop.** The WS client hand-rolled `_open()`/backoff/`onclose`→retry because raw `WebSocket` has no built-in reconnect. `EventSource` reconnects automatically and replays `Last-Event-ID` on the wire. **Decision:** drive status off `EventSource` lifecycle events (`onopen`→`connected`; `onerror` while `readyState===CONNECTING`→`reconnecting`; explicit `disconnect()`→`disconnected`). The hand-rolled backoff/jitter constants are NOT needed for reconnect (the browser owns it) — do not port that machinery; porting it would be dead code (Karpathy). The amber "Reconnecting…" banner is driven by the same `onStatusChange('reconnecting')` contract `FleetContext`/`AppShell` already consume, so no consumer changes. **Keep dedup (`_seenIds`)** — D4 — because `Last-Event-ID` replay on reconnect can re-deliver the boundary event.

- **D8 — Honour the backend allow-list; map exactly the shipped SSE event types.** The backend pushes only `ALERT_EVENT_TYPES` = {`ALARM_ACTIVE`, `ALERT_RAISED`, `ALERT_RESOLVED`, `LUGGAGE_RACK_SATURATION`, `UNATTENDED_BAG`} ([alerts_sse.py:22-28](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). The WS client's `_handleEnvelope` handles a SUPERSET (it also maps `OCCUPANCY_UPDATE`, `DOOR_OBSTRUCTION`, `OCCUPANCY_THRESHOLD_CROSSED`, `JOURNEY_*`) — those are onboard/legacy WS types the landside SSE stream does NOT emit. **Decision:** port the full `_handleEnvelope` dispatch unchanged (the extra branches are harmless dead-ends on the SSE stream and keep the mapper a faithful port — D4), BUT the SSE frame parser must read the SSE `event:` field and the `id:` field, not a JSON `event_type`/`event_id` inside `data` only — see D9. Do NOT prune the superset branches in this story (out of scope; mention as a possible follow-up).

- **D9 — SSE frame shape ≠ WS frame shape. This is the one genuinely-new parsing concern.** The WS client received one JSON object per `onmessage` and read `envelope.event_type`/`envelope.event_id` from inside it. The backend SSE frame is `event: <event_type>\nid: <event_id>\ndata: <json>\n\n` ([alerts_sse.py:69](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)) where `data` is the full event dict (which ALSO contains `event_type`/`event_id` — [alerts_sse.py:118-127](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). With `EventSource`, named events do NOT fire the default `onmessage` — they fire listeners registered per event name via `addEventListener(event_type, ...)`. **Decision:** register one listener per allow-list type (`ALARM_ACTIVE`, `ALERT_RAISED`, `ALERT_RESOLVED`, `LUGGAGE_RACK_SATURATION`, `UNATTENDED_BAG`), each parsing `JSON.parse(ev.data)` into the envelope and delegating to the ported `_handleEnvelope`. `ev.lastEventId` provides the id for dedup. Because `data` carries `event_type` internally, `_handleEnvelope` keeps working on the parsed envelope unchanged. (Verify the exact backend `data` JSON keys against [alerts_sse.py:118-127](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py) before wiring — see AC2.)

- **D10 — ADR-9/ADR-20 cross-refs + story 2-1 status note updated in the same commit (ADR-FRESHNESS rule).** ADR-20:642 records the WS-client defect as OPEN ("must be replaced"); this story closes it. Update that line to "✅ Closed by E8-S3 (2026-06-14): `RealSseClient` ships; `RealWebSocketClient.js` deleted." Add a one-line superseded-note to [2-1-real-ws-client.md](2-1-real-ws-client.md) ("Transport superseded by ADR-20; WS client replaced by `RealSseClient` in E8-S3"). No ADR *decision* changes (ADR-20 already says SSE; we are making code match it) — so this is a cross-reference freshness update, not a new ADR.

## Acceptance Criteria

**AC1 — SSE client opens against the configured URL; same public API as the WS client**
Given the dashboard loads with `VITE_SSE_URL` set, when `FleetContext` initialises, then a `new RealSseClient(onMessage, onStatusChange)` is constructed and `connect()` opens an `EventSource` against `VITE_SSE_URL` (default reference `/api/v1/alerts/stream`). The class exposes the **identical public API** to the old WS client — `constructor(onMessage, onStatusChange)`, `connect()`, `disconnect()` — so [FleetContext.jsx](../../control-centre/src/context/FleetContext.jsx) needs no shape change beyond the import + the `VITE_WS_URL`→`VITE_SSE_URL` selection rename. No `SUBSCRIPTION_REQUEST`/handshake message is sent (server-side allow-list per ADR-20).

**AC2 — every shipped SSE event type maps to the correct frontend message (ported behaviour preserved)**
Given an open stream, when the backend pushes a frame for each of `ALARM_ACTIVE`, `ALERT_RAISED`, `ALERT_RESOLVED`, `LUGGAGE_RACK_SATURATION`, `UNATTENDED_BAG` in the real backend frame shape (`event:`/`id:`/`data:` per [alerts_sse.py:69](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)), then `RealSseClient` parses `data` as the ADR-1 envelope and emits the SAME frontend `onMessage` payloads the WS client produced for those types: `ALERT_RAISED`→`ESCALATION_NEW`; `LUGGAGE_RACK_SATURATION`/`UNATTENDED_BAG`→`LUGGAGE_EVENT` with the documented `{ id, trainId, coachId, state, title, detail, confidence, timestamp, stillFrame }` shape and `normaliseCoachId` applied; `ALERT_RESOLVED`/`ALARM_ACTIVE`→the existing frontend handling. `coach_id`/`car_id` normalisation, `SEVERITY_MAP`, and `formatTimestamp` (de-AT) are byte-identical to the WS client. (Verified by porting `RealWebSocketClient`'s `_handleEnvelope` and pinning the existing [`RealWebSocketClient.test.js`](../../control-centre/src/ws/__tests__/RealWebSocketClient.test.js) luggage/dedup assertions against the new client.)

**AC3 — dedup survives `Last-Event-ID` reconnect replay**
Given the stream drops and the browser reconnects sending `Last-Event-ID`, when the backend replays the boundary event(s) that the client already delivered, then the capped `_seenIds` dedup (cap 1000, oldest-evicted) suppresses the duplicate — no duplicate item appears in the unified feed (mirrors the WS client's dedup; mirrors [alerts_sse.py:140-144](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py) replay semantics). `event_id === 0`/falsy-but-valid ids are handled via the `!= null` check, not truthiness (preserve [RealWebSocketClient.js:149](../../control-centre/src/ws/RealWebSocketClient.js)).

**AC4 — status lifecycle drives the existing "Reconnecting…" banner with no consumer change**
Given `RealSseClient`, when `EventSource` fires `onopen` → `onStatusChange('connected')` and `connected=true`; when it fires `onerror` while `readyState === EventSource.CONNECTING` → `onStatusChange('reconnecting')` (amber banner shown, fleet state NOT wiped); when `disconnect()` is called → `onStatusChange('disconnected')` and the `EventSource` is closed. The `wsStatus` contract consumed by [FleetContext.jsx:96-99](../../control-centre/src/context/FleetContext.jsx) and the AppShell banner is unchanged (`'connected'|'reconnecting'|'disconnected'`). Browser-native reconnect/`Last-Event-ID` is relied on — no hand-rolled retry socket loop.

**AC5 — mock fallback on unset `VITE_SSE_URL`; no crash**
Given `VITE_SSE_URL` is unset, when the app starts, then the browser console logs exactly one `[FleetContext] VITE_SSE_URL not set — falling back to MockWebSocketClient` warning and `MockWebSocketClient` is used; no uncaught exception. `MockWebSocketClient` remains the dev default and is otherwise unchanged (legacy name retained with a one-line "now an SSE seam" source comment).

**AC6 — dead WS client and `VITE_WS_URL` removed; no dangling references**
Given this story lands, then [`src/ws/RealWebSocketClient.js`](../../control-centre/src/ws/RealWebSocketClient.js) and [`src/ws/__tests__/RealWebSocketClient.test.js`](../../control-centre/src/ws/__tests__/RealWebSocketClient.test.js) are deleted; `VITE_WS_URL` is removed from [.env](../../control-centre/.env) and [.env.example](../../control-centre/.env.example) and replaced by `VITE_SSE_URL=` (empty, with the ADR-20 comment); and `grep -rn "RealWebSocketClient\|VITE_WS_URL" control-centre/src control-centre/.env*` returns **zero** matches. The ported tests live with the new client (`src/sse/__tests__/RealSseClient.test.js`). No deprecation stub (D2).

**AC7 — no secrets in the SSE URL or built assets**
Given the built bundle (`npm run build`), then no `VITE_API_KEY`/`X-API-Key`/JWT literal appears in any SSE URL construction or built asset; the `EventSource` opens same-origin with no credential query param (D6). `_buildUrl()` is the single, isolated site where a future `?token=` (11-1) or cross-origin key would be appended.

**AC8 — ADR cross-refs + story 2-1 note updated; gates green**
Given this story lands, then [architecture.md:642](../../_bmad-output/planning-artifacts/architecture.md) is updated from the open "❌ … must be replaced" defect to "✅ Closed by E8-S3"; [2-1-real-ws-client.md](2-1-real-ws-client.md) carries a one-line superseded note (D10); ADR-9 vs ADR-20 separation is reaffirmed (no ADR decision change). `npm run lint` clean; `npm test` (`vitest run`) green including the ported `RealSseClient` tests; the live feed is **browser-verified** per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) "Verification Requirement" — golden path (live event renders) + at least one edge state (reconnect banner shows + clears, or mock-fallback path), console monitored for errors.

## Tasks / Subtasks

- [ ] **T1 — Create `src/sse/RealSseClient.js`** (AC1, AC2, AC3, AC4, AC7; D3, D4, D6, D7, D9)
  - [ ] New file `control-centre/src/sse/RealSseClient.js`. Header comment: connects to the cloud-backend SSE stream `/api/v1/alerts/stream` (ADR-20); drop-in for `MockWebSocketClient`; same public API `(onMessage, onStatusChange)` + `connect()`/`disconnect()`.
  - [ ] **Port verbatim** from `RealWebSocketClient.js`: `normaliseCoachId`, `SEVERITY_MAP`, `SEEN_IDS_MAX`, `_seenIds`/`_seenIdsQueue` + `_trackSeenId`, `formatTimestamp`, and the **entire `_handleEnvelope` body** (all branches, unchanged — D4/D8). Do NOT port `BACKOFF_*`/`JITTER_FACTOR`/`backoffDelay`/`_attempt`/`_retryTimer`/`_open()` reconnect machinery (D7 — `EventSource` owns reconnect).
  - [ ] `_buildUrl()` (D3/D6/D7): returns `VITE_SSE_URL` as-is for this story (same-origin, no credential param). Single isolated site for a future `&token=` (11-1) / cross-origin key. Add the D6 comment.
  - [ ] `connect()`: `this._es = new EventSource(this._buildUrl())`; register `onopen`→`onStatusChange('connected')`; `onerror`→ if `readyState===EventSource.CONNECTING` then `onStatusChange('reconnecting')` (preserve state, do not wipe); `addEventListener(<type>, handler)` for each of the 5 allow-list types (D8/D9). Each handler: `JSON.parse(ev.data)`→envelope, pass to `_handleEnvelope` (which reads `event_type` from the parsed `data`); use `ev.lastEventId` where an id is needed and `data.event_id` is absent.
  - [ ] `disconnect()`: detach listeners, `this._es.close()`, `onStatusChange('disconnected')`.
  - [ ] Guard: if `VITE_SSE_URL` is unset, `connect()` calls `onStatusChange('disconnected')` and returns (mirrors WS client's empty-url guard) — the mock-selection happens in `FleetContext` (T3), but the client must not throw if constructed without a URL.
- [ ] **T2 — Port the client tests to `src/sse/__tests__/RealSseClient.test.js`** (AC2, AC3; D4)
  - [ ] Move + adapt the luggage `LUGGAGE_RACK_SATURATION`/`UNATTENDED_BAG` handler assertions and the dedup test from [`RealWebSocketClient.test.js`](../../control-centre/src/ws/__tests__/RealWebSocketClient.test.js) to drive `RealSseClient` (mock `EventSource`: dispatch named events with `data`/`lastEventId`). Assert the same `LUGGAGE_EVENT` payload shapes and that a replayed `event_id` is deduped.
  - [ ] **Add a frame-shape test (the genuinely-new surface, D9):** feed a real backend frame string shape — `event: ALERT_RAISED`, `id: <uuid>`, `data: <JSON env>` — and assert `_handleEnvelope` receives the parsed envelope and emits `ESCALATION_NEW`. This is the SSE-vs-WS parsing seam the WS tests never covered.
- [ ] **T3 — Repoint `FleetContext` + rename the selection seam** (AC1, AC4, AC5; D5)
  - [ ] [FleetContext.jsx:3](../../control-centre/src/context/FleetContext.jsx): import `RealSseClient` from `../sse/RealSseClient` (drop the `RealWebSocketClient` import).
  - [ ] [FleetContext.jsx:24-31](../../control-centre/src/context/FleetContext.jsx) `makeClient`: select `RealSseClient` when `import.meta.env.VITE_SSE_URL` is set; else `console.warn('[FleetContext] VITE_SSE_URL not set — falling back to MockWebSocketClient')` + `MockWebSocketClient`. Rename the local `wsUrl` read accordingly. Leave `wsStatus`/`wsRef` names as-is (renaming them is churn beyond scope — Karpathy surgical; note the misnomer in a comment if helpful).
  - [ ] Add a one-line comment on the `MockWebSocketClient` import noting it now backs the SSE seam (D5).
- [ ] **T4 — Delete the dead WS client + rename env var** (AC6; D2, D5)
  - [ ] Delete `control-centre/src/ws/RealWebSocketClient.js` and `control-centre/src/ws/__tests__/RealWebSocketClient.test.js`. If `src/ws/` is now empty, remove the empty dir.
  - [ ] [.env](../../control-centre/.env): `VITE_WS_URL=` → `VITE_SSE_URL=`. [.env.example](../../control-centre/.env.example): replace the `VITE_WS_URL` block with `VITE_SSE_URL=` + comment "Cloud backend SSE stream URL (ADR-20). Leave empty to use MockWebSocketClient (local dev default). Example: VITE_SSE_URL=/api/v1/alerts/stream".
  - [ ] Verify `grep -rn "RealWebSocketClient\|VITE_WS_URL" control-centre/src control-centre/.env*` → zero matches.
- [ ] **T5 — ADR cross-refs + story 2-1 note** (AC8; D10) — *ADR-FRESHNESS rule*
  - [ ] [architecture.md:642](../../_bmad-output/planning-artifacts/architecture.md): change the open "❌ `RealWebSocketClient.js` still uses `new WebSocket` … must be replaced" line to "✅ Closed by E8-S3 (2026-06-14): `RealSseClient` ships against `/api/v1/alerts/stream`; `RealWebSocketClient.js` deleted." Leave the ADR-9-vs-ADR-20 separation text intact.
  - [ ] [2-1-real-ws-client.md](2-1-real-ws-client.md): add a one-line note under Status — "Transport superseded by ADR-20 (2026-05-30); WS client replaced by `RealSseClient` in E8-S3 (2026-06-14)."
- [ ] **T6 — Gates + browser-verify** (AC8) — *control-centre/CLAUDE.md Verification Requirement*
  - [ ] `npm run lint` clean; `npm test` (= `vitest run`) green incl. ported `RealSseClient` tests.
  - [ ] Browser-verify per [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md): run `npm run dev`; with `VITE_SSE_URL` set at a stream that emits an `ALERT_RAISED`, confirm the escalation renders live; exercise one edge state (drop the stream → amber "Reconnecting…" banner shows then clears on resume, fleet state preserved); monitor console for errors. If no live backend is convenient, verify the mock-fallback golden path (unset `VITE_SSE_URL` → warning + mock renders) and the reconnect banner via a forced `onerror`. Capture proof (screenshot/console).

## Dev Notes

### Files being modified (UPDATE) — current state / change / preserve  *(FULL-FILE-READS rule)*

- **[src/ws/RealWebSocketClient.js](../../control-centre/src/ws/RealWebSocketClient.js)** (247 lines, read in full) — *current:* raw-`WebSocket` client to `VITE_WS_URL`/`/ws`; sends `SUBSCRIPTION_REQUEST`; hand-rolled `_open()`/backoff/`onclose` reconnect; `_handleEnvelope` maps a SUPERSET of event types; capped `_seenIds` dedup; `normaliseCoachId`/`SEVERITY_MAP`/`formatTimestamp`. *change:* DELETE after porting the mapper+dedup+helpers into `RealSseClient` (D2/D4). *preserve (port byte-for-byte):* `normaliseCoachId`, `SEVERITY_MAP`, `SEEN_IDS_MAX`+`_trackSeenId`+`_seenIds`/`_seenIdsQueue`, `formatTimestamp`, **all of `_handleEnvelope`** incl. the `event_id != null` dedup guard ([:149](../../control-centre/src/ws/RealWebSocketClient.js)) and the luggage `car_id`/`fill_pct`/`dwell_s` detail strings ([:206-242](../../control-centre/src/ws/RealWebSocketClient.js)). *drop (do NOT port):* `BACKOFF_*`/`JITTER_FACTOR`/`backoffDelay`/`_attempt`/`_retryTimer`/`_open()` reconnect loop + the `SUBSCRIPTION_REQUEST` handshake (D7 — EventSource owns reconnect; SSE has no handshake).
- **[src/context/FleetContext.jsx](../../control-centre/src/context/FleetContext.jsx)** (359 lines, read in full) — *current:* `makeClient` ([:24-31](../../control-centre/src/context/FleetContext.jsx)) picks `RealWebSocketClient` iff `VITE_WS_URL` set, else `MockWebSocketClient`; `onMessage` switch handles `FLEET_STATE`/`LUGGAGE_EVENT`/`ESCALATION_*`/`ALERT_*`/`TRAIN_UPDATE`/`CAMERA_*`; `onStatusChange`→`wsStatus`/`connected`. *change:* swap import + selection to `RealSseClient`/`VITE_SSE_URL` + warning string (T3). *preserve:* the ENTIRE `onMessage` handler (it consumes the frontend message shapes `RealSseClient` must keep emitting — this is the contract D4 protects), `wsStatus`/`wsReady`/`connected` state, the `luggageEventsRef` stale-closure mirror, all REST/preferences effects. Do NOT touch the message-handling switch.
- **[src/ws/__tests__/RealWebSocketClient.test.js](../../control-centre/src/ws/__tests__/RealWebSocketClient.test.js)** — *current:* luggage handler + dedup tests. *change:* move/adapt to `src/sse/__tests__/RealSseClient.test.js`, then delete original (T2/T4).
- **[.env](../../control-centre/.env) / [.env.example](../../control-centre/.env.example)** — *current:* `VITE_WS_URL=` (empty). *change:* → `VITE_SSE_URL=` (T4).

### Backend contract (READ — do not modify in this story)

- **[alerts_sse.py](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)** is the wire source of truth. Frame shape: `event: {event_type}\nid: {event_id}\ndata: {json}\n\n` ([:69](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). `data` JSON keys: `event_id, event_type, severity, journey_id, vehicle_id, timestamp, payload` ([:118-127](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). Allow-list `ALERT_EVENT_TYPES` ([:22-28](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). Reconnect cursor via `Last-Event-ID` header → `_replay_since` ([:165](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py), LIMIT 200). Keep-alive comment frames every 15s ([:154](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)) — `EventSource` ignores comment lines; no handling needed. **This story does NOT change the backend** (the route already ships and is correct). The only backend-adjacent edit is the ADR cross-ref doc (T5).

### Why the WS↔SSE envelope mapping still works after the port

`RealWebSocketClient._handleEnvelope` destructures `{ event_id, vehicle_id, event_type, severity, payload, timestamp }` from its argument. The backend SSE `data` JSON carries exactly those keys ([alerts_sse.py:118-127](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)). So once `RealSseClient` does `JSON.parse(ev.data)` and passes the result to the ported `_handleEnvelope`, the mapper is unchanged. The ONLY new code is the SSE frame ingestion (named-event listeners reading `event:`/`id:`/`data:`) — D9. The WS `onmessage`-single-JSON path is replaced by per-type `addEventListener`.

### `EventSource` specifics (verify via Context7 before wiring — MDN/WHATWG semantics)

- Named SSE events (`event: X`) do **not** trigger `onmessage`; register `addEventListener('X', cb)`. The default `onmessage` only fires for frames with no `event:` field.
- `EventSource` auto-reconnects on transport error and sends the last `id:` as `Last-Event-ID` automatically; `readyState` is `CONNECTING(0)`/`OPEN(1)`/`CLOSED(2)`. Use `CONNECTING` during `onerror` to distinguish "reconnecting" from a terminal close.
- `EventSource` cannot set request headers (the reason 11-1's D8 uses `?token=`). For same-origin it carries cookies automatically; `withCredentials` only matters cross-origin (D6).
- `ev.lastEventId` is available on the event object for the dedup id when needed.

### Testing standards

- `vitest` (control-centre). Mock `EventSource` in tests (jsdom has no native SSE) — a small fake exposing `addEventListener`, `close`, `readyState`, and a `_emit(type, {data, lastEventId})` helper. **Real-producer-shape seeding (REAL-PRODUCER TEST SEEDING rule):** the frame-shape test (T2) MUST feed the actual backend `data` JSON key set (`event_id/event_type/severity/vehicle_id/timestamp/payload`) and the `event:`/`id:` framing from [alerts_sse.py:69,118-127](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py) — NOT a hand-shaped object that bypasses the real frame contract. A green test that feeds a synthetic flat object would pass while the SSE parse is broken (the exact test/prod-divergence species epic-10 was burned by).
- No new CSS in this story → CSS-token rule N/A. (The amber banner already exists from story 2-1; this story only re-drives its existing `wsStatus` trigger.)
- `mypy`/`ruff` N/A (no Python changed — backend is read-only here).

### Project Structure Notes

- New client lives at `src/sse/RealSseClient.js` per epics.md:513,551 and the [control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) `src/ws/` → SSE-client convention ("`src/ws/` — WebSocket/SSE client"). The epic explicitly names `src/sse/RealSseClient.js`, so use `src/sse/` (not `src/ws/`).
- No variance from unified structure. `MockWebSocketClient` stays at `src/mock/websocket.js` (untouched).

### References

- [Source: epics.md#E2-S1 (rewritten by ADR-20)](../../_bmad-output/planning-artifacts/epics.md) — the never-implemented SSE-client spec this story discharges (lines 517-551).
- [Source: architecture.md#ADR-20](../../_bmad-output/planning-artifacts/architecture.md) — landside SSE transport (line 616); the open WS-client defect (line 642); `RealSseClient` named (line 1749).
- [Source: architecture.md#ADR-9](../../_bmad-output/planning-artifacts/architecture.md) — superseded-for-landside WS contract (line 586); retained onboard-only.
- [Source: 11-1-jwt-auth-foundation-login.md#D8](11-1-jwt-auth-foundation-login.md) — `?token=` requirement + the cross-task hand-off that scopes this story.
- [Source: 2-1-real-ws-client.md](2-1-real-ws-client.md) — the original WS client this supersedes (done pre-ADR-20).
- [Source: cloud-backend/routes/alerts_sse.py](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py) — backend SSE wire contract (read-only).
- [Source: control-centre/src/ws/RealWebSocketClient.js](../../control-centre/src/ws/RealWebSocketClient.js) — normalisation logic to port.
- [Source: control-centre/CLAUDE.md](../../control-centre/CLAUDE.md) — verification requirement + SSE reconnect failure scenario.

### Permission tier & review tier

- **Permission tier: Tier 2** — local file edits only (new JS client, FleetContext repoint, env rename, doc cross-refs). No DB migration, no shell/external, no new backend route, no auth change. Normal dev mode.
- **Review tier: FULL adversarial wire-replay** (A2 — this is a cross-container contract change at the SSE wire boundary, the highest-risk review class per epic-10-retro). The code-review MUST replay the **real backend SSE frame shape** (`event:`/`id:`/`data:` from [alerts_sse.py:69](../../cloud-backend/src/cloud_backend/routes/alerts_sse.py)) against `RealSseClient`, not a synthetic JSON blob — the WS→SSE frame difference (D9) is exactly where a green-but-wrong test would hide.

### Failure scenarios (OEBB-specific, require system understanding)

1. **`Last-Event-ID` replay double-delivery (control-centre SSE reconnect):** the stream drops mid-feed; on reconnect the backend `_replay_since` re-sends the boundary `ALERT_RAISED` the client already showed. The dedup `_seenIds` must suppress it so the unified feed shows the escalation once — AND the dedup must use `event_id != null` (not truthiness), because a valid `event_id` of `0` would otherwise be treated as "unseen" forever. Verify both the suppress and the `0`-id edge.
2. **Named-event vs default-`onmessage` mis-wiring (D9):** if the dev registers only `onmessage` (the WS habit) instead of `addEventListener` per allow-list type, EVERY live event is silently dropped (named SSE frames never hit `onmessage`) — the feed looks "connected" (green banner) but never updates. The browser-verify golden path (live `ALERT_RAISED` renders) is what catches this; a unit test that calls `_handleEnvelope` directly would NOT.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
