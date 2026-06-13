"""Structural integration tests for the multiplexed inference pipeline topology.

These run WITHOUT a Hailo device (the bench hardware is not yet in Vienna). They
validate the pipeline-string assembly produced by ``build_pipeline_string`` —
the design under test on bench day — so a self-inflicted per-camera decode
bottleneck cannot ship undetected:

    * ONE hailoroundrobin funnel (not one pipeline per camera)
    * ONE hailonet at batch_size=8 (single VDevice context)
    * N uridecodebin sources, each capped at the counting fps (default 5)
    * one tracker, one user callback, one fakesink

``inference.pipeline`` imports ``hailo_apps_infra`` (only present inside the Hailo
Docker image), so we inject lightweight stub helpers into ``sys.modules`` first.
The stubs echo their arguments into the string so assertions can see batch_size,
the tracker, the callback, and the sink. The source/funnel structure under test
is emitted by ``build_pipeline_string`` itself, independent of the stubs.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from inference.config import Settings


def _install_hailo_apps_stubs() -> None:
    """Inject stub hailo_apps_infra modules so pipeline.py imports without hardware."""
    app_utils = types.ModuleType("hailo_apps_infra.app_utils")

    class _StubDetectionApp:
        """Records the pipeline string instead of building a GStreamer graph."""

        def __init__(self, app_callback: Any = None, pipeline_str: str = "") -> None:
            self.app_callback = app_callback
            self.pipeline_str = pipeline_str

    app_utils.GStreamerDetectionApp = _StubDetectionApp  # type: ignore[attr-defined]

    rpi_common = types.ModuleType("hailo_apps_infra.hailo_rpi_common")
    rpi_common.INFERENCE_PIPELINE = (  # type: ignore[attr-defined]
        lambda hef_path, batch_size: f"hailonet hef-path={hef_path} batch-size={batch_size} ! "
    )
    rpi_common.TRACKER_PIPELINE = (  # type: ignore[attr-defined]
        lambda class_id: f"hailotracker class-id={class_id} ! "
    )
    rpi_common.USER_CALLBACK_PIPELINE = (  # type: ignore[attr-defined]
        lambda name: f"identity name={name} ! "
    )
    rpi_common.DISPLAY_PIPELINE = (  # type: ignore[attr-defined]
        lambda video_sink, sync, show_fps: f"{video_sink} sync={sync} "
    )

    pkg = types.ModuleType("hailo_apps_infra")
    sys.modules["hailo_apps_infra"] = pkg
    sys.modules["hailo_apps_infra.app_utils"] = app_utils
    sys.modules["hailo_apps_infra.hailo_rpi_common"] = rpi_common


@pytest.fixture
def pipeline_mod(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import inference.pipeline against stubbed hailo_apps_infra modules."""
    _install_hailo_apps_stubs()
    # Force a fresh import so the stubs are picked up even if another test imported it.
    monkeypatch.delitem(sys.modules, "inference.pipeline", raising=False)
    import inference.pipeline as mod

    return mod


def _make_callback(camera_id: str, rtsp_url: str) -> Any:
    """A minimal duck-typed stand-in for OccupancyCallback.

    build_pipeline_string only reads ``camera_id`` and ``_rtsp_url``; using a stub
    avoids constructing the full ZoneCounter/Budget graph for a string-shape test.
    """
    cb = types.SimpleNamespace()
    cb.camera_id = camera_id
    cb._rtsp_url = rtsp_url
    cb._readiness = None
    return cb


@pytest.fixture
def settings() -> Settings:
    # Person-only: matches Story 4-4 scope so InferencePipeline.__init__ accepts it.
    return Settings(detection_classes=["person"])


@pytest.fixture
def door_callbacks() -> list[Any]:
    """24 homogeneous door-line streams — the real concurrent decode load
    (max 6 wagons × 4 doors), per the 2026-06-13 scope decision."""
    return [
        _make_callback(f"C{i // 4 + 1}_DOOR_{i % 4 + 1:02d}", f"rtsp://cam/{i}")
        for i in range(24)
    ]


@pytest.mark.integration
def test_single_roundrobin_funnel(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    """Exactly ONE hailoroundrobin — the multiplex, not per-camera pipelines."""
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert s.count("hailoroundrobin") == 1, "topology must funnel all sources through one round-robin"


@pytest.mark.integration
def test_single_hailonet_one_vdevice(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    """Exactly ONE hailonet ⇒ ONE VDevice context for all 24 streams."""
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert s.count("hailonet") == 1, "single multiplexed hailonet — not one per camera"


@pytest.mark.integration
def test_batch_size_is_eight(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    """Defect 3: the multiplexed hailonet batches across the round-robin'd sources at 8."""
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert "batch-size=8" in s
    assert "batch-size=2" not in s, "batch_size=2 was the shipped worst-case value"


@pytest.mark.integration
def test_fps_defaults_to_five(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    """Defect 2: each stream caps at 5 fps (door-line counting requirement)."""
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert s.count("framerate=5/1") == len(door_callbacks)
    assert "framerate=3/1" not in s, "3 fps was the hardcoded sub-spec value"


@pytest.mark.integration
def test_one_source_branch_per_camera(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    """Defect 1: N decode sources funnel into the SINGLE pipeline — no per-camera fan-out.

    N uridecodebin sources + ONE hailonet is the multiplexed shape; N uridecodebin +
    N hailonet would be the per-camera worst case.
    """
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert s.count("uridecodebin") == len(door_callbacks)
    assert s.count("videorate") == len(door_callbacks)
    # Each source links to a distinct round-robin sink pad.
    for i in range(len(door_callbacks)):
        assert f".sink_{i}" in s
    # …all into one hailonet.
    assert s.count("hailonet") == 1


@pytest.mark.integration
def test_one_tracker_one_callback_one_sink(pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]) -> None:
    s = pipeline_mod.build_pipeline_string(door_callbacks, settings)
    assert s.count("hailotracker") == 1
    assert s.count('identity name=oebb') == 1
    assert s.count("fakesink") == 1


@pytest.mark.integration
def test_pipeline_constructs_over_multistream_without_per_camera_fanout(
    pipeline_mod: Any, settings: Settings, door_callbacks: list[Any]
) -> None:
    """InferencePipeline builds ONE graph over all 24 callbacks (no thread/pipeline fan-out).

    The stubbed GStreamerDetectionApp records the pipeline string; we assert the
    constructed object holds a single multiplexed string and a stream-id dispatch
    table covering every camera.
    """
    pipe = pipeline_mod.InferencePipeline(callbacks=door_callbacks, settings=settings)
    assert pipe.pipeline_str.count("hailonet") == 1
    assert pipe.pipeline_str.count("hailoroundrobin") == 1
    assert set(pipe._by_stream.keys()) == set(range(len(door_callbacks)))
    # app_callback is the bound _dispatch router (bound methods compare by __func__).
    assert pipe.app_callback.__func__ is pipeline_mod.InferencePipeline._dispatch


@pytest.mark.integration
def test_empty_callbacks_rejected(pipeline_mod: Any, settings: Settings) -> None:
    with pytest.raises(ValueError, match="at least one camera callback"):
        pipeline_mod.build_pipeline_string([], settings)


@pytest.mark.integration
def test_missing_rtsp_url_rejected(pipeline_mod: Any, settings: Settings) -> None:
    bad = _make_callback("C1_DOOR_01", "")
    with pytest.raises(ValueError, match="no _rtsp_url"):
        pipeline_mod.build_pipeline_string([bad], settings)


@pytest.mark.integration
def test_non_person_detection_classes_rejected(pipeline_mod: Any, door_callbacks: list[Any]) -> None:
    """Story 4-4 is person-only; widening must be explicit (per-class routing first)."""
    wide = Settings(detection_classes=["person", "suitcase"])
    with pytest.raises(ValueError, match="person-only"):
        pipeline_mod.InferencePipeline(callbacks=door_callbacks, settings=wide)


# ---------------------------------------------------------------------------
# R2-D1: multi-source dispatch / stream-id resolution.
#
# The string-builder tests above never invoke _dispatch, so the multiplexed
# routing path was untested — and previously raised NotImplementedError on the
# first buffer of any >1-camera deploy. These tests exercise the real routing.
# ---------------------------------------------------------------------------


def _routable_callback(camera_id: str) -> Any:
    """A callable stub callback with a real ReadinessHolder and call recorder.

    _dispatch reads ``callback._readiness`` and invokes ``callback(buffer, user_data)``,
    so the stub needs both — the duck-typed build-string stub above has neither.
    """
    from inference.models import ReadinessHolder

    calls: list[tuple[Any, Any]] = []

    def _cb(buffer: Any, user_data: Any) -> None:
        calls.append((buffer, user_data))

    cb = _cb  # function object; _dispatch calls it directly
    cb._readiness = ReadinessHolder(camera_id=camera_id, ready=False)  # type: ignore[attr-defined]
    cb.camera_id = camera_id  # type: ignore[attr-defined]
    cb._rtsp_url = f"rtsp://cam/{camera_id}"  # type: ignore[attr-defined]
    cb.calls = calls  # type: ignore[attr-defined]
    return cb


def _stub_hailo_with_stream_id(stream_id: str) -> Any:
    """A `hailo` module stub whose ROI returns the given stream-id string.

    Mirrors how _resolve_stream_index reads identity:
    ``hailo.get_roi_from_buffer(buffer).get_stream_id()``.
    """
    roi = types.SimpleNamespace(get_stream_id=lambda: stream_id)
    return types.SimpleNamespace(get_roi_from_buffer=lambda buffer: roi)


@pytest.fixture
def dispatch_pipe(pipeline_mod: Any, settings: Settings) -> Any:
    """A 3-camera InferencePipeline whose callbacks record their invocations."""
    cbs = [_routable_callback(f"C1_DOOR_{i:02d}") for i in range(3)]
    pipe = pipeline_mod.InferencePipeline(callbacks=cbs, settings=settings)
    return pipe


@pytest.mark.integration
def test_dispatch_routes_each_stream_to_its_own_callback(
    pipeline_mod: Any, dispatch_pipe: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A buffer stamped sink_<n> must reach ONLY callback n and flip ONLY its readiness."""
    pipe = dispatch_pipe
    for index in range(3):
        buffer = object()
        monkeypatch.setattr(
            pipeline_mod, "hailo", _stub_hailo_with_stream_id(f"sink_{index}")
        )
        pipe._dispatch(buffer, None)
        # routed to the right callback…
        assert pipe._by_stream[index].calls == [(buffer, None)]
        # …and to no other callback
        for other in range(3):
            if other != index:
                assert pipe._by_stream[other].calls == []
        # readiness flipped True only for this stream
        assert pipe._by_stream[index]._readiness.ready is True
        # reset recorder for the next iteration's cross-check
        pipe._by_stream[index].calls.clear()


@pytest.mark.integration
def test_dispatch_misroute_is_caught(
    pipeline_mod: Any, dispatch_pipe: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard: a buffer for stream 2 must NOT land on callback 0.

    This is the test the original code lacked — if a future stream-id convention
    change silently mapped every buffer to index 0, this fails loudly.
    """
    pipe = dispatch_pipe
    buffer = object()
    monkeypatch.setattr(pipeline_mod, "hailo", _stub_hailo_with_stream_id("sink_2"))
    pipe._dispatch(buffer, None)
    assert pipe._by_stream[2].calls == [(buffer, None)]
    assert pipe._by_stream[0].calls == []
    assert pipe._by_stream[1].calls == []


@pytest.mark.integration
def test_dispatch_unknown_stream_id_drops_without_raising(
    pipeline_mod: Any, dispatch_pipe: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unmappable stream-id must drop the buffer (no raise, no mis-route).

    Regression for R2-D1: the GStreamer callback path must never raise — a raise
    there tears down the pipeline thread and wedges /health/ready at 503.
    """
    pipe = dispatch_pipe
    # stream-id with no trailing index, and an out-of-range index — both unresolvable.
    for bad_id in ("camera_front", "sink_99"):
        monkeypatch.setattr(pipeline_mod, "hailo", _stub_hailo_with_stream_id(bad_id))
        pipe._dispatch(object(), None)  # must not raise
    for index in range(3):
        assert pipe._by_stream[index].calls == []
        assert pipe._by_stream[index]._readiness.ready is False


@pytest.mark.integration
def test_dispatch_single_source_skips_stream_id_read(
    pipeline_mod: Any, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One camera ⇒ index 0 fast path, even if hailo is unavailable / id is blank."""
    cb = _routable_callback("C1_DOOR_00")
    pipe = pipeline_mod.InferencePipeline(callbacks=[cb], settings=settings)
    monkeypatch.setattr(pipeline_mod, "hailo", None)  # would force _UNKNOWN if read
    buffer = object()
    pipe._dispatch(buffer, None)
    assert cb.calls == [(buffer, None)]
    assert cb._readiness.ready is True


@pytest.mark.integration
@pytest.mark.parametrize(
    ("stream_id", "expected"),
    [("sink_0", 0), ("sink_7", 7), ("src_3", 3), ("3", 3), ("", -1), ("front", -1)],
)
def test_parse_stream_index(pipeline_mod: Any, stream_id: str, expected: int) -> None:
    assert pipeline_mod._parse_stream_index(stream_id) == expected
