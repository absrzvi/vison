"""GStreamer multisource pipeline stub.

All GStreamer / HailoRT code is integration-only.
Unit tests only cover on_stream_degraded / on_stream_recovered via mocked httpx.
"""
# integration: GStreamer-dependent lines are excluded from unit coverage
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog
from oebb_shared.events.types import EventType
from oebb_shared.http.retry import DEFAULT_RETRY

from .models import CameraConfig
from .scheduler import Scheduler

log = structlog.get_logger()


class Pipeline:
    def __init__(
        self,
        cameras: list[CameraConfig],
        scheduler: Scheduler,
        event_store_url: str,
        vehicle_id: str,
    ) -> None:
        self._cameras: dict[str, CameraConfig] = {c.camera_id: c for c in cameras}
        self._scheduler = scheduler
        self._event_store_url = event_store_url
        self._vehicle_id = vehicle_id
        self._journey_id: str = "unknown"
        self._client = httpx.AsyncClient()

    def set_journey_id(self, journey_id: str) -> None:
        self._journey_id = journey_id

    async def on_stream_degraded(self, camera_id: str, reason: str) -> None:
        cfg = self._cameras.get(camera_id)
        coach_id = cfg.coach_id if cfg else ""
        log.warning(
            "camera_degraded",
            camera_id=camera_id,
            coach_id=coach_id,
            reason=reason,
            recoverable=True,
        )
        await self._post_event(
            event_type=EventType.CAMERA_DEGRADED,
            severity="warning",
            payload={"camera_id": camera_id, "coach_id": coach_id, "reason": reason},
        )

    async def on_stream_recovered(self, camera_id: str) -> None:
        cfg = self._cameras.get(camera_id)
        coach_id = cfg.coach_id if cfg else ""
        log.info("camera_recovered", camera_id=camera_id, coach_id=coach_id)
        await self._post_event(
            event_type=EventType.CAMERA_RECOVERED,
            severity="info",
            payload={"camera_id": camera_id, "coach_id": coach_id},
        )

    @DEFAULT_RETRY
    async def _post_event(
        self,
        event_type: EventType,
        severity: str,
        payload: dict[str, str],
    ) -> None:
        envelope = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "source": "rtsp-ingest",
            "journey_id": self._journey_id,
            "vehicle_id": self._vehicle_id,
            "severity": severity,
            "payload": payload,
        }
        resp = await self._client.post(
            f"{self._event_store_url}/api/v1/events",
            json=envelope,
        )
        resp.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
