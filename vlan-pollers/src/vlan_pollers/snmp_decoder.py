from __future__ import annotations

from typing import Any, Literal

import structlog

log = structlog.get_logger()

# Stadler IM MIB OID prefixes (numeric strings)
# im0AlarmEntry table: .1.3.6.1.4.1.1234.1.2.1.*  (illustrative — configure via OID constants)
IM0_ALARM_ENTRY_PREFIX = "1.3.6.1.4.1.1234.1.2.1"
IM0_TRIP_PREFIX = "1.3.6.1.4.1.1234.1.1"

# Sub-OID column indices within im0AlarmEntry
_COL_ALARM_ID = "1"
_COL_DESCRIPTION = "2"
_COL_SEVERITY = "3"
_COL_ACTIVE = "4"

# SNMP integer → severity mapping (Stadler IM convention)
_SEVERITY_MAP: dict[int, Literal["critical", "warning", "info"]] = {
    1: "critical",
    2: "critical",
    3: "warning",
    4: "warning",
    5: "info",
    6: "info",
}


def _map_severity(raw: int) -> Literal["critical", "warning", "info"]:
    return _SEVERITY_MAP.get(raw, "info")


def decode_alarm_table(
    varbinds: list[tuple[str, Any]],
) -> list[dict[str, Any]]:
    """Parse a flat list of (oid_string, value) varbinds from a GetBulk response.

    Groups by row index, builds one dict per alarm row.
    Unknown OIDs are logged and skipped — no exception raised.
    Returns list of raw row dicts; caller converts to AlarmEntry.
    """
    rows: dict[str, dict[str, Any]] = {}  # row_index → {col: value}

    for oid_str, value in varbinds:
        if not oid_str.startswith(IM0_ALARM_ENTRY_PREFIX):
            log.warning("snmp_unknown_oid", oid=oid_str, recoverable=True)
            continue

        suffix = oid_str[len(IM0_ALARM_ENTRY_PREFIX):].lstrip(".")
        parts = suffix.split(".", 1)
        if len(parts) != 2:
            log.warning("snmp_malformed_oid", oid=oid_str, recoverable=True)
            continue
        col, row_idx = parts[0], parts[1]

        if row_idx not in rows:
            rows[row_idx] = {}
        rows[row_idx][col] = value

    results = []
    for row_idx, cols in rows.items():
        try:
            results.append(_build_alarm_row(row_idx, cols))
        except Exception as exc:
            log.warning(
                "snmp_alarm_row_decode_failed", row=row_idx, error=str(exc), recoverable=True
            )
    return results


def _build_alarm_row(row_idx: str, cols: dict[str, Any]) -> dict[str, Any]:
    raw_severity = int(cols.get(_COL_SEVERITY, 6))
    raw_active = cols.get(_COL_ACTIVE, 1)
    # SNMP values arrive as strings from prettyPrint; "0" means false, anything else true.
    active = int(raw_active) != 0 if isinstance(raw_active, str) else bool(raw_active)
    return {
        "alarm_id": str(cols.get(_COL_ALARM_ID, row_idx)),
        "description": str(cols.get(_COL_DESCRIPTION, "")),
        "severity": _map_severity(raw_severity),
        "active": active,
    }


def decode_trip_number(varbinds: list[tuple[str, Any]]) -> str | None:
    """Extract im0triTripNumber string from varbinds. Returns None if not present."""
    for oid_str, value in varbinds:
        if oid_str.startswith(IM0_TRIP_PREFIX):
            return str(value)
    return None
