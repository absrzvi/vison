"""Tests for config defaults."""

from __future__ import annotations

import pytest

from vlan_pollers.config import Settings


@pytest.mark.unit
def test_settings_defaults() -> None:
    s = Settings()
    assert s.snmp_port == 161
    assert s.station_approach_window_s == 120
    assert s.snmp_poll_interval_s == 5.0


@pytest.mark.unit
def test_settings_override_via_kwargs() -> None:
    s = Settings(vehicle_id="OBB-9999", snmp_host="10.0.0.1", snmp_community="private")
    assert s.vehicle_id == "OBB-9999"
    assert s.snmp_host == "10.0.0.1"
    assert s.snmp_community == "private"
