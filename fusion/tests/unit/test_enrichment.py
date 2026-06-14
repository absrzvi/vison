"""Enrichment envelope construction + station_approach escalation — AC7, AC11."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx
from oebb_shared.events import EventEnvelope, EventType

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment, _seconds_to_departure, _severity_for


def _make_settings() -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        schema_version=1,
    )


def _make_ctx(**overrides: object) -> ContextState:
    ctx = ContextState(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
    )
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


@pytest.mark.unit
def test_severity_door_obstruction_at_speed_is_critical() -> None:
    assert _severity_for("door_obstruction", speed_kmh=15.0) == "critical"


@pytest.mark.unit
def test_severity_door_obstruction_at_zero_speed_is_warning() -> None:
    assert _severity_for("door_obstruction", speed_kmh=0.0) == "warning"


@pytest.mark.unit
def test_severity_door_obstruction_unknown_speed_is_critical_fail_closed() -> None:
    """Fail-closed: stale telemetry must not downgrade a real door fault.
    Code-review decision 3 (2026-05-20)."""
    assert _severity_for("door_obstruction", speed_kmh=None) == "critical"
    assert _severity_for("door_fault", speed_kmh=None) == "critical"


@pytest.mark.unit
def test_severity_non_door_alert_defaults_to_warning() -> None:
    assert _severity_for("slip_fall", speed_kmh=80.0) == "warning"


@pytest.mark.unit
@respx.mock
async def test_emit_alert_posts_envelope_with_source_fusion() -> None:
    settings = _make_settings()
    ctx = _make_ctx()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    assert route.called
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.source == "fusion"
    assert env.event_type == EventType.ALERT_RAISED
    assert env.severity == "warning"
    assert env.payload["alert_code"] == "slip_fall"


@pytest.mark.unit
@respx.mock
async def test_station_approach_escalates_priority() -> None:
    settings = _make_settings()
    ctx = _make_ctx(station_approach=True)
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.payload["priority"] == "escalated"


@pytest.mark.unit
@respx.mock
async def test_no_station_approach_keeps_priority_normal() -> None:
    settings = _make_settings()
    ctx = _make_ctx(station_approach=False)
    respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    # AlertRaisedPayload _drop_none keeps priority because it's set to 'normal',
    # not None. Envelope payload must reflect that.
    body = respx.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.payload["priority"] == "normal"


@pytest.mark.unit
@respx.mock
async def test_emit_envelope_for_journey_ended_with_empty_payload() -> None:
    settings = _make_settings()
    ctx = _make_ctx()
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_envelope(
            event_type_name="JOURNEY_ENDED",
            payload={},
            severity="info",
        )
    assert route.called
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.event_type == EventType.JOURNEY_ENDED
    assert env.source == "fusion"


@pytest.mark.unit
@respx.mock
async def test_emit_skipped_when_journey_id_is_none() -> None:
    """When ContextState has no journey_id (vlan-pollers hasn't pushed yet),
    fusion MUST NOT emit a synthetic placeholder — log WARN and skip.
    Code-review patch (2026-05-20)."""
    settings = _make_settings()
    ctx = _make_ctx()
    ctx.journey_id = None  # explicit: no journey known
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201)
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    assert not route.called  # NO emit with empty journey_id


# ---------------------------------------------------------------------------
# E10-S4 — seconds_to_departure derivation (AC2, AC6, D1)
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 20, 8, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_seconds_to_departure_healthy_pre_departure_at_station() -> None:
    """station_approach + a parseable future departure → positive whole seconds."""
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-20T08:01:30Z",  # 90s after _NOW
            station_approach=True,
            speed_kmh=0.0,
            now=_NOW,
        )
        == 90
    )


@pytest.mark.unit
def test_seconds_to_departure_standstill_with_future_departure() -> None:
    """Not flagged station_approach but stopped (speed 0) with a future sched → derived."""
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-20T08:02:00Z",  # 120s
            station_approach=False,
            speed_kmh=0.0,
            now=_NOW,
        )
        == 120
    )


@pytest.mark.unit
def test_seconds_to_departure_past_departure_clamps_to_zero() -> None:
    """A departure already in the past clamps to 0 (never negative)."""
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-20T07:59:00Z",  # 60s before _NOW
            station_approach=True,
            speed_kmh=0.0,
            now=_NOW,
        )
        == 0
    )


@pytest.mark.unit
def test_seconds_to_departure_crosses_midnight() -> None:
    """Full-instant parse: 23:58 now, 00:05 next-day sched → 420s, not negative.
    Guards against a time-of-day-only subtraction (ADR-2 midnight trap precedent)."""
    now = datetime(2026, 5, 20, 23, 58, 0, tzinfo=UTC)
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-21T00:05:00Z",  # 7 min later across date boundary
            station_approach=True,
            speed_kmh=0.0,
            now=now,
        )
        == 420
    )


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["", "not-a-timestamp", "2026-05-20T08:01:30"])  # last: no Z
def test_seconds_to_departure_unparseable_feed_returns_none(bad: str) -> None:
    """Empty / malformed / non-UTC departure → None (feed-degraded path, no raise)."""
    assert (
        _seconds_to_departure(
            scheduled_departure=bad,
            station_approach=True,
            speed_kmh=0.0,
            now=_NOW,
        )
        is None
    )


@pytest.mark.unit
def test_seconds_to_departure_standstill_past_departure_returns_none() -> None:
    """E10-S4 review (low): the speed-branch (stopped, NOT station_approach) requires a
    FUTURE departure per D1/AC2. A train overdue at a platform is not pre-departure →
    None, not a misleading 0. (The station_approach branch still clamps past → 0, AC6b.)"""
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-20T07:59:00Z",  # 60s before _NOW
            station_approach=False,
            speed_kmh=0.0,
            now=_NOW,
        )
        is None
    )


@pytest.mark.unit
def test_seconds_to_departure_in_transit_returns_none() -> None:
    """In-transit (moving, not at a station) → None even with a valid future sched."""
    assert (
        _seconds_to_departure(
            scheduled_departure="2026-05-20T08:01:30Z",
            station_approach=False,
            speed_kmh=80.0,
            now=_NOW,
        )
        is None
    )


# --- T1.5: ContextPushModel / ContextState plumbing ---


@pytest.mark.unit
def test_context_push_carries_scheduled_departure() -> None:
    """The real full-delta WIRE BODY (raw dict, as vlan-pollers POSTs) validates
    through ContextPushModel and scheduled_departure lands from the NESTED `pis`
    object (E6-S4 canonical wire) — not a flat key, not synthetic kwargs."""
    from fusion.models import ContextPushModel

    ctx = ContextState()
    wire_body = {
        "journey_id": "J1",
        "pis": {"scheduled_departure": "2026-05-20T08:01:30Z", "platform": "2"},
    }
    ctx.update_from_push(ContextPushModel.model_validate(wire_body))
    assert ctx.scheduled_departure == "2026-05-20T08:01:30Z"


@pytest.mark.unit
def test_context_push_absent_scheduled_departure_keeps_prior() -> None:
    """Absent field keeps prior state (present-replaces / absent-keeps) WITHIN a journey."""
    from fusion.models import ContextPushModel

    ctx = ContextState(journey_id="J1", scheduled_departure="2026-05-20T08:01:30Z")
    # same journey, no scheduled_departure key → keep prior
    ctx.update_from_push(ContextPushModel(journey_id="J1", speed_kmh=12.0))
    assert ctx.scheduled_departure == "2026-05-20T08:01:30Z"


@pytest.mark.unit
def test_journey_change_clears_stale_departure_real_wire() -> None:
    """E10-S4 invariant, re-pinned by E6-S4 review R1/R2 to the REAL wire.
    On a journey change the producer resets _state.pis (E6-S4 vlan-pollers fix), so the
    J1→J2 full-delta push carries an EMPTY nested pis. fusion's truthiness gate must
    then CLEAR the prior journey's departure (not store ""), so J2 never inherits J1's.
    The old synthetic pis=None body could never occur on the real wire and masked this."""
    from fusion.models import ContextPushModel

    ctx = ContextState(journey_id="J1", scheduled_departure="2026-05-20T08:01:30Z")
    wire = {"journey_id": "J2", "pis": {"scheduled_departure": ""}}  # real journey-change wire
    ctx.update_from_push(ContextPushModel.model_validate(wire))
    assert ctx.scheduled_departure is None


@pytest.mark.unit
def test_empty_pis_departure_keeps_prior_within_journey() -> None:
    """E6-S4 review R3: within the SAME journey, an empty nested departure (PisState
    default on an unrelated delta push) must NOT clobber a known departure — the
    truthiness gate treats "" as "no value in this push" (absent-keeps)."""
    from fusion.models import ContextPushModel

    ctx = ContextState(journey_id="J1", scheduled_departure="2026-05-20T08:01:30Z")
    wire = {"journey_id": "J1", "pis": {"scheduled_departure": ""}, "speed_kmh": 30.0}
    ctx.update_from_push(ContextPushModel.model_validate(wire))
    assert ctx.scheduled_departure == "2026-05-20T08:01:30Z"


# --- AC2: emit_alert stamps the derived value end-to-end ---


@pytest.mark.unit
@respx.mock
async def test_emit_alert_stamps_seconds_to_departure_when_pre_departure() -> None:
    settings = _make_settings()
    # sched == now → 0 seconds; the field is present (not dropped) because it's an int.
    sched = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ctx = _make_ctx(station_approach=True, speed_kmh=0.0, scheduled_departure=sched)
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="door_obstruction",
            car_id="car-6",
            description="door obstruction",
            confidence_basis="sensor",
        )
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    assert env.payload["seconds_to_departure"] == 0


@pytest.mark.unit
@respx.mock
async def test_emit_alert_logs_degraded_when_pre_departure_but_unparseable() -> None:
    """AC2: a pre-departure alert whose PIS departure is unparseable must emit a
    structured 'seconds_to_departure_unavailable' log (the None path is observable)."""
    import structlog.testing

    settings = _make_settings()
    ctx = _make_ctx(station_approach=True, speed_kmh=0.0, scheduled_departure="garbage")
    respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        with structlog.testing.capture_logs() as logs:
            await enricher.emit_alert(
                alert_code="door_obstruction",
                car_id="car-6",
                description="door obstruction",
                confidence_basis="sensor",
            )
    events = [log["event"] for log in logs]
    assert "enrichment.seconds_to_departure_unavailable" in events


@pytest.mark.unit
@respx.mock
async def test_emit_alert_no_degraded_log_when_in_transit() -> None:
    """In-transit (moving) → seconds None is EXPECTED, not degraded — no warning."""
    import structlog.testing

    settings = _make_settings()
    ctx = _make_ctx(station_approach=False, speed_kmh=80.0, scheduled_departure="garbage")
    respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        with structlog.testing.capture_logs() as logs:
            await enricher.emit_alert(
                alert_code="slip_fall",
                car_id="car-1",
                description="fall",
                confidence_basis="sensor",
            )
    events = [log["event"] for log in logs]
    assert "enrichment.seconds_to_departure_unavailable" not in events


@pytest.mark.unit
@respx.mock
async def test_emit_alert_omits_seconds_to_departure_in_transit() -> None:
    settings = _make_settings()
    ctx = _make_ctx(
        station_approach=False,
        speed_kmh=80.0,
        scheduled_departure="2026-05-20T08:01:30Z",
    )
    route = respx.post("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(201, json={"data": {"stored": True}})
    )
    async with httpx.AsyncClient() as client:
        enricher = Enrichment(client, settings, ctx)
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id="car-1",
            description="fall detected",
            confidence_basis="sensor",
        )
    body = route.calls.last.request.content.decode()
    env = EventEnvelope.model_validate_json(body)
    # None → dropped from serialization (byte-compat with consumers)
    assert "seconds_to_departure" not in env.payload
