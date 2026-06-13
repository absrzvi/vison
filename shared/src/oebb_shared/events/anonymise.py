"""Edge-boundary anonymisation for event envelopes.

This is the single transform that makes the "anonymised at the edge / structured
results only, raw video never leaves the train" privacy invariant true on the
wire. It runs at the train→cloud egress (event-store ``GET /api/v1/events``,
the path cloud-sync pulls) — NOT on ingest, NOT on the on-train ``/ws`` fan-out,
and NOT in cloud-sync (which stays pure transport). On-train fusion/ledger and
the ramp/accessibility correlation keep the full-fidelity payload because they
read from the local store and the WS path, both upstream of this function.

Policy (rationale in privacy notes / DPIA-pending):
  * ACCESSIBILITY_DETECTED is dropped entirely. ``assistance_type`` bound to a
    singled-out ``track_id`` is GDPR Article 9 special-category (health) data;
    no lawful basis + DPIA exists yet, so it must not cross the boundary. The
    on-train ramp/staff workflow is unaffected (it never reads from the cloud).
  * RAMP_DEPLOYED.triggered_by_track_id is blanked — it back-references the
    accessibility track we just dropped.
  * track_id on UNATTENDED_BAG / DOOR_OBSTRUCTION (str) and WAGON_EXIT /
    WAGON_ENTRY (int) becomes a short keyed HMAC token. Concurrent alerts stay
    distinguishable to operators; no stable cross-event person identifier
    leaves the train. The token is salted with journey_id so the same edge
    track_id in two journeys yields different tokens.
  * bbox (pixel coordinates) and camera_id are dropped from the safety events —
    no cloud consumer reads them, and they narrow the field for re-identifying
    an individual frame.

Returns a NEW redacted envelope dict, or ``None`` when the whole event must be
withheld from the cloud. The input dict is never mutated.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

# Events withheld from the cloud entirely (special-category / no lawful basis).
_DROP_EVENT_TYPES: frozenset[str] = frozenset({"ACCESSIBILITY_DETECTED"})

# event_type → payload keys to delete on egress (pixel / camera locality).
_DROP_FIELDS: dict[str, tuple[str, ...]] = {
    "UNATTENDED_BAG": ("bbox", "camera_id"),
    "DOOR_OBSTRUCTION": ("camera_id",),
}

# event_type → track-id payload key to tokenise on egress.
_TOKENISE_TRACK_ID: frozenset[str] = frozenset(
    {"UNATTENDED_BAG", "DOOR_OBSTRUCTION", "WAGON_EXIT", "WAGON_ENTRY"}
)

# Length of the hex token. 8 hex chars = 32 bits — enough to keep concurrent
# alerts on one journey distinct, short enough to read on an operator card.
_TOKEN_LEN = 8

# Replacement marker for fields whose value referenced a withheld person.
_REDACTED = "redacted"


def _token(secret: bytes, journey_id: str, track_id: object) -> str:
    """Deterministic short opaque token for a track_id within a journey.

    Keyed HMAC so the mapping cannot be reversed or precomputed without the
    secret; salted with journey_id so a track_id is not a cross-journey
    identifier. Stable for a given (secret, journey_id, track_id) so two events
    about the same track in one journey share a token.
    """
    msg = f"{journey_id}:{track_id}".encode()
    digest = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return f"tk_{digest[:_TOKEN_LEN]}"


def anonymise_envelope(
    envelope: dict[str, Any], *, secret: bytes
) -> dict[str, Any] | None:
    """Return a cloud-safe copy of ``envelope``, or ``None`` to withhold it.

    ``secret`` keys the track_id tokeniser; it must never leave the edge and is
    not derivable from the emitted tokens. A no-op (deep-copied) envelope is
    returned for event types that carry no person-level PII.
    """
    event_type = envelope.get("event_type")
    if event_type in _DROP_EVENT_TYPES:
        return None

    # Shallow-copy the envelope, deep-copy only the payload we may rewrite so we
    # never mutate the caller's dict (the local store keeps full fidelity).
    redacted = dict(envelope)
    payload = dict(envelope.get("payload") or {})
    journey_id = str(envelope.get("journey_id", ""))

    for key in _DROP_FIELDS.get(event_type, ()):  # type: ignore[arg-type]
        payload.pop(key, None)

    if event_type in _TOKENISE_TRACK_ID and "track_id" in payload:
        payload["track_id"] = _token(secret, journey_id, payload["track_id"])

    if event_type == "RAMP_DEPLOYED" and "triggered_by_track_id" in payload:
        payload["triggered_by_track_id"] = _REDACTED

    redacted["payload"] = payload
    return redacted
