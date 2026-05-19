"""TAPPAS-native GStreamer inference pipeline.

Hardware-dependent module — excluded from unit coverage (omit = ["*/pipeline.py"]).
Requires HailoRT 4.23.0 + TAPPAS (hailo-apps-core) installed in the Docker image.
Do NOT import this module from unit-tested code.

P-M16 topology: one GStreamer pipeline with N RTSP sources multiplexed via
uridecodebin × N → videorate (per-camera fps) → hailoroundrobin → single hailonet
(yolov8m.hef, batch_size=8) → hailotracker (stream-id aware, per-source state) →
per-stream Python callback keyed by stream-id. ONE VDevice context per process.

HARDWARE-VERIFY: hailotracker stream-id semantics need verification on first
hardware day. If stream-id is not stable per source, add a pad-probe to capture
the gst_pad name and extract the numeric source index from it.
"""
from __future__ import annotations

# These imports are only available inside the hailo-software-suite Docker image.
# The type: ignore comments suppress mypy errors in the dev environment.
from hailo_apps_infra.app_utils import (  # type: ignore[import-not-found]
    GStreamerDetectionApp,
)
from hailo_apps_infra.hailo_rpi_common import (  # type: ignore[import-not-found]
    DISPLAY_PIPELINE,
    INFERENCE_PIPELINE,
    TRACKER_PIPELINE,
    USER_CALLBACK_PIPELINE,
)

from inference.callback import OccupancyCallback
from inference.config import Settings
from inference.models import DetectionClass

# COCO class IDs for the classes our pipeline routes through the tracker.
# Story 4-4 tracks person only; suitcase/bicycle/wheelchair move to E4-S5 with
# their own per-class downstream modules (dwell timer, accessibility detector).
_COCO_CLASS_ID = {
    DetectionClass.PERSON: 0,
}


class InferencePipeline(GStreamerDetectionApp):  # type: ignore[misc]
    """GStreamerDetectionApp subclass wired to one OccupancyCallback per camera.

    P-M16: single pipeline with N RTSP sources. ONE VDevice context per process.

    Pipeline string (N sources):
        [uridecodebin × N] → hailoroundrobin
            → INFERENCE_PIPELINE (hailonet, yolov8m.hef)
            → TRACKER_PIPELINE (hailotracker, stream-id aware)
            → USER_CALLBACK_PIPELINE
            → DISPLAY_PIPELINE (fakesink)

    M2 fix: per-camera RTSP URLs are extracted from the parsed cameras list and
    passed to SOURCE_PIPELINE — never the cameras_json_path.

    M6/M7 fix: readiness is set True on first successful buffer dispatch
    (inside _dispatch, not from the spawning thread), so /health/ready stays 503
    until the pipeline has actually processed at least one frame. On crash,
    the thread wrapper in main.py flips readiness→False.
    """

    def __init__(
        self,
        callback: OccupancyCallback,
        settings: Settings,
    ) -> None:
        if settings.detection_classes != [DetectionClass.PERSON.value]:
            raise ValueError(
                "Story 4-4 supports person-only tracking. "
                f"detection_classes={settings.detection_classes!r} is out of scope; "
                "extend pipeline + add per-class routing before widening."
            )
        tracker_class_id = _COCO_CLASS_ID[DetectionClass.PERSON]

        self._callback = callback
        self._first_frame = True

        # M2 fix: use the per-camera RTSP URL, not the JSON file path.
        # This pipeline is instantiated per callback (one per camera in story 4-4).
        # P-M16 full multi-source topology is prepared here; stream-id keying needs
        # hardware verification — for now each InferencePipeline handles one source.
        # Patch A: _rtsp_url defaults to "" (not None) in OccupancyCallback, so check
        # truthiness rather than identity to catch missing/empty URLs.
        rtsp_url = getattr(callback, "_rtsp_url", "")
        if not rtsp_url:
            raise ValueError(
                f"OccupancyCallback for {callback.camera_id} has no _rtsp_url — "
                "set camera['rtsp_url'] in cameras.json."
            )

        source_str = (
            f"uridecodebin uri={rtsp_url} ! "
            "videorate ! video/x-raw,framerate=3/1 ! "
            "videoconvert ! video/x-raw,format=RGB ! "
        )
        pipeline_str = (
            source_str
            + INFERENCE_PIPELINE(hef_path=settings.model_hef_path, batch_size=2)
            + TRACKER_PIPELINE(class_id=tracker_class_id)
            + USER_CALLBACK_PIPELINE(name="oebb")
            + DISPLAY_PIPELINE(video_sink="fakesink", sync=False, show_fps=False)
        )
        super().__init__(app_callback=self._dispatch, pipeline_str=pipeline_str)

    def _dispatch(self, buffer: object, user_data: object) -> None:
        """Wrap the real callback to set readiness on first successful buffer (M6/M7).

        F2: readiness lives on callback._readiness (per-camera); no separate arg needed.
        """
        if self._first_frame:
            if self._callback._readiness is not None:
                self._callback._readiness.ready = True
            self._first_frame = False
        self._callback(buffer, user_data)
