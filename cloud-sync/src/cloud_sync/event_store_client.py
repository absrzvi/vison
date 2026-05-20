"""HTTP client for the onboard event-store.

cloud-sync NEVER opens event-store's SQLite file directly (ADR-4 single
writer). All reads come through ``GET /api/v1/events?after=...``; cursor
advancement is via the companion ``POST /api/v1/sync/cursor`` endpoint.

Uses ``oebb_shared.http.retry.DEFAULT_RETRY`` (5 attempts, exponential
backoff) — matches fusion/inference convention.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from oebb_shared.http.retry import DEFAULT_RETRY

from .config import Settings

log = structlog.get_logger()


@dataclass
class EventPage:
    """Lightweight projection of event-store's ``EventPage`` response."""

    data: list[dict[str, Any]]
    next_cursor: str | None
    count: int


class EventStoreClient:
    """Thin async wrapper. Tests inject a custom ``httpx.AsyncClient`` (respx)."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def _headers(self) -> dict[str, str]:
        if self._settings.event_store_api_key is None:
            return {}
        return {"X-API-Key": self._settings.event_store_api_key.get_secret_value()}

    @DEFAULT_RETRY
    async def pull(
        self, *, after_event_id: str | None, limit: int
    ) -> EventPage:
        """GET /api/v1/events?after=...&limit=..."""
        params: dict[str, str | int] = {"limit": limit}
        if after_event_id:
            params["after"] = after_event_id
        resp = await self._client.get(
            f"{self._settings.event_store_url}/api/v1/events",
            params=params,
            headers=self._headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
        body = resp.json()
        return EventPage(
            data=list(body.get("data", [])),
            next_cursor=body.get("next_cursor"),
            count=int(body.get("count", 0)),
        )

    @DEFAULT_RETRY
    async def ack_cursor(self, last_event_id: str) -> dict[str, Any]:
        """POST /api/v1/sync/cursor with the last successfully-published id.

        Event-store advances ``sync_state.last_synced_event_id`` and runs
        ``truncate_old_journeys(retain=N)``. Returns the response body.
        """
        resp = await self._client.post(
            f"{self._settings.event_store_url}/api/v1/sync/cursor",
            json={"last_event_id": last_event_id},
            headers=self._headers(),
            timeout=10.0,
        )
        if resp.status_code == 400:
            # Cursor drift — event-store doesn't know this id. Log + skip.
            log.warning(
                "cloud_sync.ack_cursor_drift",
                last_event_id=last_event_id,
                detail=resp.text,
            )
            return {"data": {"acked": None, "truncated_journeys": 0}}
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body
