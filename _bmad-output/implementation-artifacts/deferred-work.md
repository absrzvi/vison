# Deferred Work

## Deferred from: code review of 2-7-loading-skeletons (2026-05-18)

- **FleetMap renders unconditionally with empty fleet while siblings show skeletons** — FleetMap has its own empty-state handling; cosmetic inconsistency acceptable for PoC. Revisit in Epic 3 when real map data arrives.
- **Skeleton re-shows on every WS reconnect** — `fleet` resets to `[]` on reconnect, causing skeleton flash. Add a `wsReady` flag to FleetContext in a hardening story to distinguish "initial load" from "reconnect".


## Deferred from: code review of 1-1-e2e-skeleton-mvp (2026-05-17)

- **#18 `@app.on_event("startup")` deprecated** — migrate to `lifespan` context manager in a future story (FastAPI ≥0.93 deprecation)
- **#19 Timestamps stored as `TEXT` not `TIMESTAMPTZ`** — deliberate PoC simplification; impacts time-range queries; revisit in Epic 3 analytics work
- **#20 `_db_ready` global not safe under multi-worker Uvicorn** — PoC is single-worker; revisit before any production deployment
- **#21 `target_metadata = None` in Alembic** — no ORM models in PoC; autogenerate disabled intentionally
- **#22 Integration test hand-rolls DDL instead of running Alembic** — schema drift risk; fix when cloud-backend schema stabilises
- **#23 `dev-insecure-key` hardcoded default in config** — dev-only; must be overridden via `.env` before any production deployment

## Deferred from: code review of 1-3-postgresql-schema-alembic (2026-05-17)

- **#12 No index on `events.timestamp` / `event_type`** — analytics range queries and SSE alert feeds will full-scan; add composite index in Epic 3 analytics work
- **#13 No index on `journeys.vehicle_id`, `trip_number`** — fleet lookup queries degrade linearly; add when fleet-level queries are introduced
- **#14 `asyncio.run` in env.py risks `RuntimeError` if called while event loop running** — safe for current single-loop usage; review if env.py is ever called from an async context
- **#15 Missing `ingested_at` audit timestamp on events table** — no server-side insertion time; revisit before production if clock-skew detection or ingestion ordering is required
- **#16 `events.vehicle_id` denormalised, no FK/index** — design decision; add index when vehicle-level analytics queries are added

## Deferred from: code review of 1-4-sqlite-event-store (2026-05-17)

- **#6 `next_cursor` off-by-one** — non-null cursor returned when last page exactly fills `limit`; callers must handle empty follow-up page; fix when pagination contract is formalised
- **#7 Stale `after_event_id` silently restarts from page 0** — cloud-backend re-sync is idempotent so no data loss, but no error signal; revisit when sync client is hardened
- **#9 `insert_event` potential double-serialisation of payload** — depends on whether `EventEnvelope.payload` is already a JSON string; verify when oebb-shared serialisation is finalised
- **#11 `truncate_old_journeys` leaves orphan rows in `journeys` table** — journeys table not written by ingest route in this story; revisit when `POST /api/v1/journeys` is added
- **#13 `INSERT OR IGNORE` swallows CHECK constraint violations** — Pydantic validates upstream; accept for PoC; add explicit constraint error handling before production
- **#14 SIGKILL test uses `conn.close()` not true process crash** — true crash test requires subprocess; PoC scope; revisit in hardening phase
- **#15 `check_same_thread=False` without explicit lock** — single-worker PoC; add connection-per-request guard or explicit lock before multi-worker deployment

## Deferred from: code review of 1-5-apc-adapter (2026-05-17)

- **`timestamp` is an unvalidated raw string** [adapter.py:11,18] — pre-existing design decision; timestamp validation scope is broader than this story; revisit when contract tests are added
- **Hardcoded stale timestamps in mock data** [mock.py:3-8] — intentional determinism per spec; staleness logic is a downstream fusion container concern
- **`_MOCK_OCCUPANCY` mutable module-level dict** [mock.py:3] — no test mutation observed; freeze with `MappingProxyType` if test isolation issues arise
- **`car-2 count=182` exceeds realistic car capacity, no ceiling** [mock.py:5] — capacity constant out of scope for this story; revisit when occupancy alert thresholds are defined
- **`car_id` accepts empty string / whitespace without `ValueError`** [mock.py:16] — input validation not in scope; real APC identifier format not yet confirmed
- **`car_id` case sensitivity untested** [mock.py] — real APC wire format not yet confirmed; add normalisation test when format is locked

## Deferred from: code review of 2-2-kpi-strip-filter-tap-wiring (2026-05-17)

- **FleetContext provider `value` object not memoized** [FleetContext.jsx:79] — pre-existing pattern; recreated on every render causing context consumers to re-render unnecessarily. Wrap in `useMemo` in a follow-up refactor story; out of scope for this story.

## Deferred from: code review of 2-1-real-ws-client (2026-05-17)

- **`acknowledge`/`resolve` stubs log `console.warn` in production** [RealWebSocketClient.js] — explicitly scoped to E2-S5; wire REST endpoints then remove stubs
- **No banner feedback after max retries** [AppShell.jsx] — UX enhancement showing "Connection lost" after N attempts; out of this story's scope
- **`TRAIN_UPDATE` does not set `connected` state** [FleetContext.jsx] — pre-existing design; `connected` driven by `onStatusChange` callbacks only
- **Luggage escalations can be targeted by `ESCALATION_UPDATED`** [FleetContext.jsx] — pre-existing mock design; revisit when real escalation lifecycle is wired

## Deferred from: code review of 2-4-unified-feed-new-items-chip (2026-05-17)

- **Race: new item mid chip-tap smooth scroll — chip re-appears briefly** [UnifiedFeed.jsx] — low-frequency; fix if operators report confusion
- **`isAtTopRef(true)` jump-scroll on remount** [UnifiedFeed.jsx] — not in current nav flow; revisit if component is ever kept-alive across route changes
- **No upper bound on `newCount`** [UnifiedFeed.jsx] — cap at "99+" in a UI polish pass
- **`filtered` not memoized — O(n) diff on every render** [UnifiedFeed.jsx] — fine for PoC; wrap in `useMemo` when feed grows to hundreds of items
- **`role="button"` chip missing `aria-label`** [UnifiedFeed.jsx] — add `aria-label="Scroll to top, N new items"` in dedicated a11y pass

## Deferred from: code review of 2-3-fleet-list-passenger-count-sort (2026-05-17)

- **`showNormal` not reset when fleet empties then refills** [FleetList.jsx] — minor UX glitch; toggle state persists through SSE reconnect cycles; low-impact for PoC
- **No stable final tiebreak by `id`** [LiveMonitoring.jsx sortedFleet] — depot trains with equal passengers/severity jitter on SSE updates; add `a.id.localeCompare(b.id)` as last tiebreak when sort stability matters
- **Toggle button missing `aria-expanded` / `aria-controls`** [FleetList.jsx fleet-list__normal-toggle] — accessibility gap; address in a dedicated a11y pass

## Deferred from: code review of 2-5-escalation-detail-acknowledge-resolve (2026-05-17)

- **`VITE_API_KEY` shipped in browser bundle** [escalations.js:2] — known PoC limitation; Keycloak evaluation in progress; ADR-6/7 OAuth2/OIDC upgrade covers this at fleet rollout
- **`operator_id` is a static env var, not per-session** [FleetContext.jsx:8 `VITE_OPERATOR_ID`] — PoC approximation; real per-operator identity comes from Keycloak session at rollout
- **`computeElapsed` midnight wrapping bug** [EscalationDetail.jsx:31-47] — pre-existing function; HH:MM timestamp without date context produces wrong elapsed across midnight; revisit when backend sends ISO timestamps
- **`LUGGAGE_ESCALATIONS` re-appended on every FLEET_STATE** [FleetContext.jsx:49] — mock pattern; may cause duplicates on reconnect; revisit when luggage WS integration is real
- **`OPERATOR_ID` defaults to `'operator-unknown'` silently** [FleetContext.jsx:8] — PoC design; audit trail records sentinel value; must be per-operator session at fleet rollout (ADR-6/7)
- **ESC closes resolve modal discarding typed outcome silently** [EscalationDetail.jsx] — pre-existing UX pattern; add unsaved-changes guard when modal UX is hardened
- **Vitest `afterEach(vi.restoreAllMocks)` doesn't restore `vi.stubGlobal`** [escalations.test.js] — cosmetic; tests pass; `stubGlobal` persists for the file's lifetime which is fine
- **`environment: node` in vite test config — jsdom needed for React component tests** [vite.config.js] — acceptable for pure API module tests; switch to jsdom when component tests are added
- **No prop-types / runtime guard on `onResolve`/`onAcknowledge` props** [EscalationDetail.jsx] — pre-existing pattern; codebase has no prop-types; add if TypeScript is introduced

## Deferred from: code review of 2-5-escalation-detail-acknowledge-resolve round 2 (2026-05-17)

- **`TERMINAL_STATUSES` hardcoded** [FleetContext.jsx] — breaks if backend adds states like `closed`/`expired`; revisit when backend escalation status enum is locked
- **`setState` during render (prevEscId pattern) — StrictMode warnings** [EscalationDetail.jsx] — pre-existing; refactor to `useEffect` when component is overhauled
- **`ESCALATION_UPDATED` spread can null out `stillFrame` on partial payload** [FleetContext.jsx:56] — pre-existing; add payload schema validation when backend contract is formalised
- **Cancel handler doesn't reset `frameExpanded`** [EscalationDetail.jsx] — cosmetic drift; extract reset to shared helper when component is refactored
- **WS terminal tick landing before `submittedFromStatus` set** [EscalationDetail.jsx] — sub-millisecond window on single JS thread; acceptable for PoC
- **No request-in-flight de-dupe across multiple callers of `acknowledge`/`resolve`** [FleetContext.jsx] — no parallel call path exists in current UI; guard when escalation actions are exposed in more places

## Deferred from: code review of 2-6-train-detail-event-store-alert (2026-05-18)

- **AC5: ADR-10 error envelope not parsed — raw Error logged, not response body JSON** [FleetContext.jsx `fetchTrainAlerts`] — backend endpoint not live yet; revisit when REST error contract is defined
- **`td-alerts-list` testid on `<section>` always present — AC2 "list not rendered" is semantic** [TrainDetail.jsx] — section with heading always present; only list items absent; acceptable for PoC
- **CSS modifier uses `a.type` not severity — alert row styling differs from escalation rows** [TrainDetail.jsx] — alert canonical shape has no severity field; type-based CSS is correct for new shape
- **`trainAlerts` never pruned — memory growth in long operator sessions** [FleetContext.jsx] — PoC; add LRU eviction in a hardening story before fleet rollout
- **`API_KEY` in browser bundle** [escalations.js `_get`] — pre-existing; covered by ADR-6/7 Keycloak OAuth2 path
- **`_get` `res.json()` throws SyntaxError on non-JSON 200 response (proxy HTML page)** [escalations.js] — pre-existing pattern from `_post`; add content-type check in hardening pass
- **`confidence` `%` suffix assumes 0-100 scale — backend contract not yet locked** [TrainDetail.jsx] — revisit when API contract is finalised
- **WS ALERT_RAISED payload prepended as-is — may lack canonical shape fields** [FleetContext.jsx] — WS event contract not yet specced; add transformation/validation when backend defines the shape
