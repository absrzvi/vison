"""TAPPAS-native GStreamer inference pipeline.

Hardware-dependent module — excluded from unit coverage (omit = ["*/pipeline.py"]).
Requires HailoRT 4.23.0 + TAPPAS (hailo-apps-core) installed in the Docker image.
Do NOT import this module from unit-tested code.

P-M16 topology: ONE GStreamer pipeline with N RTSP sources multiplexed via
uridecodebin × N → videorate (per-stream fps) → hailoroundrobin → ONE hailonet
(yolox_s_leaky.hef, batch_size=8) → hailotracker (stream-id aware, per-source state) →
per-stream Python callback keyed by stream-id. ONE VDevice context per process.

This is the worst-case-CPU-fix: a single decode/inference graph rather than one
GStreamer pipeline + VDevice per camera. Per-camera fan-out was the worst case for
CCU decode load and would have produced a falsely decode-bound bench result.

HARDWARE-VERIFY: hailoroundrobin sink request-pad naming (sink_%u) and hailotracker
stream-id semantics need verification on first hardware day. The funnel stamps each
ROI with a stream-id string equal to its source sink-pad name (sink_<index>); we map
that back to the per-camera callback in _resolve_stream_index. If the installed
hailo-apps-core element uses a different stream-id convention, that one place changes
(and the routing test below will catch a mis-route).
"""
from __future__ import annotations

import re

import structlog

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

# hailo is only available in the TAPPAS Docker image. Imported as a module attribute
# (same pattern as inference.callback.hailo) so the stream-id read is patchable in
# tests without a Hailo device.
try:
    import hailo  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    hailo = None  # noqa: F841

log = structlog.get_logger(__name__)

# COCO class IDs for the classes our pipeline routes through the tracker.
# yolox_s_leaky.hef (YOLOX-S, Hailo Model Zoo) emits the standard 80-class COCO
# index space — identical to the retired yolov8m (person=0, bicycle=1, suitcase=28),
# so this mapping is unchanged by the detector swap (ADR-16 §465).
# Story 4-4 tracks person only; suitcase/bicycle/wheelchair move to E4-S5 with
# their own per-class downstream modules (dwell timer, accessibility detector).
_COCO_CLASS_ID = {
    DetectionClass.PERSON: 0,
}

# hailoroundrobin funnels N source pads into one src pad. GStreamer request pads on
# funnel-type elements follow the sink_%u convention. HARDWARE-VERIFY this matches the
# installed hailo-apps-core element on first hardware day.
_ROUNDROBIN_NAME = "src_rr"

# hailoroundrobin stamps each ROI's stream-id with the source sink-pad name it arrived
# on (sink_<index>). We accept that and the bare-integer form ("0"), tolerating an
# optional "src_"/"sink_" prefix so a tracker that re-stamps the id still resolves.
_STREAM_ID_INDEX_RE = re.compile(r"(?:^|_)(\d+)$")

# Sentinel returned when a buffer's stream-id can't be mapped to a known source.
# _dispatch drops + logs such buffers rather than raising on the GStreamer callback
# path (a raise there can tear down the pipeline thread and wedge /health/ready).
_UNKNOWN_STREAM = -1


def _parse_stream_index(stream_id: str) -> int:
    """Extract the numeric source index from a hailoroundrobin stream-id string.

    "sink_3" → 3, "src_3" → 3, "3" → 3. Returns _UNKNOWN_STREAM when the id carries
    no trailing integer (so the caller can drop the buffer instead of mis-routing).
    """
    match = _STREAM_ID_INDEX_RE.search(stream_id)
    return int(match.group(1)) if match else _UNKNOWN_STREAM


def _source_branch(index: int, rtsp_url: str, fps: float) -> str:
    """One decode branch feeding sink_<index> of the round-robin funnel.

    videorate caps each stream at the counting frame rate BEFORE the shared
    hailonet, so all streams contribute equally to the batch and the Hailo isn't
    fed faster than tripwire counting needs.
    """
    return (
        f"uridecodebin uri={rtsp_url} ! "
        f"videorate ! video/x-raw,framerate={int(fps)}/1 ! "
        "videoconvert ! video/x-raw,format=RGB ! "
        f"{_ROUNDROBIN_NAME}.sink_{index} "
    )


def build_pipeline_string(
    callbacks: list[OccupancyCallback],
    settings: Settings,
) -> str:
    """Build the single multiplexed pipeline string from N camera callbacks.

    Pure function — no GStreamer instantiation — so the topology can be asserted
    structurally in tests without a Hailo device (pipeline.py is excluded from
    coverage precisely because GStreamerDetectionApp.__init__ touches hardware).

    Topology (N sources):
        [uridecodebin × N → videorate → hailoroundrobin]
            → INFERENCE_PIPELINE (ONE hailonet, yolox_s_leaky.hef, batch_size=8)
            → TRACKER_PIPELINE (hailotracker, stream-id aware)
            → USER_CALLBACK_PIPELINE
            → DISPLAY_PIPELINE (fakesink)

    ONE hailonet ⇒ ONE VDevice context for the whole process.
    """
    if not callbacks:
        raise ValueError("build_pipeline_string requires at least one camera callback.")

    tracker_class_id = _COCO_CLASS_ID[DetectionClass.PERSON]

    sources: list[str] = []
    for index, cb in enumerate(callbacks):
        # Patch A: _rtsp_url defaults to "" (not None); check truthiness.
        rtsp_url = getattr(cb, "_rtsp_url", "")
        if not rtsp_url:
            raise ValueError(
                f"OccupancyCallback for {cb.camera_id} has no _rtsp_url — "
                "set camera['rtsp_url'] in cameras.json."
            )
        sources.append(_source_branch(index, rtsp_url, settings.pipeline_fps))

    # The funnel element itself carries the name the source branches link to.
    roundrobin = f"hailoroundrobin name={_ROUNDROBIN_NAME} ! "

    # str() coerces the untyped hailo_apps_infra helper fragments (Any) to str so the
    # builder satisfies mypy strict; the helpers return pipeline-string fragments.
    return str(
        "".join(sources)
        + roundrobin
        + INFERENCE_PIPELINE(
            hef_path=settings.model_hef_path,
            batch_size=settings.pipeline_batch_size,
        )
        + TRACKER_PIPELINE(class_id=tracker_class_id)
        + USER_CALLBACK_PIPELINE(name="oebb")
        + DISPLAY_PIPELINE(video_sink="fakesink", sync=False, show_fps=False)
    )


class InferencePipeline(GStreamerDetectionApp):  # type: ignore[misc]
    """ONE GStreamerDetectionApp wired to N OccupancyCallbacks via a stream-id table.

    P-M16: single multiplexed pipeline, N RTSP sources, ONE VDevice context.

    Story 4-4 supports person-only tracking; widening requires per-class routing
    downstream first (see _COCO_CLASS_ID).
    """

    def __init__(
        self,
        callbacks: list[OccupancyCallback],
        settings: Settings,
    ) -> None:
        if settings.detection_classes != [DetectionClass.PERSON.value]:
            raise ValueError(
                "Story 4-4 supports person-only tracking. "
                f"detection_classes={settings.detection_classes!r} is out of scope; "
                "extend pipeline + add per-class routing before widening."
            )
        if not callbacks:
            raise ValueError("InferencePipeline requires at least one camera callback.")

        self._callbacks = callbacks
        # Stream index → callback. The source branch order in build_pipeline_string
        # IS the stream index (sink_0, sink_1, …), so list position is the key and
        # matches the ROI stream-id hailoroundrobin stamps (resolved in
        # _resolve_stream_index).
        self._by_stream: dict[int, OccupancyCallback] = dict(enumerate(callbacks))
        self._first_frame: dict[int, bool] = {i: True for i in self._by_stream}

        pipeline_str = build_pipeline_string(callbacks, settings)
        super().__init__(app_callback=self._dispatch, pipeline_str=pipeline_str)

    def _resolve_stream_index(self, buffer: object, user_data: object) -> int:
        """Map a buffer back to its source stream index via the ROI stream-id.

        hailoroundrobin stamps each ROI with the stream-id of the source sink-pad it
        funnelled in on (sink_<index>, matching _source_branch's `.sink_{index}`
        wiring). We read that id off the buffer and parse the trailing integer.

        Single-source fast path: with one camera there is exactly one stream, so we
        skip the ROI read entirely (and stay robust if a single-source pipeline emits
        no/blank stream-id).

        Returns _UNKNOWN_STREAM (not a raise) when the id can't be resolved — the
        GStreamer callback path must never raise (that can tear down the pipeline
        thread and wedge /health/ready). _dispatch drops + logs unknown buffers.

        HARDWARE-VERIFY: confirm on first hardware day that hailoroundrobin exposes
        the source index as the ROI stream-id in the sink_<index> form. If the
        installed element stamps a different convention, _parse_stream_index is the
        single place to adapt; test_dispatch_* below will fail loudly on a mis-route.
        """
        if len(self._by_stream) == 1:
            return 0
        if hailo is None:  # pragma: no cover — only hit outside the TAPPAS image
            return _UNKNOWN_STREAM
        try:
            stream_id = str(hailo.get_roi_from_buffer(buffer).get_stream_id())
        except Exception as exc:  # pragma: no cover — defensive against malformed ROI
            log.warning("pipeline.stream_id_read_failed", error=str(exc))
            return _UNKNOWN_STREAM
        index = _parse_stream_index(stream_id)
        if index not in self._by_stream:
            return _UNKNOWN_STREAM
        return index

    def _dispatch(self, buffer: object, user_data: object) -> None:
        """Route a buffer to its per-camera callback; set readiness on first frame.

        F2: readiness lives on callback._readiness (per-camera); flipped True the
        first time a given stream produces a buffer.
        """
        index = self._resolve_stream_index(buffer, user_data)
        if index == _UNKNOWN_STREAM:
            # Unresolvable stream-id: drop this buffer (do NOT raise on the streaming
            # thread). Readiness for the affected stream stays False until a buffer
            # whose id we can map arrives, which is the correct signal.
            log.warning("pipeline.unresolved_stream_id", known=sorted(self._by_stream))
            return
        callback = self._by_stream[index]
        if self._first_frame.get(index, False):
            if callback._readiness is not None:
                callback._readiness.ready = True
            self._first_frame[index] = False
        callback(buffer, user_data)
