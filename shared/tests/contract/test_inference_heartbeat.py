"""Contract tests for story 10-1 AC3/AC4 — INFERENCE_HEARTBEAT.

InferenceHeartbeatPayload round-trips under the strict-mode envelope;
naive timestamps and negative frame counts are rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from oebb_shared.events import EventEnvelope
from oebb_shared.events.payloads import InferenceHeartbeatPayload

_VALID = {
    "train_id": "R5001C-031",
    "model_versions": {
        "detector_arch": "yolox_s_leaky",
        "detector_hef": "yolox_s_leaky.hef@ab12cd34ef56",
        "detector_code": "git:9d4a60df",
        "detector_labels": "labels@12ab34cd56ef",
    },
    "frames_processed_window": 1480,
    "last_inference_at": "2026-06-12T14:32:00Z",
    "hailo_device_ok": True,
}


@pytest.mark.contract
def test_heartbeat_payload_roundtrips() -> None:
    p = InferenceHeartbeatPayload.model_validate(_VALID)
    restored = InferenceHeartbeatPayload.model_validate_json(p.model_dump_json())
    assert restored.train_id == "R5001C-031"
    assert restored.frames_processed_window == 1480
    assert restored.hailo_device_ok is True
    assert restored.last_inference_at == datetime(2026, 6, 12, 14, 32, tzinfo=UTC)


@pytest.mark.contract
def test_heartbeat_serialises_last_inference_at_with_z_suffix() -> None:
    p = InferenceHeartbeatPayload.model_validate(_VALID)
    assert '"2026-06-12T14:32:00Z"' in p.model_dump_json()


@pytest.mark.contract
def test_heartbeat_roundtrips_via_strict_envelope() -> None:
    env = EventEnvelope(
        journey_id="R5001C-031_RJ-0847_20260612",
        vehicle_id="R5001C-031",
        event_type="INFERENCE_HEARTBEAT",
        severity="info",
        source="inference",
        payload=dict(_VALID),
    )
    assert env.event_type == "INFERENCE_HEARTBEAT"


@pytest.mark.contract
def test_heartbeat_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        InferenceHeartbeatPayload.model_validate(
            {**_VALID, "last_inference_at": "2026-06-12T14:32:00"}
        )


@pytest.mark.contract
def test_heartbeat_rejects_negative_frames() -> None:
    with pytest.raises(ValidationError):
        InferenceHeartbeatPayload.model_validate({**_VALID, "frames_processed_window": -1})


@pytest.mark.contract
def test_heartbeat_rejects_empty_train_id() -> None:
    with pytest.raises(ValidationError):
        InferenceHeartbeatPayload.model_validate({**_VALID, "train_id": ""})


@pytest.mark.contract
def test_heartbeat_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        InferenceHeartbeatPayload.model_validate({**_VALID, "unexpected": 1})
