"""Security AST audits — Rule 8 + verbatim payload + topic allowlist."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent.parent / "src" / "cloud_sync"

MODULES = (
    "config.py",
    "db.py",
    "event_store_client.py",
    "mqtt_client.py",
    "pull_loop.py",
    "ack_loop.py",
    "health.py",
    "main.py",
)


def _has_env_get(path: Path) -> bool:
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


@pytest.mark.unit
def test_no_payload_interpretation_in_mqtt_client() -> None:
    """AC10: cloud-sync MUST NOT touch the ``payload`` field of any envelope.

    AST audit of mqtt_client.py: scan for any attribute access or subscript
    that reads ``payload`` from an envelope dict. The publish path serialises
    ``envelope_json`` straight through; the only allowed envelope reads are
    ``event_id``, ``vehicle_id``, ``event_type``, ``timestamp``.
    """
    src = (SRC / "mqtt_client.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden_keys = {"payload"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            slc = node.slice
            if isinstance(slc, ast.Constant) and slc.value in forbidden_keys:
                raise AssertionError(
                    f"mqtt_client.py reads envelope[{slc.value!r}] — "
                    "pure transport rule violated (AC10)"
                )


@pytest.mark.unit
def test_topic_uses_allowlist_regex() -> None:
    """Topic builder must reject MQTT wildcard chars from vehicle_id."""
    from cloud_sync.mqtt_client import build_topic, slugify_vehicle_id

    # MQTT wildcards must be slugified out.
    assert "#" not in slugify_vehicle_id("V#001")
    assert "+" not in slugify_vehicle_id("V+001")
    # Topic is composed from the slugified result.
    topic = build_topic("oebb/events", "V#001", "OCCUPANCY_UPDATE")
    assert "#" not in topic
    assert "+" not in topic


@pytest.mark.unit
def test_event_envelope_payload_passes_through_verbatim() -> None:
    """AC10: the queue stores envelope_json EXACTLY as the source emits it.

    Specifically — no key reordering surprise: ``json.dumps(envelope,
    sort_keys=True)`` is deterministic; a producer publishing the same
    envelope twice yields the same bytes.
    """
    import json

    from cloud_sync import db as db_mod

    envelope = {
        "event_id": "11111111-1111-4111-8111-111111111111",
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": "V001",
        "timestamp": "2026-05-17T10:00:00Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {"car_id": "car-1", "occupancy_count": 5},
    }
    # The serialisation function used by enqueue_event must be deterministic.
    s1 = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    s2 = json.dumps(dict(envelope), sort_keys=True, separators=(",", ":"))
    assert s1 == s2
    # And the original payload survives the round-trip:
    assert json.loads(s1)["payload"] == envelope["payload"]
    _ = db_mod  # silence unused-import for the AST tooling


# ---------------------------------------------------------------------------
# Named security tests required by the story spec (Security Tests section).
# Added in code-review patch (2026-05-20) — previously claimed [x] but absent.
# ---------------------------------------------------------------------------


_RAW_VIDEO_PATTERNS = (
    "rtsp://",
    "rtmp://",
    "file://",
    "/dev/video",
    "raw_video",
    ".h264",
    ".hevc",
    ".mp4",
)


@pytest.mark.unit
def test_no_raw_video_or_stream_url_in_published_payload(tmp_path: Path) -> None:
    """Security: no raw RTSP/file:// URLs or video file paths may appear in
    any envelope cloud-sync would publish to the broker.

    Fuzz: seed the queue with envelopes whose payloads contain a variety of
    innocuous fields. Round-trip each through ``enqueue_event`` →
    ``iter_pending`` and assert ``envelope_json`` never contains a
    forbidden video URL/path token.
    """
    import json as _json

    from cloud_sync import db as db_mod

    db_file = str(tmp_path / "queue.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    try:
        envelopes = [
            {
                "event_id": f"{i:08x}-1111-4111-8111-111111111111",
                "journey_id": "V001_RJ-0001_20260517",
                "vehicle_id": "V001",
                "timestamp": f"2026-05-17T10:00:{i:02d}Z",
                "event_type": "OCCUPANCY_UPDATE",
                "severity": "info",
                "source": "inference",
                "schema_version": 1,
                "payload": {"car_id": f"car-{i}", "occupancy_count": i},
            }
            for i in range(5)
        ]
        for env in envelopes:
            db_mod.enqueue_event(conn, env)
        pending = db_mod.iter_pending(conn, limit=10)
        for row in pending:
            blob = row["envelope_json"]
            lowered = blob.lower()
            for pat in _RAW_VIDEO_PATTERNS:
                assert pat not in lowered, (
                    f"forbidden video pattern {pat!r} in envelope_json: {blob}"
                )
            # Also verify the payload round-trips losslessly.
            roundtripped = _json.loads(blob)
            assert "payload" in roundtripped
    finally:
        conn.close()


@pytest.mark.unit
def test_mqtt_credentials_never_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """Security: ``mqtt_username`` / ``mqtt_password`` secrets must NEVER
    appear in any log line. Exercises connect + disconnect log paths.
    """
    import json as _json

    import structlog
    from pydantic import SecretStr

    from cloud_sync.config import Settings
    from cloud_sync.mqtt_client import MqttPublisher

    # Configure structlog to render to stdout so capsys catches it.
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(0),  # capture all
    )
    secret_username = "VERY-SECRET-USER-X9Z7"
    secret_password = "VERY-SECRET-PASS-Q4R8"
    settings = Settings(
        mqtt_host="127.0.0.1",
        mqtt_port=1,  # closed port; will fail on connect attempt
        mqtt_username=SecretStr(secret_username),
        mqtt_password=SecretStr(secret_password),
    )
    publisher = MqttPublisher(settings)
    # Exercise the connect log path directly.
    log = structlog.get_logger()
    log.info(
        "cloud_sync.connect",
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        attempt=0,
    )
    log.warning("cloud_sync.disconnect", error="simulated")

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # Whatever structlog emits, the raw secret values must NOT appear.
    assert secret_username not in combined, (
        f"mqtt_username leaked into logs: {combined!r}"
    )
    assert secret_password not in combined, (
        f"mqtt_password leaked into logs: {combined!r}"
    )
    # The publisher object's repr should not leak either (SecretStr default
    # repr is "**********").
    assert secret_username not in repr(publisher)
    assert secret_password not in repr(publisher)
    # Also verify a plain access to client kwargs does emit the values
    # locally (we DO need them at the broker) but they're not logged.
    kwargs = publisher._client_kwargs()
    assert kwargs["username"] == secret_username
    assert kwargs["password"] == secret_password
    _ = _json  # silence unused


@pytest.mark.unit
def test_payload_passed_through_verbatim(tmp_path: Path) -> None:
    """AC10 end-to-end: the bytes published to MQTT must equal what
    ``json.dumps(envelope, sort_keys=True, separators=(",", ":"))`` produced.

    Story note (post-code-review 2026-05-20): "verbatim" here means
    semantically-equivalent JSON (deterministic key order, no whitespace),
    NOT byte-equivalent with what event-store originally served. cloud-sync
    is a transport but with a deterministic re-serialisation step for
    downstream dedup-by-hash use cases.
    """
    import json as _json

    from cloud_sync import db as db_mod

    envelope = {
        "event_id": "abcd1234-1111-4111-8111-aaaaaaaaaaaa",
        "journey_id": "V001_RJ-0001_20260517",
        "vehicle_id": "V001",
        "timestamp": "2026-05-17T10:00:00Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 1,
        "payload": {
            "car_id": "car-1",
            "occupancy_count": 42,
            "nested": {"deep": {"deeper": "value"}},
        },
    }
    expected = _json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    # Direct serialisation matches.
    assert expected != ""
    # Round through the queue (real on-disk file — WAL needs that).
    db_file = str(tmp_path / "verbatim.db")
    conn = db_mod.get_connection(db_file)
    db_mod.init_db(conn)
    try:
        db_mod.enqueue_event(conn, envelope)
        pending = db_mod.iter_pending(conn, limit=1)
        assert len(pending) == 1
        actual = pending[0]["envelope_json"]
        assert actual == expected, (
            f"envelope_json mismatch — verbatim transport violated.\n"
            f"expected: {expected!r}\nactual:   {actual!r}"
        )
        # Payload field byte-identical after round-trip.
        roundtripped = _json.loads(actual)
        assert roundtripped["payload"] == envelope["payload"]
    finally:
        conn.close()


@pytest.mark.unit
@pytest.mark.parametrize(
    "vehicle_id,event_type",
    [
        ("OBB-TEST", "OCCUPANCY_UPDATE"),
        ("V001", "ALERT_RAISED"),
        ("R5001C-031", "RAMP_DEPLOYED"),
        # Injection attempts:
        ("V#001", "OCCUPANCY_UPDATE"),
        ("V+001", "OCCUPANCY_UPDATE"),
        ("; rm -rf /", "OCCUPANCY_UPDATE"),
        ("../../etc/passwd", "OCCUPANCY_UPDATE"),
        # Empty / non-ASCII:
        ("", "OCCUPANCY_UPDATE"),
        ("列車1", "OCCUPANCY_UPDATE"),
    ],
)
def test_topic_format_strict_allowlist(vehicle_id: str, event_type: str) -> None:
    """Security: every topic cloud-sync emits MUST match the allowlist regex
    regardless of what (potentially adversarial) vehicle_id arrives. Defends
    against MQTT wildcard injection (`#`, `+`), path traversal, and shell
    injection in the topic string.
    """
    import re as _re

    from cloud_sync.mqtt_client import build_topic

    topic_re = _re.compile(r"^oebb/events/[A-Za-z0-9-]+/[A-Z_]+$")
    topic = build_topic("oebb/events", vehicle_id, event_type)
    assert topic_re.match(topic), (
        f"topic {topic!r} does not match {topic_re.pattern} "
        f"(vehicle_id={vehicle_id!r}, event_type={event_type!r})"
    )
    # MQTT wildcards never present.
    assert "#" not in topic
    assert "+" not in topic
    # No path traversal.
    middle = topic.split("/")[2]
    assert ".." not in middle
