"""FastAPI app — health endpoints + inbound candidate/context POSTs.

Routes:
  GET  /health/live                       — process liveness
  GET  /health/ready                      — event-store reachable (cached 1s)
  POST /context                           — vlan-pollers state push
  POST /candidates/door_obstruction       — inference candidate (FR7)
  POST /candidates/alert_raised           — inference candidate (slip_fall)
  POST /candidates/accessibility_detected — optional: update accessibility log

Code-review patches (2026-05-20):
  * Ramp emit is gated by ``SuppressionGate.should_emit()``.
  * Ramp emit is edge-triggered via ``ContextState.observe_ramp_signal`` so a
    stuck ``ramp_deployed=True`` signal across pushes only emits once.
  * Candidate handlers wrap event-store errors so inference receives 202 even
    if the downstream is unreachable (fail-safe: alert is lost but inference
    is not blocked; retry policy on the shared retry decorator catches
    transient outages).
  * Slip-fall ALERT_RAISED includes track_id + camera_id in the description.
  * Car_id resolution uses ``ContextState.car_id_for_door`` (deterministic +
    consist-aware) rather than a local first-match scan.
"""
from __future__ import annotations

import time

import httpx
import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from oebb_shared.events import (
    AccessibilityDetectedPayload,
    DoorObstructionPayload,
    WagonEntryPayload,
    WagonExitPayload,
)
from oebb_shared.events.payloads import OccupancyUpdatePayload

from fusion import accessibility as accessibility_mod
from fusion import door_obstruction as door_obstruction_mod
from fusion.comfort_index import ComfortIndexState
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
from fusion.ledger import CoachLedger
from fusion.models import ContextPushModel, SlipFallCandidate
from fusion.suppression import SuppressionGate

log = structlog.get_logger(__name__)


class _ReadinessCache:
    def __init__(self, ttl_s: float = 1.0) -> None:
        self._ttl = ttl_s
        self._last_check: float = 0.0
        self._last_result: bool = False

    async def is_ready(self, client: httpx.AsyncClient, event_store_url: str) -> bool:
        now = time.monotonic()
        if now - self._last_check < self._ttl:
            return self._last_result
        self._last_check = now
        try:
            resp = await client.get(f"{event_store_url}/health/live", timeout=2.0)
            self._last_result = resp.status_code == 200
        except httpx.HTTPError:
            self._last_result = False
        return self._last_result


def build_app(
    *,
    settings: Settings,
    ctx: ContextState,
    gate: SuppressionGate,
    enricher: Enrichment,
    client: httpx.AsyncClient,
    ledger: CoachLedger,
    comfort: ComfortIndexState,
) -> FastAPI:
    app = FastAPI(title="fusion")
    readiness = _ReadinessCache()

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> JSONResponse:
        ready = await readiness.is_ready(client, settings.event_store_url)
        if ready:
            return JSONResponse({"status": "ready"}, status_code=200)
        return JSONResponse(
            {"status": "not_ready", "reason": "event_store_unreachable"},
            status_code=503,
        )

    @app.post("/context")
    async def context_push(payload: ContextPushModel) -> dict[str, str]:
        prev_journey_id = ctx.journey_id
        ctx.update_from_push(payload)
        # P2 — reset comfort state when journey_id changes so prior-journey
        # coach baselines do not appear in AC2 edge emits on the new journey.
        if ctx.journey_id != prev_journey_id:
            comfort.reset()
        await gate.on_context_changed()
        # R4: edge-trigger ramp emit — only when ramp_deployed transitions
        # from false→true. ``ramp_deployed=None`` (absent) doesn't touch the
        # state and never triggers.
        if payload.ramp_deployed is not None:
            edge = ctx.observe_ramp_signal(payload.ramp_deployed)
            if edge:
                # Suppression check: depot/maintenance/gps_invalid suppress all
                # outbound alerts including RAMP_DEPLOYED.
                if not gate.should_emit():
                    log.debug(
                        "context.ramp_suppressed",
                        ramp_door_id=payload.ramp_door_id,
                    )
                else:
                    door_id = payload.ramp_door_id or "unknown"
                    station_id = payload.ramp_station_id or "unknown"
                    car_id = ctx.car_id_for_door(door_id) or "unknown"
                    try:
                        await accessibility_mod.handle_ramp_deployed(
                            car_id=car_id,
                            door_id=door_id,
                            station_id=station_id,
                            ctx=ctx,
                            enricher=enricher,
                            settings=settings,
                        )
                    except httpx.HTTPError as exc:
                        log.warning(
                            "context.ramp_emit_failed",
                            door_id=door_id,
                            station_id=station_id,
                            error=str(exc),
                        )

        # E4-S10 AC2: station_approach false→true edge — emit one
        # COACH_COMFORT_INDEX per observed coach. Suppression-gated;
        # downstream errors logged but do not break the /context handler.
        #
        # D3 fix: compute the edge WITHOUT committing _prev_station_approach
        # yet. Only advance the prior after the gate clears so the edge is
        # preserved if suppression is active — it will re-fire on the next
        # /context push when the gate re-opens.
        station_edge = ctx.peek_station_approach_edge()
        if station_edge:
            if not gate.should_emit():
                for car_id in comfort.observed_coaches():
                    log.debug(
                        "context.comfort_index_suppressed",
                        reason="comfort_index_suppressed",
                        trigger="station_approach_edge",
                        car_id=car_id,
                    )
            else:
                ctx.consume_station_approach_edge()
                for comfort_payload in comfort.on_station_approach_edge():
                    try:
                        await enricher.emit_envelope(
                            event_type_name="COACH_COMFORT_INDEX",
                            payload=comfort_payload.model_dump(),
                            severity="info",
                        )
                    except httpx.HTTPError as exc:
                        log.warning(
                            "context.comfort_index_emit_failed",
                            car_id=comfort_payload.car_id,
                            error=str(exc),
                        )

        return {"status": "accepted"}

    @app.post("/candidates/door_obstruction", status_code=202)
    async def candidate_door_obstruction(
        payload: DoorObstructionPayload,
    ) -> dict[str, bool]:
        try:
            await door_obstruction_mod.handle(payload, ctx, gate, enricher)
        except httpx.HTTPError as exc:
            log.warning(
                "candidate.door_obstruction.emit_failed",
                car_id=payload.car_id,
                door_id=payload.door_id,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — Pattern 3: handler must never raise
            # A malformed candidate (e.g. model_versions collapsing below the
            # fused-basis >=2 floor) must not 500 this fire-and-forget endpoint.
            log.warning(
                "candidate.door_obstruction.emit_failed",
                car_id=payload.car_id,
                door_id=payload.door_id,
                error=str(exc),
            )
        return {"received": True}

    @app.post("/candidates/alert_raised", status_code=202)
    async def candidate_alert_raised(payload: SlipFallCandidate) -> dict[str, bool]:
        if not gate.should_emit():
            log.debug("slip_fall.suppressed", car_id=payload.car_id)
            return {"received": True}
        car_id = ctx.resolve_car_id(payload.car_id)
        description = (
            f"Suspected passenger fall detected by camera "
            f"({payload.camera_id}, track {payload.track_id})"
        )
        # E10-S1 AC9: model-basis confidence from the candidate body. Missing
        # confidence fails safe to 0.0 (lowest trust) rather than dropping a
        # safety alert; missing provenance falls back to "unknown".
        if payload.confidence is None:
            log.warning("slip_fall.missing_confidence", car_id=car_id)
        try:
            await enricher.emit_alert(
                alert_code="slip_fall",
                car_id=car_id,
                description=description,
                confidence_basis="model",
                confidence_score=payload.confidence if payload.confidence is not None else 0.0,
                model_versions=payload.model_versions or {"detector_arch": "unknown"},
            )
        except httpx.HTTPError as exc:
            log.warning(
                "candidate.alert_raised.emit_failed",
                car_id=car_id,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 — Pattern 3: handler must never raise
            log.warning(
                "candidate.alert_raised.emit_failed",
                car_id=car_id,
                error=str(exc),
            )
        return {"received": True}

    @app.post("/candidates/accessibility_detected", status_code=202)
    async def candidate_accessibility(
        payload: AccessibilityDetectedPayload,
    ) -> dict[str, bool]:
        # Update fusion's recent-track log; never re-emits to event-store (R4).
        await accessibility_mod.note_accessibility_candidate(payload, ctx)
        return {"received": True}

    # ------------------------------------------------------------------
    # E4-S9 — Closed-ledger reconciliation candidate endpoints.
    # Pattern mirrors /candidates/door_obstruction: handler returns 202 even
    # when downstream emit fails, so inference is never blocked.
    # ------------------------------------------------------------------

    @app.post("/candidates/wagon_exit", status_code=202)
    async def candidate_wagon_exit(payload: WagonExitPayload) -> dict[str, bool]:
        try:
            await ledger.on_wagon_exit(payload)
        except Exception as exc:  # noqa: BLE001 — handler must never raise
            log.warning(
                "candidate.wagon_exit.failed",
                track_id=payload.track_id,
                coach_from=payload.coach_from,
                error=str(exc),
            )
        return {"received": True}

    @app.post("/candidates/wagon_entry", status_code=202)
    async def candidate_wagon_entry(payload: WagonEntryPayload) -> dict[str, bool]:
        try:
            await ledger.on_wagon_entry(payload)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "candidate.wagon_entry.failed",
                track_id=payload.track_id,
                coach_to=payload.coach_to,
                error=str(exc),
            )
        return {"received": True}

    @app.post("/candidates/occupancy_update", status_code=202)
    async def candidate_occupancy_update(
        payload: OccupancyUpdatePayload,
    ) -> dict[str, bool]:
        # Story 4-9 — Ledger drift check.
        try:
            observation = ledger.check_drift(
                payload, station_approach=ctx.station_approach
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "candidate.occupancy_update.failed",
                car_id=payload.car_id,
                error=str(exc),
            )
            observation = None

        if observation is not None:
            if not gate.should_emit():
                log.debug(
                    "ledger.drift_suppressed",
                    car_id=payload.car_id,
                    delta=observation.delta,
                    reason="ledger_drift_suppressed",
                )
            else:
                try:
                    await enricher.emit_envelope(
                        event_type_name="LEDGER_DRIFT_OBSERVATION",
                        payload=observation.model_dump(),
                        severity="info",
                    )
                except httpx.HTTPError as exc:
                    log.warning(
                        "candidate.occupancy_update.emit_failed",
                        car_id=payload.car_id,
                        error=str(exc),
                    )

        # Story 4-10 — Coach Comfort Index (AC1, AC4, AC5).
        # AC5 invariant: under suppression we drop the emit AND avoid advancing
        # `_last_emitted_pct`. We achieve that by skipping `on_occupancy_update`
        # entirely while suppressed. Side-effect: a coach first observed during
        # a suppression window won't appear in `_observed_coaches` until the
        # gate re-opens — that matches AC5's intent (no telemetry escapes,
        # state stays consistent with what we've actually published).
        if not gate.should_emit():
            log.debug(
                "candidate.comfort_index_suppressed",
                reason="comfort_index_suppressed",
                car_id=payload.car_id,
                occupancy_pct=payload.occupancy_pct,
            )
        else:
            comfort_payload = comfort.on_occupancy_update(payload)
            if comfort_payload is not None:
                try:
                    await enricher.emit_envelope(
                        event_type_name="COACH_COMFORT_INDEX",
                        payload=comfort_payload.model_dump(),
                        severity="info",
                    )
                    # P1 — advance baseline only after successful emit (AC5
                    # invariant: failed emit must not move the comparison point).
                    comfort.confirm_emit(payload.car_id, comfort_payload.occupancy_pct)
                except httpx.HTTPError as exc:
                    log.warning(
                        "candidate.comfort_index_emit_failed",
                        car_id=payload.car_id,
                        error=str(exc),
                    )

        return {"received": True}

    return app
