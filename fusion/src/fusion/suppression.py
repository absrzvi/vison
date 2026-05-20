"""Suppression state machine — AC4.

Priority: DEPOT > MAINTENANCE > GPS_INVALID > NORMAL. When non-NORMAL, all
candidates are dropped before reaching enrichment. DEPOT transitions emit one
JOURNEY_ENDED envelope per journey (idempotent within a single journey_id).
"""
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fusion.context_state import ContextState
    from fusion.enrichment import Enrichment

log = structlog.get_logger(__name__)


class SuppressionState(StrEnum):
    NORMAL = "NORMAL"
    GPS_INVALID = "GPS_INVALID"
    MAINTENANCE = "MAINTENANCE"
    DEPOT = "DEPOT"


def evaluate(ctx: ContextState) -> SuppressionState:
    """Return the dominant suppression state by priority."""
    if ctx.depot_mode:
        return SuppressionState.DEPOT
    if ctx.maintenance_mode:
        return SuppressionState.MAINTENANCE
    if not ctx.gps_valid:
        return SuppressionState.GPS_INVALID
    return SuppressionState.NORMAL


class SuppressionGate:
    """Holds previous state; logs transitions; emits one-shot JOURNEY_ENDED on DEPOT."""

    def __init__(self, ctx: ContextState, enricher: Enrichment) -> None:
        self._ctx = ctx
        self._enricher = enricher
        self._last_state: SuppressionState = SuppressionState.NORMAL
        # Track journey_ids for which JOURNEY_ENDED has already been emitted.
        self._depot_journey_ended_emitted_for: set[str] = set()

    @property
    def state(self) -> SuppressionState:
        return evaluate(self._ctx)

    async def on_context_changed(self) -> None:
        """Call after every ContextState.update_from_push so state transitions
        are observed and one-shot DEPOT actions fire promptly. Safe to call
        even when the state hasn't actually changed.
        """
        current = evaluate(self._ctx)
        if current != self._last_state:
            log.info(
                "suppression.transition",
                from_state=self._last_state.value,
                to_state=current.value,
                journey_id=self._ctx.journey_id,
            )
        if current == SuppressionState.DEPOT and self._last_state != SuppressionState.DEPOT:
            journey_id = self._ctx.journey_id or ""
            if journey_id and journey_id not in self._depot_journey_ended_emitted_for:
                self._depot_journey_ended_emitted_for.add(journey_id)
                # PoC: JourneyEndedPayload requires arrival timestamps that fusion
                # does not own. Emit with empty payload — the envelope validator
                # allows empty payloads. A later story will fill in real data.
                await self._enricher.emit_envelope(
                    event_type_name="JOURNEY_ENDED",
                    payload={},
                    severity="info",
                )
        self._last_state = current

    def should_emit(self) -> bool:
        """Return True when alert candidates should be allowed through."""
        current = evaluate(self._ctx)
        if current != SuppressionState.NORMAL:
            log.info(
                "suppression.active",
                reason=current.value,
                journey_id=self._ctx.journey_id,
            )
            return False
        return True
