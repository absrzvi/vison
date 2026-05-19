# Story 1-8: shared/ Event Contract Enforcement

**Epic:** 1 — Foundation & Shared Infrastructure (hardening)  
**Story Key:** `1-8-shared-contract-enforcement`  
**Status:** review  
**Agent:** Amelia  
**Phase:** BMAD-DEV  
**Date Created:** 2026-05-19  
**Retro Sources:** Epic-1 A1, A3 · Epic-5 C2

---

## User Story

As a developer on any OEBB container team,  
I want the CI pipeline to fail immediately when an event is constructed with a missing/invalid envelope field, an undefined EventType, a payload that doesn't match its declared model, or a naive/non-UTC timestamp,  
so that ADR-1 and NFR9 violations are caught at commit time rather than at runtime on the train.

---

## Background & Motivation

Three retrospective action items converge in a single `shared/` PR:

| Retro item | Problem | Fix |
|---|---|---|
| **A1** (Epic-1) | Any container can emit an event with a missing/invalid envelope at runtime; nothing fails CI | Contract test in `shared/tests/` that scans all containers for event construction sites and validates them against the Pydantic models |
| **A3** (Epic-1) | Coverage gate exists in `pyproject.toml` (`fail_under = 80`) and CI (`--cov-fail-under=80`) **already** — but must be verified and locked | Confirm gate is wired and add a `contract`-marked test suite so future regressions are immediately visible |
| **C2** (Epic-5) | Journey payloads (`JOURNEY_STARTED`, `JOURNEY_ENDED`) carry timestamp string fields that accept naive or non-UTC datetimes; timestamp validator only lives on the envelope, not on the payload fields | Add a Pydantic validator on `JourneyStartedPayload` and `JourneyEndedPayload` (and any future payload with timestamp fields) |

Root cause (three retros, same thread): contracts exist in ADRs and Pydantic models, but nothing fails CI when a consumer violates them.

---

## Acceptance Criteria

### AC1 — Envelope contract test (A1)

**Given** a new test file `shared/tests/contract/test_envelope_contract.py` marked `@pytest.mark.contract`,  
**When** the test runs,  
**Then:**

1. It discovers all Python files in `rtsp-ingest/`, `vlan-pollers/`, `inference/`, `event-store/`, and `cloud-backend/` that import `EventEnvelope`, `EventModel`, or `EventType`.
2. For each discovered file it asserts the import resolves to the canonical `oebb_shared.events` module (i.e. no local shadow).
3. It asserts that every member of `EventType` has a corresponding entry in `PAYLOAD_MODELS` (registry completeness — already tested in unit tests but re-verified here under the `contract` marker for CI isolation).
4. It constructs a valid `EventEnvelope` for every `EventType` in the enum, using the minimal valid payload from the registry, and asserts `ValidationError` is **not** raised.
5. It asserts that `EventEnvelope` raises `ValidationError` for each of the following deliberate violations (one assertion each):
   - Missing required field `journey_id`
   - Missing required field `vehicle_id`
   - Invalid `event_type` string not in the enum (e.g. `"DOES_NOT_EXIST"`)
   - Missing required field `severity`
   - Missing required field `source`
   - Payload dict that violates its declared Pydantic model (e.g. `OCCUPANCY_UPDATE` with `car_id` missing)
   - Extra field on the envelope (forbidden by `extra = "forbid"`)

> **Note:** The test does not exec or import the container files — it performs static file-system discovery (glob) and import-path checks only. This keeps the test hermetic without requiring container dependencies to be installed.

### AC2 — Coverage gate verification (A3)

**Given** the existing CI job `test:shared` in `.gitlab-ci.yml` (line 64),  
**When** coverage for `shared/` drops below 80%,  
**Then** CI fails with a non-zero exit code (gate already present: `--cov-fail-under=80`).

Deliverable: add a comment in `.gitlab-ci.yml` on the `test:shared` job documenting that the gate is intentional (NFR12 enforcement). No numeric change required — gate is already wired. Also add the `contract` marker to the `test:shared` job script so contract tests run in CI:

```yaml
- cd shared && python -m pytest tests/ -m "unit or contract" --cov=oebb_shared --cov-report=term-missing --cov-fail-under=80
```

> Currently the job only runs `-m "unit"`. Switching to `"unit or contract"` pulls in the new AC1 test. Coverage **must not drop** — the new contract tests add coverage, not remove it.

### AC3 — ISO-8601 UTC timestamp validator on journey payloads (C2)

**Given** `JourneyStartedPayload` and `JourneyEndedPayload` in `shared/src/oebb_shared/events/payloads.py`,  
**When** a payload is constructed with any of:
- A naive datetime string (no timezone, e.g. `"2026-05-17T10:00:00"`)
- A non-UTC offset string (e.g. `"2026-05-17T12:00:00+02:00"`)
- An invalid timestamp format (e.g. `"2026-05-17 10:00:00Z"` — space separator)

**Then** Pydantic raises `ValidationError` at construction time.

**And** valid UTC strings (`"2026-05-17T10:00:00Z"`, `"2026-05-17T10:00:00.123Z"`) pass without error.

Implementation: add a shared validator function `_validate_iso_utc(v: str) -> str` in `payloads.py` (or a mixin base class) and apply it to the four timestamp fields:
- `JourneyStartedPayload.scheduled_departure`
- `JourneyStartedPayload.actual_departure`
- `JourneyEndedPayload.scheduled_arrival`
- `JourneyEndedPayload.actual_arrival`

The same regex already used in `envelope.py` (`_TIMESTAMP_RE`) must be reused — copy it to `payloads.py` (or import it) rather than inventing a new pattern.

### AC4 — Contract test validates C2 via bad fixture

**Given** the contract test file from AC1,  
**When** it constructs a `JourneyStartedPayload` with a naive timestamp (e.g. `scheduled_departure="2026-05-17T10:00:00"`),  
**Then** `ValidationError` is raised — proving the validator fires at CI time.

**And** a valid fixture with `Z`-suffix timestamps passes without error.

### AC5 — No existing tests broken; coverage rises

**Given** the current `shared/` test suite passes with coverage ≥ 80%,  
**When** this story's changes are applied,  
**Then:**
- All existing tests in `shared/tests/unit/` continue to pass.
- Coverage does not decrease.
- `python -m pytest tests/ -m "unit or contract" --cov=oebb_shared --cov-fail-under=80` exits 0.

---

## Technical Scope

**Files to CREATE:**
- `shared/tests/contract/__init__.py` — empty, makes directory a package
- `shared/tests/contract/test_envelope_contract.py` — contract test suite (AC1, AC4)

**Files to MODIFY:**
- `shared/src/oebb_shared/events/payloads.py` — add timestamp validator to journey payloads (AC3)
- `.gitlab-ci.yml` — extend `test:shared` script to include `contract` marker; add clarifying comment (AC2)

**Files NOT to touch:**
- `shared/src/oebb_shared/events/envelope.py` — timestamp regex already correct; `_validate_timestamp` already enforces Z-suffix; no changes needed
- `shared/src/oebb_shared/events/types.py` — audit confirmed 25 EventTypes are complete; zero additions
- `shared/tests/unit/test_event_envelope.py` — existing tests must pass unchanged
- Any container source file — the contract test is read-only (static discovery, no exec)

---

## Dev Notes

### A3 is already partially done — verify, don't re-implement

`pyproject.toml` already has:
```toml
[tool.coverage.report]
fail_under = 80
```

`.gitlab-ci.yml` line 64 already has `--cov-fail-under=80`.

The only A3 gap: the CI job script runs `-m "unit"` only, so the new `contract` tests won't run unless the marker filter is updated. That one-line change to `.gitlab-ci.yml` is the entire A3 deliverable — plus a comment documenting the gate.

### What the envelope already enforces (don't re-implement)

`EventEnvelope` in `envelope.py` already validates:
- `event_id` → UUID v4 regex
- `journey_id` → `{vehicle_id}_{trip_number}_{YYYYMMDD}` regex with calendar validity
- `timestamp` → `_TIMESTAMP_RE` (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$`)
- `event_type` → Pydantic `EventType` enum (raises `ValidationError` on unknown value)
- `source` → `Literal["inference", "fusion", "vlan-pollers"]`
- `severity` → `Literal["critical", "warning", "info"]`
- `schema_version` → must be in `SUPPORTED_SCHEMA_VERSIONS = frozenset({1})`
- `extra` fields → `"forbid"` (raises on unknown fields)
- `payload` → dispatched to `PAYLOAD_MODELS[event_type].model_validate(payload)` in `_validate_payload_shape`

**C2 gap:** The envelope's `_validate_timestamp` validator applies to `envelope.timestamp` (the event emission time). It does NOT apply to string fields inside `JourneyStartedPayload` and `JourneyEndedPayload` (`scheduled_departure`, `actual_departure`, `scheduled_arrival`, `actual_arrival`) — those are plain `_NonEmptyStr` today. That's the C2 fix.

### Timestamp regex — reuse, don't copy-paste a new one

The regex is defined in `envelope.py`:
```python
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
```

In `payloads.py`, import and reuse:
```python
from .envelope import _TIMESTAMP_RE  # private, but internal to the package
```

Or extract it to a shared `_validators.py` module inside `oebb_shared/events/` and import from both `envelope.py` and `payloads.py`. Either approach is acceptable; prefer the import over duplication.

### Payload timestamp validator pattern (Pydantic v2)

```python
from pydantic import field_validator

class JourneyStartedPayload(_BasePayload):
    ...
    scheduled_departure: _NonEmptyStr
    actual_departure: _NonEmptyStr

    @field_validator("scheduled_departure", "actual_departure", mode="before")
    @classmethod
    def _validate_timestamps(cls, v: str) -> str:
        from .envelope import _TIMESTAMP_RE
        if not _TIMESTAMP_RE.fullmatch(v):
            raise ValueError(
                f"timestamp must be ISO-8601 UTC with Z suffix, got: {v!r}"
            )
        return v
```

Same pattern for `JourneyEndedPayload` covering `scheduled_arrival` and `actual_arrival`.

### Contract test — discovery approach

The test must find container files without importing them (to avoid needing container deps). Use `pathlib.Path.rglob`:

```python
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parents[4]  # adjust depth to repo root
CONTAINER_DIRS = [
    "rtsp-ingest", "vlan-pollers", "inference", "event-store", "cloud-backend"
]
SENTINEL_NAMES = {"EventEnvelope", "EventModel", "EventType"}

def find_event_construction_files() -> list[Path]:
    found = []
    for container in CONTAINER_DIRS:
        for py_file in (REPO_ROOT / container).rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            if any(name in source for name in SENTINEL_NAMES):
                found.append(py_file)
    return found
```

Then for each found file, assert the import path points to `oebb_shared.events` (check the import line with `ast.parse` or simple string search).

### Minimal valid payloads for AC1 roundtrip

The contract test needs a minimal valid payload dict for each EventType. Build a `MINIMAL_PAYLOADS` fixture dict in the test file. Use the examples from `event-payload-schemas.md`. Do not import payload model constructors in the contract test — pass dicts directly to `EventEnvelope(payload=...)` so the envelope's `_validate_payload_shape` does the validation.

Key edge cases:
- `STREAM_PRIORITY` — valid payload but this EventType should **never be written to event-store**. Include it in the roundtrip (it has a model) but add a comment.
- `EventType` values that map to payload models requiring non-empty lists: `ACCESSIBILITY_DETECTED.assistance_type`, `CAMERA_DEGRADED.affected_zones`, `JOURNEY_STARTED.consist` — all need at least one element.
- `OCCUPANCY_UPDATE.capacity` must be ≥ 1 (not 0).

### Container event construction sites (confirmed 2026-05-19)

| Container | File | EventTypes used |
|---|---|---|
| `rtsp-ingest` | `rtsp_ingest/pipeline.py` | `CAMERA_DEGRADED`, `CAMERA_RECOVERED` |
| `vlan-pollers` | `vlan_pollers/snmp_poller.py` | `ALARM_ACTIVE`, `ALARM_CLEARED` |
| `inference` | `inference/zone_counter.py` | `OCCUPANCY_UPDATE`, `OCCUPANCY_THRESHOLD_CROSSED` |
| `event-store` | `event_store/routes/events.py`, `event_store/models.py` | Deserialises `EventEnvelope` / `EventModel`; does not construct new events |
| `cloud-backend` | `cloud_backend/routes/ingest.py` | Deserialises `EventEnvelope`; does not construct new events |

event-store and cloud-backend are consumers (deserialise), not producers (construct). The contract test's file-discovery step will find them but the import-path assertion covers both cases.

### Test markers

Per `shared/CLAUDE.md` and `pyproject.toml`:
- `unit` — pure logic, no I/O
- `integration` — real adapters
- `contract` — schema version compatibility

The new test file uses `@pytest.mark.contract` throughout. The CI change adds `or contract` to the `-m` filter.

### Current coverage baseline

Run `python -m pytest tests/ -m "unit" --cov=oebb_shared --cov-report=term-missing` in `shared/` to get the current baseline before adding new tests. The new contract tests add coverage on `payloads.py` (the journey validator) and `envelope.py` (roundtrip path through `_validate_payload_shape` for all 25 types). Coverage will rise, not fall.

### What must be preserved

- The `EventModel = EventEnvelope` alias in `envelope.py` (line 134) — used by `event-store`. Do not remove.
- The `_validate_payload_shape` logic that only fires when `payload` is non-empty — this is intentional for events that legitimately carry an empty payload dict.
- The `model_config = {"use_enum_values": True}` on `EventEnvelope` — required so that `EventType.OCCUPANCY_UPDATE` is stored as the string `"OCCUPANCY_UPDATE"`, not the enum object. The contract test must pass string values to `event_type`, not raw enum members, or it will break `use_enum_values` semantics.
- All 35 existing unit tests in `test_event_envelope.py` must pass without modification.

---

## Definition of Done

- [x] `shared/tests/contract/__init__.py` created
- [x] `shared/tests/contract/test_envelope_contract.py` created; all tests pass under `pytest -m contract`
- [x] `JourneyStartedPayload` and `JourneyEndedPayload` reject naive/non-UTC timestamps via `ValidationError`
- [x] Existing 35 unit tests in `test_event_envelope.py` continue to pass
- [x] `.gitlab-ci.yml` `test:shared` job updated to `-m "unit or contract"` with NFR12 comment
- [x] `python -m pytest tests/ -m "unit or contract" --cov=oebb_shared --cov-fail-under=80` exits 0 in `shared/`
- [x] No new EventTypes added (audit confirmed 25 is complete)
- [x] Committed and pushed to `origin master` per CLAUDE.md

---

## Dev Agent Record

### Implementation Notes

- **A1 contract test:** 50 tests in `shared/tests/contract/test_envelope_contract.py` covering: PAYLOAD_MODELS completeness, all 25 EventType roundtrips (parametrised), 7 deliberate envelope violations, container file discovery + canonical import assertion.
- **Repo root fix:** `_REPO_ROOT = Path(__file__).parents[3]` (not 4) — the file is 3 levels below repo root (`shared/tests/contract/`).
- **A3:** CI already had `--cov-fail-under=80`; the only gap was `-m "unit"` filtering out contract tests. Fixed to `-m "unit or contract"`. Comment added documenting NFR12.
- **C2:** `_validate_iso_utc()` function added to `payloads.py`, importing `_TIMESTAMP_RE` from `envelope.py`. Applied via `@field_validator` to `scheduled_departure`/`actual_departure` on `JourneyStartedPayload` and `scheduled_arrival`/`actual_arrival` on `JourneyEndedPayload`. 12 parametrised bad-fixture tests confirm the validator fires at CI time.
- **Pre-existing ruff warnings** in `envelope.py`, `mock.py`, `__init__.py` are not from this story and were not touched (surgical-change principle).
- **Coverage result:** 86.65% total (up from unit-only baseline); `payloads.py` now at 100%.
- **Test count:** 99 pass (35 unit + 50 contract + 14 other unit), 20 deselected (integration).

### Files Changed

| File | Change |
|---|---|
| `shared/tests/contract/__init__.py` | Created (empty package marker) |
| `shared/tests/contract/test_envelope_contract.py` | Created (50 contract tests — AC1, AC4) |
| `shared/src/oebb_shared/events/payloads.py` | Added `_validate_iso_utc()` + `@field_validator` on journey payloads (AC3) |
| `.gitlab-ci.yml` | `-m "unit or contract"` + NFR12 comment on `test:shared` job (AC2) |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | Status updated in-progress → review |

### Change Log

- 2026-05-19: Implemented story 1-8 — A1 envelope contract test (50 tests), A3 CI marker fix, C2 UTC timestamp validator on journey payloads. 99 tests pass, 87% coverage. Committed 545ffd9 and pushed.

---

## Commit Template

```
fix(shared): event contract enforcement — A1 contract test, A3 gate, C2 UTC validator

Agent: Amelia | Phase: BMAD-DEV Step 1 (Story 1-8)
Next: Run E4-S5 story create when Hailo-8 hardware arrives — contract test will catch inference violations at CI time
Blocked: —
```
