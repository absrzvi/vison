"""POST /api/v1/sync/cursor — cloud-sync companion endpoint (story 4-CS1).

Cloud-sync calls this when it has confirmed a contiguous prefix of events
has reached the landside Mosquitto broker. The endpoint:

  1. Opens an IMMEDIATE transaction so concurrent ACK POSTs serialise
     instead of racing the existence check + advance + truncate sequence
     (code-review patch 2026-05-20).
  2. Verifies ``last_event_id`` exists in the events table (else 400
     INVALID_CURSOR — same shape as the GET /events cursor handling).
  3. If ``last_event_id == get_sync_cursor(conn)`` → idempotent no-op,
     returns 200 with ``truncated_journeys=0``.
  4. Otherwise: ``advance_cursor`` + ``truncate_old_journeys(retain=N)``.
  5. Returns ``{"data": {"acked": <id>, "truncated_journeys": N}}``.

UUID regex is case-INSENSITIVE per RFC 4122 (code-review patch).
Auth-gated by ``Depends(require_api_key)`` like the rest of /api/v1/*.
"""
from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import require_api_key
from ..database import get_sync_cursor
from ..deps import get_db
from ..sync.cursor import advance_cursor, truncate_old_journeys

router = APIRouter(prefix="/api/v1/sync", dependencies=[Depends(require_api_key)])

# RFC 4122 says UUIDs are case-insensitive; accept both.
_UUID_REGEX = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


class CursorAdvanceRequest(BaseModel):
    """Body for POST /api/v1/sync/cursor."""

    model_config = ConfigDict(extra="forbid")

    last_event_id: Annotated[str, Field(pattern=_UUID_REGEX)]


@router.post("/cursor")
def advance_sync_cursor_endpoint(
    body: CursorAdvanceRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, object]:
    """Advance sync_state cursor + run truncation.

    Wrapped in a SQLite IMMEDIATE transaction so concurrent POSTs cannot
    interleave the existence check / advance / truncate sequence.
    """
    # Begin IMMEDIATE: acquire the RESERVED lock now, blocking any other
    # writer until we commit. Critical for the race-free advance + truncate
    # sequence (code-review patch 2026-05-20).
    conn.execute("BEGIN IMMEDIATE")
    try:
        # 1. Verify the cursor event actually exists.
        row = conn.execute(
            "SELECT 1 FROM events WHERE event_id = ?", (body.last_event_id,)
        ).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_CURSOR",
                    "detail": f"event_id not found: {body.last_event_id}",
                    "recoverable": False,
                },
            )

        # 2. Idempotency: same id as current cursor → no-op.
        current = get_sync_cursor(conn)
        if current == body.last_event_id:
            conn.execute("ROLLBACK")
            return {
                "data": {
                    "acked": body.last_event_id,
                    "truncated_journeys": 0,
                }
            }

        # 3. Advance + truncate. Both helpers commit; the outer transaction
        # batches them under the same write lock so a second concurrent
        # POST sees the post-advance state.
        advance_cursor(conn, body.last_event_id)
        truncated = truncate_old_journeys(conn, retain=3)
    except HTTPException:
        raise
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    return {
        "data": {
            "acked": body.last_event_id,
            "truncated_journeys": truncated,
        }
    }
