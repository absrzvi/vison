# Story 1.6': Cloud-Backend SSE Alert Fan-Out

**Epic:** 1 — Foundation & Shared Infrastructure
**Story:** 6' (E1-S6', new 2026-05-30 per ADR-20)
**Story Key:** 1-6-prime-cloud-backend-sse-fanout
**Status:** ready-for-dev
**Date Created:** 2026-05-30

> Ratifies the already-shipped `cloud-backend/src/cloud_backend/routes/alerts_sse.py` against the 7 BDD acceptance criteria added to [epics.md §E1-S6'](../planning-artifacts/epics.md) on 2026-05-30. Extends `ALERT_EVENT_TYPES` to include the two luggage event types per **ADR-20 Migration impact #3**. Adds the integration test surface called out in **ADR-20 Test required**. Low risk, high planning-debt repayment — code is already in production paths; this story converts it from "ad-hoc" to "specified, tested, locked in".

---

## Story

**As a** developer,
**I want** the cloud-backend to expose an SSE stream on `GET /api/v1/alerts/stream` that pushes a fixed allow-list of alert event types to authenticated subscribers,
**so that** the Control Centre Dashboard receives real-time alerts over a simple HTTP-friendly transport without a bidirectional WebSocket landside.

---

## Acceptance Criteria

1. **AC1 — Stream handshake.** `GET /api/v1/alerts/stream` with a valid `X-API-Key` header returns `200` with `Content-Type: text/event-stream`; each delivered event has fields `event: <event_type>`, `id: <event_id>`, `data: <json-payload>`; the connection stays open until the client closes it.

   > ⚠️ Current `alerts_sse.py` emits **only** `id:` and `data:` — the `event: <event_type>` field is **missing**. Implementation must add it (see Task T1).

2. **AC2 — Allow-list fan-out within 500ms.** When `publish_alert(event)` is called and `event["event_type"]` is in `ALERT_EVENT_TYPES = {ALARM_ACTIVE, ALERT_RAISED, ALERT_RESOLVED, LUGGAGE_RACK_SATURATION, UNATTENDED_BAG}`, the event is delivered to all connected subscribers within 500ms of `publish_alert` returning.

   > ⚠️ Current `ALERT_EVENT_TYPES` is `{"ALARM_ACTIVE", "ALERT_RAISED", "ALERT_RESOLVED"}` — luggage types are **missing**. Adding them per ADR-20 §Migration impact #3 absorbs the transport half of E5-S1.

3. **AC3 — Non-allow-listed events not pushed.** When `publish_alert` is called (via `ingest.py`) with a type **not** in `ALERT_EVENT_TYPES` (e.g. `OCCUPANCY_UPDATE`), the event is persisted to PostgreSQL (existing path) but **never** pushed over SSE. Per `ingest.py:97` the `if ev.event_type in ALERT_EVENT_TYPES:` gate already enforces this — this AC locks the behaviour with a test.

4. **AC4 — Unauthenticated → 401 ADR-10 envelope.** `GET /api/v1/alerts/stream` with no/invalid `X-API-Key` returns HTTP 401 with the ADR-10 envelope `{"error": "UNAUTHORIZED", "detail": "API key required", "recoverable": false}`; no stream is opened.

   > FastAPI wraps the HTTPException `detail` payload in `{"detail": <payload>}`. AC pattern matches `test_no_api_key_returns_401` in `tests/unit/test_rest_api.py:50` — the envelope lives under `body["detail"]`, not at the top level.

5. **AC5 — Concurrent subscribers, isolated queues.** With ≥3 concurrent subscribers, a single `publish_alert` is received by **all** subscribers; one slow consumer (queue saturated) **does not** block others. Current implementation uses `q.put_nowait(...)` with `maxsize=256` and silently drops on `QueueFull` — this satisfies the isolation requirement.

6. **AC6 — Worker restart, no duplicate delivery.** When a uvicorn worker is restarted while a client is connected, the client (via `EventSource` auto-reconnect) reconnects with its `Last-Event-ID`. Server replays from PostgreSQL via `_replay_since`. The same `event_id` must be seen **at most once** if `Last-Event-ID` is honoured. Reconnect reconciliation of cluster-wide state is the client's job via REST endpoints — there is no server-side wire-replay beyond `_replay_since`'s LIMIT 200.

7. **AC7 — Typecheck & test coverage.**
   - `mypy --strict src/cloud_backend/routes/alerts_sse.py` passes with zero errors.
   - `pytest tests/integration/test_alerts_sse.py` covers all five behaviours from **ADR-20 §Test required**.
   - No `X-API-Key` value appears in any test fixture file, log line, or assertion message — use the `_HEADERS` indirection pattern from `tests/unit/test_rest_api.py:18`.

---

## Tasks / Subtasks

- [ ] **T1 — Add `event:` field to SSE frame.** (AC1)
  - [ ] Update `_sse_generator` in `cloud-backend/src/cloud_backend/routes/alerts_sse.py` to yield `f"event: {event['event_type']}\nid: {event['event_id']}\ndata: {data}\n\n"`.
  - [ ] Update `_replay_since` output path to emit the same three lines.
  - [ ] Verify the keep-alive frame (`: keep-alive\n\n`) stays unchanged — it has no `event:` line by SSE convention.

- [ ] **T2 — Extend `ALERT_EVENT_TYPES` allow-list.** (AC2)
  - [ ] Change `alerts_sse.py:21` to `ALERT_EVENT_TYPES = frozenset({"ALARM_ACTIVE", "ALERT_RAISED", "ALERT_RESOLVED", "LUGGAGE_RACK_SATURATION", "UNATTENDED_BAG"})`.
  - [ ] Confirm `ingest.py:97` continues to gate on the imported constant (no separate copy in `ingest.py`).
  - [ ] No DB migration needed; `_replay_since` uses `ANY(:types)` so the new types automatically participate.

- [ ] **T3 — Write integration test file.** (AC7)
  - [ ] Create `cloud-backend/tests/integration/test_alerts_sse.py` using the testcontainers + `httpx.AsyncClient` + ASGI transport pattern from `tests/integration/test_analytics_endpoints.py:1-60`.
  - [ ] Reuse the `pg_url` module-scoped fixture pattern and the `_seed` helper shape.
  - [ ] Use `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` and the `async with client.stream("GET", "/api/v1/alerts/stream", headers=_HEADERS) as response:` pattern to read SSE frames without blocking on the infinite generator (the 1-7 dev notes flagged that `TestClient.stream()` blocks; ASGITransport streaming does not).

- [ ] **T4 — Integration test cases.** (AC1–AC6)
  - [ ] `test_subscribed_client_receives_alert_within_500ms` — open stream, call `publish_alert` from another task, assert frame parsed within 500ms with `event:`, `id:`, `data:` lines (AC1, AC2).
  - [ ] `test_non_allow_listed_event_not_pushed` — open stream, call `publish_alert({"event_type": "OCCUPANCY_UPDATE", ...})` — assert no frame received within 200ms timeout (AC3). Note: the gate is in `ingest.py:97`, not in `publish_alert` itself; `publish_alert` will enqueue anything. Test against the ingest route end-to-end (POST `/api/v1/events` with mixed events; assert only alert types are pushed).
  - [ ] `test_unauthenticated_returns_401_envelope` — GET without `X-API-Key`; assert 401 + `body["detail"]["error"] == "UNAUTHORIZED"` (AC4).
  - [ ] `test_three_concurrent_subscribers_all_receive_publish` — open 3 streams in parallel via `asyncio.gather`, publish once, assert all 3 receive (AC5).
  - [ ] `test_reconnect_with_last_event_id_no_duplicate` — open stream, capture an `event_id`, close, reconnect with `Last-Event-ID: <eid>`; publish a new alert before reconnect via the ingest path; assert the new alert arrives in the replay window and the previously-seen `event_id` is NOT re-emitted (AC6).
  - [ ] `test_luggage_events_pushed_over_sse` — publish a `LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` event; assert both reach subscribers (AC2 extension, locks ADR-20 §Migration impact #3).

- [ ] **T5 — Update `test_rest_api.py` unit assertions.** (AC1)
  - [ ] The two existing unit tests at `test_rest_api.py:221, 236` exercise `publish_alert` queue behaviour at the function level — they do not check the wire format. Leave them as-is; AC1 is covered by the integration suite.
  - [ ] Add one unit test `test_alerts_sse_event_types_includes_luggage` that asserts `LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` are in the imported `ALERT_EVENT_TYPES` — this provides a fast regression check without spinning up Postgres.

- [ ] **T6 — Mypy strict pass.** (AC7)
  - [ ] Run `cd cloud-backend && python -m mypy --strict src/cloud_backend/routes/alerts_sse.py` — must be zero errors.
  - [ ] If the `dict[str, object]` typing causes friction with the new `event:` line indexing, narrow with an explicit `event_type = str(event["event_type"])` local before the f-string.

- [ ] **T7 — ADR + epics housekeeping.** (no AC — documentation)
  - [ ] Add a one-line `**Code state (2026-05-30 → post-E1-S6'):**` update under ADR-20 in `_bmad-output/planning-artifacts/architecture.md` marking the test surface as ✅ shipped and the `event:` field gap as ✅ closed.
  - [ ] No epics.md change — the story is already listed and the ACs there match this file.

---

## Security Tests

**API / SSE endpoint security (one block for the only new/changed endpoint):**
- [ ] `test_unauthenticated_returns_401_envelope` — GET `/api/v1/alerts/stream` with no `X-API-Key` → 401, ADR-10 envelope under `body["detail"]`, no stream opened. (AC4 / T4)
- [ ] `test_wrong_api_key_returns_401` — GET with `X-API-Key: wrong` → 401. (mirrors `test_rest_api.py:60`)
- [ ] `test_no_api_key_in_logs` — capture structlog output during a full subscribe+publish+disconnect cycle; assert the `_HEADERS` API-key value never appears in any emitted log record. (AC7 last bullet)
- [ ] `test_no_api_key_in_fixtures` — `grep -r "<api-key-literal>" cloud-backend/tests/integration/test_alerts_sse.py` returns zero hits; the test uses `get_settings().api_key` indirection only. (AC7 last bullet)

**OEBB-specific (kept; rest removed as N/A):**
- [ ] No raw video, RTSP URL, or CCTV stream identifier appears in any SSE frame payload — assert the `payload` dict in delivered events contains only event-schema fields, not raw-source URLs. (CLAUDE.md §Security Boundaries — raw video never leaves the train)
- [ ] Untrusted-boundary check: events flowing through `publish_alert` originate from `ingest.py` which has already validated the `EventEnvelope` via Pydantic — assert that an attempt to call `publish_alert` directly with a malformed dict in unit test does not propagate a schema violation into the SSE frame (the existing implementation does no validation; this story does not add it — flag as Decision D1 below).

---

## Dev Notes

### Files this story touches (one UPDATE, one NEW)

| File | Action | Current state | What this story changes | What must be preserved |
|---|---|---|---|---|
| `cloud-backend/src/cloud_backend/routes/alerts_sse.py` | UPDATE | 108 lines. Defines `router` with `X-API-Key` security, `ALERT_EVENT_TYPES = frozenset({"ALARM_ACTIVE", "ALERT_RAISED", "ALERT_RESOLVED"})`, `_subscribers` set of asyncio queues, `publish_alert(event)` non-blocking fan-out with `put_nowait` + silent `QueueFull` drop, `_replay_since(last_event_id, db)` that queries the `events` table with `event_id > :after` LIMIT 200, `_sse_generator` that yields `f"id: {event['event_id']}\ndata: {data}\n\n"` plus a 15s keep-alive, and `GET /stream` endpoint returning a `StreamingResponse` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`. | (1) Add `event:` line to both replay and live frame emissions. (2) Add `LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` to `ALERT_EVENT_TYPES`. | Everything else: queue semantics, `QueueFull` drop, 15s keep-alive, `_replay_since` SQL (already uses `ANY(:types)` so it picks up the new types automatically), `Cache-Control`, `X-Accel-Buffering`, security dependency on `require_api_key`. Do not change the `_subscribers` set to a `WeakSet` or restructure into a class — the function-module pattern is intentional and matches the in-process PoC scope (ADR-20 §Open follow-up OQ-13). |
| `cloud-backend/tests/integration/test_alerts_sse.py` | NEW | does not exist | Create using the `tests/integration/test_analytics_endpoints.py` testcontainers pattern: module-scoped `pg_url` fixture from `PostgresContainer("postgres:16-alpine")`, async session factory, seed helper, `httpx.AsyncClient` with `ASGITransport`. | N/A (new file) |
| `cloud-backend/tests/unit/test_rest_api.py` | UPDATE | Has two `publish_alert` queue tests at lines 221 and 236. | Add `test_alerts_sse_event_types_includes_luggage`. | Do not touch the two existing tests. |
| `cloud-backend/src/cloud_backend/routes/ingest.py` | READ-ONLY | At line 97, imports `ALERT_EVENT_TYPES` from `alerts_sse.py` and gates `publish_alert` calls on `if ev.event_type in ALERT_EVENT_TYPES`. | **No change** — the gate continues to work via the imported reference; widening the frozenset in `alerts_sse.py` automatically widens the gate. | All ingest semantics. |

### ADR-20 freshness check

Per the persistent-fact rule (STORY CONTEXT RULE — ADR FRESHNESS): the only ADR contradicted by this story is ADR-20 itself, and the contradiction is in the **Code state** section — it lists the `event:` field as not-yet-shipped and the test file as not-yet-written. T7 adds a one-line update under that section. **No new ADR is needed** — ADR-20 already ratifies SSE; this story is its closeout.

ADR-9 is already marked SUPERSEDED for landside scope; no further update needed there.

### Payload-spec audit

Per the persistent-fact rule (STORY CONTEXT RULE — PAYLOAD SPEC AUDIT): events flowing through `publish_alert` are wire-format dicts assembled in `ingest.py:98-106` from a validated `EventEnvelope`. The dict has fields `{event_id, event_type, severity, journey_id, vehicle_id, timestamp, payload}`. No divergence between epics.md and `shared/src/oebb_shared/events/payloads.py` — the story does not change payload shapes; it only widens the type allow-list and adds the SSE wire-format `event:` line. No Decisions section needed for payload alignment.

### Why no `EventType` enum import

`ALERT_EVENT_TYPES` is a `frozenset[str]` of literal type names — it does NOT import from `oebb_shared.events.types.EventType`. Two reasons: (a) `publish_alert` receives wire-format dicts where `event_type` is already a string by the time it reaches the gate at `ingest.py:97`; (b) Karpathy §Simplicity First — no abstraction for a 5-element compile-time-known set. If a future story wires `oebb_shared`'s `EventType` enum into the cloud-backend routes more broadly, refactoring this gate to `frozenset(EventType.ALARM_ACTIVE, ...)` is a one-line change. Do not do it as part of this story.

### Testing pattern reference

- **Unit**: `cloud-backend/tests/unit/test_rest_api.py` — `TestClient(app, raise_server_exceptions=False)`, `app.dependency_overrides[get_db] = _mock_db`, `_HEADERS = {"X-API-Key": get_settings().api_key}`.
- **Integration**: `cloud-backend/tests/integration/test_analytics_endpoints.py:1-60` — `PostgresContainer("postgres:16-alpine")` module-scoped, `create_async_engine` on the asyncpg URL, `async_sessionmaker` factory, `_seed` helper that CREATEs tables and INSERTs fixture rows. **Reuse this skeleton**; do not invent a new fixture style.
- **SSE streaming pattern (NEW for this story)**: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` + `async with client.stream("GET", url, headers=_HEADERS) as resp:` + `async for chunk in resp.aiter_text():` parsing for SSE frames. The 1-7 dev notes (`1-7-rest-api-sse-fleet.md:52`) flagged that `TestClient.stream()` blocks indefinitely on infinite generators — that is a sync-TestClient limitation; ASGITransport with async streaming does not have it. Pattern your test on `httpx` docs (Context7: `/encode/httpx`, search "streaming SSE ASGI").

### Concurrent-subscriber test gotcha

For AC5, do **not** use `asyncio.gather` of three blocking `client.stream(...)` opens — each one will hold the connection until the test ends. Instead: open all three streams, kick off a background task that calls `publish_alert` (or POSTs to `/api/v1/events`) after a short `asyncio.sleep(0.05)`, then race each subscriber's first-frame read against an `asyncio.wait_for(..., timeout=1.0)`. Close all streams in a `finally`.

### Worker-restart simulation

True multi-process restart is out of scope for an integration test. Simulate per ADR-20's intent: (a) open a stream, capture an `event_id` from a delivered event, (b) close the stream (simulates the connection drop), (c) call `publish_alert` for a NEW alert while the client is disconnected so the new event is persisted via the existing `ingest.py` path, (d) reopen the stream with `Last-Event-ID: <captured>` and assert: (i) the new alert arrives via `_replay_since`, (ii) the previously-captured `event_id` is NOT re-emitted. This validates the de-dup contract without needing actual uvicorn process orchestration.

### Decisions

- **D1 — `publish_alert` direct-call schema validation.** Current `publish_alert` accepts `dict[str, object]` and does no validation. The ingest path guarantees a valid envelope, but a future caller could pass garbage. **Decision: do not add validation in this story.** Reasons: (a) `publish_alert` is a private function used only by `ingest.py`; (b) adding Pydantic validation on every fan-out call is per-event overhead the PoC does not need; (c) the security test in the Security Tests block documents this assumption so any future direct caller knows the responsibility. If this changes (e.g. a second producer is added), open a follow-up story.

### Project structure notes

- New file: `cloud-backend/tests/integration/test_alerts_sse.py` — joins three existing integration tests (analytics, capacity_review, postgres_schema, migrations). No new fixtures package needed.
- All paths are already consistent with `cloud-backend/CLAUDE.md` §Module Layout. No structural variance.

### References

- [epics.md §E1-S6'](../planning-artifacts/epics.md) lines 425–464 — source of all 7 ACs
- [architecture.md §ADR-20](../planning-artifacts/architecture.md) lines 580–642 — transport decision + test required + migration impact
- [architecture.md §ADR-9](../planning-artifacts/architecture.md) lines 550–578 — superseded for landside (informational only)
- [1-7-rest-api-sse-fleet.md](1-7-rest-api-sse-fleet.md) — original SSE implementation story; dev notes line 52 on `TestClient.stream()` blocking
- `cloud-backend/src/cloud_backend/routes/alerts_sse.py` — shipped code being ratified
- `cloud-backend/src/cloud_backend/routes/ingest.py:97` — the gate that consumes `ALERT_EVENT_TYPES`
- `cloud-backend/src/cloud_backend/api/auth.py` — `X-API-Key` 401 envelope shape (under `detail` key)
- `cloud-backend/tests/integration/test_analytics_endpoints.py:1-60` — testcontainers fixture pattern to mirror
- `cloud-backend/tests/unit/test_rest_api.py:18, 50, 221, 236` — unit-test patterns to mirror
- `shared/src/oebb_shared/events/payloads.py:128, 147` — `LUGGAGE_RACK_SATURATION` and `UNATTENDED_BAG` payload models (no story change needed; informational)
- `cloud-backend/CLAUDE.md` §Review Failure Scenarios — SSE worker restart, SSE queue backpressure (both covered by AC5, AC6)

---

## Previous Story Intelligence

- **From `1-7-rest-api-sse-fleet.md`**: `alerts_sse.py` was created in story 1-7 alongside auth + fleet overview. Dev notes flagged `TestClient.stream()` blocks indefinitely on the infinite SSE generator — the workaround at the time was a route-registration check. **This story replaces that workaround with a real streaming integration test** using `httpx.AsyncClient` + `ASGITransport`.
- **From `1-5-apc-adapter.md` review pattern**: integration tests for cloud-backend use the testcontainers shared module-scoped fixture; do not spin up a Postgres per test.
- **From `4-7-event-store-onboard-rest-api-websocket.md`**: the onboard event-store retained its WS handler. Do NOT cross-wire onboard WS code into the cloud-backend SSE path — they are different transports for different consumer sets per ADR-20's transport map.
- **From E5 luggage stories (5-1..5-4, all done)**: luggage events were originally routed via `RealWebSocketClient`. ADR-20 §Migration impact #3 mandates routing them via SSE instead. This story owns the cloud-backend half (allow-list extension); the client-side rewrite of `RealWebSocketClient` → SSE is E2-S1 (separate story, blocked on this one).

---

## Git Intelligence

Recent commits relevant to this story:

- `656f57d chore(planning): sprint-planning re-run — add Epic 6/7/8/9 + E1-S6'` — added this story to the sprint
- `87e083f docs(architecture): ADR-20 ratify SSE as landside push transport` — added ADR-20, which this story closes out
- `5b25a30 docs(planning): close 12/13 readiness findings — PRD v1.1 + epics backfill` — PRD §9 reworded for SSE; this story does not touch PRD
- `1a1ee39` and `0c84e9e` — unrelated to this story

The `M cloud-backend/Dockerfile` and `M cloud-backend/migrations/versions/0001_initial_schema.py` in the working tree are unrelated changes; do not include them in this story's commit. Stage only `alerts_sse.py`, the new `tests/integration/test_alerts_sse.py`, the `test_rest_api.py` additions, and the ADR-20 housekeeping line.

---

## Latest Tech Information

No new library introduced. Stack stays on:

- FastAPI `StreamingResponse` for SSE (already in use)
- `asyncio.Queue` per-subscriber (already in use)
- `httpx >=0.27` `AsyncClient` with `ASGITransport` for streaming integration tests — verify against `cloud-backend/pyproject.toml`; if missing, add to `[project.optional-dependencies] dev`.
- `testcontainers[postgres]` `postgres:16-alpine` (already in `test_analytics_endpoints.py`)

If `httpx` streaming details are unclear, query Context7 with `mcp__plugin_context7_context7__resolve-library-id` for `httpx`, then `query-docs` for "streaming response ASGI transport". Do not invent a new HTTP client.

---

## Project Context Reference

See `project-context.md` for: ÖBB rail domain, Karpathy guidelines, async stale-closure traps (relevant to multi-subscriber tests), and CSS tokens (not applicable to this story — backend only).

This story is **backend-only** — no UI work, no CSS, no Control Centre changes. E2-S1 (Real SSE Client) is the paired frontend story and is blocked on this one shipping.

---

## Dev Agent Record

### Agent Model Used

_(populated by dev agent)_

### Debug Log References

_(populated by dev agent)_

### Completion Notes List

_(populated by dev agent)_

### File List

_(populated by dev agent — expected: `cloud-backend/src/cloud_backend/routes/alerts_sse.py` MOD, `cloud-backend/tests/integration/test_alerts_sse.py` NEW, `cloud-backend/tests/unit/test_rest_api.py` MOD, `_bmad-output/planning-artifacts/architecture.md` MOD (one-line ADR-20 update))_

---

## Story Completion Status

- Status: **ready-for-dev**
- Completion note: Ultimate context engine analysis completed — comprehensive developer guide created. ACs lifted verbatim from epics.md §E1-S6' and locked against shipped code in `alerts_sse.py`; two implementation gaps (missing `event:` field, missing luggage types) and one test surface gap (no integration tests) explicitly enumerated as tasks. ADR-20 freshness checked: no new ADR required, one-line housekeeping update to existing ADR-20 added as T7. Decision D1 documents the deliberate non-addition of `publish_alert` validation.
