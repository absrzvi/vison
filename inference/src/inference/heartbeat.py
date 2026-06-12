"""INFERENCE_HEARTBEAT emitter — story 10-1 AC7.

Emits a heartbeat envelope to event-store every settings.heartbeat_interval_s,
independent of detections. Failure to emit is logged at WARNING and never
crashes the loop. frames_processed_window counts frames since the last
SUCCESSFUL emit — on failure the counter keeps accumulating so the next
heartbeat reports the true window.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime

import httpx
import structlog
from oebb_shared.events import EventEnvelope, EventType, InferenceHeartbeatPayload

from inference.config import Settings
from inference.models import JourneyHolder, ReadinessHolder

log = structlog.get_logger(__name__)


class HeartbeatEmitter:
    """One per container. record_frames() is called from the GStreamer streaming
    threads; the counter is guarded by a threading.Lock (not asyncio.Lock) because
    producers are plain threads."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        journey_holder: JourneyHolder,
        model_versions: dict[str, str],
        readiness: list[ReadinessHolder],
    ) -> None:
        self._settings = settings
        self._client = client
        self._journey_holder = journey_holder
        self._model_versions = model_versions
        self._readiness = readiness
        self._frames = 0
        self._frames_lock = threading.Lock()
        self._last_inference_at = datetime.now(UTC)

    def record_frames(self, n: int = 1) -> None:
        """Called from GStreamer callback threads on each processed frame."""
        with self._frames_lock:
            self._frames += n
            self._last_inference_at = datetime.now(UTC)

    def _device_ok(self) -> bool:
        return any(r.ready for r in self._readiness)

    async def emit_once(self) -> None:
        with self._frames_lock:
            frames = self._frames
            last_at = self._last_inference_at

        payload = InferenceHeartbeatPayload(
            train_id=self._settings.vehicle_id,
            model_versions=self._model_versions,
            frames_processed_window=frames,
            last_inference_at=last_at,
            hailo_device_ok=self._device_ok(),
        )
        envelope = EventEnvelope(
            journey_id=self._journey_holder.journey_id,
            vehicle_id=self._settings.vehicle_id,
            event_type=EventType.INFERENCE_HEARTBEAT,
            severity="info",
            source="inference",
            schema_version=self._settings.schema_version,
            payload=payload.model_dump(mode="json"),
        )
        try:
            resp = await self._client.post(
                f"{self._settings.event_store_url}/api/v1/events",
                json=envelope.model_dump(mode="json"),
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning(
                "heartbeat.emit_failed",
                train_id=self._settings.vehicle_id,
                error=str(exc),
            )
            return
        # Reset only after a successful emit — the window stays truthful on failure.
        with self._frames_lock:
            self._frames -= frames

    async def run(self) -> None:
        """Heartbeat loop. Cancelled at shutdown via task.cancel()."""
        while True:
            await asyncio.sleep(self._settings.heartbeat_interval_s)
            await self.emit_once()
