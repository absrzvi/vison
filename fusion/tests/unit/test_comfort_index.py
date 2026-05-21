"""Unit tests for the Coach Comfort Index engine (E4-S10, ADR-18).

Covers AC1, AC2, AC3, AC4, AC5, AC6 from the story spec. Suppression-gate
behaviour (AC5) is verified at the handler layer in ``test_health.py``;
this module focuses on the ``ComfortIndexState`` pure-state machine.
"""
from __future__ import annotations

import pytest
from oebb_shared.events.payloads import OccupancyUpdatePayload

from fusion.comfort_index import ComfortIndexState
from fusion.config import Settings


def _settings(threshold: float = 0.10) -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        ledger_db_path=":memory:",
        comfort_index_pct_threshold=threshold,
    )


def _occupancy(car_id: str, pct: float, capacity: int = 200) -> OccupancyUpdatePayload:
    count = int(round(pct * capacity))
    return OccupancyUpdatePayload(
        car_id=car_id,
        zone=None,
        occupancy_count=count,
        occupancy_pct=pct,
        capacity=capacity,
        service_tier="standard",
    )


# ---------------------------------------------------------------------------
# AC4 — first OCCUPANCY_UPDATE per coach seeds baseline, no emit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_first_occupancy_seeds_baseline_no_emit() -> None:
    state = ComfortIndexState(_settings())
    out = state.on_occupancy_update(_occupancy("car-1", 0.40))
    assert out is None
    # Baseline is seeded so the next delta check has a value to compare.
    assert state._last_emitted_pct["car-1"] == pytest.approx(0.40)
    assert "car-1" in state._observed_coaches


# ---------------------------------------------------------------------------
# AC1 — emit only when |delta| > threshold
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sub_threshold_delta_no_emit() -> None:
    state = ComfortIndexState(_settings(threshold=0.10))
    state.on_occupancy_update(_occupancy("car-1", 0.40))  # seed
    out = state.on_occupancy_update(_occupancy("car-1", 0.49))  # delta = 0.09
    assert out is None
    # Baseline must NOT advance on sub-threshold ticks (AC1 only updates on emit).
    assert state._last_emitted_pct["car-1"] == pytest.approx(0.40)


@pytest.mark.unit
def test_above_threshold_delta_emits_and_advances_baseline() -> None:
    state = ComfortIndexState(_settings(threshold=0.10))
    state.on_occupancy_update(_occupancy("car-1", 0.40))  # seed
    out = state.on_occupancy_update(_occupancy("car-1", 0.55))  # delta = 0.15 > 0.10
    assert out is not None
    assert out.car_id == "car-1"
    assert out.occupancy_pct == pytest.approx(0.55)
    # comfort_score = 1.0 - 0.55 = 0.45
    assert out.comfort_score == pytest.approx(0.45)
    # Baseline advances on emit.
    assert state._last_emitted_pct["car-1"] == pytest.approx(0.55)


@pytest.mark.unit
def test_delta_exactly_at_threshold_no_emit() -> None:
    """Story AC1 specifies `> threshold`, strict. delta == threshold must NOT emit."""
    state = ComfortIndexState(_settings(threshold=0.10))
    state.on_occupancy_update(_occupancy("car-1", 0.40))
    out = state.on_occupancy_update(_occupancy("car-1", 0.50))  # delta == 0.10 exactly
    assert out is None


@pytest.mark.unit
def test_negative_delta_above_threshold_emits() -> None:
    """A drop in occupancy that crosses the threshold also emits."""
    state = ComfortIndexState(_settings(threshold=0.10))
    state.on_occupancy_update(_occupancy("car-1", 0.80))
    out = state.on_occupancy_update(_occupancy("car-1", 0.50))  # delta = -0.30
    assert out is not None
    assert out.occupancy_pct == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# AC3 — payload shape + comfort_score clamping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_payload_shape_and_environmental_fields_none() -> None:
    state = ComfortIndexState(_settings())
    state.on_occupancy_update(_occupancy("car-1", 0.20))
    out = state.on_occupancy_update(_occupancy("car-1", 0.60))
    assert out is not None
    dumped = out.model_dump()
    assert dumped["car_id"] == "car-1"
    assert dumped["comfort_score"] == pytest.approx(0.40)
    assert dumped["occupancy_pct"] == pytest.approx(0.60)
    assert dumped["temperature_c"] is None
    assert dumped["noise_db"] is None


@pytest.mark.unit
def test_comfort_score_clamps_at_zero_occupancy() -> None:
    state = ComfortIndexState(_settings(threshold=0.05))
    state.on_occupancy_update(_occupancy("car-1", 0.50))
    out = state.on_occupancy_update(_occupancy("car-1", 0.0))
    assert out is not None
    assert out.comfort_score == pytest.approx(1.0)
    assert out.occupancy_pct == pytest.approx(0.0)


@pytest.mark.unit
def test_comfort_score_clamps_at_full_occupancy() -> None:
    state = ComfortIndexState(_settings(threshold=0.05))
    state.on_occupancy_update(_occupancy("car-1", 0.50))
    out = state.on_occupancy_update(_occupancy("car-1", 1.0))
    assert out is not None
    assert out.comfort_score == pytest.approx(0.0)
    assert out.occupancy_pct == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# AC2 — station_approach edge emits one payload per observed coach
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_station_approach_edge_emits_for_all_observed_coaches() -> None:
    state = ComfortIndexState(_settings())
    state.on_occupancy_update(_occupancy("car-1", 0.30))
    state.on_occupancy_update(_occupancy("car-2", 0.55))
    state.on_occupancy_update(_occupancy("car-3", 0.80))
    payloads = state.on_station_approach_edge()
    assert len(payloads) == 3
    by_car = {p.car_id: p for p in payloads}
    assert by_car["car-1"].comfort_score == pytest.approx(0.70)
    assert by_car["car-2"].comfort_score == pytest.approx(0.45)
    assert by_car["car-3"].comfort_score == pytest.approx(0.20)


@pytest.mark.unit
def test_station_approach_edge_does_not_advance_baseline() -> None:
    """Station-edge emits MUST NOT advance `_last_emitted_pct` — that's reserved
    for delta-driven emits (Dev Notes line 183-184)."""
    state = ComfortIndexState(_settings())
    state.on_occupancy_update(_occupancy("car-1", 0.30))
    state.on_occupancy_update(_occupancy("car-1", 0.50))  # 1st emit, baseline → 0.50
    baseline = state._last_emitted_pct["car-1"]
    state.on_station_approach_edge()
    assert state._last_emitted_pct["car-1"] == baseline


@pytest.mark.unit
def test_station_approach_edge_with_no_observed_coaches_returns_empty() -> None:
    state = ComfortIndexState(_settings())
    assert state.on_station_approach_edge() == []


# ---------------------------------------------------------------------------
# AC5 verified at handler layer; AC6 verified by Enrichment (existing tests).
# ---------------------------------------------------------------------------
