"""Occupancy passthrough — AC10 (ADR-15).

Camera count is authoritative. APC presence triggers a WARNING log when drift
exceeds calibration_drift_threshold; no event is emitted in this story.
No weight_camera / weight_apc parameters exist.
"""
from __future__ import annotations

import structlog
from oebb_shared.events import EventType, OccupancyUpdatePayload

from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment

log = structlog.get_logger(__name__)


async def process_occupancy_update(
    payload: OccupancyUpdatePayload,
    ctx: ContextState,
    enricher: Enrichment,
    settings: Settings,
    apc_count: int | None = None,
) -> None:
    """Forward the camera-derived occupancy verbatim. Optionally compare
    against an APC reading (passed from a future caller) and log drift.
    """
    if apc_count is not None and payload.occupancy_count > 0:
        delta = abs(payload.occupancy_count - apc_count)
        drift = delta / payload.occupancy_count
        if drift > settings.calibration_drift_threshold:
            log.warning(
                "occupancy.calibration_drift",
                car_id=payload.car_id,
                camera_count=payload.occupancy_count,
                apc_count=apc_count,
                drift=drift,
                threshold=settings.calibration_drift_threshold,
            )

    envelope_payload = payload.model_dump()
    await enricher.emit_envelope(
        event_type_name=EventType.OCCUPANCY_UPDATE.value,
        payload=envelope_payload,
        severity="info",
    )
