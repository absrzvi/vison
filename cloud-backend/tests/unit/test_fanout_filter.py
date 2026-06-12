"""Story 10-1 ST5 + AC13 — kill-switch fan-out filter (unit level).

The SSE wire-level behaviour is covered by tests/integration/test_killswitch_fanout.py;
these tests pin the filter predicate and cache semantics without a DB.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cloud_backend.services.fanout_filter import AlertClassFilter

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 6, 12, 12, 0, 0, tzinfo=UTC)
_DISABLED_AT = _NOW - timedelta(minutes=10)


def _db_returning(rows: list[Any]) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(rows))
    db.execute = AsyncMock(return_value=result)
    return db


def _disabled_row(alert_code: str, disabled_at: datetime) -> MagicMock:
    row = MagicMock()
    row.alert_code = alert_code
    row.disabled_at = disabled_at
    return row


@pytest.mark.asyncio
async def test_alert_raised_after_disabled_at_is_filtered() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    filtered = await f.is_filtered(
        db,
        event_type="ALERT_RAISED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_NOW,
    )
    assert filtered is True


@pytest.mark.asyncio
async def test_inflight_alert_raised_before_disabled_at_stays_visible() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    filtered = await f.is_filtered(
        db,
        event_type="ALERT_RAISED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_DISABLED_AT - timedelta(minutes=5),
    )
    assert filtered is False


@pytest.mark.asyncio
async def test_other_alert_codes_not_filtered() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    filtered = await f.is_filtered(
        db,
        event_type="ALERT_RAISED",
        payload={"alert_code": "slip_fall"},
        t_raised=_NOW,
    )
    assert filtered is False


@pytest.mark.asyncio
async def test_non_alert_raised_event_types_never_filtered() -> None:
    """The kill-switch keys on ALERT_RAISED alert_code only — ALERT_RESOLVED and
    other allow-listed types always pass (resolution of an in-flight escalation
    must reach the operator)."""
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    filtered = await f.is_filtered(
        db,
        event_type="ALERT_RESOLVED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_NOW,
    )
    assert filtered is False


@pytest.mark.asyncio
async def test_state_is_cached_within_ttl() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    await f.is_filtered(
        db, event_type="ALERT_RAISED", payload={"alert_code": "x"}, t_raised=_NOW
    )
    await f.is_filtered(
        db, event_type="ALERT_RAISED", payload={"alert_code": "y"}, t_raised=_NOW
    )
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_invalidate_forces_reload() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    await f.is_filtered(
        db, event_type="ALERT_RAISED", payload={"alert_code": "x"}, t_raised=_NOW
    )
    f.invalidate()
    db2 = _db_returning([])
    filtered = await f.is_filtered(
        db2,
        event_type="ALERT_RAISED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_NOW,
    )
    assert db2.execute.await_count == 1
    assert filtered is False


@pytest.mark.asyncio
async def test_empty_table_means_all_enabled() -> None:
    f = AlertClassFilter(ttl_s=60.0)
    db = _db_returning([])
    filtered = await f.is_filtered(
        db,
        event_type="ALERT_RAISED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_NOW,
    )
    assert filtered is False
