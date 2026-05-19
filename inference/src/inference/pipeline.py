"""TAPPAS-native GStreamer inference pipeline.

Hardware-dependent module — excluded from unit coverage (omit = ["*/pipeline.py"]).
Requires HailoRT 4.23.0 + TAPPAS (hailo-apps-core) installed in the Docker image.
Do NOT import this module from unit-tested code.
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
    SOURCE_PIPELINE,
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
    """GStreamerDetectionApp subclass wired to OccupancyCallback.

    Pipeline string:
        SOURCE_PIPELINE → INFERENCE_PIPELINE (hailonet) → TRACKER_PIPELINE (hailotracker)
        → USER_CALLBACK_PIPELINE (fires handoff to OccupancyCallback) → DISPLAY_PIPELINE (fakesink)
    """

    def __init__(self, callback: OccupancyCallback, settings: Settings) -> None:
        # Tracker class_id is derived from Settings.detection_classes — if the config
        # widens (E4-S5), the tracker config widens with it. Single source of truth.
        if settings.detection_classes != [DetectionClass.PERSON.value]:
            raise ValueError(
                "Story 4-4 supports person-only tracking. "
                f"detection_classes={settings.detection_classes!r} is out of scope; "
                "extend pipeline + add per-class routing before widening."
            )
        tracker_class_id = _COCO_CLASS_ID[DetectionClass.PERSON]

        pipeline_str = (
            SOURCE_PIPELINE(settings.cameras_json_path)
            + INFERENCE_PIPELINE(hef_path=settings.model_hef_path, batch_size=2)
            + TRACKER_PIPELINE(class_id=tracker_class_id)
            + USER_CALLBACK_PIPELINE(name="oebb")
            + DISPLAY_PIPELINE(video_sink="fakesink", sync=False, show_fps=False)
        )
        super().__init__(app_callback=callback, pipeline_str=pipeline_str)
