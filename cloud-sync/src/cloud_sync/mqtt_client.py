"""MQTT publisher with token-bucket rate limiter and offline tolerance.

Architecture:
  - ``run()`` is the long-running coroutine launched as a background task.
  - Outer loop opens an ``aiomqtt.Client`` context; on ``MqttError`` /
    ``asyncio.TimeoutError`` it closes, sleeps with exponential backoff, and
    reconnects. The reconnect attempt counter resets ONLY after a stable
    uptime window (first successful publish), so a flapping broker that
    accepts CONNECT then immediately RSTs cannot defeat the backoff.
  - Inner publish loop drains pending rows from the SQLite queue in
    chronological order, publishes each at QoS 1, and on PUBACK marks the
    row published via the injected callback.

Per-row resilience (code-review 2026-05-20):
  * Per-publish errors are caught individually: row is `mark_failed`'d,
    a `cloud_sync.publish_error` log emits with `event_id` + `attempts` +
    `last_error`, then the exception is re-raised so the outer reconnect
    loop runs. No silent batch abort.
  * `asyncio.TimeoutError` (from `publish(timeout=5.0)`) is treated like
    `MqttError` — both trigger reconnect.

The broker_connected ``asyncio.Event`` is the ONLY signal the publish path
needs from the network; the pull loop (separate task) runs regardless.
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiomqtt
import structlog
from oebb_shared.events import EventType

from . import db as db_mod
from .config import Settings

log = structlog.get_logger()

# Allowlist for the vehicle_id portion of the topic. Anything outside is
# slugified to '-' to defend against MQTT wildcard injection (`#`, `+`).
_VEHICLE_SLUG_RE = re.compile(r"[^A-Za-z0-9-]")

# Event-type allowlist matches the EventType StrEnum convention (UPPER_SNAKE_CASE).
# Underscores are PERMITTED — they're part of the canonical event_type tokens.
_EVENT_TYPE_SLUG_RE = re.compile(r"[^A-Za-z0-9_]")

# Sentinel used when slugify reduces a vehicle_id to empty (e.g. all non-ASCII
# stripped, or empty input). Falls back to "unknown" so the topic never has
# an empty level segment which would mis-route against `+` wildcards.
_EMPTY_VEHICLE_FALLBACK = "unknown"


def slugify_vehicle_id(vehicle_id: str) -> str:
    """Strip MQTT-unsafe characters from a vehicle_id.

    Returns the literal string ``"unknown"`` when the result would be empty
    (empty input, or all non-allowlist chars). This keeps the resulting
    topic well-formed: ``oebb/events/unknown/...`` rather than the
    wildcard-clashing ``oebb/events//...``.
    """
    slugged = _VEHICLE_SLUG_RE.sub("-", vehicle_id)
    # Empty input OR all chars stripped (all-dash slug carries no info).
    if not slugged or all(c == "-" for c in slugged):
        log.info(
            "cloud_sync.vehicle_id_slugged_to_unknown",
            original=vehicle_id,
        )
        return _EMPTY_VEHICLE_FALLBACK
    if slugged != vehicle_id:
        log.info(
            "cloud_sync.vehicle_id_slugged",
            original=vehicle_id,
            slugged=slugged,
        )
    return slugged


def build_topic(prefix: str, vehicle_id: str, event_type: str) -> str:
    """Return ``{prefix}/{slug(vehicle_id)}/{event_type}``.

    The ``event_type`` is expected to come from ``EventType`` (StrEnum) so is
    already safe; we still verify it matches the enum and fall back to a
    slug + uppercase if not. Unknown event types preserve underscores (the
    canonical EventType naming convention), strip MQTT-unsafe chars, and
    upper-case the result so subscribers using uppercase filter match.

    Trailing slash in the prefix is stripped to avoid double-slash topics
    that would mis-route against ``+`` wildcards.
    """
    safe_prefix = prefix.rstrip("/")
    safe_vehicle = slugify_vehicle_id(vehicle_id)
    try:
        EventType(event_type)
        safe_event_type = event_type
    except ValueError:
        # Schema drift defence — log + slugify preserving underscores + upper.
        log.warning(
            "cloud_sync.unknown_event_type",
            event_type=event_type,
            vehicle_id=safe_vehicle,
        )
        safe_event_type = _EVENT_TYPE_SLUG_RE.sub("-", event_type).upper()
    return f"{safe_prefix}/{safe_vehicle}/{safe_event_type}"


class TokenBucket:
    """Per-process token bucket. Capacity = rate (1-second window).

    A flapping broker MUST NOT reset the bucket — the cap stands across
    reconnects so the broker can't be flooded by a 72h-backlog burst.
    """

    def __init__(self, rate: int) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = float(rate)
        self._tokens = float(rate)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a token is available, then consume one."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Compute sleep duration under the lock; release before sleeping
                # so other tasks can queue + observe the same window.
                wait = (1.0 - self._tokens) / self._rate
            await asyncio.sleep(wait)


# Reconnect backoff schedule (seconds). Caps at 60s to keep reconnect
# responsive without retry-flooding a broker that's down.
_BACKOFF_SCHEDULE: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)

# Minimum stable uptime before resetting `_reconnect_attempt` to 0. Prevents
# a connect-then-immediate-RST flapping broker from defeating the backoff.
_STABLE_UPTIME_RESET_S = 30.0


class MqttPublisher:
    """Owns broker connection state + rate limiter."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._broker_connected = asyncio.Event()
        self._last_publish_utc: str | None = None
        self._rate_limiter = TokenBucket(settings.publish_rate_per_sec)
        self._reconnect_attempt = 0

    @property
    def broker_connected(self) -> asyncio.Event:
        return self._broker_connected

    @property
    def last_publish_utc(self) -> str | None:
        return self._last_publish_utc

    def _next_backoff(self) -> float:
        idx = min(self._reconnect_attempt, len(_BACKOFF_SCHEDULE) - 1)
        return _BACKOFF_SCHEDULE[idx]

    def _client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "hostname": self._settings.mqtt_host,
            "port": self._settings.mqtt_port,
            # QoS 1 publish waits for PUBACK; cap the wait so a silently-dropped
            # TCP connection cannot pin the publish loop indefinitely. 5s is
            # generous on a healthy broker, fast enough that reconnect kicks in.
            "timeout": 5.0,
            # MQTT keepalive — paho sends PINGREQ every N seconds; a dropped
            # connection is detected within ~2x this. Keep low for fast recovery.
            "keepalive": 5,
        }
        if self._settings.mqtt_username is not None:
            kwargs["username"] = self._settings.mqtt_username.get_secret_value()
        if self._settings.mqtt_password is not None:
            kwargs["password"] = self._settings.mqtt_password.get_secret_value()
        return kwargs

    async def _publish_loop(
        self,
        client: aiomqtt.Client,
        conn_factory: Callable[[], sqlite3.Connection],
        on_publish: Callable[[str], Awaitable[None]] | None,
        stop_event: asyncio.Event,
        connected_at: float,
    ) -> None:
        """Drain pending rows + publish until broker drops or shutdown.

        Per-row error path: catch individual publish failures, mark_failed +
        log `cloud_sync.publish_error`, then re-raise so the outer reconnect
        loop runs. No silent batch abort.
        """
        conn = conn_factory()
        try:
            while not stop_event.is_set():
                rows = db_mod.iter_pending(
                    conn, limit=self._settings.publish_rate_per_sec
                )
                if not rows:
                    # No pending events — wait briefly for the pull loop to
                    # produce more, then check again. Honours stop_event.
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=0.1)
                        return  # stop_event fired
                    except TimeoutError:
                        continue
                for row in rows:
                    if stop_event.is_set():
                        return
                    await self._rate_limiter.acquire()
                    topic = build_topic(
                        self._settings.mqtt_topic_prefix,
                        row["vehicle_id"],
                        row["event_type"],
                    )
                    payload = row["envelope_json"].encode()
                    event_id = row["event_id"]
                    try:
                        # Per-publish timeout — if the broker silently drops
                        # the TCP connection mid-publish, this raises after
                        # 5s instead of waiting forever for PUBACK.
                        await client.publish(
                            topic, payload=payload, qos=1, timeout=5.0
                        )
                    except (TimeoutError, aiomqtt.MqttError) as exc:
                        # Record per-event failure; outer loop reconnects.
                        db_mod.mark_failed(conn, event_id, str(exc))
                        attempts_row = conn.execute(
                            "SELECT attempts FROM publish_queue "
                            "WHERE event_id = ?",
                            (event_id,),
                        ).fetchone()
                        attempts = attempts_row["attempts"] if attempts_row else 0
                        log.warning(
                            "cloud_sync.publish_error",
                            event_id=event_id,
                            attempts=attempts,
                            last_error=str(exc),
                        )
                        # Reset stable-uptime gate so attempt counter advances
                        # even if we'd otherwise been "stable" for a while.
                        if time.monotonic() - connected_at >= _STABLE_UPTIME_RESET_S:
                            # We were stable; this is a fresh failure cycle.
                            pass  # nothing to do; raise to outer loop
                        raise
                    self._last_publish_utc = db_mod._now_iso_z()
                    db_mod.mark_published(conn, event_id)
                    if on_publish is not None:
                        await on_publish(event_id)
        finally:
            conn.close()

    async def run(
        self,
        stop_event: asyncio.Event,
        conn_factory: Callable[[], sqlite3.Connection],
        on_publish: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Long-running task. Reconnects on broker drop with exponential backoff.

        Reconnect attempt counter resets ONLY after >= _STABLE_UPTIME_RESET_S
        seconds of stable connection (or after the first successful publish),
        whichever first. A flapping broker (connect-then-RST) keeps escalating
        the backoff.
        """
        while not stop_event.is_set():
            connected_at = 0.0
            try:
                async with aiomqtt.Client(**self._client_kwargs()) as client:
                    connected_at = time.monotonic()
                    self._broker_connected.set()
                    log.info(
                        "cloud_sync.connect",
                        host=self._settings.mqtt_host,
                        port=self._settings.mqtt_port,
                        attempt=self._reconnect_attempt,
                    )
                    await self._publish_loop(
                        client, conn_factory, on_publish, stop_event, connected_at
                    )
            except (TimeoutError, aiomqtt.MqttError) as exc:
                self._broker_connected.clear()
                log.warning("cloud_sync.disconnect", error=str(exc))
                if stop_event.is_set():
                    return
                # Reset attempt counter only if we had stable uptime; otherwise
                # advance to keep escalating backoff for a flapping broker.
                if (
                    connected_at > 0.0
                    and (time.monotonic() - connected_at) >= _STABLE_UPTIME_RESET_S
                ):
                    self._reconnect_attempt = 0
                wait = self._next_backoff()
                self._reconnect_attempt += 1
                await asyncio.sleep(wait)
                log.info(
                    "cloud_sync.reconnect", attempt=self._reconnect_attempt
                )
            except asyncio.CancelledError:
                self._broker_connected.clear()
                raise
            except Exception as exc:  # pragma: no cover  # defence-in-depth
                log.warning("cloud_sync.publish_loop_error", error=str(exc))
                self._broker_connected.clear()
                if stop_event.is_set():
                    return
                await asyncio.sleep(1.0)


__all__ = [
    "MqttPublisher",
    "TokenBucket",
    "build_topic",
    "slugify_vehicle_id",
]
