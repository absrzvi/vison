"""Security tests — AST audits for Rule 8 (no os.environ.get) + payload schema checks."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src" / "fusion"

MODULES = (
    "config.py",
    "models.py",
    "context_state.py",
    "suppression.py",
    "door_obstruction.py",
    "occupancy.py",
    "accessibility.py",
    "enrichment.py",
    "health.py",
    "main.py",
    "ledger.py",
)


def _has_env_get(path: Path) -> bool:
    """Return True if the file contains os.environ.get() calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
        ):
            return True
    return False


@pytest.mark.unit
@pytest.mark.parametrize("module", MODULES)
def test_no_env_get_in_module(module: str) -> None:
    assert not _has_env_get(SRC / module), f"{module} must not call os.environ.get (Rule 8)"


def _has_sql_injection_risk(path: Path) -> list[str]:
    """Return offending source lines where Connection/Cursor.execute is called
    with an f-string or % formatted string (parameterised queries only — AC11).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in {"execute", "executemany", "executescript"}:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.JoinedStr):  # f-string
            offenders.append(f"line {node.lineno}: f-string in {node.func.attr}()")
        elif isinstance(first, ast.BinOp) and isinstance(first.op, (ast.Mod, ast.Add)):
            offenders.append(
                f"line {node.lineno}: {type(first.op).__name__} string build in {node.func.attr}()"
            )
    return offenders


@pytest.mark.unit
def test_ledger_uses_parameterised_sql_only() -> None:
    """AC11 + Security Tests: no SQL string-building inside .execute() calls."""
    offenders = _has_sql_injection_risk(SRC / "ledger.py")
    assert not offenders, f"ledger.py contains SQL-injection risks: {offenders}"


@pytest.mark.unit
def test_alert_raised_payload_schema_valid() -> None:
    from oebb_shared.events import AlertRaisedPayload

    p = AlertRaisedPayload(
        alert_id="11111111-1111-4111-8111-111111111111",
        alert_code="door_obstruction",
        car_id="car-1",
        zone=None,
        description="Door obstruction detected",
        priority="normal",
    )
    dumped = p.model_dump()
    for f in ("alert_id", "alert_code", "car_id", "description"):
        assert f in dumped


@pytest.mark.unit
def test_ramp_deployed_payload_schema_valid() -> None:
    from oebb_shared.events import RampDeployedPayload

    p = RampDeployedPayload(
        car_id="car-1",
        door_id="door-1A",
        triggered_by_track_id="42",
        deployed_by="auto",
        station_id="VIE-HBF",
    )
    dumped = p.model_dump()
    for f in ("car_id", "door_id", "triggered_by_track_id", "deployed_by", "station_id"):
        assert f in dumped


@pytest.mark.unit
def test_envelope_source_field_includes_fusion() -> None:
    """EventEnvelope must accept source='fusion'."""
    from oebb_shared.events import EventEnvelope, EventType

    env = EventEnvelope(
        journey_id="OBB-TEST_t1_20260520",
        vehicle_id="OBB-TEST",
        event_type=EventType.ALERT_RAISED,
        severity="warning",
        source="fusion",
        schema_version=1,
        payload={
            "alert_id": "11111111-1111-4111-8111-111111111111",
            "alert_code": "door_obstruction",
            "car_id": "car-1",
            "description": "Door obstruction detected",
        },
    )
    assert env.source == "fusion"


@pytest.mark.unit
def test_context_push_maintenance_mode_malformed_returns_422() -> None:
    """StrictBool must reject string 'yes' for maintenance_mode."""
    from pydantic import ValidationError

    from fusion.models import ContextPushModel

    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"maintenance_mode": "yes"})


@pytest.mark.unit
def test_context_push_extra_field_returns_422() -> None:
    from pydantic import ValidationError

    from fusion.models import ContextPushModel

    with pytest.raises(ValidationError):
        ContextPushModel.model_validate({"unknown_field": True})


@pytest.mark.unit
def test_slip_fall_candidate_alert_type_literal() -> None:
    from pydantic import ValidationError

    from fusion.models import SlipFallCandidate

    # Wrong literal value rejected.
    with pytest.raises(ValidationError):
        SlipFallCandidate.model_validate(
            {
                "alert_type": "unknown",
                "car_id": "car-1",
                "track_id": 42,
                "camera_id": "C1_DOOR_01",
            }
        )
    # Correct shape accepted — track_id is int (matches hailotracker source).
    SlipFallCandidate.model_validate(
        {
            "alert_type": "slip_fall",
            "car_id": "car-1",
            "track_id": 42,
            "camera_id": "C1_DOOR_01",
        }
    )
    # Non-numeric string track_id MUST be rejected.
    with pytest.raises(ValidationError):
        SlipFallCandidate.model_validate(
            {
                "alert_type": "slip_fall",
                "car_id": "car-1",
                "track_id": "not-a-number",
                "camera_id": "C1_DOOR_01",
            }
        )


@pytest.mark.unit
def test_no_raw_video_or_stream_url_in_envelope() -> None:
    """Security: no raw video paths, RTSP URLs, or video file references may
    appear in any envelope emitted by fusion. Fuzz the typical alert paths
    and confirm payloads stay free of forbidden patterns.
    """
    import json
    import re

    from oebb_shared.events import (
        AccessibilityDetectedPayload,
        AlertRaisedPayload,
        DoorObstructionPayload,
        RampDeployedPayload,
    )

    forbidden = re.compile(
        r"(rtsp://|rtmp://|http(?:s)?://[^\s\"]+\.(?:mp4|mkv|ts|h264|hevc)"
        r"|/dev/video|/var/lib/cctv|file://|raw_video|\.h264\b|\.hevc\b)",
        re.IGNORECASE,
    )

    samples = [
        AlertRaisedPayload(
            alert_id="11111111-1111-4111-8111-111111111111",
            alert_code="door_obstruction",
            car_id="car-1",
            description="Door obstruction on door-1A (person)",
            priority="normal",
        ).model_dump(),
        DoorObstructionPayload(
            car_id="car-1",
            door_id="door-1A",
            obstruction_type="person",
            track_id="42",
            camera_id="C1_DOOR_01",
            confidence=None,
            door_state="closed",
        ).model_dump(),
        AccessibilityDetectedPayload(
            car_id="car-1",
            zone="door",
            track_id="trk-7",
            assistance_type=["wheelchair"],
            camera_id="C1_DOOR_01",
            confidence=None,
            near_door_id="door-1A",
        ).model_dump(),
        RampDeployedPayload(
            car_id="car-1",
            door_id="door-1A",
            triggered_by_track_id="trk-7",
            deployed_by="auto",
            station_id="VIE-HBF",
        ).model_dump(),
    ]
    for payload in samples:
        rendered = json.dumps(payload)
        assert not forbidden.search(rendered), f"forbidden pattern in payload: {rendered}"


@pytest.mark.unit
def test_no_raw_video_in_ledger_drift_observation_payload_or_logs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Story 4-9 Security Tests: no raw video / CCTV URL / Hailo frame data may
    appear in any LedgerDriftObservationPayload field or in ledger log lines.
    Round-1 review P13."""
    import json
    import re

    import structlog.testing
    from oebb_shared.events.payloads import (
        LedgerDriftObservationPayload,
        OccupancyUpdatePayload,
        WagonExitPayload,
    )

    from fusion.config import Settings
    from fusion.ledger import CoachLedger

    forbidden = re.compile(
        r"(rtsp://|rtmp://|http(?:s)?://[^\s\"]+\.(?:mp4|mkv|ts|h264|hevc)"
        r"|/dev/video|/var/lib/cctv|file://|raw_video|\.h264\b|\.hevc\b)",
        re.IGNORECASE,
    )

    # Payload field check.
    payload = LedgerDriftObservationPayload(
        car_id="car-1",
        camera_count=50,
        ledger_count=55,
        delta=5,
        threshold=3,
        surface_to_operator=False,
    ).model_dump()
    assert not forbidden.search(json.dumps(payload))

    # Log-line check — exercise the ledger paths and confirm nothing forbidden
    # appears in captured structlog events.
    settings = Settings(
        event_store_url="http://event-store-test",
        ledger_db_path=str(tmp_path / "ledger.db"),
        ledger_pending_timeout_s=0.05,
    )
    import asyncio

    async def _drive() -> list[dict[str, object]]:
        ledger = CoachLedger(settings)
        try:
            with structlog.testing.capture_logs() as captured:
                await ledger.on_wagon_exit(
                    WagonExitPayload(
                        track_id=1,
                        coach_from="car-1",
                        coach_to="car-2",
                        camera_id="C1_FWD",
                        traversal="from_to",
                        confidence=0.9,
                        expect_orphan=True,
                    )
                )
                ledger._rows["car-1"].ledger_count = 50
                ledger.check_drift(
                    OccupancyUpdatePayload(
                        car_id="car-1",
                        zone=None,
                        occupancy_count=10,
                        occupancy_pct=0.05,
                        capacity=200,
                        service_tier="standard",
                    ),
                    station_approach=False,
                )
            return list(captured)
        finally:
            ledger.close()

    logs = asyncio.run(_drive())
    rendered = json.dumps(logs, default=str)
    assert not forbidden.search(rendered), f"forbidden pattern in ledger logs: {rendered}"
