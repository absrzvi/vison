"""Door obstruction candidate handling — AC5, AC6 (FR7, FR9).

Inference posts DOOR_OBSTRUCTION candidates with door_state='unknown'. Fusion
looks up the authoritative ZFR-derived state from ContextState. If the door is
'closing' or 'closed' the alert is emitted; otherwise the candidate is dropped.
Speed-correlated severity (FR9) is decided in enrichment._severity_for.

Code-review patch (2026-05-20 decision 1, AC9 wiring):
  * ``payload.car_id`` is normalised through ``ctx.resolve_car_id`` so a
    numeric or short-form coach identifier from an upstream system is resolved
    against the ``consist`` mapping before downstream lookups.
"""
from __future__ import annotations

import structlog
from oebb_shared.events import DoorObstructionPayload

from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.suppression import SuppressionGate

log = structlog.get_logger(__name__)


async def handle(
    payload: DoorObstructionPayload,
    ctx: ContextState,
    gate: SuppressionGate,
    enricher: Enrichment,
) -> None:
    """Cross-reference camera obstruction with ZFR door state. Emit only when
    the door is commanded shut (closing/closed) and suppression is NORMAL.
    """
    if not gate.should_emit():
        log.debug(
            "door_obstruction.suppressed",
            car_id=payload.car_id,
            door_id=payload.door_id,
        )
        return

    # R3: normalise car_id through consist mapping (passthrough when absent).
    car_id = ctx.resolve_car_id(payload.car_id)

    door_state = ctx.door_state_for(car_id, payload.door_id)
    if door_state not in {"closing", "closed"}:
        log.debug(
            "door_obstruction.candidate_discarded",
            car_id=car_id,
            door_id=payload.door_id,
            door_state=door_state,
            reason="zfr_door_not_shut",
        )
        return

    description = (
        f"Door obstruction on {payload.door_id} ({payload.obstruction_type}) "
        f"with door state {door_state}"
    )
    await enricher.emit_alert(
        alert_code="door_obstruction",
        car_id=car_id,
        description=description,
    )
