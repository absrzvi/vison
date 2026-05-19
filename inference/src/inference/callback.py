"""Thin GStreamer handoff callback — extracts HailoROI metadata and delegates to ZoneCounter.

No GStreamer pipeline creation here (Rule 6). No os.environ.get() (Rule 8).
hailo is imported as a module attribute so unit tests can patch
`inference.callback.hailo` directly.

The callback is SYNCHRONOUS — GStreamer's handoff signal fires from the streaming
thread and expects a sync return. Async event-store POSTs are scheduled onto an
asyncio loop owned by main.py via asyncio.run_coroutine_threadsafe. The loop
reference is provided by a LoopHolder so the same object can be passed to the
callback at construction time and rebound by main's lifespan once the real loop
is running.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from typing import Any

import structlog

from inference.budget import Budget
from inference.config import Settings
from inference.models import LoopHolder, ZoneMask
from inference.zone_counter import ZoneCounter

log = structlog.get_logger(__name__)

# hailo is only available in the TAPPAS Docker image. Imported as a module attribute
# so unit tests can patch `inference.callback.hailo`.
try:
    import hailo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    hailo = None  # noqa: F841


def _on_segment(
    x: float, y: float, x1: float, y1: float, x2: float, y2: float
) -> bool:
    """Return True if (x,y) lies on the line segment (x1,y1)-(x2,y2) (inclusive)."""
    # Collinear check via cross product == 0 with a small tolerance.
    cross = (y - y1) * (x2 - x1) - (x - x1) * (y2 - y1)
    if abs(cross) > 1e-9:
        return False
    # Within bounding box of the segment (inclusive).
    return (
        min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9
        and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9
    )


def _point_in_polygon(x: float, y: float, polygon: list[list[int]]) -> bool:
    """Ray-casting point-in-polygon.

    Points exactly on an edge or vertex are treated as inside (M5 fix — the
    previous ray-cast formula used strict ``>`` comparisons and silently
    excluded points sitting on horizontal edges or vertices).
    """
    if len(polygon) < 3:
        return False

    # Explicit edge-inclusion check first — guarantees boundary points are inside
    # regardless of ray-cast parity behaviour on horizontal edges / vertex hits.
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i][0], polygon[i][1]
        x2, y2 = polygon[(i + 1) % n][0], polygon[(i + 1) % n][1]
        if _on_segment(x, y, x1, y1, x2, y2):
            return True

    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _bbox_in_any_zone(
    bbox: tuple[float, float, float, float], zones: list[ZoneMask]
) -> bool:
    """Centroid-based zone membership test."""
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    return any(_point_in_polygon(cx, cy, z.polygon) for z in zones)


def _on_post_done(future: Future[Any]) -> None:
    """Log exceptions from scheduled async POSTs so failures aren't silently swallowed."""
    exc = future.exception()
    if exc is not None:
        log.warning("callback.scheduled_post_failed", error=str(exc))


class OccupancyCallback:
    """Thin GStreamer handoff callback wired to the USER_CALLBACK_PIPELINE identity element.

    One instance per camera/pipeline. TAPPAS handoff buffers do not carry a stable
    camera identifier through pad metadata, so we bind one callback to one source.
    """

    def __init__(
        self,
        camera: dict[str, Any],
        zone_masks: list[ZoneMask],
        zone_counter: ZoneCounter,
        budget: Budget,
        settings: Settings,
        loop_holder: LoopHolder,
    ) -> None:
        self._zone_counter = zone_counter
        self._budget = budget
        self._settings = settings
        self._zone_masks = zone_masks
        self._loop_holder = loop_holder

        self._camera_id = str(camera["camera_id"])
        self._car_id = str(camera["coach_id"])
        self._priority = str(camera.get("priority", "P1"))
        # M2/P-M16: RTSP URL stored here so InferencePipeline can pass it to GStreamer
        # without re-reading cameras.json (single source of truth).
        self._rtsp_url = str(camera.get("rtsp_url", ""))

        if not zone_masks:
            log.critical(
                "callback.missing_zone_config",
                camera_id=self._camera_id,
                car_id=self._car_id,
            )
            raise RuntimeError(f"Missing zone config for camera {self._camera_id}")

        self._allowed_labels: frozenset[str] = frozenset(settings.detection_classes)

        # P-M20: bbox coord space verification — first-frame range check.
        # HARDWARE-VERIFY: Hailo bbox space (pixel vs normalized) confirmed on first
        # hardware day. If hardware emits normalized (0..1), this assertion fires
        # loudly so we know to switch.
        self._bbox_space_verified: bool = False

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def _verify_bbox_space(self, bbox: tuple[float, float, float, float]) -> bool:
        """First-frame bbox-range check. Returns False on violation (caller drops frame).

        Pixel space expected: 0 <= x <= frame_width, 0 <= y <= frame_height.
        Logs CRITICAL on first violation, sets a sticky flag so we don't log per frame.
        """
        x_min, y_min, x_max, y_max = bbox
        w, h = self._settings.frame_width, self._settings.frame_height
        if not (0 <= x_min <= w and 0 <= x_max <= w and 0 <= y_min <= h and 0 <= y_max <= h):
            if not self._bbox_space_verified:  # log once, not per frame
                log.critical(
                    "callback.bbox_out_of_pixel_range",
                    camera_id=self._camera_id,
                    bbox=bbox,
                    expected_max=(w, h),
                    hint="bboxes may be normalized (0..1) — switch coord space",
                )
                self._bbox_space_verified = True
            return False
        return True

    def __call__(self, buffer: Any, user_data: Any) -> None:
        """Sync handoff entry point. GStreamer fires this from the streaming thread."""
        if hailo is None:
            log.error("callback.hailo_not_available", camera_id=self._camera_id)
            return

        if not self._budget.should_process(self._camera_id, self._priority):
            return

        try:
            roi = hailo.get_roi_from_buffer(buffer)
            detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
        except Exception as exc:  # pragma: no cover — defensive against malformed buffers
            log.warning("callback.roi_extract_failed", camera_id=self._camera_id, error=str(exc))
            return

        accepted: list[dict[str, Any]] = []
        for det in detections:
            try:
                label = det.get_label()
            except Exception:  # pragma: no cover
                continue
            if label not in self._allowed_labels:
                continue

            try:
                uid_list = det.get_objects_typed(hailo.HAILO_UNIQUE_ID)
                track_id = uid_list[0].get_id() if uid_list else None
                bbox_obj = det.get_bbox()
                # HARDWARE-VERIFY: bbox coord space — see _verify_bbox_space.
                bbox = (bbox_obj.xmin(), bbox_obj.ymin(), bbox_obj.xmax(), bbox_obj.ymax())
            except Exception:  # pragma: no cover
                continue

            if track_id is None:
                continue

            if not self._verify_bbox_space(bbox):
                continue

            if not _bbox_in_any_zone(bbox, self._zone_masks):
                continue

            accepted.append({"track_id": track_id, "label": label, "bbox": bbox})

        loop = self._loop_holder.loop
        if loop is None:
            log.warning("callback.no_loop_yet", camera_id=self._camera_id)
            return

        # M11: loop may be closing between the None check and the schedule call
        # (shutdown TOCTOU). Catch RuntimeError so the streaming thread doesn't crash.
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._zone_counter.update(self._car_id, accepted),
                loop,
            )
            fut.add_done_callback(_on_post_done)
        except RuntimeError as exc:
            log.warning(
                "callback.schedule_during_shutdown",
                camera_id=self._camera_id,
                error=str(exc),
            )
