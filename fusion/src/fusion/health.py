"""FastAPI app — health endpoints + inbound candidate/context POSTs.

Routes:
  GET  /health/live                       — process liveness
  GET  /health/ready                      — event-store reachable (cached 1s)
  POST /context                           — vlan-pollers state push
  POST /candidates/door_obstruction       — inference candidate (FR7)
  POST /candidates/alert_raised           — inference candidate (slip_fall)
  POST /candidates/accessibility_detected — optional: update accessibility log
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from oebb_shared.events import AccessibilityDetectedPayload, DoorObstructionPayload

from fusion import accessibility as accessibility_mod
from fusion import door_obstruction as door_obstruction_mod
from fusion.config import Settings
from fusion.context_state import ContextState
from fusion.enrichment import Enrichment
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
        ctx.update_from_push(payload)
        await gate.on_context_changed()
        if payload.ramp_deployed:
            door_id = payload.ramp_door_id or "unknown"
            station_id = payload.ramp_station_id or "unknown"
            car_id = _car_id_for_door(ctx, door_id)
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
        return {"status": "accepted"}

    @app.post("/candidates/door_obstruction", status_code=202)
    async def candidate_door_obstruction(
        payload: DoorObstructionPayload,
    ) -> dict[str, Any]:
        await door_obstruction_mod.handle(payload, ctx, gate, enricher)
        return {"received": True}

    @app.post("/candidates/alert_raised", status_code=202)
    async def candidate_alert_raised(payload: SlipFallCandidate) -> dict[str, Any]:
        if not gate.should_emit():
            log.debug("slip_fall.suppressed", car_id=payload.car_id)
            return {"received": True}
        await enricher.emit_alert(
            alert_code="slip_fall",
            car_id=payload.car_id,
            description="Suspected passenger fall detected by camera",
        )
        return {"received": True}

    @app.post("/candidates/accessibility_detected", status_code=202)
    async def candidate_accessibility(
        payload: AccessibilityDetectedPayload,
    ) -> dict[str, Any]:
        # Update fusion's recent-track log; never re-emits to event-store (R4).
        await accessibility_mod.note_accessibility_candidate(payload, ctx)
        return {"received": True}

    return app


def _car_id_for_door(ctx: ContextState, door_id: str) -> str:
    """Best-effort: find a car_id whose context.door_state has this door_id.

    The ramp signal arrives without a car_id; we infer it from the most recent
    door_state mapping (door key format is ``{car_id}:{door_id}``). If no entry
    exists, fall back to 'unknown' so the RAMP_DEPLOYED payload remains valid.
    """
    suffix = f":{door_id}"
    for key in ctx.door_state:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return "unknown"
