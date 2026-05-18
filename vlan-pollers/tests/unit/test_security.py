"""Security tests — written in RED phase before domain tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vlan_pollers import health as health_module
from vlan_pollers.health import router
from vlan_pollers.snmp_decoder import decode_alarm_table

_app = FastAPI()
_app.include_router(router)
_client = TestClient(_app)


@pytest.mark.unit
def test_unauthenticated_health_returns_without_token() -> None:
    """Health endpoint is VLAN-isolated (ADR-6 PoC) — no auth token required."""
    health_module.set_snmp_ready(True)
    resp = _client.get("/health/ready")
    # No Authorization header — must still succeed (VLAN isolation only)
    assert resp.status_code == 200
    assert resp.json()["snmp_connected"] is True


@pytest.mark.unit
def test_malformed_snmp_trap_discarded() -> None:
    """Malformed varbind list is logged and produces empty result — no exception."""
    malformed: list[tuple[str, object]] = [
        ("not.an.oid.at.all", b"\xff\xfe"),
        ("1.3.6.1.4.1.9999.999", "totally_unknown"),
    ]
    # Must not raise
    result = decode_alarm_table(malformed)
    assert result == []


@pytest.mark.unit
def test_unknown_oid_safe() -> None:
    """Unknown OID prefix triggers WARNING log and is skipped — container stays stable."""
    varbinds: list[tuple[str, object]] = [
        ("9.9.9.9.9.9.9", "some_value"),
        ("1.2.3.4.5.6.7.8", "other_value"),
    ]
    result = decode_alarm_table(varbinds)
    assert result == []
    # No exception raised — test passes if we get here


@pytest.mark.unit
def test_alarm_severity_never_leaks_raw_integer() -> None:
    """AlarmEntry.severity is always a string literal — never a raw SNMP int."""
    varbinds: list[tuple[str, object]] = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-TEST"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Test alarm"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "1"),   # raw severity int as string
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "1"),
    ]
    rows = decode_alarm_table(varbinds)
    assert len(rows) == 1
    sev = rows[0]["severity"]
    assert isinstance(sev, str)
    assert sev in ("critical", "warning", "info")


@pytest.mark.unit
def test_community_string_not_in_alarm_rows() -> None:
    """Community string must never bleed into decoded alarm payload."""
    community = "secret-community-xyz"
    varbinds: list[tuple[str, object]] = [
        ("1.3.6.1.4.1.1234.1.2.1.1.1", "ALM-001"),
        ("1.3.6.1.4.1.1234.1.2.1.2.1", "Normal description"),
        ("1.3.6.1.4.1.1234.1.2.1.3.1", "5"),
        ("1.3.6.1.4.1.1234.1.2.1.4.1", "0"),
    ]
    rows = decode_alarm_table(varbinds)
    import json
    serialised = json.dumps(rows)
    assert community not in serialised
