"""Coach Comfort Index — Story 4-10 (ADR-18).

Composite per-coach comfort signal computed from camera-derived occupancy.
Emits a ``COACH_COMFORT_INDEX`` event when:

  * (AC1) ``|occupancy_pct - _last_emitted_pct[car_id]| > pct_threshold`` — i.e.
    a significant change in observed occupancy.
  * (AC2) ``ContextState.station_approach`` transitions ``False → True`` — emit
    one event per coach previously observed in this journey, regardless of
    delta. Caller drives this via ``on_station_approach_edge()``.

Suppression / cold-start invariants:

  * (AC4) The first OCCUPANCY_UPDATE for a coach seeds ``_last_emitted_pct``
    and ``_observed_coaches`` but does NOT emit (no baseline to compare).
  * (AC5) Under suppression, the handler layer drops the emit AND does not
    advance ``_last_emitted_pct`` — the next delta check after the gate
    re-opens uses the last truly-emitted value as baseline.
  * (AC6) Journey-id absence is handled in ``Enrichment._build_envelope`` —
    not this module's concern.

Decisions folded in (4-10 D1–D5):
  * D1 — Use shipped ``CoachComfortIndexPayload`` (not epic-spec divergent shape).
  * D2 — ``temperature_c`` and ``noise_db`` are PoC-deferred → emit ``None``.
  * D3 — No reservations math; ``comfort_score = 1.0 - occupancy_pct`` clamped.
  * D4 — Ingest reuses Story 4-9's ``/candidates/occupancy_update`` endpoint.
  * D5 — Consumer ordering: ``ledger.check_drift`` runs first; this module
    runs after, both flowing through ``Enrichment.emit_envelope`` independently.
"""
from __future__ import annotations

import structlog
from oebb_shared.events.payloads import (
    CoachComfortIndexPayload,
    OccupancyUpdatePayload,
)

from fusion.config import Settings

log = structlog.get_logger(__name__)


class ComfortIndexState:
    """Per-coach comfort-index state owned by the fusion FastAPI lifespan.

    Two parallel structures:

    * ``_last_emitted_pct[car_id]`` — the ``occupancy_pct`` from the most recent
      OCCUPANCY_UPDATE that satisfied AC4's seed OR drove an AC1 delta emit.
      Used as the comparison baseline for the next delta check.

    * ``_observed_coaches`` — set of all coach ids for which at least one
      OCCUPANCY_UPDATE has been seen this journey. Needed for AC2: on the
      station_approach edge, emit for EVERY observed coach even those whose
      delta never crossed the threshold.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pct_threshold = settings.comfort_index_pct_threshold
        self._last_emitted_pct: dict[str, float] = {}
        self._observed_coaches: set[str] = set()

    # ------------------------------------------------------------------
    # Public API — called by health.py candidate / context handlers
    # ------------------------------------------------------------------

    def on_occupancy_update(
        self, payload: OccupancyUpdatePayload
    ) -> CoachComfortIndexPayload | None:
        """Return a payload to emit, or ``None`` for cold-start / sub-threshold.

        State is NOT mutated until ``confirm_emit`` is called with the returned
        payload. This two-phase design upholds the AC5 invariant: if the
        downstream emit fails, the baseline never advances and the next delta
        check runs against the last truly-published value.

          * AC4 cold-start: seeds ``_last_emitted_pct`` + ``_observed_coaches``
            immediately (no emit), returns ``None``.
          * AC1 delta-crossed: returns a payload WITHOUT advancing the baseline.
            The caller must call ``confirm_emit(car_id, occupancy_pct)`` after a
            successful event-store POST.
        """
        car_id = payload.car_id
        self._observed_coaches.add(car_id)

        # P4 — clamp on store so _last_emitted_pct never holds an out-of-range
        # value that would produce spurious large deltas on subsequent updates.
        pct = max(0.0, min(1.0, payload.occupancy_pct))

        prior = self._last_emitted_pct.get(car_id)
        if prior is None:
            # AC4 — first OCCUPANCY for this coach seeds the baseline.
            self._last_emitted_pct[car_id] = pct
            return None

        if abs(pct - prior) <= self._pct_threshold:
            # Sub-threshold — no emit.
            return None

        # AC1 — delta crossed; return payload but do NOT advance baseline yet.
        return self._compute_payload(car_id, pct)

    def confirm_emit(self, car_id: str, occupancy_pct: float) -> None:
        """Advance ``_last_emitted_pct`` after a successful AC1 emit.

        Called by the handler only when event-store POST succeeds. Keeps the
        baseline in sync with what was actually published (AC5 invariant).
        """
        self._last_emitted_pct[car_id] = max(0.0, min(1.0, occupancy_pct))

    def observed_coaches(self) -> list[str]:
        """Return a sorted snapshot of all coaches seen this journey."""
        return sorted(self._observed_coaches)

    def reset(self) -> None:
        """Clear all per-journey state on journey_id transition.

        Called by the /context handler when journey_id changes so that stale
        coach baselines from a prior journey do not leak into AC2 edge emits
        on the new journey.
        """
        self._last_emitted_pct.clear()
        self._observed_coaches.clear()

    def on_station_approach_edge(self) -> list[CoachComfortIndexPayload]:
        """AC2 — return one payload per observed coach on a station_approach edge.

        Does NOT mutate ``_last_emitted_pct``. Station-edge emits are an
        independent trigger from the delta-driven path; mixing them would
        cause the next legitimate delta-emit to compute against a stale
        baseline.

        Iterates a snapshot of ``_observed_coaches`` so a concurrent
        ``on_occupancy_update`` adding a new coach mid-iteration cannot corrupt
        the loop (single event-loop, but await points inside the loop mean
        coroutines can interleave).
        """
        out: list[CoachComfortIndexPayload] = []
        for car_id in sorted(list(self._observed_coaches)):
            pct = self._last_emitted_pct.get(car_id)
            if pct is None:
                # Defensive: a coach in _observed_coaches should always also
                # be in _last_emitted_pct (both populated together by AC4
                # seeding). Skip with a debug log rather than crash.
                log.debug(
                    "comfort_index.station_edge_missing_pct",
                    reason="missing_last_pct",
                    car_id=car_id,
                )
                continue
            out.append(self._compute_payload(car_id, pct))
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_payload(car_id: str, occupancy_pct: float) -> CoachComfortIndexPayload:
        """AC3 — clamped comfort_score; environmental sensors deferred (D2)."""
        comfort_score = max(0.0, min(1.0, 1.0 - occupancy_pct))
        return CoachComfortIndexPayload(
            car_id=car_id,
            comfort_score=comfort_score,
            occupancy_pct=max(0.0, min(1.0, occupancy_pct)),
            temperature_c=None,
            noise_db=None,
        )
