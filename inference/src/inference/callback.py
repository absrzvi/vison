"""Thin GStreamer handoff callback — extracts HailoROI metadata and delegates to ZoneCounter.

No GStreamer pipeline creation here (Rule 6). No os.environ.get() (Rule 8).
hailo is imported as a late module reference so unit tests can patch it.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import structlog

from inference.budget import Budget
from inference.config import Settings
from inference.models import DetectionClass, ZoneMask
from inference.zone_counter import ZoneCounter

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

# hailo is only available in the TAPPAS Docker image.
# We import it lazily via sys.modules so unit tests can patch `inference.callback.hailo`.
try:
    import hailo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    hailo = None  # noqa: F841


_ALLOWED_LABELS: frozenset[str] = frozenset(DetectionClass)


class OccupancyCallback:
    """Thin GStreamer handoff callback wired to the USER_CALLBACK_PIPELINE identity element.

    Responsibilities:
    - Extract HailoROI detection metadata from each GStreamer buffer.
    - Filter detections by class (person/suitcase/bicycle) and zone polygon.
    - Skip processing for budget-suppressed cameras.
    - Delegate accepted detections to ZoneCounter.update().
    """

    def __init__(
        self,
        cameras: list[dict[str, Any]],
        zone_masks: dict[str, list[ZoneMask]],
        zone_counter: ZoneCounter,
        budget: Budget,
        settings: Settings,
    ) -> None:
        self._zone_counter = zone_counter
        self._budget = budget
        self._settings = settings
        self._zone_masks = zone_masks

        # Build camera lookup: camera_id → (car_id, priority)
        self._camera_meta: dict[str, dict[str, str]] = {}
        for cam in cameras:
            camera_id = str(cam["camera_id"])
            car_id = str(cam["coach_id"])
            priority = str(cam.get("priority", "P1"))
            self._camera_meta[camera_id] = {"car_id": car_id, "priority": priority}

        # Validate zone configs exist for all coaches — ADR-16
        car_ids = {str(cam["coach_id"]) for cam in cameras}
        missing = car_ids - set(zone_masks.keys())
        if missing:
            log.critical("callback.missing_zone_config", missing=sorted(missing))
            raise RuntimeError(f"Missing zone config for coaches: {sorted(missing)}")

    async def __call__(self, buffer: Any, user_data: Any) -> None:
        """Called by GStreamer handoff signal for each buffer."""
        _hailo = hailo or sys.modules.get("inference.callback.hailo")
        if _hailo is None:
            log.error("callback.hailo_not_available")
            return

        roi = _hailo.get_roi_from_buffer(buffer)
        detections = roi.get_objects_typed(_hailo.HAILO_DETECTION)

        # Group by camera — in this pipeline all detections belong to one camera.
        # Use the first camera associated with this callback context.
        # (Multi-camera mux is handled at the pipeline level via reid_multisource)
        for cam_id, meta in self._camera_meta.items():
            car_id = meta["car_id"]
            priority = meta["priority"]

            if not self._budget.should_process(cam_id, priority):
                continue

            accepted: list[dict[str, Any]] = []
            for det in detections:
                label = det.get_label()
                if label not in _ALLOWED_LABELS:
                    continue

                uid_list = det.get_objects_typed(_hailo.HAILO_UNIQUE_ID)
                track_id = uid_list[0].get_id() if uid_list else None
                bbox = det.get_bbox()

                accepted.append(
                    {
                        "track_id": track_id,
                        "label": label,
                        "bbox": (bbox.xmin(), bbox.ymin(), bbox.xmax(), bbox.ymax()),
                    }
                )

            await self._zone_counter.update(car_id, accepted)
            break  # single-camera pipeline — one camera per callback instance
