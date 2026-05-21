"""ContextState + ContextPushModel — AC3, AC9."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from fusion.context_state import ContextState
from fusion.models import ContextPushModel


@pytest.mark.unit
def test_context_push_strict_bool_rejects_strings() -> None:
    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"maintenance_mode": "yes"})
    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"depot_mode": 1})


@pytest.mark.unit
def test_context_push_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"made_up_field": True})


@pytest.mark.unit
def test_context_push_accepts_full_state() -> None:
    model = ContextPushModel.model_validate(
        {
            "journey_id": "OBB-TEST_t1_20260520",
            "vehicle_id": "OBB-TEST",
            "speed_kmh": 42.5,
            "station_approach": True,
            "maintenance_mode": False,
            "depot_mode": False,
            "gps_valid": True,
            "door_release": {"car-1:door-1A": True},
            "door_state": {"car-1:door-1A": "closing"},
            "reservations": {"car-1": 12},
            "consist": {"1": "car-1", "2": "car-2"},
        }
    )
    assert model.station_approach is True
    assert model.door_state == {"car-1:door-1A": "closing"}


@pytest.mark.unit
def test_update_from_push_writes_all_fields() -> None:
    ctx = ContextState()
    model = ContextPushModel.model_validate(
        {
            "journey_id": "OBB-TEST_t1_20260520",
            "vehicle_id": "OBB-TEST",
            "speed_kmh": 30.0,
            "maintenance_mode": True,
            "depot_mode": False,
            "gps_valid": False,
            "station_approach": True,
            "door_state": {"car-1:door-1A": "closed"},
            "reservations": {"car-1": 5},
            "consist": {"1": "car-1"},
        }
    )
    ctx.update_from_push(model)
    assert ctx.journey_id == "OBB-TEST_t1_20260520"
    assert ctx.vehicle_id == "OBB-TEST"
    assert ctx.speed_kmh == 30.0
    assert ctx.maintenance_mode is True
    assert ctx.gps_valid is False
    assert ctx.station_approach is True
    assert ctx.door_state["car-1:door-1A"] == "closed"
    assert ctx.reservations == {"car-1": 5}
    assert ctx.consist == {"1": "car-1"}


@pytest.mark.unit
def test_door_state_for_returns_unknown_when_missing() -> None:
    ctx = ContextState()
    assert ctx.door_state_for("car-9", "door-9X") == "unknown"


@pytest.mark.unit
def test_resolve_car_id_consist_mapping() -> None:
    ctx = ContextState()
    ctx.consist = {"1": "car-1", "2": "car-2"}
    assert ctx.resolve_car_id("1") == "car-1"
    assert ctx.resolve_car_id(2) == "car-2"


@pytest.mark.unit
def test_resolve_car_id_passthrough_when_missing() -> None:
    ctx = ContextState()
    # Empty consist → passthrough.
    assert ctx.resolve_car_id("car-7") == "car-7"
    ctx.consist = {"1": "car-1"}
    # Index not in map → passthrough.
    assert ctx.resolve_car_id("99") == "99"


@pytest.mark.unit
def test_resolve_car_id_empty_string_passthrough() -> None:
    """An empty-string value in consist is treated as a passthrough, not as a
    successful mapping — otherwise downstream door_state keys become ":door-X".
    """
    ctx = ContextState()
    ctx.consist = {"1": ""}
    assert ctx.resolve_car_id("1") == "1"


@pytest.mark.unit
def test_partial_push_keeps_prior_state_for_omitted_fields() -> None:
    """New push semantics: absent field == keep prior; explicit value == replace."""
    ctx = ContextState()
    initial = ContextPushModel.model_validate(
        {
            "maintenance_mode": True,
            "gps_valid": False,
            "speed_kmh": 25.0,
            "door_state": {"car-1:door-1A": "closed"},
        }
    )
    ctx.update_from_push(initial)
    assert ctx.maintenance_mode is True
    assert ctx.gps_valid is False
    assert ctx.speed_kmh == 25.0
    assert ctx.door_state == {"car-1:door-1A": "closed"}

    # Partial push: only speed_kmh — all other fields preserved.
    partial = ContextPushModel.model_validate({"speed_kmh": 35.0})
    ctx.update_from_push(partial)
    assert ctx.speed_kmh == 35.0
    assert ctx.maintenance_mode is True
    assert ctx.gps_valid is False
    assert ctx.door_state == {"car-1:door-1A": "closed"}


@pytest.mark.unit
def test_explicit_empty_dict_clears_prior_state() -> None:
    """Empty dict on a dict field explicitly clears (distinct from absent)."""
    ctx = ContextState()
    ctx.update_from_push(
        ContextPushModel.model_validate({"door_state": {"car-1:door-1A": "closed"}})
    )
    assert ctx.door_state == {"car-1:door-1A": "closed"}

    ctx.update_from_push(ContextPushModel.model_validate({"door_state": {}}))
    assert ctx.door_state == {}


@pytest.mark.unit
def test_observe_ramp_signal_edge_trigger() -> None:
    ctx = ContextState()
    # false → true: edge fires
    assert ctx.observe_ramp_signal(True) is True
    # true → true: no edge
    assert ctx.observe_ramp_signal(True) is False
    # true → false: no edge (only false→true fires)
    assert ctx.observe_ramp_signal(False) is False
    # false → true again: edge fires
    assert ctx.observe_ramp_signal(True) is True


@pytest.mark.unit
def test_observe_station_approach_edge_trigger() -> None:
    """E4-S10 AC2 — mirror of observe_ramp_signal for station_approach."""
    ctx = ContextState()
    # Default: station_approach=False, _prev_station_approach=False → no edge.
    assert ctx.observe_station_approach_edge() is False
    # Simulate ContextPushModel applying station_approach=True.
    ctx.station_approach = True
    assert ctx.observe_station_approach_edge() is True
    # Steady True — no further edge.
    assert ctx.observe_station_approach_edge() is False
    # True → False: no edge (only false→true fires).
    ctx.station_approach = False
    assert ctx.observe_station_approach_edge() is False
    # False → True again: edge fires.
    ctx.station_approach = True
    assert ctx.observe_station_approach_edge() is True


@pytest.mark.unit
def test_car_id_for_door_basic() -> None:
    ctx = ContextState()
    ctx.door_state = {"car-3:door-3B": "closing"}
    assert ctx.car_id_for_door("door-3B") == "car-3"
    assert ctx.car_id_for_door("door-9X") is None


@pytest.mark.unit
def test_accessibility_recency_lookup_within_window() -> None:
    ctx = ContextState()
    ctx.note_accessibility("car-1", "door-1A", "trk-42", now=100.0)
    found = ctx.find_recent_accessibility("car-1", "door-1A", window_s=60.0, now=110.0)
    assert found == "trk-42"


@pytest.mark.unit
def test_accessibility_recency_expires_after_ttl() -> None:
    ctx = ContextState()
    ctx.note_accessibility("car-1", "door-1A", "trk-42", now=100.0)
    expired = ctx.find_recent_accessibility("car-1", "door-1A", window_s=60.0, now=300.0)
    assert expired is None


@pytest.mark.unit
def test_accessibility_recency_returns_none_for_unknown_car() -> None:
    ctx = ContextState()
    assert ctx.find_recent_accessibility("car-99", "door-1A", window_s=60.0) is None
