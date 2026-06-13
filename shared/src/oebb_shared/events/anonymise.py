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

# Pass-through-safe: structured operational/telemetry events that carry no
# per-person identity (aggregate counts, camera-health, alert metadata, journey
# lifecycle, kill-switch audit). Listed EXPLICITLY so the egress boundary fails
# CLOSED — a new event type is not cloud-safe until it is consciously placed in
# one of these policy buckets. test_every_event_type_has_an_egress_policy pins
# this: adding an EventType without a policy entry fails CI. (Round-2 P3.)
_PASS_THROUGH_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "OCCUPANCY_UPDATE",
        "OCCUPANCY_THRESHOLD_CROSSED",
        "ALERT_RAISED",
        "ALERT_RESOLVED",
        "VESTIBULE_CONGESTION",
        "LUGGAGE_RACK_SATURATION",
        "ALARM_ACTIVE",
        "ALARM_CLEARED",
        "JOURNEY_STARTED",
        "JOURNEY_ENDED",
        "CAMERA_DEGRADED",
        "CAMERA_RECOVERED",
        "SYNC_COMPLETED",
        "LEDGER_DRIFT_OBSERVATION",
        "CALIBRATION_DRIFT",
        "COACH_COMFORT_INDEX",
        "INFERENCE_HEARTBEAT",
        "ALERT_CLASS_DISABLED",
        "ALERT_CLASS_REENABLED",
        "STREAM_PRIORITY",
    }
)

# event_type → payload keys to delete on egress (pixel / camera locality).
# camera_id is dropped from every track-bearing event: it ties the tokenised
# person to a precise on-train location and is the re-identification vector the
# tokeniser otherwise closes (no cloud consumer reads it).
_DROP_FIELDS: dict[str, tuple[str, ...]] = {
    "UNATTENDED_BAG": ("bbox", "camera_id"),
    "DOOR_OBSTRUCTION": ("camera_id",),
    "WAGON_EXIT": ("camera_id",),
    "WAGON_ENTRY": ("camera_id",),
}

# event_type → track-id payload key to tokenise on egress.
_TOKENISE_TRACK_ID: frozenset[str] = frozenset(
    {"UNATTENDED_BAG", "DOOR_OBSTRUCTION", "WAGON_EXIT", "WAGON_ENTRY"}
)

# Length of the hex token. 16 hex chars = 64 bits — collision-negligible across
# a full multi-camera journey's track count (32 bits birthday-collided ~50% at
# ~77k tracks), still short enough to read on an operator card.
_TOKEN_LEN = 16

# Replacement marker for fields whose value referenced a withheld person.
_REDACTED = "redacted"

# Event types that ARE redacted in-place by this module (field-drop, track_id
# tokenisation, or the RAMP_DEPLOYED back-reference blank). Derived from the
# policy tables so the three never drift out of sync.
_REDACT_IN_PLACE_EVENT_TYPES: frozenset[str] = (
    frozenset(_DROP_FIELDS) | _TOKENISE_TRACK_ID | frozenset({"RAMP_DEPLOYED"})
)

# Every event type the egress boundary knows how to make cloud-safe. Anything
# NOT in this set is withheld (fail closed) — see anonymise_envelope.
_KNOWN_EVENT_TYPES: frozenset[str] = (
    _DROP_EVENT_TYPES | _PASS_THROUGH_EVENT_TYPES | _REDACT_IN_PLACE_EVENT_TYPES
)


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

    Fails CLOSED: an event type with no explicit egress policy is withheld, so a
    new PII-bearing type cannot leak to the cloud by default. (Round-2 P3.)
    """
    event_type = envelope.get("event_type")
    if event_type in _DROP_EVENT_TYPES:
        return None
    if event_type not in _KNOWN_EVENT_TYPES:
        # Unclassified — withhold rather than pass raw. Add it to a policy bucket
        # (pass-through, drop-fields, tokenise, or drop-event) to release it.
        return None

    # Shallow-copy the envelope, deep-copy only the payload we may rewrite so we
    # never mutate the caller's dict (the local store keeps full fidelity).
    redacted = dict(envelope)
    payload = dict(envelope.get("payload") or {})
    journey_id = str(envelope.get("journey_id", ""))

    for key in _DROP_FIELDS.get(event_type, ()):
        payload.pop(key, None)

    if event_type in _TOKENISE_TRACK_ID and "track_id" in payload:
        payload["track_id"] = _token(secret, journey_id, payload["track_id"])

    if event_type == "RAMP_DEPLOYED" and "triggered_by_track_id" in payload:
        payload["triggered_by_track_id"] = _REDACTED

    redacted["payload"] = payload
    return redacted
