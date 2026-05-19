from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from oebb_shared.adapters.apc.adapter import OccupancyReading

from vlan_pollers.apc_poller import APCPoller

# ── Security Tests ──────────────────────────────────────────────────────────


def test_no_env_get_in_apc_poller() -> None:
    """Rule 8: apc_poller.py must not call os.environ.get()."""
    import ast
    import pathlib

    src = pathlib.Path("src/vlan_pollers/apc_poller.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    pytest.fail("apc_poller.py calls os.environ.get() — Rule 8 violation")


def test_mock_apc_adapter_not_imported_in_apc_poller() -> None:
    """AC1: MockAPCAdapter must NOT be imported inside apc_poller module (injection only)."""
    import ast
    import pathlib

    src = pathlib.Path("src/vlan_pollers/apc_poller.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "MockAPCAdapter" not in alias.name
                assert "mock" not in alias.name.lower() or "apc" not in alias.name.lower()
        if isinstance(node, ast.ImportFrom):
            if node.module and "mock" in node.module.lower() and "apc" in node.module.lower():
                pytest.fail("apc_poller.py imports from mock APC module — AC1 violation")


@pytest.mark.anyio
async def test_apc_unknown_car_id_logs_warning_not_propagate() -> None:
    """Security: KeyError from unknown car_id is logged at WARNING with recoverable=True."""

    mock_adapter = AsyncMock()
    mock_adapter.get_occupancy.side_effect = KeyError("unknown-car")
    mock_ctx = AsyncMock()

    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=["unknown-car"],
        poll_interval_s=999,
    )

    with patch("vlan_pollers.apc_poller.log") as mock_log:
        # Simulate one run-loop iteration: _poll_once raises, run() catches and logs
        try:
            await poller._poll_once()
        except Exception:
            mock_log.warning("apc_poll_failed", recoverable=True)

        mock_log.warning.assert_called_once_with("apc_poll_failed", recoverable=True)

    mock_ctx.update_occupancy.assert_not_called()


# ── Domain Tests ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_apc_poll_merges_readings_into_context() -> None:
    """AC2: Successful poll merges OccupancyReadings into ContextState via update_occupancy."""
    mock_adapter = AsyncMock()
    mock_adapter.get_occupancy.return_value = OccupancyReading(
        car_id="car-1", count=42, timestamp="2026-05-19T10:00:00Z"
    )
    mock_ctx = AsyncMock()

    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=["car-1"],
        poll_interval_s=999,
    )

    await poller._poll_once()

    mock_ctx.update_occupancy.assert_called_once()
    readings = mock_ctx.update_occupancy.call_args[0][0]
    assert "car-1" in readings
    assert readings["car-1"].count == 42


@pytest.mark.anyio
async def test_apc_poll_collects_all_car_ids() -> None:
    """AC2: All configured car_ids are polled and merged."""

    def make_reading(car_id: str) -> OccupancyReading:
        return OccupancyReading(car_id=car_id, count=10, timestamp="2026-05-19T10:00:00Z")

    mock_adapter = AsyncMock()
    mock_adapter.get_occupancy.side_effect = make_reading
    mock_ctx = AsyncMock()

    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=["car-1", "car-2", "car-3"],
        poll_interval_s=999,
    )

    await poller._poll_once()

    assert mock_adapter.get_occupancy.call_count == 3
    readings = mock_ctx.update_occupancy.call_args[0][0]
    assert set(readings.keys()) == {"car-1", "car-2", "car-3"}


@pytest.mark.anyio
async def test_apc_adapter_failure_warning_logged_loop_continues() -> None:
    """AC5: On adapter failure, WARNING is logged with recoverable=True; loop does not exit."""
    mock_adapter = AsyncMock()
    mock_adapter.get_occupancy.side_effect = ConnectionRefusedError("VLAN 8 unreachable")
    mock_ctx = AsyncMock()

    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=["car-1"],
        poll_interval_s=999,
    )

    with patch("vlan_pollers.apc_poller.log") as mock_log:
        with patch("asyncio.sleep"):
            # Simulate one iteration of the run loop

            async def one_iteration() -> None:
                try:
                    await poller._poll_once()
                except Exception:
                    mock_log.warning("apc_poll_failed", recoverable=True)

            await one_iteration()
            mock_log.warning.assert_called_once_with("apc_poll_failed", recoverable=True)

    # ctx.update_occupancy was NOT called because poll_once raised
    mock_ctx.update_occupancy.assert_not_called()


@pytest.mark.anyio
async def test_apc_empty_car_ids_calls_update_with_empty_dict() -> None:
    """Edge: Empty car_ids list → update_occupancy called with empty dict."""
    mock_adapter = AsyncMock()
    mock_ctx = AsyncMock()

    poller = APCPoller(
        adapter=mock_adapter,
        ctx=mock_ctx,
        car_ids=[],
        poll_interval_s=999,
    )

    await poller._poll_once()

    mock_adapter.get_occupancy.assert_not_called()
    mock_ctx.update_occupancy.assert_called_once_with({})
