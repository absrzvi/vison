"""ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation — AC8 (R4).

Inference posts ACCESSIBILITY_DETECTED directly to event-store and may also
notify fusion via the optional ``/candidates/accessibility_detected`` endpoint
so we can update the TTL-bounded recent-track log. When vlan-pollers reports
``ramp_deployed=true`` in a context push, fusion emits a RAMP_DEPLOYED event
attributing the most recent accessibility track for that (car_id, door_id).

Code-review patches (2026-05-20):
  * When ``door_id == "unknown"`` the recent-track lookup is short-circuited to
    ``triggered_by_track_id="unknown"`` — otherwise a stray AccessibilityDetected
    payload with ``near_door_id="unknown"`` could be falsely correlated.
"""
from __future__ import annotations

import structlog
from oebb_shared.events import AccessibilityDetectedPayload, EventType, RampDeployedPayload

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment

log = structlog.get_logger(__name__)


async def note_accessibility_candidate(
    payload: AccessibilityDetectedPayload,
    ctx: ContextState,
) -> None:
    """Record the track for later ramp correlation. We key by near_door_id so
    the ramp lookup can match the door_id reported by vlan-pollers; we also
    store under the zone string as a fallback for cases where the camera
    reports a zone but no near_door_id mapping was established yet.
    """
    ctx.note_accessibility(payload.car_id, payload.near_door_id, payload.track_id)
    if payload.zone:
        ctx.note_accessibility(payload.car_id, payload.zone, payload.track_id)


async def handle_ramp_deployed(
    *,
    car_id: str,
    door_id: str,
    station_id: str,
    ctx: ContextState,
    enricher: Enrichment,
    settings: Settings,
) -> None:
    """Emit RAMP_DEPLOYED with triggered_by_track_id set from the recent
    accessibility log (within TTL) or 'unknown' when no match is in window.

    When ``door_id == "unknown"`` we do NOT look up the recent log — that would
    accidentally match a track recorded under a literal ``near_door_id="unknown"``
    string, falsifying R4 attribution. Caller already failed to resolve the
    door from context; pass that uncertainty through to the event.
    """
    if door_id == "unknown":
        log.warning(
            "accessibility.ramp_with_unknown_door",
            car_id=car_id,
            station_id=station_id,
        )
        track_id: str | None = None
    else:
        track_id = ctx.find_recent_accessibility(
            car_id, door_id, settings.accessibility_recent_window_s
        )
    triggered_by = track_id if track_id else "unknown"
    ramp_payload = RampDeployedPayload(
        car_id=car_id,
        door_id=door_id,
        triggered_by_track_id=triggered_by,
        deployed_by="auto",
        station_id=station_id,
    )
    await enricher.emit_envelope(
        event_type_name=EventType.RAMP_DEPLOYED.value,
        payload=ramp_payload.model_dump(),
        severity="info",
    )
