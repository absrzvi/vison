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
async def test_concurrent_cold_load_queries_once() -> None:
    """R3 clou-3/4: two concurrent is_filtered on a cold cache must issue ONE
    query — the lock + double-check serialise the check-await-set."""
    import asyncio

    f = AlertClassFilter(ttl_s=60.0)
    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_execute(stmt: Any, params: Any = None) -> MagicMock:
        started.set()
        await release.wait()  # hold the "query" open so the 2nd caller queues
        result = MagicMock()
        result.__iter__ = MagicMock(
            return_value=iter([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
        )
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_slow_execute)

    async def _call() -> bool:
        return await f.is_filtered(
            db, event_type="ALERT_RAISED", payload={"alert_code": "x"}, t_raised=_NOW
        )

    t1 = asyncio.create_task(_call())
    await started.wait()
    t2 = asyncio.create_task(_call())  # arrives while t1 holds the lock+query
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(t1, t2)
    assert db.execute.await_count == 1  # second caller reused the cached load


@pytest.mark.asyncio
async def test_invalidate_during_inflight_load_keeps_cache_stale() -> None:
    """R3 clou-3/4: an invalidate() landing during the load's query must NOT let
    that pre-write snapshot cache — else the kill-switch is masked for a TTL."""
    import asyncio

    f = AlertClassFilter(ttl_s=60.0)
    in_query = asyncio.Event()
    release = asyncio.Event()

    async def _slow_execute(stmt: Any, params: Any = None) -> MagicMock:
        in_query.set()
        await release.wait()
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter([]))  # pre-disable snapshot
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=_slow_execute)

    task = asyncio.create_task(
        f.is_filtered(
            db, event_type="ALERT_RAISED", payload={"alert_code": "x"}, t_raised=_NOW
        )
    )
    await in_query.wait()
    f.invalidate()  # admin disable lands mid-query
    release.set()
    await task
    # The racy snapshot must not have refreshed _loaded_at → next call re-loads.
    db2 = _db_returning([_disabled_row("UNATTENDED_BAG", _DISABLED_AT)])
    filtered = await f.is_filtered(
        db2,
        event_type="ALERT_RAISED",
        payload={"alert_code": "UNATTENDED_BAG"},
        t_raised=_NOW,
    )
    assert db2.execute.await_count == 1  # forced reload, not served from stale map
    assert filtered is True


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
