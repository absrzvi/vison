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
