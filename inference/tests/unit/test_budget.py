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
    """Identical updates must not flip state — verified through behavioural invariance."""
    budget.on_context_update({"p2_throttled": True})
    assert budget._p2_throttled is True
    budget.on_context_update({"p2_throttled": True})
    assert budget._p2_throttled is True
    assert budget.should_process("C1_INT_01", "P2") is False


@pytest.mark.unit
def test_missing_p2_throttled_key_defaults_false(budget: Budget) -> None:
    budget.on_context_update({})
    assert budget.should_process("C1_INT_01", "P2") is True


@pytest.mark.unit
def test_string_false_does_not_engage_throttle(budget: Budget) -> None:
    """String 'false' must not be coerced to True via bool() truthiness."""
    budget.on_context_update({"p2_throttled": "false"})  # type: ignore[dict-item]
    assert budget._p2_throttled is False
    assert budget.should_process("C1_INT_01", "P2") is True


@pytest.mark.unit
def test_non_bool_type_ignored(budget: Budget) -> None:
    budget.on_context_update({"p2_throttled": 1})  # type: ignore[dict-item]
    assert budget._p2_throttled is False
