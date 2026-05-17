"""AC18: SubscriptionRequest filter logic — severity, event_type, coach_id."""
import pytest
from oebb_shared.ws.subscription import SubscriptionRequest


@pytest.mark.unit
def test_min_severity_info_accepts_all() -> None:
    sub = SubscriptionRequest(event_types=["OCCUPANCY_UPDATE"], min_severity="info")
    assert sub.matches("OCCUPANCY_UPDATE", "info")
    assert sub.matches("OCCUPANCY_UPDATE", "warning")
    assert sub.matches("OCCUPANCY_UPDATE", "critical")


@pytest.mark.unit
def test_min_severity_warning_rejects_info() -> None:
    sub = SubscriptionRequest(event_types=["OCCUPANCY_UPDATE"], min_severity="warning")
    assert not sub.matches("OCCUPANCY_UPDATE", "info")
    assert sub.matches("OCCUPANCY_UPDATE", "warning")
    assert sub.matches("OCCUPANCY_UPDATE", "critical")


@pytest.mark.unit
def test_min_severity_critical_rejects_warning_and_info() -> None:
    sub = SubscriptionRequest(event_types=["ALERT_RAISED"], min_severity="critical")
    assert not sub.matches("ALERT_RAISED", "info")
    assert not sub.matches("ALERT_RAISED", "warning")
    assert sub.matches("ALERT_RAISED", "critical")


@pytest.mark.unit
def test_event_type_filter_rejects_unlisted_type() -> None:
    sub = SubscriptionRequest(event_types=["OCCUPANCY_UPDATE"], min_severity="info")
    assert not sub.matches("DOOR_OBSTRUCTION", "info")
    assert not sub.matches("ALERT_RAISED", "critical")


@pytest.mark.unit
def test_coach_id_filter_rejects_other_coaches() -> None:
    sub = SubscriptionRequest(
        event_types=["OCCUPANCY_UPDATE"],
        min_severity="info",
        coach_ids=["car-3"],
    )
    assert sub.matches("OCCUPANCY_UPDATE", "info", coach_id="car-3")
    assert not sub.matches("OCCUPANCY_UPDATE", "info", coach_id="car-1")


@pytest.mark.unit
def test_coach_id_none_accepts_all_coaches() -> None:
    sub = SubscriptionRequest(event_types=["OCCUPANCY_UPDATE"], min_severity="info", coach_ids=None)
    assert sub.matches("OCCUPANCY_UPDATE", "info", coach_id="car-1")
    assert sub.matches("OCCUPANCY_UPDATE", "info", coach_id="car-99")


@pytest.mark.unit
def test_reconnect_replay_depth_default() -> None:
    sub = SubscriptionRequest(event_types=["OCCUPANCY_UPDATE"], min_severity="info")
    assert sub.reconnect_replay_depth == 50


@pytest.mark.unit
def test_reconnect_replay_depth_configurable() -> None:
    sub = SubscriptionRequest(
        event_types=["OCCUPANCY_UPDATE"], min_severity="info", reconnect_replay_depth=10
    )
    assert sub.reconnect_replay_depth == 10
