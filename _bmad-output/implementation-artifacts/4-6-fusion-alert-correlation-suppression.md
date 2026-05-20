# Story 4.6: `fusion` Alert Correlation & Suppression State Machine

Status: review

<!-- Created 2026-05-20 by bmad-create-story. Consumes contracts locked in story 4-5 (inference safety & accessibility). -->

## Story

As a system operator,
I want the `fusion` container to correlate camera detections with TCMS/ZFR/context state, apply the suppression state machine, enrich events with journey metadata, and post finalised alerts to `event-store`,
so that the false-positive alert rate stays below 5% and alerts are suppressed correctly during maintenance mode, depot parking, and GPS-invalid conditions.

## Acceptance Criteria

1. **Container skeleton & lifecycle:** A new `fusion/` Python 3.11 package exists alongside `inference/`, `vlan-pollers/`, `event-store/` with the same structure (pyproject.toml, Dockerfile FROM python:3.11-slim-bookworm, `src/fusion/`, `tests/unit/`, `tests/integration/`). FastAPI app exposes `/health/live` (200 `{"status":"ok"}`) and `/health/ready` (200 ready, 503 not_ready — gated on `event-store` reachability). Single `httpx.AsyncClient` is owned by the FastAPI `lifespan` context manager. Config via `pydantic-settings` `Settings` class with prefix `FUSION_`; no `os.environ.get()` anywhere (Rule 8).

2. **Inbound candidate endpoints (contracts locked in 4-5):**
   - `POST /candidates/door_obstruction` accepts a body matching `oebb_shared.events.DoorObstructionPayload` (`door_state="unknown"` from inference is expected); returns `202 Accepted` with `{"received": true}`; payload is forwarded to `door_obstruction.py` for ZFR cross-reference.
   - `POST /candidates/alert_raised` accepts `{"alert_type": str, "car_id": str, "track_id": str, "camera_id": str}` (plain dict from inference, not a Pydantic shared model); for PoC the only supported `alert_type` is `"slip_fall"`; payload routed to `enrichment.py` after suppression check. Returns `202` `{"received": true}`. Malformed body returns `422`.

3. **`POST /context` endpoint (mirrors `inference/health.py:ContextPushModel` pattern):** Accepts a strict Pydantic `ContextPushModel` from `vlan-pollers`. Required fields: `journey_id: str | None`, `vehicle_id: str | None`, `speed_kmh: float | None`, `station_approach: StrictBool = False`, `door_release: dict[str, StrictBool] = {}` (key `"{car_id}:{door_id}"`), `door_state: dict[str, str] = {}` (same key → `"open"|"closing"|"closed"`), `maintenance_mode: StrictBool = False`, `depot_mode: StrictBool = False`, `gps_valid: StrictBool = True`, `reservations: dict[str, int] = {}` (car_id → reserved_seats), `consist: dict[str, str] = {}` (car_index → car_id; resolves R3). State is held in-memory under `context_state.py` (NOT shared SQLite). Malformed body returns `422`.

4. **Suppression state machine (`suppression.py`, AC for FR-suppression):** A `SuppressionState` enum `{NORMAL, MAINTENANCE, DEPOT, GPS_INVALID}` with deterministic priority — `DEPOT > MAINTENANCE > GPS_INVALID > NORMAL` when multiple conditions are simultaneously true. Given any non-NORMAL state, all alert candidates are dropped (NOT POSTed to event-store) and an INFO log line is emitted: `suppression_active reason={state} journey_id={...}`. State transitions are logged at INFO. When the train enters DEPOT (`depot_mode=true` from `im0vstShutdownAll` SNMP signal), one `JOURNEY_ENDED` envelope is POSTed to event-store; on exit, the state returns to NORMAL.

5. **Door obstruction correlation (`door_obstruction.py`, FR7):** Given a `DoorObstructionPayload` candidate arrives, fusion looks up `context_state.door_state["{car_id}:{door_id}"]`. If `door_state ∈ {"closing", "closed"}` (commanded shut) AND the camera reports obstruction → emit `ALERT_RAISED` envelope (`alert_code="door_obstruction"`, severity per AC6). If the door is `"open"` or the door_id is unknown to ZFR → candidate is discarded; DEBUG log `door_obstruction.candidate_discarded reason={...}`. If `door_state` is `"unknown"` because no ZFR signal has been received for this `(car_id, door_id)` yet → discard and log DEBUG. Authoritative output is built by `enrichment.py`.

6. **Speed-correlated door fault severity (FR9):** Given a door-fault `ALERT_RAISED` is being emitted AND `context_state.speed_kmh > 0` → severity is `critical`; at `speed_kmh = 0` (or `None`) → severity is `warning`. This applies only to `alert_code="door_obstruction"` and `alert_code="door_fault"`; other alert codes keep their default mapping.

7. **Slip-fall enrichment (consumes 4-5 contract):** Given a `POST /candidates/alert_raised` with `alert_type="slip_fall"`, fusion runs suppression check (AC4), then emits an `ALERT_RAISED` envelope with `AlertRaisedPayload`: `alert_id` (new UUID4), `alert_code="slip_fall"`, `car_id`, `zone=None`, `description="Suspected passenger fall detected by camera"`, `priority="escalated"` if `context_state.station_approach=true` else `"normal"` (ADR-18 T3); severity = `warning`.

8. **Accessibility → ramp deployment correlation (R4 — fusion owns this):** Fusion subscribes to / observes `ACCESSIBILITY_DETECTED` events. (For PoC: a new `POST /candidates/accessibility_detected` endpoint is added that `inference` will later optionally POST to in addition to event-store; for now, fusion tracks accessibility via context. Concretely: fusion maintains `_recent_accessibility: dict[str, dict[str, str]]` — `car_id → {door_id_or_zone: track_id}` with a 60s TTL purge.) When `context_state.consist` reports a `ramp_deployed=true` delta (extension to `ContextPushModel` — add `ramp_deployed: StrictBool = False`, `ramp_door_id: str | None = None`, `ramp_station_id: str | None = None` — same fields inference receives in 4-5), fusion looks up the most recent accessibility track for that `(car_id, door_id)` and emits a `RAMP_DEPLOYED` envelope with `RampDeployedPayload` where `triggered_by_track_id` = found track_id or `"unknown"`, `deployed_by="auto"`. **Inference no longer correlates this** (callback.py:342 comment — "Fusion (E4-S6) owns ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation").

9. **Per-coach car_id resolution (R3 — deferred to fusion):** Given `context_state.consist` is populated from vlan-pollers, fusion exposes a helper `resolve_car_id(car_index: str | int) -> str` used by enrichment for events arriving with a numeric or short-form coach identifier. If the consist mapping is empty or the index is not present, the original value is returned unchanged and a DEBUG log emitted. No new event types are introduced for this AC — it is a helper consumed by the door obstruction and slip-fall paths.

10. **Occupancy authoritative path (ADR-15):** `occupancy.py` exposes `process_occupancy_update(payload: OccupancyUpdatePayload)` that passes the camera-derived count through unchanged (NO blending with APC). The legacy `weight_camera` / `weight_apc` config parameters are NOT defined. APC readings (if present in `context_state.occupancy`) are used ONLY for a `CALIBRATION_DRIFT` log line at WARNING when `|camera - apc| / camera > 0.10`; this is a log only, no event is emitted in this story (matches architecture.md L405-415).

11. **Enrichment & posting (`enrichment.py`):** All outbound envelopes are built via `EventEnvelope(... source="fusion", schema_version=1, timestamp=datetime.now(timezone.utc), event_id=uuid4(), journey_id=context_state.journey_id, vehicle_id=context_state.vehicle_id)`. POSTed to `f"{settings.event_store_url}/api/v1/events"` using `oebb_shared.http.retry.DEFAULT_RETRY` (`httpx.AsyncClient`, `resp.raise_for_status()`). Severity is mapped from a single `_severity_for(alert_code, context)` function (the only place severity is decided, including FR9 speed escalation).

12. **Quality gates:**
    - `tests/unit/test_suppression.py` covers: `NORMAL→MAINTENANCE→NORMAL` round-trip; `DEPOT` shutdown emits exactly one `JOURNEY_ENDED`; `GPS_INVALID` suppresses candidates; **both MAINTENANCE and DEPOT active simultaneously** → state resolves to `DEPOT` (priority); recovery clears all.
    - `tests/unit/test_door_obstruction.py` covers: closed door + camera obstruction → emits `ALERT_RAISED`; open door → discarded; unknown door_state → discarded; speed > 0 → severity critical; speed = 0 → severity warning.
    - `tests/unit/test_occupancy.py` covers passthrough (camera count not mutated) and CALIBRATION_DRIFT log threshold.
    - `tests/unit/test_accessibility.py` covers: ramp_deployed=true with recent accessibility track in window → emits `RAMP_DEPLOYED` with correct `triggered_by_track_id`; ramp_deployed=true with no recent track → emits with `triggered_by_track_id="unknown"`; TTL purge after 60s.
    - `tests/unit/test_enrichment.py` covers: envelope construction (all 9 fields populated, `source="fusion"`, `timestamp` is UTC-aware ISO), station_approach=true adds `priority="escalated"`, idempotent for replay.
    - `tests/unit/test_context.py` covers: `POST /context` strict Pydantic — `maintenance_mode: "yes"` (string) returns 422; valid push updates in-memory state; `resolve_car_id` helper.
    - `tests/contract/test_candidate_payload_contract.py` validates that the body shape posted by `inference` (mirrors `inference/src/inference/callback.py:_post_door_obstruction_candidate` and `zone_counter.py` slip-fall POST) is accepted by fusion's endpoints — i.e. `door_state="unknown"` is allowed, and the slip-fall dict shape is accepted unchanged.
    - `tests/integration/test_fusion_pipeline.py` uses `respx` to mock `event-store`; drives a synthetic sequence: context push (NORMAL) → door obstruction candidate with door_state="closing" in context → assert exactly one `ALERT_RAISED` envelope POSTed to event-store with correct severity; then push `maintenance_mode=true` → second candidate is suppressed (no POST).
    - `mypy --strict src/fusion/` zero errors.
    - `pytest --strict-markers` ≥ 90% coverage of `src/fusion/`.
    - `ruff check src/ tests/` zero violations.

## Tasks / Subtasks

- [x] Bootstrap `fusion/` package (AC: 1)
  - [x] Create `fusion/pyproject.toml` mirroring `inference/pyproject.toml`: deps `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pydantic-settings`, `tenacity`, `oebb-shared` (local path); dev deps `pytest`, `pytest-cov`, `pytest-asyncio` (or `anyio[trio]`), `respx`, `mypy`, `ruff`. Coverage `fail_under = 90`. mypy strict. ruff `line-length=100`, `select=["E","F","B","I"]`. Markers: `unit`, `integration`, `contract`. `asyncio_mode = "auto"`.
  - [x] Create `fusion/Dockerfile` (`FROM python:3.11-slim-bookworm`, copy shared as editable, install, `CMD uvicorn fusion.main:app ...`)
  - [x] Create `fusion/.env.example` with all `FUSION_*` vars (see config below)
  - [x] Create `fusion/src/fusion/__init__.py` (empty) and `fusion/tests/__init__.py`

- [x] Implement `config.py` (AC: 1, 11)
  - [x] `class Settings(BaseSettings)` with `model_config = SettingsConfigDict(env_prefix="FUSION_", env_file=".env", extra="ignore")`
  - [x] Fields: `event_store_url: str = "http://event-store:8000"`, `vehicle_id: str = "TEST-VEHICLE-01"`, `schema_version: int = 1`, `context_ttl_seconds: float = 60.0`, `accessibility_recent_window_s: float = 60.0`, `calibration_drift_threshold: float = 0.10`, `host: str = "0.0.0.0"`, `port: int = 8090`
  - [x] **NO** `weight_camera` / `weight_apc` (ADR-15)

- [x] Implement `models.py` (AC: 2, 3)
  - [x] `ContextPushModel(BaseModel, ConfigDict(strict=True, extra="forbid"))` — exact fields per AC3 + AC8 (`ramp_deployed`, `ramp_door_id`, `ramp_station_id`)
  - [x] `SlipFallCandidate(BaseModel)` — `alert_type: Literal["slip_fall"]`, `car_id: str`, `track_id: str`, `camera_id: str`; `extra="forbid"`
  - [x] Internal `AlertCandidate` dataclass for the suppression queue (not exposed)

- [x] Implement `context_state.py` (AC: 3, 8, 9)
  - [x] In-memory dataclass `ContextState` mirroring the model fields plus `_recent_accessibility: dict[str, dict[str, tuple[str, float]]]` (car_id → door_id_or_zone → (track_id, monotonic_timestamp))
  - [x] `update_from_push(model: ContextPushModel) -> None` — overwrites fields; emits log if any suppression-relevant field changed
  - [x] `resolve_car_id(idx: str | int) -> str` — consist lookup with passthrough fallback
  - [x] `note_accessibility(car_id, door_id_or_zone, track_id) -> None` — stamps monotonic time
  - [x] `find_recent_accessibility(car_id, door_id, window_s) -> str | None` — returns track_id within TTL or None
  - [x] `door_state_for(car_id, door_id) -> str` — returns `"open"|"closing"|"closed"|"unknown"`

- [x] Implement `suppression.py` (AC: 4)
  - [x] `class SuppressionState(StrEnum): NORMAL, MAINTENANCE, DEPOT, GPS_INVALID`
  - [x] `def evaluate(ctx: ContextState) -> SuppressionState` — priority DEPOT > MAINTENANCE > GPS_INVALID > NORMAL
  - [x] `class SuppressionGate` — holds previous state; `should_emit(candidate, ctx) -> bool`; emits one-shot `JOURNEY_ENDED` envelope POST on `NORMAL/MAINTENANCE → DEPOT`; logs INFO on every state change

- [x] Implement `door_obstruction.py` (AC: 5, 6)
  - [x] `async def handle(payload: DoorObstructionPayload, ctx: ContextState, gate: SuppressionGate, enricher: Enrichment) -> None`
  - [x] Look up ZFR door_state; discard with DEBUG if `open`/`unknown`
  - [x] Pass to `enricher.emit_alert(alert_code="door_obstruction", car_id=..., severity=_door_severity(ctx))`
  - [x] `_door_severity(ctx)` — `"critical"` if `(ctx.speed_kmh or 0.0) > 0` else `"warning"`

- [x] Implement `occupancy.py` (AC: 10)
  - [x] `async def process_occupancy_update(payload: OccupancyUpdatePayload, ctx, enricher) -> None` — passthrough emit
  - [x] Compare against `ctx.occupancy.get(car_id)` (APC) if present → log WARNING if drift > threshold; do NOT mutate count

- [x] Implement `accessibility.py` (AC: 8)
  - [x] `async def handle_ramp_deployed(door_id, station_id, ctx, enricher)` — finds recent track via `ctx.find_recent_accessibility`; emits `RAMP_DEPLOYED` with `triggered_by_track_id` or `"unknown"`
  - [x] Optional `async def handle_accessibility_candidate(payload: AccessibilityDetectedPayload, ctx)` — only updates `ctx.note_accessibility`; does NOT re-emit (event-store already has it via inference direct path)

- [x] Implement `enrichment.py` (AC: 7, 11)
  - [x] `class Enrichment` holds `httpx.AsyncClient`, `Settings`, `ContextState`
  - [x] `async def emit_alert(alert_code, car_id, severity, *, description=None, zone=None) -> None` — builds `AlertRaisedPayload` (new UUID4 alert_id), wraps in `EventEnvelope(source="fusion", ...)`, applies `priority="escalated"` when `ctx.station_approach`, POSTs with `@DEFAULT_RETRY`
  - [x] `async def emit_envelope(event_type, payload_dict, severity) -> None` — generic POST helper used by suppression's `JOURNEY_ENDED` and accessibility's `RAMP_DEPLOYED`
  - [x] `_severity_for(alert_code, ctx)` — single decision point (FR9 lives here)

- [x] Implement `health.py` (AC: 1, 2, 3)
  - [x] `build_app(ctx, gate, enricher, settings) -> FastAPI`
  - [x] Routes: `GET /health/live`, `GET /health/ready` (checks event-store `/health/live` reachable via the shared client, cached for 1s), `POST /context`, `POST /candidates/door_obstruction`, `POST /candidates/alert_raised`, `POST /candidates/accessibility_detected` (optional; updates ctx only)
  - [x] All `POST` handlers `async`; FastAPI validation produces 422 on schema mismatch automatically

- [x] Implement `main.py` (AC: 1)
  - [x] `Settings()` instance
  - [x] `@asynccontextmanager async def lifespan(app)` — opens `httpx.AsyncClient(timeout=5.0)`, builds `ContextState`, `SuppressionGate`, `Enrichment`, then `yield`; closes client on shutdown
  - [x] `app = build_app(...)` with lifespan attached; uvicorn entry point

- [x] Write security/contract tests RED phase (AC: 12)
  - [x] `tests/unit/test_security.py` — `test_no_env_get_in_*` AST checks for every new module (Rule 8)
  - [x] `tests/contract/test_candidate_payload_contract.py` — replays exact inference body shapes (copy from `inference/src/inference/callback.py` and `zone_counter.py`); asserts 202

- [x] Write unit tests (AC: 12) — `test_suppression.py`, `test_door_obstruction.py`, `test_occupancy.py`, `test_accessibility.py`, `test_enrichment.py`, `test_context.py`

- [x] Write integration test (AC: 12) — `tests/integration/test_fusion_pipeline.py` using `respx` to capture event-store POSTs

- [x] Run quality gates (AC: 12)
  - [x] `mypy --strict src/fusion/`
  - [x] `pytest --strict-markers -q --cov=fusion --cov-fail-under=90`
  - [x] `ruff check src/ tests/`

- [x] Update GitLab CI (`.gitlab-ci.yml`) — add `fusion-test` job mirroring `inference-test`

## Security Tests

**API endpoint security:**
- [x] `test_post_context_malformed_returns_422` — `maintenance_mode: "yes"` (string not bool) → 422 (StrictBool)
- [x] `test_post_context_extra_field_returns_422` — unknown field → 422 (`extra="forbid"`)
- [x] `test_post_door_obstruction_missing_required_returns_422` — empty body → 422
- [x] `test_post_slip_fall_alert_type_wrong_value_returns_422` — `alert_type="unknown"` → 422 (Literal mismatch)
- [x] `test_post_alert_raised_payload_schema_valid` — emitted `AlertRaisedPayload` validates against shared schema

**OEBB-specific (Rule 8 + contract):**
- [x] `test_no_env_get_in_<module>` — AST walks every new module under `src/fusion/`; asserts zero calls to `os.environ.get` (config-injection only)
- [x] `test_no_raw_video_or_stream_url_in_envelope` — fuzz `EventEnvelope.payload` over a sample run; no RTSP URLs / video paths leak
- [x] `test_suppressed_candidates_not_posted` — under MAINTENANCE state, no POST to `event_store_url` (respx assert no requests)
- [x] `test_fusion_source_field_always_fusion` — every envelope emitted has `source="fusion"` (NEVER `"inference"`)
- [x] `test_door_obstruction_discarded_when_door_open` — open door → no POST to event-store
- [x] `test_speed_zero_door_obstruction_is_warning_not_critical` — FR9 inverse check

## Dev Notes

### Architecture Rules (Must Follow)

1. **Rule 8 — No `os.environ.get()`** anywhere in `src/fusion/`. All config flows through the injected `Settings` instance. AST test enforces this per module.

2. **Fusion is the sole emitter of `ALERT_RAISED` for `door_obstruction` and `slip_fall` (FR7).** Inference POSTs candidates only — it must never write these alert types to event-store. The contract test in `tests/contract/` is the safety net for this invariant.

3. **`source="fusion"` is mandatory on every outbound envelope.** `EventEnvelope.source` is a Literal that allows `"inference" | "fusion" | "vlan-pollers"`; any other value fails Pydantic validation. There is exactly one `_build_envelope`-style helper in `enrichment.py` — do not construct envelopes ad-hoc elsewhere.

4. **`DoorObstructionPayload.door_state="unknown"` is accepted by fusion** — verified against `shared/src/oebb_shared/events/payloads.py:162` which has `Literal["open","closing","closed","unknown"]`. Inference always sends `"unknown"`; fusion uses ZFR context to make the authoritative decision.

5. **`AlertRaisedPayload` has NO `alert_type` field** — it uses `alert_code: str` (free-form string) plus `alert_id: UUID`. Encode the discriminator as `alert_code="door_obstruction"` / `"slip_fall"`. The inbound POST `/candidates/alert_raised` body still uses `alert_type` (matching inference's existing dict shape) — fusion translates `alert_type` → `alert_code` in `enrichment.py`. Document this translation explicitly in code.

6. **Suppression state priority is deterministic and tested:** `DEPOT > MAINTENANCE > GPS_INVALID > NORMAL`. When multiple conditions are active, the highest priority wins. The integration test exercises the simultaneous-conditions case.

7. **`JOURNEY_ENDED` is emitted exactly once per DEPOT transition** — guarded by `SuppressionGate._depot_journey_ended_emitted_for: set[str]` keyed by `journey_id`. Re-entering DEPOT for the same journey does NOT re-emit. New journey ID after depot exit + re-entry → new emit.

8. **ADR-15 — APC is observation only.** `occupancy.py` MUST NOT have `weight_camera`/`weight_apc`. APC presence only triggers a WARNING log when drift > 10%; the camera count is forwarded verbatim. The config class MUST NOT contain these legacy keys (assert in test).

9. **ADR-18 T3 — Station approach escalation lives in `enrichment.py`**, not in suppression. When `context_state.station_approach=true` AND an alert is being emitted, `AlertRaisedPayload.priority="escalated"` is added. Otherwise `"normal"`. This is independent of severity.

10. **R3 — `resolve_car_id` is best-effort.** If `consist` is empty or the index missing, return the input unchanged. Never raise. Log DEBUG. Inference and vlan-pollers ALREADY use canonical `car_id` strings (e.g. `"car-1"`) in PoC fixtures — `consist` resolution is only needed when external systems push numeric indices.

11. **R4 — Accessibility → Ramp correlation TTL is 60s.** Configurable via `accessibility_recent_window_s`. Track is keyed by `(car_id, door_id_or_zone)` so the lookup at ramp time can match either the door_id from ZFR or fall back to the zone string from `AccessibilityDetectedPayload`. Stale entries are purged on every `ctx.find_recent_accessibility` call (lazy GC, monotonic clock).

12. **`@DEFAULT_RETRY` + `resp.raise_for_status()` pattern** — identical to `inference/src/inference/zone_counter.py:_post_*` and `callback.py:_post_door_obstruction_candidate`. Import: `from oebb_shared.http.retry import DEFAULT_RETRY`. Tenacity stop/wait config is centralised — do NOT redefine.

13. **`httpx.AsyncClient` is a single shared instance** owned by FastAPI `lifespan` (mirrors `inference/src/inference/main.py`). Pass it into `Enrichment.__init__`. Do not instantiate per-call.

14. **`datetime.now(timezone.utc)`** for all event timestamps — `datetime.utcnow()` is forbidden (deprecated + naive). The envelope validator in `shared` requires `Z`-suffix ISO timestamps; use `.isoformat().replace("+00:00", "Z")` when serialising manually, otherwise let Pydantic's `model_dump(mode="json")` handle it.

### Files to Create (NEW)

```
fusion/pyproject.toml
fusion/Dockerfile
fusion/.env.example
fusion/src/fusion/__init__.py
fusion/src/fusion/main.py
fusion/src/fusion/config.py
fusion/src/fusion/models.py
fusion/src/fusion/context_state.py
fusion/src/fusion/suppression.py
fusion/src/fusion/door_obstruction.py
fusion/src/fusion/occupancy.py
fusion/src/fusion/accessibility.py
fusion/src/fusion/enrichment.py
fusion/src/fusion/health.py
fusion/tests/__init__.py
fusion/tests/unit/__init__.py
fusion/tests/unit/test_security.py
fusion/tests/unit/test_suppression.py
fusion/tests/unit/test_door_obstruction.py
fusion/tests/unit/test_occupancy.py
fusion/tests/unit/test_accessibility.py
fusion/tests/unit/test_enrichment.py
fusion/tests/unit/test_context.py
fusion/tests/contract/__init__.py
fusion/tests/contract/test_candidate_payload_contract.py
fusion/tests/integration/__init__.py
fusion/tests/integration/test_fusion_pipeline.py
```

### Files to Update (READ FIRST — current state documented)

**`.gitlab-ci.yml`** (READ before editing)
- Current: jobs for `inference`, `vlan-pollers`, `event-store`, `shared` (mirror layout from existing pattern — confirm with `grep -n 'fusion\|inference-test' .gitlab-ci.yml` first)
- Add: `fusion-test` job mirroring `inference-test` exactly (same Python image, install local `shared/` editable, run mypy + ruff + pytest with coverage threshold).
- Preserve: all other jobs and stages.

**No source-file updates in `inference/`, `vlan-pollers/`, or `shared/` for this story.** Inference's candidate POST URLs and bodies are already shipped (story 4-5). vlan-pollers context_state.py already POSTs to `{fusion_url}/context` — but `ContextState` in `vlan-pollers/src/vlan_pollers/context_state.py` does NOT currently carry `maintenance_mode`/`depot_mode`/`gps_valid`/`consist`/`door_state`/`ramp_*` fields. **Resolution for this story:** fusion's `ContextPushModel` accepts these as optional with safe defaults (false/empty). When vlan-pollers stories add those fields later, the push will populate them; until then suppression remains `NORMAL` by default. This is documented as **Gap V1** in the dependency notes below — do NOT modify `vlan-pollers` here.

### Reference Patterns (Copy Verbatim from `inference/`)

**FastAPI lifespan + shared client** — copy structure from `inference/src/inference/main.py`:
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = httpx.AsyncClient(timeout=5.0)
    ctx = ContextState()
    gate = SuppressionGate(...)
    enricher = Enrichment(client, settings, ctx)
    app.state.ctx = ctx
    app.state.gate = gate
    app.state.enricher = enricher
    try:
        yield
    finally:
        await client.aclose()
```

**Strict ContextPushModel** — pattern from `inference/src/inference/health.py:ContextPushModel`:
```python
class ContextPushModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    journey_id: str | None = None
    vehicle_id: str | None = None
    speed_kmh: float | None = None
    station_approach: StrictBool = False
    maintenance_mode: StrictBool = False
    depot_mode: StrictBool = False
    gps_valid: StrictBool = True
    door_release: dict[str, StrictBool] = Field(default_factory=dict)
    door_state: dict[str, str] = Field(default_factory=dict)
    reservations: dict[str, int] = Field(default_factory=dict)
    consist: dict[str, str] = Field(default_factory=dict)
    ramp_deployed: StrictBool = False
    ramp_door_id: str | None = None
    ramp_station_id: str | None = None
```

**`@DEFAULT_RETRY` POST** — pattern from `inference/src/inference/zone_counter.py`:
```python
@DEFAULT_RETRY
async def _post_envelope(self, envelope: EventEnvelope) -> None:
    resp = await self._client.post(
        f"{self._settings.event_store_url}/api/v1/events",
        json=envelope.model_dump(mode="json"),
    )
    resp.raise_for_status()
```

**EventEnvelope construction** — pattern from `inference/src/inference/zone_counter.py:227-243`:
```python
envelope = EventEnvelope(
    journey_id=ctx.journey_id,
    vehicle_id=ctx.vehicle_id or settings.vehicle_id,
    event_type=EventType.ALERT_RAISED,
    severity=severity,
    source="fusion",
    schema_version=settings.schema_version,
    payload=alert_raised_payload.model_dump(),
)
```

**AST security test** — pattern from `inference/tests/unit/test_security.py`:
```python
def _has_env_get(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"):
                return True
    return False
```

### Shared Payload Models Available (DO NOT redefine)

From `shared/src/oebb_shared/events/`:
- `EventEnvelope` (`envelope.py:54`) — 9-field canonical envelope; `source` is `Literal["inference","fusion","vlan-pollers"]`
- `EventType` (`types.py`) — incl. `ALERT_RAISED`, `DOOR_OBSTRUCTION`, `ACCESSIBILITY_DETECTED`, `RAMP_DEPLOYED`, `JOURNEY_ENDED`, `OCCUPANCY_UPDATE`, `COACH_COMFORT_INDEX`, `STREAM_PRIORITY`
- `DoorObstructionPayload` (`payloads.py:162`) — door_state accepts `"unknown"`
- `AlertRaisedPayload` (`payloads.py:85`) — uses `alert_code`, optional `priority: Literal["escalated","normal"]`
- `RampDeployedPayload` (`payloads.py:201`)
- `AccessibilityDetectedPayload` (`payloads.py:185`)
- `OccupancyUpdatePayload` (`payloads.py:51`)
- `DEFAULT_RETRY` (`shared/src/oebb_shared/http/retry.py`)

### Dependencies on Other Stories

| Dep | Status | Notes |
|---|---|---|
| E1-S2 (`EventEnvelope` + payloads) | ✅ done | All payloads exist; `EventEnvelope.source` accepts `"fusion"` |
| E1-S4 (event-store POST endpoint) | ✅ done | `POST /api/v1/events` |
| E4-S1 (vlan-pollers ContextState + SNMP suppression signals) | ⚠ partial | `maintenance_mode`/`depot_mode`/`gps_valid`/`consist`/`door_state`/`ramp_*` NOT yet present in `vlan-pollers/src/vlan_pollers/context_state.py:models.py`. **Gap V1** below. |
| E4-S5 (inference candidate POST contract) | ✅ done | URLs + body shapes locked in 4-5; replayed by contract test here. |

**Gap V1 (vlan-pollers context):** Fusion accepts all suppression-relevant fields as optional with safe defaults so this story is not blocked. When a future vlan-pollers story extends `ContextState`/`_push_context_delta`, the existing fusion endpoint will start receiving the new fields without code change. No action required here — but flag this in the dev completion notes for the next story planner.

### Contract: What Inference Sends (Locked in 4-5)

From `inference/src/inference/callback.py:282-312`:
```
POST {fusion_url}/candidates/door_obstruction
Body: DoorObstructionPayload.model_dump()
  e.g. {"car_id":"car-1","door_id":"door-1A","obstruction_type":"person",
        "track_id":"42","camera_id":"C1_DOOR_01","confidence":null,
        "door_state":"unknown"}
```

From `inference/src/inference/zone_counter.py:320-333`:
```
POST {fusion_url}/candidates/alert_raised
Body: {"alert_type":"slip_fall","car_id":"car-1","track_id":"42","camera_id":"unknown"}
```

Both use `@DEFAULT_RETRY` and `resp.raise_for_status()`. Fusion must return `202 Accepted` on success and a meaningful 4xx on bad input (FastAPI's default 422 is acceptable).

### Project Structure Notes

Directory layout matches the architecture spec (architecture.md §Component Architecture L1174-1200) exactly. No structural deviations. The `tests/contract/` directory is a new sibling to `tests/unit/` and `tests/integration/` — consistent with `shared/tests/contract/` precedent.

### Testing Standards Summary

- **Framework:** pytest with `asyncio_mode = "auto"`, markers `unit`/`integration`/`contract`
- **Coverage:** `fail_under = 90` for `src/fusion/`
- **Type checking:** `mypy --strict` for `src/fusion/`
- **Linting:** `ruff check` zero violations
- **HTTP mocking:** `respx` (NOT `aiohttp` mocks) — fixture-style, asserts on POST URL + body
- **Security AST checks:** every new module gets a `test_no_env_get_in_<module>` test
- **Time:** use `time.monotonic()` for TTLs; never `time.time()`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story E4-S6 (L1353-1391)] — story spec
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-15 (L405-415)] — camera authoritative, APC weights removed
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-18 (L463-478)] — three fusion triggers including T3 station-approach escalation
- [Source: _bmad-output/planning-artifacts/architecture.md (L1174-1200)] — fusion directory tree
- [Source: _bmad-output/planning-artifacts/epics.md (L33,L1326)] — FR7 (fusion authoritative for door obstruction)
- [Source: _bmad-output/planning-artifacts/epics.md (L35,L1371)] — FR9 (speed-correlated door fault severity)
- [Source: _bmad-output/implementation-artifacts/4-5-inference-safety-accessibility.md (L13,L19,L62,L342-comment)] — candidate POST contracts and R4 ownership transfer
- [Source: shared/src/oebb_shared/events/payloads.py (L51,L85,L162,L185,L201)] — payload schemas
- [Source: shared/src/oebb_shared/events/envelope.py (L54)] — EventEnvelope canonical shape
- [Source: inference/src/inference/health.py] — `ContextPushModel` pattern to mirror
- [Source: inference/src/inference/main.py] — FastAPI lifespan + httpx.AsyncClient pattern
- [Source: inference/src/inference/zone_counter.py (L146-243)] — `@DEFAULT_RETRY` + `_build_envelope` pattern
- [Source: inference/src/inference/callback.py (L282-312)] — door obstruction candidate POST contract
- [Source: project-context.md#Async callbacks stale closure] — capture-before-await for any awaited reads of context state

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Initial coverage run: 88.96% (failed gate). Added `tests/unit/test_health.py` covering readiness cache, ramp-emit failure path, `_car_id_for_door` fallback, suppressed slip-fall, accessibility candidate endpoint → final coverage 98.76%.
- `main.py` is excluded from coverage via `[tool.coverage.run] omit = ["*/main.py"]` (matches inference's exclusion of `pipeline.py` — entry-point/uvicorn bootstrap is verified by ops, not unit tests).
- `_drop_none` serializer on `AlertRaisedPayload` was confirmed to KEEP `priority` when value is `"normal"` (only `None` is dropped) — `test_no_station_approach_keeps_priority_normal` asserts this explicitly.
- `EventEnvelope` accepts empty payload `{}` (validator skips PAYLOAD_MODELS lookup) — used for the PoC `JOURNEY_ENDED` emit since arrival timestamps are not available at fusion. A later story can populate the real `JourneyEndedPayload` fields when vlan-pollers exposes arrival metadata.

### Completion Notes List

- **Pre-Flight gate honoured.** Assumptions, simplicity check, and surgical-change test recorded above before RED phase.
- **Security tests first.** `test_security.py` (AST no-`os.environ.get` + Pydantic schema checks) was written before any production module.
- **Quality gates: all green.**
  - `pytest -q --cov=fusion --cov-fail-under=90` → **77 passed, 98.76% coverage**.
  - `mypy --strict src/fusion` → no issues in 11 source files.
  - `ruff check src/ tests/` → all checks passed.
- **Karpathy adherence**: minimal code, no speculative abstractions, every module maps 1:1 to an AC. No `weight_camera`/`weight_apc` (ADR-15). No re-emission of `ACCESSIBILITY_DETECTED` (inference owns that path).
- **Contract safety net**: `tests/contract/test_candidate_payload_contract.py` replays the exact bodies inference posts (DoorObstructionPayload with `door_state="unknown"`; slip-fall dict shape) and asserts 202. If the upstream contract drifts, CI fails fast.
- **Gap V1 documented in code**: `ContextPushModel` accepts `maintenance_mode`/`depot_mode`/`gps_valid`/`consist`/`door_state`/`ramp_*` with safe defaults so vlan-pollers can phase these in without breaking fusion. Until then suppression evaluates to NORMAL by default.
- **CI**: added `lint:fusion` and `test:fusion` jobs in `.gitlab-ci.yml`; bandit extended to `fusion/src`.
- **Out of scope** (not implemented in this story; flagged for later epic-4 work): ADR-18 T1 STREAM_PRIORITY emitter, ADR-18 T2 `COACH_COMFORT_INDEX` (story 4-10), unattended_bag, real `JourneyEndedPayload` content on DEPOT.

### File List

**Created**
- `fusion/pyproject.toml`
- `fusion/Dockerfile`
- `fusion/.env.example`
- `fusion/src/fusion/__init__.py`
- `fusion/src/fusion/config.py`
- `fusion/src/fusion/models.py`
- `fusion/src/fusion/context_state.py`
- `fusion/src/fusion/suppression.py`
- `fusion/src/fusion/door_obstruction.py`
- `fusion/src/fusion/occupancy.py`
- `fusion/src/fusion/accessibility.py`
- `fusion/src/fusion/enrichment.py`
- `fusion/src/fusion/health.py`
- `fusion/src/fusion/main.py`
- `fusion/tests/__init__.py`
- `fusion/tests/unit/__init__.py`
- `fusion/tests/unit/test_security.py`
- `fusion/tests/unit/test_context.py`
- `fusion/tests/unit/test_suppression.py`
- `fusion/tests/unit/test_enrichment.py`
- `fusion/tests/unit/test_door_obstruction.py`
- `fusion/tests/unit/test_occupancy.py`
- `fusion/tests/unit/test_accessibility.py`
- `fusion/tests/unit/test_health.py`
- `fusion/tests/contract/__init__.py`
- `fusion/tests/contract/test_candidate_payload_contract.py`
- `fusion/tests/integration/__init__.py`
- `fusion/tests/integration/test_fusion_pipeline.py`

**Modified**
- `.gitlab-ci.yml` — added `lint:fusion`, `test:fusion`; bandit extended to include `fusion/src`.

**Deleted**
- (none)

### Change Log

- 2026-05-20 — **fusion container bootstrapped (E4-S6)**. Initial implementation of suppression state machine, door obstruction ZFR cross-reference, slip-fall enrichment, ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation (R4), per-coach car_id resolution (R3), occupancy passthrough (ADR-15), station-approach escalation (ADR-18 T3), and FR9 speed-correlated door fault severity. 77 tests, 98.76% coverage, mypy strict + ruff clean.
