"""Suppression state machine — AC4."""
from __future__ import annotations

from typing import Any

import pytest

from fusion.context_state import ContextState
from fusion.suppression import SuppressionGate, SuppressionState, evaluate


class _RecordingEnricher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def emit_envelope(
        self,
        *,
        event_type_name: str,
        payload: dict[str, Any],
        severity: str,
    ) -> None:
        self.calls.append(
            {"event_type_name": event_type_name, "payload": payload, "severity": severity}
        )


@pytest.mark.unit
def test_evaluate_normal_when_all_clear() -> None:
    assert evaluate(ContextState()) == SuppressionState.NORMAL


@pytest.mark.unit
def test_evaluate_gps_invalid_when_gps_not_valid() -> None:
    ctx = ContextState(gps_valid=False)
    assert evaluate(ctx) == SuppressionState.GPS_INVALID


@pytest.mark.unit
def test_evaluate_maintenance_takes_priority_over_gps_invalid() -> None:
    ctx = ContextState(maintenance_mode=True, gps_valid=False)
    assert evaluate(ctx) == SuppressionState.MAINTENANCE


@pytest.mark.unit
def test_evaluate_depot_takes_top_priority() -> None:
    ctx = ContextState(maintenance_mode=True, depot_mode=True, gps_valid=False)
    assert evaluate(ctx) == SuppressionState.DEPOT


@pytest.mark.unit
async def test_should_emit_true_when_normal() -> None:
    ctx = ContextState()
    gate = SuppressionGate(ctx, _RecordingEnricher())  # type: ignore[arg-type]
    assert gate.should_emit() is True


@pytest.mark.unit
async def test_should_emit_false_under_maintenance() -> None:
    ctx = ContextState(maintenance_mode=True)
    gate = SuppressionGate(ctx, _RecordingEnricher())  # type: ignore[arg-type]
    assert gate.should_emit() is False


@pytest.mark.unit
async def test_should_emit_false_when_gps_invalid() -> None:
    ctx = ContextState(gps_valid=False)
    gate = SuppressionGate(ctx, _RecordingEnricher())  # type: ignore[arg-type]
    assert gate.should_emit() is False


@pytest.mark.unit
async def test_depot_transition_emits_journey_ended_exactly_once() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520")
    enricher = _RecordingEnricher()
    gate = SuppressionGate(ctx, enricher)  # type: ignore[arg-type]

    # NORMAL → DEPOT
    ctx.depot_mode = True
    await gate.on_context_changed()
    assert len(enricher.calls) == 1
    assert enricher.calls[0]["event_type_name"] == "JOURNEY_ENDED"

    # Re-entering DEPOT for the same journey does NOT re-emit.
    ctx.depot_mode = False
    await gate.on_context_changed()
    ctx.depot_mode = True
    await gate.on_context_changed()
    assert len(enricher.calls) == 1


@pytest.mark.unit
async def test_new_journey_after_depot_exit_re_emits_journey_ended() -> None:
    ctx = ContextState(journey_id="OBB-TEST_t1_20260520")
    enricher = _RecordingEnricher()
    gate = SuppressionGate(ctx, enricher)  # type: ignore[arg-type]

    ctx.depot_mode = True
    await gate.on_context_changed()
    ctx.depot_mode = False
    await gate.on_context_changed()
    # New journey id, then DEPOT again.
    ctx.journey_id = "OBB-TEST_t2_20260521"
    ctx.depot_mode = True
    await gate.on_context_changed()
    assert len(enricher.calls) == 2


@pytest.mark.unit
async def test_recovery_to_normal_clears_suppression() -> None:
    ctx = ContextState(maintenance_mode=True)
    gate = SuppressionGate(ctx, _RecordingEnricher())  # type: ignore[arg-type]
    assert gate.should_emit() is False
    ctx.maintenance_mode = False
    await gate.on_context_changed()
    assert gate.should_emit() is True
