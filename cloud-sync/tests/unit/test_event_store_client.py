"""EventStoreClient — pull + ack_cursor + cursor drift handling."""
from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from cloud_sync.config import Settings
from cloud_sync.event_store_client import EventStoreClient


@pytest.mark.unit
@respx.mock
async def test_pull_sends_api_key_header() -> None:
    """X-API-Key header is included when api_key is configured."""
    settings = Settings(
        event_store_url="http://event-store-test",
        event_store_api_key=SecretStr("test-key"),
    )
    route = respx.get("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(
            200, json={"data": [], "count": 0, "journey_id": None, "next_cursor": None}
        )
    )
    async with httpx.AsyncClient() as http_client:
        client = EventStoreClient(http_client, settings)
        await client.pull(after_event_id=None, limit=10)
    assert route.calls.last.request.headers.get("X-API-Key") == "test-key"


@pytest.mark.unit
@respx.mock
async def test_pull_omits_header_when_no_api_key() -> None:
    settings = Settings(event_store_url="http://event-store-test")
    respx.get("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(
            200, json={"data": [], "count": 0, "journey_id": None, "next_cursor": None}
        )
    )
    async with httpx.AsyncClient() as http_client:
        client = EventStoreClient(http_client, settings)
        await client.pull(after_event_id=None, limit=10)
    # Last request didn't include X-API-Key.
    headers = respx.calls.last.request.headers
    assert "X-API-Key" not in headers and "x-api-key" not in headers


@pytest.mark.unit
@respx.mock
async def test_pull_passes_after_cursor_when_provided() -> None:
    settings = Settings(event_store_url="http://event-store-test")
    respx.get("http://event-store-test/api/v1/events").mock(
        return_value=httpx.Response(
            200, json={"data": [], "count": 0, "journey_id": None, "next_cursor": None}
        )
    )
    async with httpx.AsyncClient() as http_client:
        client = EventStoreClient(http_client, settings)
        await client.pull(after_event_id="abc-123", limit=50)
    req = respx.calls.last.request
    assert req.url.params.get("after") == "abc-123"
    assert req.url.params.get("limit") == "50"


@pytest.mark.unit
@respx.mock
async def test_ack_cursor_returns_event_store_body() -> None:
    settings = Settings(event_store_url="http://event-store-test")
    respx.post("http://event-store-test/api/v1/sync/cursor").mock(
        return_value=httpx.Response(
            200, json={"data": {"acked": "abc-123", "truncated_journeys": 2}}
        )
    )
    async with httpx.AsyncClient() as http_client:
        client = EventStoreClient(http_client, settings)
        body = await client.ack_cursor("abc-123")
    assert body == {"data": {"acked": "abc-123", "truncated_journeys": 2}}


@pytest.mark.unit
@respx.mock
async def test_ack_cursor_400_returns_acked_none() -> None:
    """When event-store returns 400 INVALID_CURSOR, we log + return acked=None
    so the ack_loop can skip the advance without raising."""
    settings = Settings(event_store_url="http://event-store-test")
    respx.post("http://event-store-test/api/v1/sync/cursor").mock(
        return_value=httpx.Response(
            400,
            json={
                "detail": {
                    "error": "INVALID_CURSOR",
                    "detail": "event_id not found",
                    "recoverable": False,
                }
            },
        )
    )
    async with httpx.AsyncClient() as http_client:
        client = EventStoreClient(http_client, settings)
        body = await client.ack_cursor("stale-cursor")
    assert body["data"]["acked"] is None
    assert body["data"]["truncated_journeys"] == 0
