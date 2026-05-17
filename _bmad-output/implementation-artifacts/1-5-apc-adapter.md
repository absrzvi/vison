# Story 1-5: APC Adapter Interface & Mock

**Epic:** 1 — Foundation & Shared Infrastructure
**Story:** E1-S5
**Story Key:** 1-5-apc-adapter
**Status:** review
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
