# Story 1-2: Event Envelope & Pydantic Models

**Epic:** 1 — Foundation & Shared Infrastructure
**Story:** 2
**Story Key:** 1-2-event-envelope-pydantic-models
**Status:** review
**Date Created:** 2026-05-17

---

## User Story

**As a** developer,
**I want** a canonical `EventEnvelope` Pydantic model and all 17 event payload models living in `shared/events/`,
**so that** every container produces and consumes events with a single, validated, type-safe schema and no ad-hoc dict manipulation.

---

## Acceptance Criteria

- [x] **AC1** — `EventType` StrEnum in `shared/events/types.py` contains exactly 17 values matching `event-payload-schemas.md`. Import passes ruff + mypy --strict.
- [x] **AC2** — `EventEnvelope` Pydantic model in `shared/events/envelope.py`: `event_id` UUID v4 str, `journey_id` matching pattern `{vehicle_id}_{trip_number}_{YYYYMMDD}`, `timestamp` ISO-8601 UTC Z, `event_type` EventType member, `severity` critical|warning|info, `source` inference|fusion|vlan-pollers. Validation raises on unrecognised `event_type`.
- [x] **AC3** — Unrecognised `event_type` raises `ValidationError` (no silent coercion).
- [x] **AC4** — `shared/events/payloads.py` exports one Pydantic model per EventType (17 total), field names and types exactly matching `event-payload-schemas.md`.
- [x] **AC5** — `OCCUPANCY_UPDATE` payload: `confidence` field is optional and omitted from serialised output when not set (not 0, not null).
- [x] **AC6** — `mypy --strict shared/events/` passes with zero errors.
- [x] **AC7** — `pytest tests/unit/test_event_envelope.py` achieves ≥80% coverage of `shared/events/` (actual: 100%).
- [x] **AC8** — `EventEnvelope.model_json_schema()` can be called without error.

---

## Tasks / Subtasks

- [x] **T1** — Strengthen `envelope.py`: add `EventEnvelope` as canonical Pydantic model name; add journey_id pattern validator; ensure unrecognised event_type raises ValidationError
  - [x] T1.1 — Add `EventEnvelope` (alias or rename from `EventModel`) with Pydantic v2 `field_validator` for `journey_id` pattern
  - [x] T1.2 — `EventModel` retained as backwards-compatible alias; `use_enum_values = True` kept for serialisation
- [x] **T2** — Create `shared/src/oebb_shared/events/payloads.py` with all 17 payload models
  - [x] T2.1 — Occupancy: `OccupancyUpdatePayload`, `OccupancyThresholdCrossedPayload`
  - [x] T2.2 — Alerts: `AlertRaisedPayload`, `AlertResolvedPayload`
  - [x] T2.3 — Congestion/Luggage: `VestibuleCongestionPayload`, `LuggageRackSaturationPayload`
  - [x] T2.4 — Safety: `UnattendedBagPayload`, `DoorObstructionPayload`
  - [x] T2.5 — Accessibility: `AccessibilityDetectedPayload`, `RampDeployedPayload`
  - [x] T2.6 — TCMS/Alarms: `AlarmActivePayload`, `AlarmClearedPayload`
  - [x] T2.7 — Journey: `JourneyStartedPayload`, `JourneyEndedPayload`
  - [x] T2.8 — System: `CameraDegradedPayload`, `CameraRecoveredPayload`, `SyncCompletedPayload`
- [x] **T3** — Update `shared/src/oebb_shared/events/__init__.py` to export `EventEnvelope` and payload models
- [x] **T4** — Write `shared/tests/unit/test_event_envelope.py` covering all ACs
- [x] **T5** — Run `mypy --strict shared/src/oebb_shared/events/` — 0 errors
- [x] **T6** — Run `pytest --cov=oebb_shared.events --cov-fail-under=80` — 29/29 passed, 100% coverage

---

## Dev Notes

- Package layout: `shared/src/oebb_shared/events/` — installed as `oebb-shared`
- `EventType` already complete in `types.py` (17 values) — do not modify
- `EventModel` in `envelope.py` was created in E1-S1 as a skeleton. This story adds `EventEnvelope` as the canonical name and adds validation.
- Pydantic v2: use `model_validator(mode="before")` for journey_id pattern check; `model_config = {"use_enum_values": True}` is fine — enum values are strings
- `confidence` optional omission: use `Optional[float] = None` with `model_config = {"exclude_none": True}` **per model** or use `Field(default=None)` with `model_serializer` — simplest is `model_config` on the specific payload class
- Payload `__init__.py` should export a `PAYLOAD_MODELS: dict[EventType, type[BaseModel]]` registry for downstream consumers
- Ref: `_bmad-output/planning-artifacts/event-payload-schemas.md`

---

## Dev Agent Record

### Implementation Plan
- Strengthen `envelope.py`: rename/alias `EventModel` → `EventEnvelope`, add journey_id regex validator
- Write `payloads.py`: 17 models, `confidence` optional with exclude_none
- Update `__init__.py` exports
- Write comprehensive tests

### Debug Log
_Empty_

### Completion Notes
- `EventEnvelope` added as canonical name; `EventModel` kept as backwards-compatible alias for event-store code from E1-S1.
- `journey_id` pattern validated via Pydantic `field_validator`: must match `^[^_]+_[^_]+_\d{8}$`.
- `confidence` omission implemented via Pydantic `model_serializer(mode="wrap")` — cleaner than overriding `model_dump` and fully mypy-strict compatible.
- `AlertRaisedPayload.priority` uses same pattern (omitted when None) per ADR-18 Trigger 3.
- `PAYLOAD_MODELS` registry exported from `__init__.py` for downstream consumers.
- 29 unit tests, 100% coverage of `shared/events/`, 33/33 total suite passing, 0 regressions.

---

## File List

- `shared/src/oebb_shared/events/envelope.py` — modified
- `shared/src/oebb_shared/events/payloads.py` — created
- `shared/src/oebb_shared/events/__init__.py` — modified
- `shared/tests/unit/test_event_envelope.py` — created

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-17 | Story created |
| 2026-05-17 | Implementation complete — all ACs satisfied, status → review |
