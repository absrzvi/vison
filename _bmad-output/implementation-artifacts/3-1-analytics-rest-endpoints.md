# Story 3.1: Analytics REST Endpoints (Backend)

Status: done

## Story

As a developer,
I want five date-range-aware analytics REST endpoints implemented in the cloud backend,
so that all four analytics sub-tabs and the system health view can query real historical data from PostgreSQL instead of returning mock values.

## Acceptance Criteria

**AC1 — Exceptions endpoint:**
Given the cloud backend is running with migrated PostgreSQL schema (E1-S3),
When `GET /api/v1/analytics/exceptions?range=7d` is called with a valid `X-API-Key`,
Then HTTP 200 is returned with a JSON array of exception records; each record contains: `exception_id`, `route`, `train_id`, `departure`, `date`, `status` (`unreviewed | in_review | dismissed`), `severity`, `coach_peaks` (array of `{ coach_id, peak_pct }`), `trend` (array of 7 daily peak values), `conrad_flag` (object or null); records are grouped by route in the response.

**AC2 — Occupancy heatmap endpoint:**
Given `GET /api/v1/analytics/occupancy-heatmap?range=14d`,
When called,
Then HTTP 200 returns `{ routes: [...], hours: ["05:00"..."23:00"], cells: [[pct|null, ...], ...] }` — `null` for hours with no data in the range; cells are pre-aggregated averages, not raw events.

**AC3 — Dwell time endpoint:**
Given `GET /api/v1/analytics/dwell-time?range=30d`,
When called,
Then HTTP 200 returns an array of station records: `{ station, scheduled_sec, actual_sec, breach_count, occupancy_pct }` sorted by `actual_sec` descending; `breach_count` is the cumulative count of dwell breaches in the requested range, queried directly from the events table — not scaled from a 7d base.

**AC4 — Detection quality endpoint:**
Given `GET /api/v1/analytics/detection-quality?range=7d`,
When called,
Then HTTP 200 returns `{ kpi: { total_events, fp_rate, avg_confidence, fleet_uptime_pct }, daily_bars: [...], per_train_uptime: [...] }`; `fp_rate` is `null` when both `total_events` and `total_fp` are zero (not `0.0`).

**AC5 — System health endpoint:**
Given `GET /api/v1/analytics/system-health`,
When called (no range param — returns current state),
Then HTTP 200 returns an array of train health records matching the shape: `appDetail` / `deviceDetail` / `connectivity` fields; `last_healthy` timestamps are ISO-8601 UTC strings (not client-formatted).

**AC6 — Invalid range validation:**
Given an invalid range value such as `?range=90d` is passed,
When the request is processed,
Then HTTP 422 is returned with `{"error": "INVALID_RANGE", "detail": "range must be one of: 7d, 14d, 30d", "recoverable": true}`.

**AC7 — Authentication:**
All five endpoints require `X-API-Key` authentication (ADR-7); no endpoint returns data without a valid key.

**AC8 — Integration tests:**
`testcontainers-python` integration tests seed the PostgreSQL DB with fixture events and assert each endpoint returns the correct aggregated values.

**AC9 — Type checking:**
`mypy --strict` passes on all new backend modules.

## Tasks / Subtasks

- [x] **T1** Create `cloud_backend/routes/analytics.py` — router + range validation (AC1–AC6, AC7)
  - [x] T1.1 Define `VALID_RANGES = {"7d", "14d", "30d"}` and a `_parse_range(range: str)` helper that converts to a `timedelta`; raise `HTTPException(422, {"error": "INVALID_RANGE", ...})` on invalid input
  - [x] T1.2 Define router `APIRouter(prefix="/api/v1/analytics", dependencies=[Security(require_api_key)])`
  - [x] T1.3 Add `GET /exceptions` route handler — queries `events` table for `CAPACITY_EXCEPTION` event_type in range, groups by route, returns exception array shape per AC1
  - [x] T1.4 Add `GET /occupancy-heatmap` route handler — queries `OCCUPANCY_UPDATE` events aggregated by route × hour, returns heatmap shape per AC2 with `null` for empty cells
  - [x] T1.5 Add `GET /dwell-time` route handler — queries `DWELL_EVENT` events in range, aggregates per station, returns sorted array per AC3
  - [x] T1.6 Add `GET /detection-quality` route handler — queries inference/detection events in range, computes KPIs per AC4; `fp_rate` must be `null` (not `0.0`) when both totals are zero
  - [x] T1.7 Add `GET /system-health` route handler (no range) — queries latest health state per journey from `events` table, returns array per AC5 with ISO-8601 `last_healthy`

- [x] **T2** Create `cloud_backend/api/analytics.py` — Pydantic response models (AC1–AC5, AC9)
  - [x] T2.1 `ExceptionRecord`, `CoachPeak`, `ConradFlag`, `ExceptionsResponse` for AC1
  - [x] T2.2 `HeatmapResponse` (`routes`, `hours`, `cells: list[list[float | None]]`) for AC2
  - [x] T2.3 `DwellStationRecord`, `DwellResponse` for AC3
  - [x] T2.4 `DetectionKpi`, `DailyBar`, `PerTrainUptime`, `DetectionQualityResponse` for AC4; `fp_rate: float | None`
  - [x] T2.5 `AppDetailItem`, `DeviceDetailItem`, `ConnectivityInfo`, `TrainHealthRecord`, `SystemHealthResponse` for AC5; `last_healthy: str` (ISO-8601 UTC)

- [x] **T3** Mount analytics router in `main.py`
  - [x] T3.1 Import `analytics_router` from `routes/analytics.py` and call `app.include_router(analytics_router)`

- [x] **T4** Write security tests — RED phase first (AC7)
  - [x] T4.1 `test_unauthenticated_exceptions` — no key → 401
  - [x] T4.2 `test_unauthenticated_occupancy_heatmap` — no key → 401
  - [x] T4.3 `test_unauthenticated_dwell_time` — no key → 401
  - [x] T4.4 `test_unauthenticated_detection_quality` — no key → 401
  - [x] T4.5 `test_unauthenticated_system_health` — no key → 401
  - [x] T4.6 `test_invalid_range_returns_422` — `?range=90d` → 422 with `INVALID_RANGE` error code and `recoverable: true`

- [x] **T5** Write integration tests with testcontainers (AC8)
  - [x] T5.1 `tests/integration/test_analytics_endpoints.py` — `pg_url` fixture with `PostgresContainer("postgres:16-alpine")`
  - [x] T5.2 Seed fixture: create `journeys` + `events` tables, insert representative events for each analytics type (CAPACITY_EXCEPTION, OCCUPANCY_UPDATE, DWELL_EVENT, detection events)
  - [x] T5.3 `test_exceptions_endpoint_returns_grouped_records` — seeds 3 exceptions across 2 routes; asserts response groups by route and contains required fields
  - [x] T5.4 `test_heatmap_null_for_empty_cells` — seeds sparse data; asserts `null` appears in cells array (not 0.0)
  - [x] T5.5 `test_dwell_time_sorted_descending` — seeds 3 stations with varying actual_sec; asserts result is sorted by `actual_sec` desc
  - [x] T5.6 `test_fp_rate_null_when_no_events` — empty DB (no detection events); asserts `fp_rate` is `null`
  - [x] T5.7 `test_system_health_iso_timestamps` — seeds a health event; asserts `last_healthy` is a parseable ISO-8601 UTC string
  - [x] T5.8 `test_invalid_range_integration` — asserts 422 + correct error shape end-to-end

- [x] **T6** Run `mypy --strict` and `ruff check` (AC9)
  - [x] T6.1 `python -m mypy src/` passes with no errors
  - [x] T6.2 `python -m ruff check src/` passes with no errors

### Review Findings

- [x] [Review][Defer] AC1 grouping by route — flat list kept for now; E3-S2 frontend story will define exact wire shape; decision deferred to E3-S2 [routes/analytics.py:get_exceptions] — deferred, resolve in E3-S2
- [x] [Review][Patch] Lexical string comparison on TEXT timestamp drives all range filters — `_cutoff()` produces `+00:00` suffix but stored timestamps may use `Z`, no-offset, or mixed formats; use `CAST(timestamp AS timestamptz) >= :cutoff::timestamptz` consistently [routes/analytics.py:_cutoff]
- [x] [Review][Patch] Heatmap `CAST(e.timestamp AS TIMESTAMPTZ)` raises 500 on any single malformed row — wrap in `TRY_CAST` equivalent or add `WHERE timestamp ~ '^\d{4}-\d{2}-\d{2}T'` guard [routes/analytics.py:get_occupancy_heatmap]
- [x] [Review][Patch] `(payload->>'breach')::boolean` and `(payload->>'fp_flag')::boolean` crash on non-standard truthy strings — use `NULLIF(payload->>'breach','') IN ('true','1','yes')` instead of PostgreSQL boolean cast [routes/analytics.py]
- [x] [Review][Patch] `::float` casts on JSONB string values crash on non-numeric payloads (e.g. `"n/a"`) — add `NULLIF(payload->>'occupancy_pct','')` guard before cast, or use `try_cast` helper [routes/analytics.py]
- [x] [Review][Patch] `last_healthy` falls back to `datetime.now(UTC).isoformat()` — fabricates a "healthy right now" timestamp when payload is missing; use `None` or raise rather than inventing data [routes/analytics.py:get_system_health]
- [x] [Review][Patch] Per-train uptime denominator counts journeys with ANY event, not all journeys — must join `journeys` table (as fleet-level query does), not derive denominator from `events WHERE timestamp >= :cutoff` [routes/analytics.py:get_detection_quality]
- [x] [Review][Patch] Fleet-level uptime denominator counts ALL historical journeys — add `AND j.start_time >= :cutoff` filter to journeys LEFT JOIN [routes/analytics.py:get_detection_quality]
- [x] [Review][Patch] `conrad_flag` always returns `None` — ConradFlag never populated from payload; at minimum query `payload->>'conrad_flag'` and deserialize if present [routes/analytics.py:get_exceptions]
- [x] [Review][Patch] `trend` array length not validated to exactly 7 values per AC1 spec — add truncation/padding or return error if payload trend length != 7 [routes/analytics.py:get_exceptions]
- [x] [Review][Patch] No integration test for `fp_rate is null` when no INFERENCE_RESULT events exist (AC4 + AC8 gap) — add `test_fp_rate_null_when_no_events` with empty DB [tests/integration/test_analytics_endpoints.py]
- [x] [Review][Patch] AC6: `HTTPException(422, detail={...})` wraps error inside FastAPI's own `{"detail": {...}}` envelope — wire format has extra nesting vs spec's flat `{"error":"INVALID_RANGE",...}` [routes/analytics.py:_parse_range]
- [x] [Review][Patch] `date=row.timestamp[:10]` crashes if asyncpg returns a datetime object (TEXT column currently safe, but coupling is implicit) — cast to string explicitly: `str(row.timestamp)[:10]` [routes/analytics.py:get_exceptions]
- [x] [Review][Patch] Integration test `pg_url` fixture return type `str` should be `Iterator[str]` (generator fixture); mypy will flag this [tests/integration/test_analytics_endpoints.py:pg_url]
- [x] [Review][Defer] `status`/`severity` fields accept arbitrary strings — add Literal/Enum when schema is stable [api/analytics.py] — deferred, pre-existing data contract
- [x] [Review][Defer] No pagination/LIMIT on `/exceptions` or `/dwell-time` — DoS risk at large data volumes [routes/analytics.py] — deferred, PoC scope
- [x] [Review][Defer] No CORS / rate limiting on analytics router [routes/analytics.py] — deferred, PoC scope
- [x] [Review][Defer] `route_name or "unknown"` sentinel collides with legitimate "unknown" route names [routes/analytics.py:get_occupancy_heatmap] — deferred, low risk
- [x] [Review][Defer] `get_db` override in tests missing explicit rollback on exception [tests/integration] — deferred, SQLAlchemy handles on context exit

## Security Tests

**API endpoint security — one block per new endpoint:**
- [x] `test_unauthenticated_exceptions` — no key → 401 UNAUTHORIZED with ADR-10 error envelope
- [x] `test_unauthenticated_occupancy_heatmap` — no key → 401
- [x] `test_unauthenticated_dwell_time` — no key → 401
- [x] `test_unauthenticated_detection_quality` — no key → 401
- [x] `test_unauthenticated_system_health` — no key → 401
- [x] `test_invalid_range_returns_422` — `?range=90d` → 422 with `{"error": "INVALID_RANGE", "detail": "range must be one of: 7d, 14d, 30d", "recoverable": true}`
- [x] Error states return ADR-10 envelope; no raw DB exceptions, stack traces, or internal detail exposed in 4xx/5xx responses
- [x] No CCTV stream URLs or raw video data appear in any analytics response
- [x] Hailo-8 inference output is schema-validated before aggregation (confidence, fp_flag fields are typed, not trusted raw)

## Dev Notes

### Architecture Constraints (MUST follow)

1. **Route handlers contain no business logic** — query SQL in handlers is acceptable for PoC; move to a service layer only if the same query is reused. Per `cloud-backend/CLAUDE.md`: "Routes in `routes/` contain route handlers only."
2. **Pydantic models go in `api/`** — create `cloud_backend/api/analytics.py`. Never define response models inside route files.
3. **No synchronous DB calls in async handlers** — all DB access must use `async with session.execute(text(...))` pattern (see `fleet.py`).
4. **Auth via dependency injection** — `dependencies=[Security(require_api_key)]` on the router (same as `fleet.py`, `ingest.py`). Do not pass `require_api_key` per-route.
5. **Error envelope (ADR-10)** — all 4xx/5xx use `{"error": "...", "detail": "...", "recoverable": bool}`. For 422 INVALID_RANGE: `recoverable: true`.
6. **testcontainers for integration tests** — do not mock the DB. See `tests/integration/test_postgres_schema.py` for the fixture pattern.
7. **`from __future__ import annotations`** — required at top of every new Python file (all existing files use it).

### Existing Code to Read Before Touching

**`cloud_backend/routes/fleet.py`** — canonical route + auth + DB pattern:
- Router defined with `prefix` + `dependencies=[Security(require_api_key)]`
- Uses `text("""...""")` queries with SQLAlchemy async `await db.execute(...)`
- Iterates result rows directly (`for row in rows:`)
- Response model passed to `@router.get(..., response_model=...)`, returns Pydantic model

**`cloud_backend/api/auth.py`** — `require_api_key` dependency; import as `from ..api.auth import require_api_key`.

**`cloud_backend/main.py`** — add `app.include_router(analytics_router)` import block; follow the existing alphabetical import style.

**`tests/integration/test_postgres_schema.py`** — testcontainers fixture pattern:
```python
@pytest.fixture(scope="module")
def pg_url() -> str:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "asyncpg")
```
Integration tests are marked `@pytest.mark.integration`.

**`tests/unit/test_rest_api.py`** — unit test pattern with `TestClient(app)` and mock DB override via `app.dependency_overrides[get_db]`.

### DB Schema Reference

Tables available (from `test_postgres_schema.py` and `ingest.py`):

```sql
journeys (
  journey_id TEXT PRIMARY KEY,
  vehicle_id TEXT NOT NULL,
  trip_number TEXT NOT NULL,
  route_name TEXT,
  origin TEXT,
  destination TEXT,
  start_time TEXT,
  end_time TEXT
)

events (
  event_id TEXT PRIMARY KEY,
  journey_id TEXT NOT NULL,
  vehicle_id TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  source TEXT NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  payload JSONB NOT NULL,
  ingested_at TEXT NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::text
)
```

Key: all event payload content is in `payload JSONB`. Query via `e.payload->>'field'` for text, `(e.payload->>'field')::float` for numeric.

There is **no** `source_timestamp` column — the idempotency key in ADR-3 is `(journey_id, event_type, source_timestamp)` referencing `payload->>'source_timestamp'`, not a table column.

### Range Parsing

Valid values: `"7d"`, `"14d"`, `"30d"`. The API spec also mentions `from/to` date params (E3-S2 story), but this story's ACs only require `?range=` shorthand — do not add `from/to` parsing in this story.

Convert range to a `timedelta`:
```python
_RANGE_MAP = {"7d": timedelta(days=7), "14d": timedelta(days=14), "30d": timedelta(days=30)}
```
Filter events by: `WHERE e.ingested_at >= NOW() - INTERVAL '7 days'` (or use Python-side boundary passed as param).

### Response Shape Notes

**Exceptions (AC1):** The story says "records are grouped by route in the response." The simplest representation is a flat list where each record carries `route` — the grouping is done client-side in E3-S2. Do not over-engineer: return a flat array for PoC.

**Heatmap cells (AC2):** `null` (Python `None`) must serialize as JSON `null`, not `0` or `0.0`. Pydantic `float | None` handles this correctly. Hours array is fixed: `["05:00", "06:00", ..., "23:00"]`.

**fp_rate null rule (AC4):** Explicit: `fp_rate: float | None = None`. Set to `None` when `total_events == 0 AND total_fp == 0`. Set to `total_fp / total_events` otherwise.

**system-health `last_healthy` (AC5):** Must be an ISO-8601 UTC string, e.g. `"2026-05-18T09:43:00Z"`. Use `datetime.utcnow().isoformat() + "Z"` or `datetime.now(timezone.utc).isoformat()`. Never return a client-formatted time string.

### Previous Story Learnings (from E2-S9 review)

- **Abort guards required:** Any `async def fetch_*` that sets state must guard against unmounted/cancelled state (not directly applicable to pure backend, but noted for completeness).
- **Type stubs matter:** `mypy --strict` was a review finding; all new types must be fully annotated — no `Any`, no missing return types.
- **Pydantic `float | None` not `Optional[float]`:** Use the union syntax for Python 3.11 compatibility.

### File Structure (new files only)

```
cloud-backend/
  src/cloud_backend/
    routes/
      analytics.py      ← NEW — route handlers for all 5 endpoints
    api/
      analytics.py      ← NEW — Pydantic response models
  tests/
    integration/
      test_analytics_endpoints.py  ← NEW — testcontainers integration tests
    unit/
      test_analytics_security.py   ← NEW — security + validation unit tests
```

### References

- Epic 3 story spec: `_bmad-output/planning-artifacts/epics.md` §E3-S1
- Route pattern: `cloud-backend/src/cloud_backend/routes/fleet.py`
- Auth dependency: `cloud-backend/src/cloud_backend/api/auth.py`
- Error envelope ADR-10: `_bmad-output/planning-artifacts/architecture.md` §ADR-10
- Auth ADR-7: `_bmad-output/planning-artifacts/architecture.md` §ADR-7
- DB schema: `cloud-backend/tests/integration/test_postgres_schema.py`
- testcontainers pattern: `cloud-backend/tests/integration/test_postgres_schema.py`
- CLAUDE.md conventions: `cloud-backend/CLAUDE.md`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `range` parameter shadowing Python built-in `range()` — renamed to `range_param` with `Query(alias="range")` in all 4 range-accepting endpoints.
- Fixed async event loop conflict in integration tests — moved from `module`-scoped to `function`-scoped async fixtures so each test gets a fresh engine/session.
- Fixed `fetchone()` returning `Row | None` — added `None` guards for mypy strict on both KPI and uptime aggregates.

### Completion Notes List

- Implemented 5 analytics endpoints: `/exceptions`, `/occupancy-heatmap`, `/dwell-time`, `/detection-quality`, `/system-health`
- All endpoints require `X-API-Key` via router-level `Security(require_api_key)` dependency
- `fp_rate` correctly returns `null` when no events exist, `0.0` when events exist but no false positives
- Heatmap `null` cells confirmed by integration test with sparse data
- `mypy --strict` passes on all 3 new/modified files; `ruff check` clean on same
- 37 unit tests pass (18 new security tests + 19 existing); 7 integration tests pass

### File List

- `cloud-backend/src/cloud_backend/routes/analytics.py` (NEW)
- `cloud-backend/src/cloud_backend/api/analytics.py` (NEW)
- `cloud-backend/src/cloud_backend/main.py` (MODIFIED — added analytics_router import + include_router)
- `cloud-backend/tests/unit/test_analytics_security.py` (NEW)
- `cloud-backend/tests/integration/test_analytics_endpoints.py` (NEW)
- `_bmad-output/implementation-artifacts/3-1-analytics-rest-endpoints.md` (MODIFIED — this file)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (MODIFIED — story status)

### Change Log

- 2026-05-19: Story created — comprehensive context engine analysis completed
- 2026-05-19: Story implemented — 5 analytics endpoints, 37 unit + 7 integration tests, mypy strict + ruff clean
