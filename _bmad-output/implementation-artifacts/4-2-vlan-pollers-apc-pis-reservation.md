# Story 4.2: vlan-pollers APC, PIS & Reservation Pollers

Status: done

## Story

As a system operator,
I want `vlan-pollers` to poll APC door counts (VLAN 8), PIS schedule/delay state (VLAN 3), and reservation data (VLAN 6) and expose a unified `ContextState` to downstream containers,
so that fusion and inference have live schedule, occupancy ground-truth, and reservation context without polling these VLANs directly.

## Acceptance Criteria

1. **APC adapter injection:** `apc_poller.py` uses `MockAPCAdapter` from `shared/src/oebb_shared/adapters/apc/mock.py` by default. The adapter is injected via constructor — no direct instantiation inside `apc_poller.py`. Swapping to a real adapter requires only changing the injected instance in `main.py`.

2. **APC occupancy in ContextState:** When `MockAPCAdapter.get_occupancy("car-3")` is called and succeeds, the returned `OccupancyReading` is merged into the next `ContextState` delta push to `fusion` and `inference`. The `ContextState.occupancy` field holds a `dict[str, OccupancyReading]` keyed by `car_id`.

3. **PIS schedule/delay update:** When `pis_poller.py` receives a platform change or delay message from its mock source, `ContextState.pis` is updated with `{ next_station, scheduled_departure, actual_departure, platform, delay_min }`. A delta push is triggered to `fusion` and `inference` within 2 seconds.

4. **Reservation data in ContextState:** When `reservation_poller.py` polls VLAN 6 and receives data, `ContextState.reservations` is updated with per-coach reservation counts (dict keyed by `car_id`). Data is available to `fusion` on the next context state read.

5. **Poller fault isolation:** When any VLAN poller fails to reach its target (connection refused, timeout, any exception), the error is logged at WARNING with `recoverable=True` and the last known state is retained. The container does NOT exit. The specific poller retries with `DEFAULT_RETRY` exponential backoff.

6. **Dev synthetic endpoints:** `docker-compose.dev.yml` provides synthetic APC, PIS, and reservation endpoints (mock HTTP services) so all pollers function without real VLAN hardware.

7. **Quality gates:** `mypy --strict src/` passes; `pytest --strict-markers` achieves ≥ 90% coverage of `src/vlan_pollers/` (combined total including E4-S1 tests). No poller uses `os.environ.get()` — all config comes from `pydantic-settings` `config.py`.

## Tasks / Subtasks

- [x] Extend `models.py` with new ContextState fields (AC: 2, 3, 4)
  - [x] Add `occupancy: dict[str, OccupancyReading]` field to `ContextState` (import from `oebb_shared.adapters.apc.adapter`)
  - [x] Add `reservations: dict[str, int]` field to `ContextState` (car_id → seat count)
  - [x] Extend `PisState` with: `scheduled_departure: str`, `actual_departure: str`, `platform: str`, `delay_min: int` (all default empty/0)

- [x] Extend `config.py` with new VLAN settings (AC: 5, 7)
  - [x] Add: `apc_url: str = "http://apc-mock:8010"`, `pis_url: str = "http://pis-mock:8011"`, `reservation_url: str = "http://reservation-mock:8012"`
  - [x] Add: `apc_poll_interval_s: float = 5.0`, `pis_poll_interval_s: float = 5.0`, `reservation_poll_interval_s: float = 30.0`
  - [x] Add: `car_ids: list[str] = ["car-1", "car-2", "car-3", "car-4", "car-5"]` (used by apc_poller and reservation_poller)

- [x] Extend `context_state.py` — new update methods (AC: 2, 4)
  - [x] Add `update_occupancy(readings: dict[str, OccupancyReading]) -> None` — detects change vs `_state.occupancy`, triggers `_push_context_delta()` on change
  - [x] Add `update_reservations(data: dict[str, int]) -> None` — detects change vs `_state.reservations`, triggers `_push_context_delta()` on change
  - [x] Extend `_state_to_dict` to serialize `occupancy` and `reservations` fields
  - [x] **Note:** `update_pis` already exists and handles `PisState`; extend `PisState` fields only — do NOT rewrite `update_pis`

- [x] Implement `apc_poller.py` (AC: 1, 2, 5)
  - [x] `APCPoller.__init__(self, adapter: APCAdapter, ctx: ContextStateManager, car_ids: list[str], poll_interval_s: float)` — inject adapter, no instantiation inside
  - [x] `async def run(self) -> None` — loop: for each car_id call `adapter.get_occupancy(car_id)`, collect all readings, call `ctx.update_occupancy(readings)`, sleep `poll_interval_s`
  - [x] Wrap each adapter call in try/except; on any exception log WARNING with `recoverable=True`, retain last state, continue loop
  - [x] Use `DEFAULT_RETRY` decorator on the `_fetch_occupancy` helper; the run loop itself does NOT use DEFAULT_RETRY (loop must not exit on retry exhaustion)

- [x] Implement `pis_poller.py` (AC: 3, 5)
  - [x] `PISPoller.__init__(self, pis_url: str, ctx: ContextStateManager, poll_interval_s: float)` — no adapter protocol needed; poll HTTP endpoint directly
  - [x] `async def run(self) -> None` — loop: GET `{pis_url}/schedule`, parse JSON response into `PisState`, call `ctx.update_pis(pis_state)`, sleep `poll_interval_s`
  - [x] Expected JSON shape from mock: `{ "next_station": str, "next_station_arrival_utc": str, "scheduled_departure": str, "actual_departure": str, "platform": str, "delay_min": int }`
  - [x] On HTTP error or parse failure: log WARNING with `recoverable=True`, retain last `ContextState.pis`, continue loop
  - [x] Use `httpx.AsyncClient` (module-level, shared) with `DEFAULT_RETRY` on the fetch helper

- [x] Implement `reservation_poller.py` (AC: 4, 5)
  - [x] `ReservationPoller.__init__(self, reservation_url: str, ctx: ContextStateManager, car_ids: list[str], poll_interval_s: float)`
  - [x] `async def run(self) -> None` — loop: GET `{reservation_url}/reservations`, parse JSON `{ "car-1": 42, "car-2": 180, ... }`, call `ctx.update_reservations(data)`, sleep `poll_interval_s`
  - [x] On failure: log WARNING with `recoverable=True`, retain last state, continue loop
  - [x] Use `httpx.AsyncClient` (module-level, shared) with `DEFAULT_RETRY` on the fetch helper

- [x] Wire pollers into `main.py` (AC: 1, 6)
  - [x] Import `APCPoller`, `PISPoller`, `ReservationPoller` and instantiate with injected deps
  - [x] Inject `MockAPCAdapter()` as the APC adapter — single line change to swap for real adapter
  - [x] Create asyncio tasks for `apc_poller.run()`, `pis_poller.run()`, `reservation_poller.run()` in `_lifespan`
  - [x] Close new `httpx.AsyncClient` instances in lifespan finally block

- [x] Update `docker-compose.dev.yml` — synthetic VLAN endpoints (AC: 6)
  - [x] Add three mock services using `mockoon/mockoon-cli` or a tiny FastAPI image (see Dev Notes for preferred approach)
  - [x] `apc-mock`: responds to `GET /occupancy/{car_id}` with static `OccupancyReading` JSON
  - [x] `pis-mock`: responds to `GET /schedule` with static `PisState` JSON
  - [x] `reservation-mock`: responds to `GET /reservations` with static per-coach JSON

- [x] Write unit tests (AC: 1, 2, 3, 4, 5, 7)
  - [x] `tests/unit/test_apc_poller.py` — happy path (readings merged into ContextState), adapter failure (WARNING logged, loop continues), adapter injection (no MockAPCAdapter import in apc_poller module)
  - [x] `tests/unit/test_pis_poller.py` — valid JSON → PisState updated, HTTP error → last state retained + WARNING, malformed JSON → recoverable log
  - [x] `tests/unit/test_context_state.py` — extend existing: `update_occupancy` delta suppression, `update_reservations` delta suppression, serialization of new fields in `_state_to_dict`

## Security Tests

- [x] `test_no_env_get_in_pollers` — `grep -r "os.environ.get" src/vlan_pollers/apc_poller.py src/vlan_pollers/pis_poller.py src/vlan_pollers/reservation_poller.py` returns empty (enforce rule 8)
- [x] `test_apc_unknown_car_id` — `MockAPCAdapter.get_occupancy("unknown-car")` raises `KeyError`; `apc_poller` logs WARNING and does NOT propagate exception
- [x] `test_pis_malformed_json` — PIS endpoint returns `{invalid json}`; `pis_poller` logs WARNING with `recoverable=True` and retains previous `ContextState.pis`

## Dev Notes

### What E4-S1 built — read these files before touching them

| File | Current state | What E4-S2 changes |
|---|---|---|
| `src/vlan_pollers/models.py` | `ContextState`, `AlarmEntry`, `TripInfo`, `PisState`, `VehicleState` | Add `occupancy`, `reservations` to `ContextState`; extend `PisState` with 4 new fields |
| `src/vlan_pollers/config.py` | 10 settings fields, pydantic-settings, defaults for all | Add `apc_url`, `pis_url`, `reservation_url`, `apc_poll_interval_s`, `pis_poll_interval_s`, `reservation_poll_interval_s`, `car_ids` |
| `src/vlan_pollers/context_state.py` | `ContextStateManager` with `update_journey`, `update_alarm`, `update_speed`, `update_pis`, `set_door_release`, `set_station_approach`, `_push_context_delta` | Add `update_occupancy`, `update_reservations`; extend `_state_to_dict` |
| `src/vlan_pollers/main.py` | Instantiates `JourneyTracker`, `ContextStateManager`, `SnmpPoller`; starts 2 asyncio tasks | Instantiate 3 new pollers; start 3 new tasks; close new HTTP clients in lifespan |
| `docker-compose.dev.yml` | Has `snmp-stub` + `vlan-pollers` + `event-store` + `cloud-backend` | Add `apc-mock`, `pis-mock`, `reservation-mock` services |
| `tests/unit/test_context_state.py` | Tests for `update_journey`, `update_alarm`, `update_speed`, `update_pis`, delta suppression | Extend with `update_occupancy` and `update_reservations` cases |

**Preserve without changes:** `snmp_poller.py`, `snmp_decoder.py`, `journey_tracker.py`, `health.py`, `models.AlarmEntry`, `models.TripInfo`, `models.VehicleState`. Do NOT touch them.

### PIS adapter in shared — important distinction

`shared/src/oebb_shared/adapters/pis/` defines a **write** adapter (`PISAdapter.display_message`, `PISAdapter.clear_message`) — this is for pushing messages *to* PIS screens. It is **not** for reading schedule/delay data.

`pis_poller.py` reads *from* VLAN 3 (schedule inbound), not writes to screens. Use a plain `httpx.AsyncClient` GET poll against the mock HTTP endpoint — no PIS adapter Protocol involved.

### APC adapter — constructor injection pattern

The epics file requires that `MockAPCAdapter` is never instantiated inside `apc_poller.py`. The correct pattern:

```python
# apc_poller.py
from oebb_shared.adapters.apc.adapter import APCAdapter, OccupancyReading

class APCPoller:
    def __init__(
        self,
        adapter: APCAdapter,
        ctx: ContextStateManager,
        car_ids: list[str],
        poll_interval_s: float,
    ) -> None:
        self._adapter = adapter
        self._ctx = ctx
        self._car_ids = car_ids
        self._poll_interval_s = poll_interval_s
```

```python
# main.py — the ONLY place MockAPCAdapter is imported
from oebb_shared.adapters.apc.mock import MockAPCAdapter
from .apc_poller import APCPoller

_apc_poller = APCPoller(
    adapter=MockAPCAdapter(),
    ctx=_ctx,
    car_ids=settings.car_ids,
    poll_interval_s=settings.apc_poll_interval_s,
)
```

### ContextState model extension — exact shape required

```python
# models.py additions
from oebb_shared.adapters.apc.adapter import OccupancyReading

@dataclass
class PisState:
    next_station: str = ""
    next_station_arrival_utc: str = ""   # already exists
    scheduled_departure: str = ""         # NEW
    actual_departure: str = ""            # NEW
    platform: str = ""                    # NEW
    delay_min: int = 0                    # NEW

@dataclass
class ContextState:
    # ... existing fields unchanged ...
    occupancy: dict[str, OccupancyReading] = field(default_factory=dict)   # NEW
    reservations: dict[str, int] = field(default_factory=dict)              # NEW
```

`OccupancyReading` is a `dataclass` — use `dataclasses.asdict()` for serialization in `_state_to_dict`.

### Poller run-loop fault isolation pattern

The run loop **must not exit** on poller failure. The correct pattern for all three pollers:

```python
async def run(self) -> None:
    while True:
        try:
            await self._poll_once()
        except Exception:
            log.warning("apc_poll_failed", recoverable=True)
        await asyncio.sleep(self._poll_interval_s)
```

`DEFAULT_RETRY` goes on `_poll_once` or its inner fetch helper, NOT on `run`. If `DEFAULT_RETRY` exhausts retries, it raises — the `try/except` in `run` catches it, logs, and keeps the loop alive.

```python
# correct structure
@DEFAULT_RETRY
async def _fetch_occupancy(self, car_id: str) -> OccupancyReading:
    return await self._adapter.get_occupancy(car_id)

async def _poll_once(self) -> None:
    readings: dict[str, OccupancyReading] = {}
    for car_id in self._car_ids:
        reading = await self._fetch_occupancy(car_id)
        readings[car_id] = reading
    await self._ctx.update_occupancy(readings)
```

### docker-compose.dev.yml — mock services preferred approach

Use a single lightweight Python script served by `uvicorn` baked into a `python:3.11-slim-bookworm` image, or use static JSON responses via `nginx`. The simplest approach is an inline `Dockerfile` for each mock under `vlan-pollers/tests/mocks/`:

```
vlan-pollers/tests/mocks/
├── apc_mock.py       # FastAPI app: GET /occupancy/{car_id}
├── pis_mock.py       # FastAPI app: GET /schedule
└── reservation_mock.py  # FastAPI app: GET /reservations
```

Each mock app returns hard-coded JSON. Add three services to `docker-compose.dev.yml` — they don't need Dockerfiles if you use `command: python -m uvicorn ...` with the shared `python:3.11-slim` image.

Alternatively, use a single `mock-vlans` service that handles all three routes (simpler). Either approach is acceptable — consistency with the snmp-stub pattern is more important than having separate containers.

### config.py — new fields to add

```python
# Append to existing Settings class
apc_url: str = "http://apc-mock:8010"
pis_url: str = "http://pis-mock:8011"
reservation_url: str = "http://reservation-mock:8012"
apc_poll_interval_s: float = 5.0
pis_poll_interval_s: float = 5.0
reservation_poll_interval_s: float = 30.0
car_ids: list[str] = ["car-1", "car-2", "car-3", "car-4", "car-5"]
```

`list[str]` is supported by pydantic-settings via comma-separated env var: `CAR_IDS=car-1,car-2,car-3`.

### httpx client management in new pollers

`pis_poller.py` and `reservation_poller.py` each need a module-level `httpx.AsyncClient` (same pattern as `context_state.py` and `snmp_poller.py`). Close them in the `_lifespan` finally block in `main.py`.

```python
# pis_poller.py
_http_client = httpx.AsyncClient()

# main.py lifespan finally block — add alongside existing client closes:
from .pis_poller import _http_client as _pis_client
from .reservation_poller import _http_client as _res_client
# ...
await _pis_client.aclose()
await _res_client.aclose()
```

`apc_poller.py` does NOT need its own HTTP client — it goes through the injected `APCAdapter`.

### 14 Enforcement Rules — unchanged, all still apply

Carry over from E4-S1 Dev Notes. Critical for this story:
- Rule 8: no `os.environ.get()` — all new settings in `config.py`
- Rule 9: `httpx` async only — no `requests`
- Rule 11: inject adapters — `MockAPCAdapter` never instantiated inside `apc_poller.py`
- Rule 12: `datetime.now(timezone.utc)` — no naive datetimes in new code
- Rule 4: `structlog` for all logging — `recoverable=True` on all WARNING logs

### Deferred from E4-S1 — relevant to this story

**F23 (deferred in E4-S1):** `snmp_speed_oid` is configured but never used in `snmp_poller.py`. This is still deferred — do NOT implement speed polling from SNMP OID in this story. Speed update via `ctx.update_speed()` remains a stub.

**F7 (deferred in E4-S1):** `update_speed` is wired in the E4-S1 deferred notes as "wire in E4-S2". However the epics file E4-S2 ACs do not mention speed polling. Do NOT add speed wiring — keep the deferred status. If you see the `update_speed` method called nowhere, that is expected.

### Shared module reuse table

| Symbol | Import path | Notes |
|---|---|---|
| `APCAdapter` | `oebb_shared.adapters.apc.adapter` | Protocol — type-hint only in `apc_poller.py` |
| `OccupancyReading` | `oebb_shared.adapters.apc.adapter` | Dataclass from `get_occupancy()` return |
| `MockAPCAdapter` | `oebb_shared.adapters.apc.mock` | Import ONLY in `main.py` |
| `DEFAULT_RETRY` | `oebb_shared.http.retry` | On every outbound HTTP fetch helper |
| `EventType`, `EventEnvelope` | `oebb_shared.events.*` | Not needed for this story — no new events emitted |

### Test strategy

**`test_apc_poller.py`** — use `AsyncMock` for the adapter, not `MockAPCAdapter`:

```python
from unittest.mock import AsyncMock, patch
from vlan_pollers.apc_poller import APCPoller
from oebb_shared.adapters.apc.adapter import OccupancyReading

async def test_apc_poll_merges_readings():
    mock_adapter = AsyncMock()
    mock_adapter.get_occupancy.return_value = OccupancyReading(
        car_id="car-1", count=42, timestamp="2026-05-19T10:00:00Z"
    )
    mock_ctx = AsyncMock()
    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=["car-1"],
        poll_interval_s=999,  # prevent loop
    )
    await poller._poll_once()
    mock_ctx.update_occupancy.assert_called_once()
    readings = mock_ctx.update_occupancy.call_args[0][0]
    assert readings["car-1"].count == 42
```

**`test_pis_poller.py`** — mock `httpx.AsyncClient` via `respx` or `unittest.mock.patch`:

```python
# Use respx for httpx mocking (already in pyproject.toml dev deps from E4-S1)
import respx, httpx

@respx.mock
async def test_pis_poll_updates_context():
    respx.get("http://pis-mock:8011/schedule").mock(
        return_value=httpx.Response(200, json={
            "next_station": "Wien Hbf",
            "next_station_arrival_utc": "2026-05-19T12:00:00Z",
            "scheduled_departure": "2026-05-19T12:05:00Z",
            "actual_departure": "2026-05-19T12:07:00Z",
            "platform": "3A",
            "delay_min": 2,
        })
    )
    ...
```

Check if `respx` is already in `pyproject.toml` dev deps — if not, add it.

### Coverage note

The ≥90% coverage target is for `src/vlan_pollers/` **combined**. New files `apc_poller.py`, `pis_poller.py`, `reservation_poller.py` must each have high coverage. Mark `run()` loops as `# pragma: no cover` (same as E4-S1 pattern for `SnmpPoller.run`) — test `_poll_once()` and `_fetch_*` helpers directly.

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` — Epic 4, Story E4-S2]
- [Source: `_bmad-output/implementation-artifacts/4-1-vlan-pollers-snmp-context-state.md` — Dev Agent Record, Review Findings]
- [Source: `_bmad-output/planning-artifacts/architecture.md` — §APC Adapter Protocol ADR, §ADR-15, §ADR-18, §vlan-pollers directory scaffold]
- [Source: `shared/src/oebb_shared/adapters/apc/adapter.py` — APCAdapter Protocol, OccupancyReading, DoorState]
- [Source: `shared/src/oebb_shared/adapters/apc/mock.py` — MockAPCAdapter, deterministic data for cars 1–5]
- [Source: `shared/src/oebb_shared/adapters/pis/base.py` — PISAdapter is a WRITE adapter, not for polling]
- [Source: `vlan-pollers/src/vlan_pollers/context_state.py` — existing update methods; extend, do not rewrite]
- [Source: `vlan-pollers/src/vlan_pollers/models.py` — ContextState, PisState current shape]
- [Source: `vlan-pollers/src/vlan_pollers/config.py` — existing Settings fields; append new fields only]
- [Source: `vlan-pollers/src/vlan_pollers/main.py` — lifespan pattern, asyncio task management, client close pattern]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- `apc_poller.py` greenfield; `MockAPCAdapter` injected exclusively in `main.py` — AC1 enforced by AST test
- `pis_poller.py` polls HTTP GET `/schedule`; note: shared `PISAdapter` is a write adapter (screens), not used here
- `reservation_poller.py` filters response to configured `car_ids` — prevents unknown cars from leaking into ContextState
- `models.py`: `OccupancyReading` imported from shared; `PisState` extended with 4 new fields (additive only)
- `context_state.py`: `update_occupancy` uses `dataclasses.asdict()` comparison for deep equality; `update_reservations` uses dict equality
- `main.py`: 3 new asyncio tasks + 2 new HTTP clients closed in lifespan finally block
- `docker-compose.dev.yml`: single `mock-vlans` service on port 8010 serving all three VLAN routes at `/apc/*`, `/pis/*`, `/reservation/*`
- mypy --strict: 0 errors (12 source files); ruff: 0 errors; pytest: 81/81 passed; coverage: 98.04% (≥90% gate passed)
- F7/F23 from E4-S1 review remain deferred — speed wiring not in scope for this story

### File List

- `vlan-pollers/src/vlan_pollers/models.py` (modified)
- `vlan-pollers/src/vlan_pollers/config.py` (modified)
- `vlan-pollers/src/vlan_pollers/context_state.py` (modified)
- `vlan-pollers/src/vlan_pollers/apc_poller.py` (new)
- `vlan-pollers/src/vlan_pollers/pis_poller.py` (new)
- `vlan-pollers/src/vlan_pollers/reservation_poller.py` (new)
- `vlan-pollers/src/vlan_pollers/main.py` (modified)
- `vlan-pollers/tests/mocks/mock_vlans.py` (new)
- `vlan-pollers/tests/unit/test_apc_poller.py` (new)
- `vlan-pollers/tests/unit/test_pis_poller.py` (new)
- `vlan-pollers/tests/unit/test_reservation_poller.py` (new)
- `vlan-pollers/tests/unit/test_context_state.py` (modified)
- `docker-compose.dev.yml` (modified)

### Review Findings

- [x] [Review][Patch] `update_pis` delta-check misses new PisState fields — delay/platform changes silent [context_state.py:87-94]
- [x] [Review][Patch] `apc_url` / `APC_URL` is dead config — `apc_url` in Settings and `APC_URL` in docker-compose are never read by APCPoller [config.py, docker-compose.dev.yml]
- [x] [Review][Patch] Module-level `httpx.AsyncClient` created at import time — moved to instance-level with `aclose()` method [pis_poller.py, reservation_poller.py]
- [x] [Review][Patch] `str(None)` → `"None"` for missing PIS JSON fields — fixed with `or ""` / `or 0` guards [pis_poller.py:43-49]
- [x] [Review][Defer] No `asyncio.Lock` on `ContextState` — pre-existing architectural decision; CPython event loop single-threaded, no preemption at sync assignments [context_state.py] — deferred, pre-existing
- [x] [Review][Defer] Partial APC car-id failure aborts entire `_poll_once` — pre-existing, matches SNMP poller all-or-nothing pattern; product decision needed for best-effort vs atomic [apc_poller.py:41-48] — deferred, pre-existing
