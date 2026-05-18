"""Tests for snmp_decoder — alarm table parsing and trip number extraction."""

from __future__ import annotations

import pytest

from vlan_pollers.snmp_decoder import (
    IM0_ALARM_ENTRY_PREFIX,
    IM0_TRIP_SCALAR_OID,
    decode_alarm_table,
    decode_trip_number,
)


def _alarm_varbinds(
    row: str, alarm_id: str, desc: str, sev: str, active: str
) -> list[tuple[str, str]]:
    prefix = IM0_ALARM_ENTRY_PREFIX
    return [
        (f"{prefix}.1.{row}", alarm_id),
        (f"{prefix}.2.{row}", desc),
        (f"{prefix}.3.{row}", sev),
        (f"{prefix}.4.{row}", active),
    ]


@pytest.mark.unit
def test_decode_single_active_critical_alarm() -> None:
    varbinds = _alarm_varbinds("1", "ALM-001", "Door obstruction", "1", "1")
    rows = decode_alarm_table(varbinds)
    assert len(rows) == 1
    row = rows[0]
    assert row["alarm_id"] == "ALM-001"
    assert row["description"] == "Door obstruction"
    assert row["severity"] == "critical"
    assert row["active"] is True


@pytest.mark.unit
def test_decode_inactive_warning_alarm() -> None:
    varbinds = _alarm_varbinds("2", "ALM-002", "HVAC low", "3", "0")
    rows = decode_alarm_table(varbinds)
    assert len(rows) == 1
    assert rows[0]["severity"] == "warning"
    assert rows[0]["active"] is False


@pytest.mark.unit
def test_decode_info_alarm_from_high_severity_int() -> None:
    """SNMP severity 5 and 6 map to 'info'."""
    varbinds = _alarm_varbinds("3", "ALM-003", "Status update", "6", "1")
    rows = decode_alarm_table(varbinds)
    assert rows[0]["severity"] == "info"


@pytest.mark.unit
def test_decode_multiple_alarm_rows() -> None:
    varbinds = (
        _alarm_varbinds("1", "ALM-001", "Alarm one", "1", "1")
        + _alarm_varbinds("2", "ALM-002", "Alarm two", "3", "0")
    )
    rows = decode_alarm_table(varbinds)
    assert len(rows) == 2
    alarm_ids = {r["alarm_id"] for r in rows}
    assert alarm_ids == {"ALM-001", "ALM-002"}


@pytest.mark.unit
def test_unknown_oid_skipped_no_crash() -> None:
    """Unknown OID prefix must be silently skipped — no exception."""
    varbinds: list[tuple[str, str]] = [
        ("9.9.9.9.9.9.9", "garbage"),
        ("1.2.3.4.5.6.7", "also_garbage"),
    ]
    rows = decode_alarm_table(varbinds)
    assert rows == []


@pytest.mark.unit
def test_mixed_known_and_unknown_oids() -> None:
    """Known OIDs are decoded; unknown ones are skipped."""
    varbinds: list[tuple[str, str]] = [
        ("9.9.9.9", "skip_me"),
        *_alarm_varbinds("1", "ALM-001", "Real alarm", "2", "1"),
        ("8.8.8.8", "skip_me_too"),
    ]
    rows = decode_alarm_table(varbinds)
    assert len(rows) == 1
    assert rows[0]["alarm_id"] == "ALM-001"


@pytest.mark.unit
def test_decode_trip_number_found() -> None:
    varbinds: list[tuple[str, str]] = [
        (IM0_TRIP_SCALAR_OID, "T12345"),
    ]
    result = decode_trip_number(varbinds)
    assert result == "T12345"


@pytest.mark.unit
def test_decode_trip_number_not_present() -> None:
    varbinds: list[tuple[str, str]] = [
        ("9.9.9.9.9", "irrelevant"),
    ]
    result = decode_trip_number(varbinds)
    assert result is None


@pytest.mark.unit
def test_decode_trip_number_prefix_sibling_not_matched() -> None:
    """A sibling OID under the trip prefix subtree must NOT be matched (exact scalar only)."""
    varbinds: list[tuple[str, str]] = [
        ("1.3.6.1.4.1.1234.1.1.2.0", "SIBLING"),  # sibling, not the exact trip scalar
    ]
    result = decode_trip_number(varbinds)
    assert result is None


@pytest.mark.unit
def test_decode_active_truthvalue_false2() -> None:
    """SNMP TruthValue false(2) must decode to active=False, not True."""
    varbinds = _alarm_varbinds("1", "ALM-TV", "TruthValue alarm", "1", "2")
    rows = decode_alarm_table(varbinds)
    assert rows[0]["active"] is False


@pytest.mark.unit
def test_severity_unknown_int_defaults_to_info() -> None:
    """An unmapped SNMP severity integer falls back to 'info'."""
    varbinds = _alarm_varbinds("1", "ALM-X", "Unknown sev", "99", "1")
    rows = decode_alarm_table(varbinds)
    assert rows[0]["severity"] == "info"
