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
import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from oebb_shared.events import (
    AccessibilityDetectedPayload,
    DoorObstructionPayload,
    EventEnvelope,
    EventType,
)
from oebb_shared.http.retry import DEFAULT_RETRY

from inference.budget import Budget
from inference.config import Settings
from inference.models import LoopHolder, ReadinessHolder, ZoneMask
from inference.zone_counter import ZoneCounter

if TYPE_CHECKING:
    from inference.safety import SafetyHandler

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
        readiness: ReadinessHolder | None = None,
        cameras_json: dict[str, Any] | None = None,
        event_store_client: httpx.AsyncClient | None = None,
        safety_handler: SafetyHandler | None = None,
    ) -> None:
        self._zone_counter = zone_counter
        self._budget = budget
        self._settings = settings
        self._zone_masks = zone_masks
        self._loop_holder = loop_holder
        # F2: per-camera readiness holder; pipeline._dispatch flips it on first frame.
        self._readiness = readiness
        self._event_store_client = event_store_client
        self._safety_handler = safety_handler

        self._camera_id = str(camera["camera_id"])
        self._car_id = str(camera["coach_id"])
        self._camera_zone = str(camera.get("zone", "interior"))
        self._priority = str(camera.get("priority", "P1"))
        # M2/P-M16: RTSP URL stored here so InferencePipeline can pass it to GStreamer
        # without re-reading cameras.json (single source of truth).
        self._rtsp_url = str(camera.get("rtsp_url", ""))
        # R5: optional vestibule polygon for door cameras. When present, callback
        # tags persons whose centroid falls inside it; ZoneCounter uses the count
        # of tagged persons for VESTIBULE_CONGESTION (not the seat-zone count).
        vest_raw = camera.get("vestibule_zone")
        self._vestibule_zone: ZoneMask | None = None
        if isinstance(vest_raw, dict) and vest_raw.get("polygon"):
            self._vestibule_zone = ZoneMask(
                name=str(vest_raw.get("name", "vestibule")),
                polygon=[list(p) for p in vest_raw["polygon"]],
            )

        if not zone_masks:
            log.critical(
                "callback.missing_zone_config",
                camera_id=self._camera_id,
                car_id=self._car_id,
            )
            raise RuntimeError(f"Missing zone config for camera {self._camera_id}")

        self._allowed_labels: frozenset[str] = frozenset(settings.detection_classes)

        # Build camera_id → door_id reverse map from cameras_json
        door_camera_map: dict[str, list[str]] = (
            cameras_json.get("door_camera_map", {}) if cameras_json else {}
        )
        self._cam_to_door: dict[str, str] = {}
        for door_id, cam_ids in door_camera_map.items():
            for cam_id in cam_ids:
                self._cam_to_door[cam_id] = door_id

        # E4-S5: door obstruction consecutive frame tracking
        # Key: (camera_id, track_id_or_bbox_hash) → consecutive frame count
        self._door_zone_hits: dict[tuple[str, int], int] = {}
        # E4-S5: last suitcase bbox per camera for IoU-based pseudo-tracking
        self._last_suitcase_bbox: dict[str, tuple[float, float, float, float] | None] = {}
        # E4-S5: bicycle rate-limit — one emit per camera per 10s
        self._bicycle_last_emit: dict[str, float] = {}

        # P-M20: bbox coord space verification — first-frame range check.
        # HARDWARE-VERIFY: Hailo bbox space (pixel vs normalized) confirmed on first
        # hardware day. If hardware emits normalized (0..1), this assertion fires
        # loudly so we know to switch.
        self._bbox_space_verified: bool = False

    @property
    def camera_id(self) -> str:
        return self._camera_id

    def _iou(
        self,
        a: tuple[float, float, float, float],
        b: tuple[float, float, float, float],
    ) -> float:
        """Intersection-over-Union for two (xmin, ymin, xmax, ymax) boxes."""
        ix1 = max(a[0], b[0])
        iy1 = max(a[1], b[1])
        ix2 = min(a[2], b[2])
        iy2 = min(a[3], b[3])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def _handle_suitcase_door_obstruction(
        self,
        bboxes: list[tuple[float, float, float, float]],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Track suitcase detections via IoU and emit candidate after min_frames."""
        prev = self._last_suitcase_bbox.get(self._camera_id)
        best_bbox = bboxes[0]
        hit_key = (self._camera_id, -1)  # suitcase uses sentinel track_id -1

        if prev is not None and self._iou(prev, best_bbox) > 0.5:
            count = self._door_zone_hits.get(hit_key, 0) + 1
        else:
            count = 1
        self._door_zone_hits[hit_key] = count
        self._last_suitcase_bbox[self._camera_id] = best_bbox

        if count >= self._settings.door_obstruction_min_frames:
            self._door_zone_hits[hit_key] = 0  # reset to avoid per-frame flood
            door_id = self._cam_to_door.get(self._camera_id, "unknown")
            # R12: unique per-emit track_id so fusion can dedupe vs distinct obstructions.
            unique_track = f"suitcase-{int(time.monotonic() * 1000) % 100000}"
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self._post_door_obstruction_candidate(
                        door_id=door_id,
                        obstruction_type="object",
                        track_id=unique_track,
                        confidence=None,
                    ),
                    loop,
                )
                fut.add_done_callback(_on_post_done)
            except RuntimeError as exc:
                log.warning(
                    "callback.schedule_during_shutdown",
                    camera_id=self._camera_id,
                    error=str(exc),
                )

    def _handle_person_door_obstruction(
        self,
        track_id: int,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Track person detections in door zone and emit candidate after min_frames."""
        hit_key = (self._camera_id, track_id)
        count = self._door_zone_hits.get(hit_key, 0) + 1
        self._door_zone_hits[hit_key] = count

        if count >= self._settings.door_obstruction_min_frames:
            self._door_zone_hits[hit_key] = 0  # reset to avoid per-frame flood
            door_id = self._cam_to_door.get(self._camera_id, "unknown")
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self._post_door_obstruction_candidate(
                        door_id=door_id,
                        obstruction_type="person",
                        track_id=str(track_id),
                        confidence=None,
                    ),
                    loop,
                )
                fut.add_done_callback(_on_post_done)
            except RuntimeError as exc:
                log.warning(
                    "callback.schedule_during_shutdown",
                    camera_id=self._camera_id,
                    error=str(exc),
                )

    @DEFAULT_RETRY
    async def _post_door_obstruction_candidate(
        self,
        door_id: str,
        obstruction_type: str,
        track_id: str,
        confidence: float | None,
    ) -> None:
        if self._event_store_client is None:
            return
        log.info(
            "callback.door_state_unknown",
            camera_id=self._camera_id,
            note="door_state unknown until ZFR cross-reference in fusion",
        )
        _valid_types = ("person", "object", "unknown")
        safe_type = obstruction_type if obstruction_type in _valid_types else "unknown"
        payload = DoorObstructionPayload(
            car_id=self._car_id,
            door_id=door_id,
            obstruction_type=safe_type,  # type: ignore[arg-type]
            track_id=track_id,
            camera_id=self._camera_id,
            confidence=confidence,
            door_state="unknown",
        )
        resp = await self._event_store_client.post(
            f"{self._settings.fusion_url}/candidates/door_obstruction",
            json=payload.model_dump(),
        )
        resp.raise_for_status()

    async def _dispatch_bicycle(
        self,
        camera_id: str,
        confidence: float | None,
        bbox: tuple[float, float, float, float],
    ) -> None:
        """Evaluate bicycle detection and emit ACCESSIBILITY_DETECTED if threshold met."""
        threshold = self._settings.accessibility_confidence_threshold
        # F13: None confidence means detector gave no score — skip rather than assume pass
        if confidence is None or confidence < threshold:
            return

        # F6: rate-limit to one emit per camera per 10s
        now = time.monotonic()
        if now - self._bicycle_last_emit.get(camera_id, 0.0) < 10.0:
            return
        self._bicycle_last_emit[camera_id] = now

        near_door_id = self._cam_to_door.get(camera_id)
        if near_door_id is None:
            log.critical(
                "callback.accessibility_unmapped_camera",
                camera_id=camera_id,
                hint="Add camera to door_camera_map in cameras.json",
            )
            return

        synthetic_track = f"acc-{camera_id}-{int(time.monotonic() * 1000) % 100000}"
        # R4 (2026-05-20): no longer correlates with SafetyHandler. Fusion (E4-S6)
        # owns ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation.
        await self._post_accessibility_event(
            camera_id=camera_id,
            track_id=synthetic_track,
            confidence=confidence,
            car_id=self._car_id,
            zone=self._camera_zone,
        )

    @DEFAULT_RETRY
    async def _post_accessibility_event(
        self,
        camera_id: str,
        track_id: str,
        confidence: float | None,
        car_id: str,
        zone: str,
    ) -> None:
        if self._event_store_client is None:
            return
        near_door_id = self._cam_to_door.get(camera_id)
        if near_door_id is None:
            return
        payload = AccessibilityDetectedPayload(
            car_id=car_id,
            zone=zone,
            track_id=track_id,
            assistance_type=["wheelchair"],
            camera_id=camera_id,
            confidence=confidence,
            near_door_id=near_door_id,
        )
        envelope = EventEnvelope(
            journey_id=self._zone_counter._journey_holder.journey_id,
            vehicle_id=self._settings.vehicle_id,
            event_type=EventType.ACCESSIBILITY_DETECTED,
            severity="warning",
            source="inference",
            schema_version=self._settings.schema_version,
            payload=payload.model_dump(),
        )
        resp = await self._event_store_client.post(
            f"{self._settings.event_store_url}/api/v1/events",
            json=envelope.model_dump(mode="json"),
        )
        resp.raise_for_status()

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
        bicycle_detections: list[tuple[float | None, tuple[float, float, float, float]]] = []
        suitcase_detections: list[tuple[float, float, float, float]] = []

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
                try:
                    conf_list = det.get_objects_typed(hailo.HAILO_CONFIDENCE)
                    confidence: float | None = conf_list[0].get_confidence() if conf_list else None
                except Exception:  # pragma: no cover
                    confidence = None
            except Exception:  # pragma: no cover
                continue

            if not self._verify_bbox_space(bbox):
                continue

            if not _bbox_in_any_zone(bbox, self._zone_masks):
                continue

            if label == "person":
                if track_id is None:
                    continue
                # R5: tag persons whose centroid falls inside the vestibule polygon
                # so ZoneCounter can score vestibule congestion on the correct count.
                in_vestibule = (
                    self._vestibule_zone is not None
                    and _bbox_in_any_zone(bbox, [self._vestibule_zone])
                )
                accepted.append(
                    {
                        "track_id": track_id,
                        "label": label,
                        "bbox": bbox,
                        "in_vestibule": in_vestibule,
                    }
                )
            elif label == "bicycle":
                bicycle_detections.append((confidence, bbox))
            elif label == "suitcase":
                suitcase_detections.append(bbox)

        loop = self._loop_holder.loop
        if loop is None:
            log.warning("callback.no_loop_yet", camera_id=self._camera_id)
            return

        # M11: loop may be closing between the None check and the schedule call
        # (shutdown TOCTOU). Catch RuntimeError so the streaming thread doesn't crash.
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._zone_counter.update(
                    self._car_id, accepted, camera_id=self._camera_id
                ),
                loop,
            )
            fut.add_done_callback(_on_post_done)
        except RuntimeError as exc:
            log.warning(
                "callback.schedule_during_shutdown",
                camera_id=self._camera_id,
                error=str(exc),
            )

        # Door obstruction: suitcase detections (IoU-based pseudo-tracking)
        if self._camera_zone == "door" and suitcase_detections:
            self._handle_suitcase_door_obstruction(suitcase_detections, loop)
        elif self._camera_zone == "door":
            # F3: no suitcases this frame — clear stale bbox so next detection resets IoU
            self._last_suitcase_bbox.pop(self._camera_id, None)
            self._door_zone_hits.pop((self._camera_id, -1), None)

        # Door obstruction: person detections in door zone via track_id
        if self._camera_zone == "door":
            active_track_ids = {det["track_id"] for det in accepted}
            # F1: prune hits for tracks that disappeared from frame
            stale = [
                k for k in self._door_zone_hits
                if k[0] == self._camera_id and k[1] >= 0 and k[1] not in active_track_ids
            ]
            for k in stale:
                del self._door_zone_hits[k]
            for det in accepted:
                self._handle_person_door_obstruction(det["track_id"], loop)

        # Bicycle → accessibility
        for conf, bbox in bicycle_detections:
            try:
                fut2 = asyncio.run_coroutine_threadsafe(
                    self._dispatch_bicycle(self._camera_id, conf, bbox),
                    loop,
                )
                fut2.add_done_callback(_on_post_done)
            except RuntimeError as exc:
                log.warning(
                    "callback.schedule_during_shutdown",
                    camera_id=self._camera_id,
                    error=str(exc),
                )
