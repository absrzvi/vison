# Deferred Work

## Deferred from: post-followup code review on 4-5-inference-safety-accessibility (2026-05-20, opus-4.7)

- **S2** — `cameras.json:14` `vestibule_zone` polygon is identical to the `aisle` `seat_zones` polygon `[[200,300],[440,300],[440,480],[200,480]]`. Every person standing in the aisle is double-counted as in_vestibule, so VESTIBULE_CONGESTION will fire on aisle crowding rather than near-door clustering. Tolerable in the single-camera PoC (only one door camera, fixed simulator stream); real deployments need a near-door rectangle. Needs ops/UX polygon data — out of PoC scope. [cameras.json:14]
- **S3** — Test hygiene: 5 `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited` in `test_door_obstruction.py` and `test_vestibule_congestion.py`. Tests bind `resp.raise_for_status` as `AsyncMock` but production calls it synchronously (`resp.raise_for_status()` on httpx.Response). Fix is mechanical: bind as `MagicMock`. No production impact.

## Deferred from: code review follow-up on 4-5-inference-safety-accessibility (2026-05-20)

- **R3 (PoC)** — `RampDeployedPayload.car_id` is sourced from `settings.vehicle_id` (whole train), not a coach-level identifier. vlan-pollers `POST /context` carries no per-coach signal. Resolution requires either (a) adding `ramp_car_id` to `ContextPushModel` with vlan-pollers cooperation or (b) injecting a `door_id → car_id` reverse map from `cameras.json` into `SafetyHandler`. Decision: ship as-is for PoC; revisit with E4-S6 (fusion) when ZFR per-coach signals are available. [safety.py module docstring; safety.py:55]
- **R11** — `OccupancyCallback._event_store_client` posts to `fusion_url` — variable name misleading. Cross-cutting rename to `_http_client`. Pre-existing single-client architecture decision from 4-4. [callback.py]
- **R15** — `_handle_suitcase_door_obstruction` processes only `bboxes[0]` — multiple suitcases per frame silently dropped. PoC simplification. [callback.py:210]
- **R16** — Slip/fall has no rate-limit / in-flight suppression at source — relies on fusion suppression (E4-S6 contract). [zone_counter.py:244-280]
- **R17** — Suitcase obstruction `track_id` deduplication semantics — now generates unique per-emit IDs (`suitcase-{ms}`) via R12 fix; fusion contract for whether to treat as distinct objects vs single logical obstruction is still TBD in E4-S6.
- **R18** — Multi-camera-per-car: partially resolved. `_track_bboxes` now keyed by `(car_id, camera_id)` and `_camera_zone` keyed by `(car_id, camera_id)` (R7 fix). Remaining gap: `_handle_suitcase_door_obstruction` uses `(camera_id, -1)` sentinel — collision-free across cameras but only one suitcase per camera tracked at a time.
- **R20** — `zone_counter.update()` serially awaits 4 POSTs — safety prioritization inverted vs occupancy. Fusion suppression mitigates. [zone_counter.py:152-159]
- **R22** — Person/suitcase obstruction emit cadence every 2 frames (~666ms at 3fps) after counter reset — relies on fusion suppression. [callback.py:220-221, 252-253]

## Deferred from: code review of 4-5-inference-safety-accessibility (2026-05-19)

- **F14** — Private access `self._zone_counter._journey_holder.journey_id` in `callback.py._post_accessibility_event`. Pre-existing pattern in codebase (same pattern in zone_counter.py); refactor to a public accessor when codebase-wide cleanup pass is done. [callback.py]

## Deferred from: code review of 4-4-inference-detection-tracking-occupancy (2026-05-19)

- **B** — `asyncio.Lock` constructed before event loop: PoC targets Python 3.11 where deferred loop-binding is fine; pre-3.10 would warn. No action needed until target Python version changes. [zone_counter.py:88-91]
- **D** — `_in_flight` flag is logically redundant with per-car lock; cleanup blocked on decision C resolution. [zone_counter.py:125-130]
- **G** — `_first_frame` TOCTOU is idempotent (setting ready=True twice is harmless); multi-source `_first_frame` semantics deferred to hardware validation day. [pipeline.py:130-135]
- **L** — Pipeline crash keeps `/health/live` green; liveness vs. readiness probe separation is an ops/k8s configuration concern outside PoC scope. [main.py:118-128]
- **N** — AC7 P2/P1 suppression not re-exercised through new lifespan path; original budget unit tests cover logic; no regression in diff. [budget.py]
- **O** — `getattr(callback, "_rtsp_url", None)` accesses private attribute; refactor to public property/constructor arg in a cleanup pass. [pipeline.py:106]
- **P** — `threshold_count = threshold_pct * capacity` float arithmetic: off-by-fraction for non-round capacities; PoC uses multiples of 10 so low risk; add `int(round(...))` when capacity types are formalised. [zone_counter.py:178]
- **Q** — `uridecodebin` in single-source path has no `name=` tag; collides with `_source_pipeline_multi` naming scheme on multi-source upgrade; fix on hardware day. [pipeline.py:116]

## Deferred to E4-S6 (fusion) from story 4-4 party mode (2026-05-19)

- **Coach-level "occupancy signal lost" health indicator.** Trigger: coach is in scheduled service AND zero detections for >5 minutes. Visualisation: amber badge on Control Centre map; "?" instead of occupancy bar on Conductor App. Promote to red when correlated with APC door-cycle events (APC says boarding happened, camera says zero → confirmed fault). Owns cross-VLAN correlation: APC + camera + scheduled service window. Per ADR-18 this lives in fusion, not inference.

## Deferred from: META code review of story 4-4 — commit d861d45 (2026-05-19)

- M18 capacity `int()` truncates floats and accepts strings — minor type-strictness cleanup
- M19 Polygon shape validation (concave / self-intersecting / collinear / negative coords) at startup — config validation cross-cut
- M21 OccupancyState restart resets to 0.0 — false rising fire on already-crowded restart; state persistence is out of 4-4 scope
- M23 pipeline.py is coverage-omitted; integration boundary untested. Requires a TAPPAS test fixture / hardware-in-loop — E4 hardware bring-up
- M24 test_threshold_falling_emits_event drives via private-state mutation rather than real update() chain — test refactor
- M25 test_no_loop_yet_skips_dispatch indistinguishable outcome from budget-suppress / hailo-None tests — test sharpening
- M26 AST `os.environ.get` checks not extended to main.py/health.py — currently only required for business-logic modules per Rule 8

## Deferred from: code review of story 4-4 (2026-05-19)

- cameras.json includes `priority="P3"` but budget only handles "P2" — priority tier system out of scope for 4-4
- `coach_id` vs `car_id` naming inconsistency between cameras.json and event payloads — codebase-wide rename, separate concern
- `tops_total` / `tops_budget_pct_threshold` config fields dead — read by nothing in inference; remove or wire to budget in later story
- `door_camera_map` in cameras.json never read by inference — used by fusion (E4-S6), not inference
- All `seat_zones` polygons are placeholders covering full frame — real polygons require ops/UX data
- No validation for unknown `priority` values (e.g. "P4" typos) — cross-cutting config validation concern

## E4 Sprint Planning Triage (2026-05-19)

Items from previous stories reviewed for E4 relevance. E4 is the onboard edge pipeline (Python async, no React).

### Carry into E4 backlog

| Item | From | Story | Rationale |
|------|------|-------|-----------|
| ESC during `--loading` doesn't abort in-flight POST — wire `AbortController` | E3-S7 | maintenance ticket | Applies to any future UI with async POST; not E4 (no React) — defer to E5 |
| No ticket persistence — tickets exist only in logs | E3-S7 | maintenance ticket | Belongs in a dedicated Maintenance Epic, not E4 |
| `5-hex ticket ID` collision risk at scale | E3-S7 | maintenance ticket | Belongs with persistence story above |
| `@app.on_event("startup")` deprecated — migrate to `lifespan` | E1-S1 | cloud-backend | Low risk; do in E4 when touching `main.py` for new routers |
| No index on `events.timestamp` / `event_type` | E1-S3 | PostgreSQL schema | Add in E4 when analytics query patterns are confirmed |
| `next_cursor` off-by-one in SQLite event-store | E1-S4 | event-store | Fix in E4-S7 (event-store onboard REST API) — cursor contract will be formalised |
| `insert_event` potential double-serialisation of payload | E1-S4 | event-store | Verify during E4-S7 when `oebb-shared` serialisation is finalised |
| AbortController not used in analytics fetch (all components) | E3-S1–S5 | multiple | Pre-existing; address in a hardening sprint after E4 |

### Not E4 — defer to later epics or hardening sprint

| Item | Reason |
|------|--------|
| All React component deferred items (stale fetch, AbortController in JSX, etc.) | E4 has no React; address in E5 or hardening sprint |
| `VITE_API_KEY` in browser bundle | Covered by ADR-6/7 Keycloak path at fleet rollout |
| Operator identity from Keycloak session | Same ADR-6/7 path |
| CSS class references without styles | Polish sprint after E4 |
| All mock-data anchored issues (luggage `elapsedMin`, etc.) | Resolved in E5-S4 (ISO timestamp migration, done) |

### Already resolved

| Item | Resolution |
|------|-----------|
| `Math.random()` ticket ref | Replaced with server-assigned `uuid4` in E3-S7 |
| `_RAISED_BY` logging API key | Fixed in E3-S7 review (uses `'operator'` literal) |
| `--obb-sev-high` CSS token error | Fixed in E3-S5 review (use `--obb-sev-critical`) |

---

## Deferred from: code review of 3-4-dwell-time-real-data (2026-05-19)

- **Stale fetch / no AbortController** [DwellTime.jsx] — pre-existing in all analytics components (ExceptionWorkflow, OccupancyHeatmap, SystemHealth); not introduced here

## Deferred from: code review of 3-5-ai-detection-quality-real-data (2026-05-19)

- **Missing CSS classes** (`analytics-retry-btn`, `ai-detection__skeleton`, `ai-detection--error`) [AIDetection.jsx] — pre-existing pattern across E3-S2/S3/S4; all analytics components use unstyled class references
- **Race condition on rapid dateRange change** (no AbortController) [AIDetection.jsx] — pre-existing across all analytics components; explicitly noted in story spec
- **`fp_count`/`total_events` null coercion in aggregation** [AIDetection.jsx] — Pydantic backend validates int; low runtime risk
- **`barPct` no upper clamp** (>100% overflow) [AIDetection.jsx] — pre-existing pattern in uptime bar from original mock component
- **`breach_count` float from backend** [DwellTime.jsx] — backend Pydantic schema declares `int`; PoC acceptable; validate if backend changes
- **`occupancy_pct = 0` as valid scatter point** [DwellTime.jsx] — null means no data per spec; 0 is valid occupancy; revisit if backend uses 0 as sentinel
- **Trend line SVG coords unclamped** [DwellTime.jsx] — pre-existing math; only visible with steep slopes from sparse data; low risk for PoC
- **`key={i}` on scatter dots** [DwellTime.jsx] — pre-existing pattern across codebase; no functional impact at PoC scale

## Deferred from: code review of 3-3-occupancy-heatmap-real-data (2026-05-19)

- **`peakHours` not memoized** [OccupancyHeatmap.jsx] — pre-existing pattern; recomputes on hover; cheap enough for PoC route counts
- **Retry button not debounced** [OccupancyHeatmap.jsx] — N rapid clicks fire N requests; acceptable for PoC; add debounce/in-flight guard if operators report issues
- **AbortController not used** [OccupancyHeatmap.jsx, analytics.js] — fetch leaks on rapid range changes; pre-existing in all analytics API functions; add when AbortSignal support is standardised across the API module
- **Error state swallows `.status`** [OccupancyHeatmap.jsx] — no 401/timeout differentiation; matches ExceptionWorkflow pattern; revisit when auth error handling is centralised
- **`encodeURIComponent` coverage missing for special char range values** [analytics.test.js] — low risk; range is always one of `7d|14d|30d`
- **`RANGE_DAYS[dateRange] ?? 7` silent fallback** [OccupancyHeatmap.jsx] — dateRange is constrained by Analytics.jsx toggle to known values; will never hit the fallback in practice

## Deferred from: create-story of 3-2-capacity-exceptions-real-data (2026-05-19)

- **Full calendar date picker with `from/to` API params** [ExceptionWorkflow.jsx, analytics routes] — Epic AC specifies a full calendar picker; deferred because E3-S1 backend only accepts `range=7d|14d|30d`; 3-option toggle satisfies PoC needs; implement as additive backend change when capacity planners need arbitrary windows
- **`trendDirection` / `trendWeeks` not returned by server** [ExceptionWorkflow.jsx `TrendBadge`] — mock-only fields; trend badge will be hidden for server data; re-introduce when inference pipeline adds historical trend computation to `CAPACITY_EXCEPTION` payload

## Deferred from: code review of 5-4-luggage-iso-timestamps (2026-05-19)

- **`getLuggageKPIs` silently drops unattended events when `elapsedMin` returns null** [`luggage.js:213`] — pre-existing null-elapsed contract; add explicit null guard in `getLuggageKPIs` if timestamp quality degrades in production

## Deferred from: code review of 3-2-capacity-exceptions-real-data (2026-05-19)

- **F11: `departure_date` stored as Text with mixed formats** [`cloud-backend/migrations/versions/0003_add_capacity_review_queue.py`] — COALESCE picks ISO date or datetime string depending on which payload field is present; normalise to ISO date when data contract with `events.payload` is locked
- **F13: Export CSV materialises entire result set in memory** [`routes/capacity_review.py`] — acceptable for PoC; add server-side cursor streaming or pagination when queue reaches thousands of rows
- **F15: No DB index on `status` or `queued_at` on `capacity_review_queue`** [`migrations/versions/0003_add_capacity_review_queue.py`] — add when query volumes warrant; likely needed at fleet rollout
- **F16: `gen_random_uuid()` may require `pgcrypto` on Postgres < 13** [`migrations/versions/0003_add_capacity_review_queue.py`] — dev target is Postgres 14+; add a migration guard or switch to `uuid_generate_v4()` if older Postgres is needed

## Deferred from: code review of 3-1-analytics-rest-endpoints (2026-05-19)

- **`status`/`severity` fields accept arbitrary strings** [`api/analytics.py`] — add `Literal`/`Enum` validation when data contract with frontend is stable
- **No pagination/LIMIT on `/exceptions` or `/dwell-time`** [`routes/analytics.py`] — DoS risk at large data volumes; add `limit`/`offset` query params at fleet rollout
- **No CORS / rate limiting on analytics router** [`routes/analytics.py`] — PoC scope; add middleware at fleet rollout
- **`route_name or "unknown"` sentinel collides with legitimate "unknown" route names** [`routes/analytics.py:get_occupancy_heatmap`] — use `None` or a UUID sentinel when route name cardinality is known
- **`get_db` override in tests missing explicit rollback on exception** [`tests/integration/test_analytics_endpoints.py`] — SQLAlchemy handles on context exit; revisit if partial-write test states become flaky
- **AC1 /exceptions grouping by route** [`routes/analytics.py:get_exceptions`] — current flat list deferred to E3-S2; frontend story will clarify exact wire shape; may require adding `list[RouteGroup]` response model
- **`elapsedMin` grows unbounded with fixed anchor dates in dev** [`luggage.js:196-203`] — expected dev behaviour, noted in file header comment; not a defect
- **Duplicate `formatTimestamp` describe blocks across two test files** — intentional cross-version regression coverage (E5-S2 vs E5-S4 contract); removing could mask regressions

## Deferred from: code review of 5-3-luggage-kpi-live-monitoring (2026-05-18)

- **Staleness banner uses global `lastUpdate` not luggage-specific last event** — spec Dev Notes explicitly accept this as a reasonable proxy for this story; add dedicated `luggageLastUpdate` timestamp in a future hardening story [LuggageMonitoring.jsx]
- **localStorage accepts arbitrary integers outside allowed options** — pre-existing pattern across all thresholds; add allow-list validation in a hardening pass [FleetContext.jsx:54]
- **`clearedLastHour` has no time filter** — pre-existing naming/logic mismatch in luggage.js; fix in a polish pass when mock data semantics are tightened [luggage.js]
- **`prevValue` capture relies on synchronous setState callback** — pre-existing across all three threshold update callbacks; refactor to ref-based capture if React concurrent rendering causes issues [FleetContext.jsx]
- **Server GET can overwrite optimistic PATCH on slow network** — pre-existing race across all preferences; needs AbortController + sequence counter when preferences API is hardened [FleetContext.jsx]
- **`elapsedMin` silently returns null for malformed timestamps, dropping events from alert count** — pre-existing elapsedMin contract; add explicit null guard in getLuggageKPIs if timestamp quality degrades in production [luggage.js]

## Deferred from: code review of 5-2-luggage-monitoring-live-ui (2026-05-18)

- **F7 — IIFE in JSX for confidence rendering** [`LuggageFeed.jsx:136`] — style issue, not a correctness bug; refactor to variable in a polish pass
- **F8 — Mixed-feed elapsed inconsistency: mock HH:MM + live ISO events in same KPI** [`mock/luggage.js getLuggageKPIs`] — dev-only; no mock seed events in production; revisit if mock-seeded dev mode is formally supported
- **F11 — `elapsedMin` HH:MM path clamps negative elapsed to 0 across midnight/11:35 anchor** [`mock/luggage.js`] — pre-existing behaviour; not a regression; revisit if mock scenario spans midnight

## Deferred from: code review of 5-1-luggage-ws-live-feed (2026-05-19)

- **`elapsedMin` anchored to mock `"11:35"`** — all live timestamps show "0 min"; deferred to E5-S4 (ISO timestamp story) [control-centre/src/mock/luggage.js]
- **Unbounded `luggageEvents` array growth** — no cap on accumulation over long sessions; add sliding window in hardening pass [control-centre/src/context/FleetContext.jsx]
- **`getLuggageKPIs.longestUnattended` always "0 min" for live events** — HH:MM anchor means duration calc is broken until E5-S4 refactors timestamp display

## Deferred from: code review of 2-9-system-health-data-feed (2026-05-19)

- **API key shipped in client bundle (`VITE_API_KEY` / `X-API-Key` in health.js)** — pre-existing from E2-S1; covered by ADR-6/7 Keycloak OAuth2/OIDC path at fleet rollout
- **`Math.random()` ticket ref collision-prone** [SystemHealth.jsx `confirmRaiseTicket`] — AC7 explicitly defers server-assigned ticket IDs to Phase 2; use `crypto.randomUUID()` or server-issued ID when Phase 2 lands
- **`fleet.find` O(N·M) per WS CAMERA tick in merge effect** [SystemHealth.jsx WS merge useEffect] — PoC fleet sizes acceptable; replace with a `Map<id, cctvStatus>` when fleet grows
- **`ticketRaisedIds` Set rebuilt with spread on each insert** [SystemHealth.jsx `confirmRaiseTicket`] — `new Set([...prev, id])` is O(n); use `new Set(prev).add(id)` in a hardening pass
- **No auto-retry on WS reconnect when error state is showing** [SystemHealth.jsx] — UX enhancement; re-call `fetchHealth` when `wsStatus` transitions to `connected`; not required by any AC
- **1-second `tick` interval runs when tab hidden** [SystemHealth.jsx] — pre-existing battery/CPU pattern from E2-S7; gate on `visibilitychange` in a hardening pass

## Deferred from: code review of 2-8-per-operator-configurable-alert-threshold (2026-05-18)

- **API key used directly as operator_id (PK)** [0002_operator_preferences.py] — single-operator dev environment by design (pre-flight block); multi-tenant identity will come from Keycloak (ADR-6/7) at fleet rollout
- **VITE_API_KEY in client bundle** — pre-existing architecture from E2-S1; covered by ADR-6/7 OAuth2/OIDC path
- **PATCH {} creates row with server defaults instead of no-op** [preferences.py] — no AC requires empty-PATCH to be a no-op; revisit if a future story requires idempotent empty patches

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

## Deferred from: code review of 4-1-vlan-pollers-snmp-context-state (2026-05-19)

- **F17: `duration_s: 0.0` hardcoded for ALARM_CLEARED** [snmp_poller.py] — track alarm activation timestamp in `_prev_alarms` to compute real duration; deferred as PoC doesn't require accurate duration
- **F18: AC1 — no 30 s startup timer** [health.py] — spec says "within 30 s"; current impl just returns 503 until SNMP connects; acceptable for PoC single-process deployment
- **F19: AC8 — station-approach "after stop" semantics not enforced; 2 s SLA fragile** [main.py] — watchdog sleeps 2 s; "after stop" (speed reached ~0) not tracked; add `has_stopped` flag and tighten poll interval in hardening story
- **F20: Module-level `_snmp_connected` global defeats multi-worker deploys** [health.py] — PoC single-worker; migrate to `app.state` before multi-worker production deploy
- **F21: `_push_context_delta` non-atomic across fusion+inference** [context_state.py] — sequential posts may leave consumers divergent on retry failure; add sequence number + per-service error capture in hardening story
- **F23: `snmp_speed_oid` configured but never used** [snmp_poller.py / config.py] — speed varbind polling deferred until Stadler MIB OID for speed is confirmed; wire `update_speed` in E4-S2 when APC/SNMP speed OID is known

## Deferred from: code review of 4-2-vlan-pollers-apc-pis-reservation round 2 (2026-05-19)

- **Module-scope PISPoller/ReservationPoller construction creates httpx.AsyncClient at import time** [main.py:62-72] — pre-existing pattern from SnmpPoller; ResourceWarning in tests that import main.py without entering lifespan; fix by constructing pollers lazily inside _lifespan
- **`mock-vlans` pip install on every container start** [docker-compose.dev.yml] — slow startup; fails without network; bake a proper image or use pre-built fastapi image in hardening sprint
- **Sequential APC fetch blocks poll cycle on one slow car; partial successes discarded** [apc_poller.py] — pre-existing all-or-nothing decision; use asyncio.gather with return_exceptions=True when partial-write semantics are decided

## Deferred from: code review of 4-3-rtsp-ingest-camera-pipeline (2026-05-19)

- **`Gate` stores `self._cameras` but never reads it** [gate.py:21] — dead state; safe to remove but minor; clean up in a polish pass
- **P3 gate has no hysteresis** [gate.py:30-35] — speed oscillation around 20 km/h causes rapid on/off toggling of P3 streams; acceptable for PoC; add a ±2 km/h deadband in a hardening story before production

## Deferred from: code review of 4-2-vlan-pollers-apc-pis-reservation (2026-05-19)

- **No `asyncio.Lock` on `ContextState`** [context_state.py] — pre-existing architectural decision; CPython event loop is single-threaded, coroutines only interleave at `await` points, synchronous assignments are atomic; a lock would be needed only for OS thread concurrency
- **Partial APC car-id failure aborts entire `_poll_once`** [apc_poller.py] — all-or-nothing matches existing SNMP poller pattern; best-effort partial writes require a product decision on partial state validity; defer to hardening story

## Deferred from: code review of 3-7-system-health-maintenance-ticket-api (2026-05-19)

- **ESC during `--loading` clears UI but doesn't abort in-flight POST** [SystemHealth.jsx] — AC4 covers pre-send confirmation only; wire AbortController from ESC to fetch in a hardening story
- **5-hex ticket ID has ~1M space, birthday collisions at ~1,200 tickets** [maintenance.py:33] — PoC scope; add UUID persistence + unique constraint when moving to production
- **No input validation on TicketRequest fields (empty strings, unbounded length)** [maintenance.py:21] — add Pydantic validators (`min_length`, `max_length`) when persistence is added
- **No ticket persistence — tickets exist only in logs** [maintenance.py] — explicitly PoC-deferred; add DB write + GET endpoint in maintenance epic
- **Error toast swallows error object, no status differentiation** [SystemHealth.jsx:~180] — log to console and surface status code in a UX polish pass
- **No rate limiting on ticket creation endpoint** [maintenance.py] — add per-key quota when API key rotates to OAuth2 (ADR-6/7)
- **Orphan ticket on response timeout — no idempotency key** [maintenance.js + maintenance.py] — add `X-Idempotency-Key` header when persistence lands
- **setState after unmount during in-flight ticket POST** [SystemHealth.jsx] — pre-existing React pattern; add `isMountedRef` pattern in hardening pass

## Deferred from: code review of 1-8-shared-contract-enforcement (2026-05-19)

- **D1** — Payload timestamp regex accepts impossible calendar values (month 13, hour 25) — `_TIMESTAMP_RE` only checks digit shape; no `datetime.strptime` follow-up in payload layer. Pre-existing regex design, low practical risk.
- **D2** — Empty payload `{}` bypasses `_validate_payload_shape` — pre-existing envelope design choice; enforcing non-empty would be a breaking change.
- **D3** — Lowercase `z` in timestamp rejected silently — deliberate NFR9 Z-suffix-only contract; document in ADR if needed.
- **D4** — Journey timestamp cross-field ordering not enforced (actual before scheduled is accepted) — would require cross-field `model_validator`; low operational risk.
- **D5** — `_REPO_ROOT = parents[3]` fragile if test file moves or package is installed as wheel — acceptable for in-tree dev tests; would need fix if `oebb-shared` is ever published to PyPI.
- **D6** — `STREAM_PRIORITY` constructable as valid `EventEnvelope` despite ADR-18 "never written to event-store" — enforcement gap at the envelope layer; would require a custom validator that checks ADR-18 semantics.
- **D7** — Sub-second precision unbounded (`(\.\d+)?` allows nanosecond strings) — no practical issue; Python `datetime` drops anything beyond microseconds on round-trip.

## Deferred from: code review of story 4-6-fusion-alert-correlation-suppression (2026-05-20)

- **`main.py` bootstrap-shell + lifespan route-append pattern is fragile.** OpenAPI/`/docs` ends up empty because the schema is cached from the bare shell before lifespan appends routes. Matches `inference/main.py` verbatim — refactoring needs to land across both containers in a single story. Risk: low (PoC `/docs` not used).
- **`@DEFAULT_RETRY` retries on 4xx as well as 5xx.** Lives in `shared/src/oebb_shared/http/retry.py`. Changing this policy ripples into every container; needs a coordinated story with a contract test for the desired retry classes.
- **`SuppressionGate._depot_journey_ended_emitted_for` grows unbounded across journey rotations.** Long-running PoC concern. Correct fix: prune on journey_id transition (clear when entering NORMAL with a new journey_id). Defer until E4 retro / a real long-run test.
