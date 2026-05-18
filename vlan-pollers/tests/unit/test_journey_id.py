"""ADR-2 midnight-crossing stability test — required by architecture."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from vlan_pollers.journey_tracker import JourneyTracker


@pytest.mark.unit
def test_midnight_crossing_stability() -> None:
    """journey_id must not change when wall-clock rolls past midnight for same trip_number."""
    tracker = JourneyTracker()
    vehicle_id = "OBB-4711"
    trip_number = "T999"

    # First seen at 23:45 on 2026-05-17
    t1 = datetime(2026, 5, 17, 23, 45, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t1
        j1 = tracker.get_journey_id(vehicle_id, trip_number)

    # Same trip, event arrives at 00:05 on 2026-05-18
    t2 = datetime(2026, 5, 18, 0, 5, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t2
        j2 = tracker.get_journey_id(vehicle_id, trip_number)

    assert j1 == j2, "journey_id must not change across midnight for same trip_number"
    assert j1.endswith("20260517"), "date segment must be first-seen date, not post-midnight date"


@pytest.mark.unit
def test_new_trip_number_gets_fresh_date() -> None:
    """Different trip_number records its own start date independently."""
    tracker = JourneyTracker()
    vehicle_id = "OBB-4711"

    t1 = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t1
        j1 = tracker.get_journey_id(vehicle_id, "T100")

    t2 = datetime(2026, 5, 18, 8, 0, 0, tzinfo=UTC)
    with patch("vlan_pollers.journey_tracker.datetime") as mock_dt:
        mock_dt.now.return_value = t2
        j2 = tracker.get_journey_id(vehicle_id, "T101")

    assert j1.endswith("20260517")
    assert j2.endswith("20260518")
    assert j1 != j2


@pytest.mark.unit
def test_journey_id_format() -> None:
    """journey_id must match {vehicle_id}_{trip_number}_{YYYYMMDD} format."""
    tracker = JourneyTracker()
    jid = tracker.get_journey_id("OBB-1234", "T555")
    parts = jid.split("_")
    assert len(parts) == 3
    assert parts[0] == "OBB-1234"
    assert parts[1] == "T555"
    assert len(parts[2]) == 8
    assert parts[2].isdigit()


@pytest.mark.unit
def test_known_trips_tracks_seen_trips() -> None:
    tracker = JourneyTracker()
    tracker.get_journey_id("V1", "T1")
    tracker.get_journey_id("V1", "T2")
    assert "T1" in tracker.known_trips()
    assert "T2" in tracker.known_trips()


@pytest.mark.unit
def test_current_journey_id_for_known_trip() -> None:
    tracker = JourneyTracker()
    tracker.get_journey_id("V1", "T99")
    jid = tracker.current_journey_id("V1", "T99")
    assert "V1" in jid
    assert "T99" in jid


@pytest.mark.unit
def test_current_journey_id_for_unknown_trip_uses_today() -> None:
    """current_journey_id for an unseen trip falls back to today's date."""
    tracker = JourneyTracker()
    jid = tracker.current_journey_id("V1", "UNKNOWN")
    from datetime import UTC, datetime
    today = datetime.now(UTC).strftime("%Y%m%d")
    assert jid.endswith(today)
