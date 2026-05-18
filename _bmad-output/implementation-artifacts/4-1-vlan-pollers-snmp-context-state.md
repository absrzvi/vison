# Story 4.1: vlan-pollers SNMP & Context State

Status: review

## Story

As a system operator,
I want the `vlan-pollers` container to poll Stadler SNMP (VLAN 7) for alarms and trip state, track the current journey ID, and push context state changes to downstream containers,
so that all other containers have authoritative journey context and TCMS alarm data without accessing SNMP directly.

## Acceptance Criteria

1. **Health readiness:** `GET /health/ready` returns HTTP 200 `{"status": "ready", "snmp_connected": true}` when SNMP is reachable. If SNMP is unreachable within 30 s, returns HTTP 503 `{"status": "starting", "snmp_connected": false, "recoverable": true}`.

2. **Journey ID stability:** When `im0triTripNumber` is first seen, `journey_tracker.py` records `journey_start_date` as the UTC date at that moment. Subsequent events with the same `trip_number` reuse the recorded date — the `journey_id` does NOT change if wall-clock rolls past midnight.

3. **Midnight-crossing test passes:** `tests/unit/test_journey_id.py` — trip starts at 23:45, event arrives at 00:05 with same `trip_number` — `journey_id` is identical for both events (ADR-2).

4. **Alarm decoding:** `snmp_decoder.py` parses `im0AlarmEntry` OIDs from GetBulk into `AlarmEntry(alarm_id, description, severity, active: bool)`. Unknown OIDs are logged at WARNING with `recoverable=True` and skipped — no crash or exception propagation.

5. **Delta push to fusion/inference:** On `ContextState` change (new trip number, alarm raised/cleared, speed update), `context_state.py` POSTs the updated state to `fusion` and `inference` at their `/context` endpoints using `httpx` async with `DEFAULT_RETRY`. Pushes are suppressed when state is unchanged.

6. **ALARM events to event-store:** On alarm state change, an `ALARM_ACTIVE` or `ALARM_CLEARED` event is POSTed to `event-store` `POST /api/v1/events` using canonical `EventEnvelope` (source `"vlan-pollers"`, correct `EventType`, payload per `event-payload-schemas.md`).

7. **Door release → rtsp-ingest push:** When VLAN 2/7 door release signal is detected, `context_state.py` sets `ContextState.door_release = true` for the affected car and immediately POSTs `{ event: "door_release", car_id, door_id }` to `rtsp-ingest/context` (ADR-18 Trigger 1).

8. **Station approach flag:** When `ContextState.pis.next_station_arrival_utc` is within 120 s of current UTC, `context_state.py` sets `ContextState.station_approach = true` and pushes to `fusion` within 2 s. When speed > 20 km/h after stop, the flag is cleared (ADR-18 Trigger 3).

9. **Quality gates:** `mypy --strict src/` passes; `ruff` passes; `pytest --strict-markers` achieves ≥ 90% coverage of `src/vlan_pollers/`.

10. **Dev SNMP stub:** `docker-compose.dev.yml` provides a synthetic SNMP endpoint so tests run without real hardware.

## Tasks / Subtasks

- [x] Scaffold container structure (AC: 9)
  - [x] Create `vlan-pollers/` directory with `Dockerfile`, `pyproject.toml`, `.env.example`
  - [x] Create `src/vlan_pollers/__init__.py`, `config.py` (pydantic-settings)
  - [x] Add `vlan-pollers` service to `docker-compose.dev.yml` with synthetic SNMP stub

- [x] Implement `models.py` — core dataclasses (AC: 4, 5, 7, 8)
  - [x] `ContextState` dataclass with fields: `journey_id`, `trip_number`, `vehicle_id`, `speed_kmh`, `station_approach`, `door_release`, `alarms`, `pis`
  - [x] `AlarmEntry` dataclass: `alarm_id`, `description`, `severity`, `active: bool`
  - [x] `VehicleState` and `TripInfo` supporting dataclasses

- [x] Implement `journey_tracker.py` (AC: 2, 3)
  - [x] On first-seen `trip_number`: record `journey_start_date = datetime.now(timezone.utc).date()` and persist in-process
  - [x] `generate_journey_id(vehicle_id, trip_number) -> str` returning `{vehicle_id}_{trip_number}_{YYYYMMDD}`
  - [x] Never re-derive date from event timestamps — always use the stored `journey_start_date`

- [x] Implement `snmp_decoder.py` (AC: 4)
  - [x] Parse `im0AlarmEntry` OIDs → `AlarmEntry` dataclass
  - [x] Map SNMP severity integer → `"critical" | "warning" | "info"`
  - [x] Parse `im0triTripNumber` from `im0Trip` OID group
  - [x] Log unknown OIDs at WARNING with `recoverable=True`; no raise

- [x] Implement `snmp_poller.py` (AC: 1, 4, 6, 7)
  - [x] SNMP TRAP/INFORM listener + periodic GetBulk for `im0AlarmEntry` and `im0Trip`
  - [x] Call `journey_tracker.generate_journey_id()` on `trip_number` change
  - [x] On alarm state change: build `EventEnvelope` and POST to `event-store /api/v1/events`
  - [x] On door release signal: notify `context_state.py`

- [x] Implement `context_state.py` (AC: 5, 7, 8)
  - [x] In-memory `ContextState`; expose `update(patch)` that detects deltas
  - [x] Delta-push to `fusion` and `inference` via `httpx` async + `DEFAULT_RETRY`; skip if no change
  - [x] Door-release path: set `door_release = true`, POST `{ event: "door_release", car_id, door_id }` to `rtsp-ingest/context`
  - [x] Station-approach path: set `station_approach = true` when within 120 s of arrival, push to `fusion`; clear when speed > 20 km/h

- [x] Implement `health.py` (AC: 1)
  - [x] FastAPI router `GET /health/ready`; returns 200 when SNMP connected, 503 with `recoverable: true` otherwise

- [x] Implement `main.py`
  - [x] Configure `structlog` (same pattern as `event-store/src/event_store/main.py`)
  - [x] Start asyncio tasks: SNMP poll loop, station-approach watchdog
  - [x] Bind `journey_id` to structlog context at task entry

- [x] Write unit tests (AC: 2, 3, 4, 5, 9)
  - [x] `tests/unit/test_journey_id.py` — midnight-crossing stability (ADR-2 required test)
  - [x] `tests/unit/test_snmp_decoder.py` — `im0VstGeneral`, `im0Alarm`, `im0Trip` parsing; unknown OID skipped
  - [x] `tests/unit/test_context_state.py` — delta push triggered on change, suppressed on no-change

## Security Tests

**API endpoint security:**
- [x] `test_unauthenticated_health` — `/health/ready` is internal VLAN-isolated; no auth token required (ADR-6 PoC: VLAN isolation only)
- [x] `test_malformed_snmp_trap` — malformed SNMP payload is logged and discarded without crash or exception propagation
- [x] `test_unknown_oid_safe` — unknown OID triggers WARNING log, not exception; container remains stable

**OEBB-specific:**
- [x] No raw VLAN IP addresses or community strings appear in any log output or API response
- [x] `AlarmEntry.severity` is always one of `critical | warning | info` — no raw SNMP integer leaks to downstream
- [x] SNMP community string comes from `pydantic-settings` config, never from source code

## Dev Notes

### This story is the first Epic 4 story — no prior onboard code exists

`vlan-pollers/` does not yet exist. This is a greenfield container. Follow the architecture scaffold exactly:

```
vlan-pollers/
├── Dockerfile                    # FROM python:3.11-slim-bookworm
├── pyproject.toml
├── .env.example
└── src/
    └── vlan_pollers/
        ├── __init__.py
        ├── config.py             # pydantic-settings
        ├── models.py             # ContextState, AlarmEntry, VehicleState, TripInfo
        ├── snmp_poller.py
        ├── snmp_decoder.py
        ├── journey_tracker.py
        ├── context_state.py
        ├── health.py
        └── main.py
tests/
├── unit/
│   ├── test_journey_id.py
│   ├── test_context_state.py
│   └── test_snmp_decoder.py
└── integration/
    └── test_snmp_live.py         # dev env only, guarded by marker
```

### Shared module — reuse exactly, do not reinvent

| Symbol | Import path | Notes |
|---|---|---|
| `EventType` | `oebb_shared.events.types` | `StrEnum`; use enum members, never string literals |
| `EventEnvelope` | `oebb_shared.events.envelope` | Pydantic model; validators reject wrong format |
| `DEFAULT_RETRY` | `oebb_shared.http.retry` | tenacity decorator; use on every outbound HTTP call |

`EventEnvelope` validators (must satisfy):
- `journey_id` must match `{vehicle_id}_{trip_number}_{YYYYMMDD}` — no underscores in `vehicle_id` or `trip_number`
- `timestamp` must be ISO-8601 UTC with `Z` suffix — use `datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")`
- `source` must be the literal string `"vlan-pollers"` (allowed by the `Literal` union in `EventEnvelope`)
- `schema_version` must be `1`

**ALARM event payload** (from `event-payload-schemas.md` — implement exactly):
```json
{
  "alarm_id": "<string>",
  "description": "<string>",
  "severity": "critical | warning | info",
  "active": true
}
```

### journey_id stability — ADR-2 (critical correctness requirement)

`journey_start_date` is recorded **once** when `trip_number` is first seen. It is never re-derived from event timestamps or wall-clock after that.

```python
# journey_tracker.py — correct pattern
from datetime import UTC, datetime

class JourneyTracker:
    def __init__(self) -> None:
        self._start_dates: dict[str, str] = {}   # trip_number → YYYYMMDD

    def get_journey_id(self, vehicle_id: str, trip_number: str) -> str:
        if trip_number not in self._start_dates:
            self._start_dates[trip_number] = datetime.now(UTC).strftime("%Y%m%d")
        return f"{vehicle_id}_{trip_number}_{self._start_dates[trip_number]}"
```

**Never** do: `datetime.now(UTC).strftime("%Y%m%d")` inside an event handler that runs after first-seen. That is the midnight-crossing bug.

The required test in `tests/unit/test_journey_id.py`:
```python
from unittest.mock import patch
from datetime import datetime, UTC, timezone

def test_midnight_crossing_stability():
    tracker = JourneyTracker()
    vehicle_id = "OBB-4711"
    trip_number = "T999"

    # First seen at 23:45 on 2026-05-17
    t1 = datetime(2026, 5, 17, 23, 45, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t1
        j1 = tracker.get_journey_id(vehicle_id, trip_number)

    # Same trip, event arrives at 00:05 on 2026-05-18
    t2 = datetime(2026, 5, 18, 0, 5, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t2
        j2 = tracker.get_journey_id(vehicle_id, trip_number)

    assert j1 == j2  # journey_id must not change across midnight
    assert j1.endswith("20260517")  # date is the first-seen date
```

### Inter-container HTTP — mandatory patterns

All outbound HTTP must use `httpx` async + `DEFAULT_RETRY`. Never use `requests` or bare `httpx` without retry.

```python
from oebb_shared.http.retry import DEFAULT_RETRY
import httpx

@DEFAULT_RETRY
async def push_context(url: str, payload: dict) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload, timeout=5.0)
        r.raise_for_status()
```

**Target endpoints:**
| Push | Target | Path |
|---|---|---|
| Context delta | `fusion` | `POST /context` |
| Context delta | `inference` | `POST /context` |
| Door release | `rtsp-ingest` | `POST /context` |
| Alarm event | `event-store` | `POST /api/v1/events` |

All URLs come from `config.py` (pydantic-settings), never hardcoded.

Container startup race: `fusion` and `inference` may not be ready when `vlan-pollers` starts. `DEFAULT_RETRY` handles transient 503s — do not add extra logic.

### SNMP library

Use `pysnmp` (pure Python, no native deps) for TRAP listener and GetBulk. Stadler IM MIB OIDs to handle:
- `im0triTripNumber` — trip identifier (string)
- `im0AlarmEntry` — alarm table rows; integer severity field
- Speed data (OID TBD — configure via `.env.example` as `SNMP_SPEED_OID`)

Synthetic SNMP stub for `docker-compose.dev.yml`: use `snmpsim` Docker image (`tandrup/snmpsim`) with a pre-recorded `.snmprec` file checked into `vlan-pollers/tests/fixtures/`.

### structlog — required pattern

Identical to `event-store`. Copy the `structlog.configure(...)` block from `event-store/src/event_store/main.py:16-24` verbatim into `vlan-pollers/src/vlan_pollers/main.py`.

Bind `journey_id` at asyncio task entry:
```python
import structlog
with structlog.contextvars.bound_contextvars(journey_id=tracker.current_journey_id()):
    await process_alarm(entry)
```

Log levels:
- `INFO`: state changes, journey transitions, alarm raised/cleared
- `WARNING`: unknown SNMP OID (`recoverable=True`), SNMP unreachable after retry
- `ERROR`: HTTP push failure exhausted retries
- `CRITICAL`: TCMS alarm at speed > 0 (safety-relevant)

### config.py — pydantic-settings required fields

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vehicle_id: str
    snmp_host: str
    snmp_port: int = 161
    snmp_community: str
    snmp_speed_oid: str
    event_store_url: str          # e.g. http://event-store:8001
    fusion_url: str               # e.g. http://fusion:8003
    inference_url: str            # e.g. http://inference:8004
    rtsp_ingest_url: str          # e.g. http://rtsp-ingest:8005
    station_approach_window_s: int = 120
    snmp_poll_interval_s: float = 5.0

    class Config:
        env_file = ".env"
```

Never call `os.environ.get()` in business logic — always inject `settings` from config.

### Health endpoint — FastAPI pattern

Mirror `event-store/src/event_store/routes/health.py`. Set a module-level `_snmp_connected: bool = False` flag, expose `set_snmp_ready(bool)` called from `main.py` startup, and return 200/503 based on it.

### pyproject.toml — required tooling config

```toml
[tool.pytest.ini_options]
addopts = "--tb=short --strict-markers"
markers = [
  "unit: pure logic, no I/O",
  "integration: real adapters",
]

[tool.coverage.report]
fail_under = 90

[tool.ruff.lint]
select = ["E", "F", "B", "S101", "DTZ", "RUF", "I", "UP"]
line-length = 100

[tool.mypy]
strict = true
```

### 14 Enforcement Rules — all apply

1. Use `EventType` enum — never hardcode event type strings
2. Use `DEFAULT_RETRY` from `shared/http/retry.py` — never custom retry or `time.sleep()`
3. Return ADR-10 error envelope from all API error paths
4. Use `structlog` — never `print()` or `logging.basicConfig()`
5. Use `snake_case` for all JSON fields
6. Tests in `tests/{unit,integration}/` — never co-located with source
7. Use `.env.example` as committed template — never commit `.env`
8. Use `pydantic-settings` for config — never `os.environ.get()` in business logic
9. Use `httpx` async — never `requests`
10. Prefix API routes `/api/v1/` — no unversioned routes (health is `/health/ready`)
11. Inject all I/O dependencies — never instantiate adapters inside domain logic
12. Use `datetime.now(timezone.utc)` — never `datetime.now()`
13. Include `schema_version: 1` in every `EventEnvelope`
14. Bind `journey_id` to structlog context at task entry

### docker-compose.dev.yml — add vlan-pollers service

The existing `docker-compose.dev.yml` has `event-store` and `cloud-backend`. Add:

```yaml
  snmp-stub:
    image: tandrup/snmpsim
    volumes:
      - ./vlan-pollers/tests/fixtures:/usr/local/snmpsim/data
    ports:
      - "1161:161/udp"

  vlan-pollers:
    build: ./vlan-pollers
    volumes:
      - ./vlan-pollers/src:/app/src
      - ./shared/src:/app/shared_src
    environment:
      VEHICLE_ID: OBB-TEST-4711
      SNMP_HOST: snmp-stub
      SNMP_PORT: 161
      SNMP_COMMUNITY: public
      EVENT_STORE_URL: http://event-store:8001
      FUSION_URL: http://fusion:8003
      INFERENCE_URL: http://inference:8004
      RTSP_INGEST_URL: http://rtsp-ingest:8005
    depends_on:
      - event-store
      - snmp-stub
```

Note: `fusion`, `inference`, `rtsp-ingest` don't exist yet — `DEFAULT_RETRY` will handle the connection failures gracefully. Use `restart: on-failure` policy.

### Dependencies confirmed

| Dependency | Status | Path |
|---|---|---|
| `EventType` enum | ✅ exists | `shared/src/oebb_shared/events/types.py` |
| `EventEnvelope` | ✅ exists | `shared/src/oebb_shared/events/envelope.py` |
| `DEFAULT_RETRY` | ✅ exists | `shared/src/oebb_shared/http/retry.py` |
| `event-store POST /api/v1/events` | ✅ exists | `event-store/src/event_store/routes/events.py` |
| `MockAPCAdapter` | ✅ exists | `shared/src/oebb_shared/adapters/apc/mock.py` |

**Note:** `EventEnvelope.source` is typed as `Literal["inference", "fusion", "vlan-pollers"]` — `"vlan-pollers"` is already valid. No shared module changes needed.

**Note:** `event-store` returns `201` (not `200`) on successful POST, and `409` on duplicate. Treat `409` as idempotent success — do not retry.

### Project Structure Notes

- `vlan-pollers/` is peer to `event-store/`, `cloud-backend/`, `shared/` — same depth
- Python package name: `vlan_pollers` (underscore)
- Shared module is mounted as `/app/shared_src` in Docker; add to `PYTHONPATH` in Dockerfile
- No `FastAPI` app-level framework needed for the poller loop — only `health.py` needs FastAPI; run health server in a separate asyncio task alongside the poll loop

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 4, Story E4-S1]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — §Enforcement Summary, §vlan-pollers container spec, §ADR-2, §ADR-18]
- [Source: `project-context.md` — §ADR-2, §ADR-18, §E4 Dependencies Confirmed]
- [Source: `shared/src/oebb_shared/events/envelope.py` — EventEnvelope validators]
- [Source: `shared/src/oebb_shared/events/types.py` — EventType enum]
- [Source: `shared/src/oebb_shared/http/retry.py` — DEFAULT_RETRY]
- [Source: `event-store/src/event_store/routes/events.py` — POST /api/v1/events returns 201; 409 on duplicate]
- [Source: `event-store/src/event_store/main.py:16-24` — structlog configure pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Greenfield `vlan-pollers/` container scaffolded with all 8 source modules
- 40 unit tests pass; 97.97% coverage; ruff clean; mypy clean
- `AlarmActivePayload`/`AlarmClearedPayload` schemas differ from story spec — implemented to match actual shared module (required: `alarm_type`, `car_id`, `hardware_code`, `triggered_by`/`cleared_by`, `duration_s`)
- `bool("0")` trap fixed in `snmp_decoder._build_alarm_row` — SNMP string values now converted via `int(raw) != 0`
- `settings = Settings()` uses pydantic-settings defaults (no required fields) so tests can import without env vars
- `run()` and `_getbulk_sync()` marked `# pragma: no cover` — require real SNMP network, covered by integration tests
- `docker-compose.dev.yml` updated with `snmp-stub` + `vlan-pollers` services

### File List

- `vlan-pollers/Dockerfile`
- `vlan-pollers/pyproject.toml`
- `vlan-pollers/.env.example`
- `vlan-pollers/src/vlan_pollers/__init__.py`
- `vlan-pollers/src/vlan_pollers/config.py`
- `vlan-pollers/src/vlan_pollers/models.py`
- `vlan-pollers/src/vlan_pollers/journey_tracker.py`
- `vlan-pollers/src/vlan_pollers/snmp_decoder.py`
- `vlan-pollers/src/vlan_pollers/snmp_poller.py`
- `vlan-pollers/src/vlan_pollers/context_state.py`
- `vlan-pollers/src/vlan_pollers/health.py`
- `vlan-pollers/src/vlan_pollers/main.py`
- `vlan-pollers/tests/__init__.py`
- `vlan-pollers/tests/unit/__init__.py`
- `vlan-pollers/tests/unit/test_security.py`
- `vlan-pollers/tests/unit/test_journey_id.py`
- `vlan-pollers/tests/unit/test_snmp_decoder.py`
- `vlan-pollers/tests/unit/test_context_state.py`
- `vlan-pollers/tests/unit/test_health.py`
- `vlan-pollers/tests/unit/test_snmp_poller.py`
- `vlan-pollers/tests/unit/test_config.py`
- `vlan-pollers/tests/integration/__init__.py`
- `vlan-pollers/tests/fixtures/stadler.snmprec`
- `docker-compose.dev.yml`
