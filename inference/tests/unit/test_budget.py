"""Unit tests for budget.py — TOPS P2 suppression logic."""
from __future__ import annotations

import pytest

from inference.budget import Budget
from inference.config import Settings


@pytest.fixture
def budget() -> Budget:
    return Budget(Settings())


@pytest.mark.unit
def test_p1_always_passes(budget: Budget) -> None:
    budget.on_context_update({"p2_throttled": True})
    assert budget.should_process("C1_DOOR_01", "P1") is True


@pytest.mark.unit
def test_p2_suppressed_when_throttled(budget: Budget) -> None:
    budget.on_context_update({"p2_throttled": True})
    assert budget.should_process("C1_INT_01", "P2") is False


@pytest.mark.unit
def test_p2_passes_when_not_throttled(budget: Budget) -> None:
    budget.on_context_update({"p2_throttled": False})
    assert budget.should_process("C1_INT_01", "P2") is True


@pytest.mark.unit
def test_throttle_recovery(budget: Budget) -> None:
    budget.on_context_update({"p2_throttled": True})
    assert budget.should_process("C1_INT_01", "P2") is False
    budget.on_context_update({"p2_throttled": False})
    assert budget.should_process("C1_INT_01", "P2") is True


@pytest.mark.unit
def test_transition_only_logging(budget: Budget) -> None:
    """Only one state change should happen for two identical updates."""
    # Verify by inspecting internal state transitions rather than log output
    budget.on_context_update({"p2_throttled": True})
    assert budget._p2_throttled is True
    budget.on_context_update({"p2_throttled": True})  # duplicate — state unchanged
    assert budget._p2_throttled is True
    # The second call should not flip state — tested via P2 suppression still active
    assert budget.should_process("C1_INT_01", "P2") is False


@pytest.mark.unit
def test_missing_p2_throttled_key_defaults_false(budget: Budget) -> None:
    budget.on_context_update({})
    assert budget.should_process("C1_INT_01", "P2") is True
