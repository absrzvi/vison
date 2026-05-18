"""Tests for SnmpPoller — alarm event emission and door release signalling."""

from __future__ import annotations

import httpx
import pytest
import respx

from vlan_pollers.context_state import ContextStateManager
from vlan_pollers.journey_tracker import JourneyTracker
from vlan_pollers.snmp_poller import SnmpPoller, _post_event_with_retry

FUSION = "http://fusion-test:8003"
INFERENCE = "http://inference-test:8004"
RTSP = "http://rtsp-test:8005"
EVENT_STORE = "http://event-store-test:8001"


def _make_poller(set_ready_fn: object = None) -> SnmpPoller:
    tracker = JourneyTracker()
    ctx = ContextStateManager(
        fusion_url=FUSION, inference_url=INFERENCE, rtsp_ingest_url=RTSP
    )
    return SnmpPoller(
        vehicle_id="OBB-1",
        snmp_host="localhost",
        snmp_port=161,
        snmp_community="public",
        snmp_speed_oid="1.3.6.1.4.1.9999.1.0",
        poll_interval_s=0.01,
        tracker=tracker,
        ctx=ctx,
        event_store_url=EVENT_STORE,
        set_snmp_ready_fn=set_ready_fn or (lambda x: None),
    )


@pytest.mark.unit
@respx.mock
async def test_emit_alarm_active_event_posts_to_event_store() -> None:
    """On first alarm (None → active), an ALARM_ACTIVE event is POSTed."""
    es_route = respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(201))
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    # Set journey context first
    poller._tracker.get_journey_id("OBB-1", "T1")

    varbinds = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-001"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Door obstruction"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "1"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "1"),
        ("1.3.6.1.4.1.1234.1.1.1.0", "T1"),  # exact scalar OID
    ]
    await poller._process(varbinds)

    assert es_route.called
    import json
    body = json.loads(es_route.calls[0].request.content)
    assert body["event_type"] == "ALARM_ACTIVE"
    assert body["source"] == "vlan-pollers"
    assert body["payload"]["alarm_id"] == "ALM-001"
    assert body["payload"]["triggered_by"] == "automatic"


@pytest.mark.unit
@respx.mock
async def test_emit_alarm_cleared_on_state_transition() -> None:
    """Alarm transitioning active → inactive emits ALARM_CLEARED."""
    es_route = respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(201))
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    poller._tracker.get_journey_id("OBB-1", "T1")
    poller._prev_alarms["ALM-001"] = True  # was active

    varbinds = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-001"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Door clear"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "3"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "0"),
        ("1.3.6.1.4.1.1234.1.1.1.0", "T1"),  # exact scalar OID
    ]
    await poller._process(varbinds)

    assert es_route.called
    import json
    body = json.loads(es_route.calls[0].request.content)
    assert body["event_type"] == "ALARM_CLEARED"


@pytest.mark.unit
@respx.mock
async def test_no_event_emitted_when_alarm_state_unchanged() -> None:
    """No event emitted when alarm active state has not changed."""
    es_route = respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(201))
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    poller._tracker.get_journey_id("OBB-1", "T1")
    poller._prev_alarms["ALM-001"] = True  # already active

    varbinds = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-001"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Door obstruction"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "1"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "1"),   # still active
        ("1.3.6.1.4.1.1234.1.1.1.0", "T1"),  # exact scalar OID
    ]
    await poller._process(varbinds)

    assert not es_route.called  # state unchanged — no emit


@pytest.mark.unit
@respx.mock
async def test_409_duplicate_treated_as_success() -> None:
    """event-store 409 is idempotent — must not raise."""
    respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(409))
    # Should complete without raising
    await _post_event_with_retry(EVENT_STORE, {"event_type": "ALARM_ACTIVE"})


@pytest.mark.unit
@respx.mock
async def test_door_release_signal_posts_to_rtsp() -> None:
    """signal_door_release triggers POST to rtsp-ingest/context."""
    rtsp_route = respx.post(f"{RTSP}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    await poller.signal_door_release("CAR-2", "DOOR-B")

    assert rtsp_route.called
    import json
    body = json.loads(rtsp_route.calls[0].request.content)
    assert body["event"] == "door_release"
    assert body["car_id"] == "CAR-2"
    assert body["door_id"] == "DOOR-B"


@pytest.mark.unit
@respx.mock
async def test_alarm_row_drop_emits_cleared() -> None:
    """Active alarm absent from SNMP table (row-drop) → ALARM_CLEARED emitted (F2/F3)."""
    es_route = respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(201))
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    poller._tracker.get_journey_id("OBB-1", "T1")
    poller._prev_alarms["ALM-GONE"] = True  # was active, now missing from table

    # Varbinds contain a different alarm only — ALM-GONE has vanished
    varbinds = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-OTHER"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Other alarm"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "3"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "1"),
        ("1.3.6.1.4.1.1234.1.1.1.0", "T1"),  # exact scalar OID
    ]
    await poller._process(varbinds)

    import json
    events = [json.loads(c.request.content) for c in es_route.calls]
    cleared_events = [e for e in events if e["event_type"] == "ALARM_CLEARED"]
    assert any(e["payload"]["alarm_id"] == "ALM-GONE" for e in cleared_events), (
        "Must emit ALARM_CLEARED for alarm that vanished from SNMP table"
    )
    # ALM-GONE must be evicted from prev_alarms after successful clear
    assert "ALM-GONE" not in poller._prev_alarms


@pytest.mark.unit
@respx.mock
async def test_failed_emit_keeps_transition_for_retry() -> None:
    """If event-store POST fails, _prev_alarms is not updated — transition retried next poll."""
    respx.post(f"{EVENT_STORE}/api/v1/events").mock(return_value=httpx.Response(500))
    respx.post(f"{FUSION}/context").mock(return_value=httpx.Response(200))
    respx.post(f"{INFERENCE}/context").mock(return_value=httpx.Response(200))

    poller = _make_poller()
    poller._tracker.get_journey_id("OBB-1", "T1")
    # No prior state — first encounter, active=True, emit expected to fail
    varbinds = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-FAIL"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Fail alarm"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "1"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "1"),
        ("1.3.6.1.4.1.1234.1.1.1.0", "T1"),  # exact scalar OID
    ]
    await poller._process(varbinds)

    # prev_alarms must NOT have been updated — so next poll retries the emit
    assert "ALM-FAIL" not in poller._prev_alarms


@pytest.mark.unit
async def test_process_skips_when_no_trip_number() -> None:
    """_process must do nothing if no trip number in varbinds."""
    call_count = 0

    async def fake_update(*args: object, **kwargs: object) -> None:
        nonlocal call_count
        call_count += 1

    poller = _make_poller()
    poller._ctx.update_journey = fake_update  # type: ignore[method-assign]

    # Varbinds with no trip OID
    await poller._process([("9.9.9.9", "irrelevant")])
    assert call_count == 0
