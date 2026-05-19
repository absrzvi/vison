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


class InferencePipeline(GStreamerDetectionApp):  # type: ignore[misc]
    """GStreamerDetectionApp subclass wired to OccupancyCallback.

    Pipeline string:
        SOURCE_PIPELINE → INFERENCE_PIPELINE (hailonet) → TRACKER_PIPELINE (hailotracker)
        → USER_CALLBACK_PIPELINE (fires handoff to OccupancyCallback) → DISPLAY_PIPELINE (fakesink)
    """

    def __init__(self, callback: OccupancyCallback, settings: Settings) -> None:
        pipeline_str = (
            SOURCE_PIPELINE(settings.cameras_json_path)
            + INFERENCE_PIPELINE(hef_path=settings.model_hef_path, batch_size=2)
            + TRACKER_PIPELINE(class_id=0)
            + USER_CALLBACK_PIPELINE(name="oebb")
            + DISPLAY_PIPELINE(video_sink="fakesink", sync=False, show_fps=False)
        )
        super().__init__(app_callback=callback, pipeline_str=pipeline_str)
