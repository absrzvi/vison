"""POST /api/v1/sync/cursor — cloud-sync companion endpoint (story 4-CS1).

Cloud-sync calls this when it has confirmed a contiguous prefix of events
has reached the landside Mosquitto broker. The endpoint:

  1. Verifies ``last_event_id`` exists in the events table (else 400
     INVALID_CURSOR — same shape as the GET /events cursor handling).
  2. If ``last_event_id == get_sync_cursor(conn)`` → idempotent no-op,
     returns 200 with ``truncated_journeys=0``.
  3. Otherwise: ``advance_cursor`` + ``truncate_old_journeys(retain=N)``.
  4. Returns ``{"data": {"acked": <id>, "truncated_journeys": N}}``.

Auth-gated by ``Depends(require_api_key)`` like the rest of /api/v1/*.
"""
from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import require_api_key
from ..config import settings as settings_module  # noqa: F401  (kept for future deps)
from ..database import get_sync_cursor
from ..deps import get_db
from ..sync.cursor import advance_cursor, truncate_old_journeys

router = APIRouter(prefix="/api/v1/sync", dependencies=[Depends(require_api_key)])

_UUID_REGEX = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
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
    """Advance sync_state cursor + run truncation."""
    # 1. Verify the cursor event actually exists.
    row = conn.execute(
        "SELECT 1 FROM events WHERE event_id = ?", (body.last_event_id,)
    ).fetchone()
    if row is None:
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
        return {
            "data": {
                "acked": body.last_event_id,
                "truncated_journeys": 0,
            }
        }

    # 3. Advance + truncate.
    advance_cursor(conn, body.last_event_id)
    truncated = truncate_old_journeys(conn, retain=3)
    return {
        "data": {
            "acked": body.last_event_id,
            "truncated_journeys": truncated,
        }
    }
