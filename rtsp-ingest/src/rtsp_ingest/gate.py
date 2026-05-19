from __future__ import annotations

import structlog

from .config import Settings
from .models import CameraConfig
from .scheduler import Scheduler

log = structlog.get_logger()


class Gate:
    def __init__(
        self,
        cameras: list[CameraConfig],
        scheduler: Scheduler,
        settings: Settings,
        door_camera_map: dict[str, list[str]],
    ) -> None:
        self._cameras = cameras
        self._scheduler = scheduler
        self._settings = settings
        self._door_camera_map = door_camera_map

    def on_context_update(self, payload: dict[str, object]) -> None:
        speed = payload.get("speed_kmh")
        next_station = payload.get("next_station")
        threshold = self._settings.station_speed_threshold_kmh

        should_activate = (
            isinstance(speed, (int, float))
            and speed < threshold
            and bool(next_station)
        )
        self._scheduler.gate_p3(should_activate)
        log.info(
            "p3_gate_updated",
            speed_kmh=speed,
            next_station=next_station,
            p3_active=should_activate,
        )

    def on_door_release(self, car_id: str, door_id: str) -> None:
        camera_ids = self._door_camera_map.get(door_id, [])
        if not camera_ids:
            log.warning("door_release_no_cameras", door_id=door_id, car_id=car_id, recoverable=True)
            return
        self._scheduler.override_to_p1(camera_ids, self._settings.door_release_override_s)
        # STREAM_PRIORITY is internal only — not posted to event-store, not published via MQTT
        log.info(
            "stream_priority_internal",
            command="STREAM_PRIORITY",
            door_id=door_id,
            car_id=car_id,
            camera_ids=camera_ids,
            duration_s=self._settings.door_release_override_s,
        )
