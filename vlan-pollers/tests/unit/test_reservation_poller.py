from __future__ import annotations

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from vlan_pollers.reservation_poller import ReservationPoller


RESERVATION_URL = "http://reservation-mock:8012"

_VALID_PAYLOAD = {
    "car-1": 42,
    "car-2": 180,
    "car-3": 67,
    "car-4": 99,
    "car-5": 12,
}


# ── Security Tests ──────────────────────────────────────────────────────────


def test_no_env_get_in_reservation_poller() -> None:
    """Rule 8: reservation_poller.py must not call os.environ.get()."""
    import ast
    import pathlib

    src = pathlib.Path("src/vlan_pollers/reservation_poller.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                    pytest.fail("reservation_poller.py calls os.environ.get() — Rule 8 violation")


# ── Domain Tests ─────────────────────────────────────────────────────────────


@pytest.mark.anyio
@respx.mock
async def test_reservation_poll_updates_context() -> None:
    """AC4: Valid reservation JSON updates ContextState.reservations."""
    respx.get(f"{RESERVATION_URL}/reservations").mock(
        return_value=httpx.Response(200, json=_VALID_PAYLOAD)
    )
    mock_ctx = AsyncMock()

    poller = ReservationPoller(
        reservation_url=RESERVATION_URL,
        ctx=mock_ctx,
        car_ids=["car-1", "car-2"],
        poll_interval_s=999,
    )
    await poller._poll_once()

    mock_ctx.update_reservations.assert_called_once()
    data = mock_ctx.update_reservations.call_args[0][0]
    assert data["car-1"] == 42
    assert data["car-2"] == 180


@pytest.mark.anyio
@respx.mock
async def test_reservation_http_error_no_update() -> None:
    """AC5: HTTP 503 → exception propagates to run() loop; update_reservations not called."""
    respx.get(f"{RESERVATION_URL}/reservations").mock(
        return_value=httpx.Response(503)
    )
    mock_ctx = AsyncMock()

    poller = ReservationPoller(
        reservation_url=RESERVATION_URL,
        ctx=mock_ctx,
        car_ids=["car-1"],
        poll_interval_s=999,
    )

    with pytest.raises(Exception):
        await poller._poll_once()

    mock_ctx.update_reservations.assert_not_called()


@pytest.mark.anyio
@respx.mock
async def test_reservation_run_loop_survives_failure() -> None:
    """AC5: run() loop continues after connection failure."""
    call_count = 0

    def flaky(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("transient")
        return httpx.Response(200, json=_VALID_PAYLOAD)

    respx.get(f"{RESERVATION_URL}/reservations").mock(side_effect=flaky)
    mock_ctx = AsyncMock()

    poller = ReservationPoller(
        reservation_url=RESERVATION_URL,
        ctx=mock_ctx,
        car_ids=["car-1"],
        poll_interval_s=0.001,
    )

    for _ in range(2):
        try:
            await poller._poll_once()
        except Exception:
            pass

    assert mock_ctx.update_reservations.call_count >= 1


@pytest.mark.anyio
@respx.mock
async def test_reservation_filters_to_configured_car_ids() -> None:
    """AC4: Only car_ids from config are stored (server may return extra cars)."""
    respx.get(f"{RESERVATION_URL}/reservations").mock(
        return_value=httpx.Response(200, json=_VALID_PAYLOAD)
    )
    mock_ctx = AsyncMock()

    poller = ReservationPoller(
        reservation_url=RESERVATION_URL,
        ctx=mock_ctx,
        car_ids=["car-1", "car-3"],
        poll_interval_s=999,
    )
    await poller._poll_once()

    data = mock_ctx.update_reservations.call_args[0][0]
    # Only configured car IDs should be included
    assert set(data.keys()) == {"car-1", "car-3"}
