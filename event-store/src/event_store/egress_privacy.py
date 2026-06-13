"""Edge-egress anonymisation for the cloud-sync pull path.

The on-train store keeps full-fidelity events (fusion/ledger and the WS fan-out
read them). The ONLY path off the train is ``GET /api/v1/events``, which
cloud-sync polls. ``anonymise_page`` is applied there so every envelope that
leaves the edge is redacted per ``oebb_shared.events.anonymise`` — making the
"anonymised at the edge" privacy claim true on the wire.

The HMAC key that salts the track_id tokeniser comes from ``EVENT_STORE_ANONYMISE_KEY``.
When unset we fall back to a fixed dev key and emit a startup WARN (cloud egress
is still anonymised — the tokens just aren't secret in dev).
"""
from __future__ import annotations

from typing import Any

from oebb_shared.events import anonymise_envelope

from .config import settings

# Fixed dev key — used only when EVENT_STORE_ANONYMISE_KEY is unset. Tokens are
# still opaque and stable; they are simply not secret. Production MUST set the
# env var (a startup WARN in main.py flags the dev-mode fallback).
_DEV_KEY = b"event-store-dev-anonymise-key"


def egress_key() -> bytes:
    """Return the HMAC key for track_id tokenisation (config or dev fallback)."""
    configured = settings.anonymise_key
    if configured is None:
        return _DEV_KEY
    return configured.get_secret_value().encode()


def anonymise_page(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Redact a page of event envelopes for the cloud. Drops withheld events
    (e.g. ACCESSIBILITY_DETECTED) entirely."""
    key = egress_key()
    out: list[dict[str, Any]] = []
    for row in rows:
        redacted = anonymise_envelope(row, secret=key)
        if redacted is not None:
            out.append(redacted)
    return out
