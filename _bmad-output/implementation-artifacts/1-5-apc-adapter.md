# Story 1-5: APC Adapter Interface & Mock

**Epic:** 1 — Foundation & Shared Infrastructure
**Story:** E1-S5
**Story Key:** 1-5-apc-adapter
**Status:** done
**Date Created:** 2026-05-17

---

## User Story

**As a** developer,
**I want** a typed `APCAdapter` Protocol and a `MockAPCAdapter` implementation with deterministic synthetic data,
**so that** all fusion container development and tests can proceed without real APC hardware, and swapping in the real adapter when the format is confirmed is a single-file change.

---

## Acceptance Criteria

- [x] **AC1** — `shared/adapters/apc/adapter.py` exports `APCAdapter` as a `typing.Protocol` with exactly these async methods: `get_occupancy(car_id: str) -> OccupancyReading` and `get_door_state(car_id: str) -> DoorState`
- [x] **AC2** — `shared/adapters/apc/mock.py` exports `MockAPCAdapter` with deterministic synthetic data for car-1 through car-5
- [x] **AC3** — A test injecting `MockAPCAdapter` where `APCAdapter` is type-hinted passes mypy strict
- [x] **AC4** — Zero tests blocked on APC hardware availability
- [x] **AC5** — `from shared.adapters.apc import APCAdapter, MockAPCAdapter` works
- [x] **AC6** — `pytest tests/unit/test_apc_adapter.py` achieves ≥80% coverage of `shared/adapters/apc/` (actual: 100%)

---

## Tasks / Subtasks

- [x] **T1** — Rename `base.py` → `adapter.py`; update import in `mock.py`
- [x] **T2** — Fix `shared/adapters/apc/__init__.py` to export `APCAdapter`, `MockAPCAdapter`, `OccupancyReading`, `DoorState`
- [x] **T3** — Write `shared/tests/unit/test_apc_adapter.py` covering all methods + unknown car_id error path + Protocol structural subtyping
- [x] **T4** — Run `pytest shared/tests/unit/test_apc_adapter.py --cov=oebb_shared.adapters.apc --cov-fail-under=80` + `mypy --strict`

---

## Dev Notes

### What already exists

- `shared/src/oebb_shared/adapters/apc/base.py` — `APCAdapter` Protocol, `OccupancyReading`, `DoorState` dataclasses
- `shared/src/oebb_shared/adapters/apc/mock.py` — `MockAPCAdapter` with car-1..5 occupancy fixtures, runtime Protocol check
- `shared/src/oebb_shared/adapters/apc/__init__.py` — empty

### What's missing

- `adapter.py` (deliverable name per story spec; content of `base.py` must move here)
- `__init__.py` re-exports
- `tests/unit/test_apc_adapter.py`

### Package layout

`shared/` is an editable install (`shared/src/oebb_shared/`). Tests live in `shared/tests/unit/`.

---

## Dev Agent Record

### Implementation Plan

1. Move `base.py` → `adapter.py` (git mv to preserve history)
2. Update `mock.py` relative import `.base` → `.adapter`
3. Populate `__init__.py`
4. Write test file
5. Validate

### Debug Log

### Completion Notes

- `base.py` git-moved to `adapter.py`; mock.py import updated to `.adapter`
- `__init__.py` now re-exports `APCAdapter`, `MockAPCAdapter`, `OccupancyReading`, `DoorState`
- 18 tests in `test_apc_adapter.py`: covers occupancy (5 cars), door state (5 cars), unknown car KeyError, Protocol structural subtyping, runtime protocol check, package-level imports
- `mypy --package oebb_shared` → 16 files, 0 errors (strict)
- `pytest --cov=oebb_shared.adapters.apc --cov-fail-under=80` → 100% coverage, 51 tests pass (no regressions)

---

## File List

- `shared/src/oebb_shared/adapters/apc/adapter.py` — renamed from `base.py`
- `shared/src/oebb_shared/adapters/apc/mock.py` — import updated `.base` → `.adapter`
- `shared/src/oebb_shared/adapters/apc/__init__.py` — populated with re-exports
- `shared/tests/unit/test_apc_adapter.py` — new, 18 tests, 100% coverage

---

## Change Log

- 2026-05-17: E1-S5 implemented — APCAdapter Protocol + MockAPCAdapter; 100% coverage; mypy strict clean

---

### Review Findings

**Decision-Needed**
- [ ] [Review][Decision] Should `OccupancyReading.count` enforce `>= 0` via `__post_init__`? — APC sensors can emit negative delta counts on door-close miscounts; `count: int` currently accepts negatives silently. If the dataclass is the canonical validation boundary, add `__post_init__`. If validation belongs in the real adapter (not the schema), defer. [adapter.py:9]
- [ ] [Review][Decision] Should `APCAdapter` be decorated `@runtime_checkable`? — Without it, `isinstance(MockAPCAdapter(), APCAdapter)` raises `TypeError`. The current `_assert_protocol()` guard is mypy-only and gives false runtime confidence. If runtime protocol checks are needed (e.g. by fusion container injection), add `@runtime_checkable`. [adapter.py:21]

**Patch**
- [x] [Review][Patch] Move `_assert_protocol()` out of module-level into a test [mock.py:29]
- [x] [Review][Patch] `get_door_state` silently accepts unknown `car_id` — asymmetric with `get_occupancy` which raises KeyError [mock.py:20]
- [x] [Review][Patch] Use `@pytest.mark.asyncio` + `async def` tests instead of bare `asyncio.run()` [test_apc_adapter.py]
- [x] [Review][Patch] Add `is_open=True` fixture path test for `DoorState` — currently always `False`, open-door path untested [test_apc_adapter.py]
- [x] [Review][Patch] Add test for unknown `car_id` in `get_door_state` (mirrors existing occupancy test) [test_apc_adapter.py]
- [x] [Review][Patch] `test_door_state_fields` does not assert `timestamp` — asymmetric with `test_occupancy_reading_fields` [test_apc_adapter.py:34]
- [x] [Review][Patch] `test_runtime_protocol_check_passes` removed; replaced with `test_mock_satisfies_protocol_isinstance` using @runtime_checkable [test_apc_adapter.py]

**Deferred**
- [x] [Review][Defer] `timestamp` is an unvalidated raw string [adapter.py:11,18] — deferred, pre-existing design decision; timestamp validation scope is broader than this story
- [x] [Review][Defer] Hardcoded stale timestamps in mock data [mock.py:3-8] — deferred, intentional determinism per spec; staleness logic is downstream concern
- [x] [Review][Defer] `_MOCK_OCCUPANCY` is a mutable module-level dict (test isolation risk) [mock.py:3] — deferred, no evidence of mutation in current tests
- [x] [Review][Defer] `car-2 count=182` exceeds realistic car capacity, no ceiling enforced [mock.py:5] — deferred, capacity constant out of scope for this story
- [x] [Review][Defer] `car_id` accepts empty string / whitespace without `ValueError` [mock.py:16] — deferred, input validation not in scope; real format not yet confirmed
- [x] [Review][Defer] `car_id` case sensitivity untested [mock.py] — deferred, real APC identifier format not yet confirmed per story context
