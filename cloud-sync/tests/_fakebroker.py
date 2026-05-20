"""Minimal asyncio MQTT 3.1.1 broker for integration tests.

Implements only what aiomqtt's publish-with-QoS-1 needs:
  * CONNECT  → CONNACK (return code 0)
  * PUBLISH  (QoS 1) → PUBACK
  * PINGREQ  → PINGRESP
  * SUBSCRIBE → SUBACK (accepted but no fan-out — cloud-sync only publishes)
  * DISCONNECT

Captures every received PUBLISH in ``received`` (a list of (topic, payload)
tuples) so tests can assert on order and content.

``connectable: asyncio.Event``:
  * When SET (default): listener accepts; existing connections operate normally.
  * When CLEARED: listener refuses new connections AND existing connections are
    actively force-closed via ``go_offline()``. This drops aiomqtt's pending
    QoS 1 PUBACK wait so the publish loop sees ``MqttError`` immediately
    instead of timing out on keepalive.
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field

# MQTT 3.1.1 fixed-header types (high nibble).
_CONNECT = 0x10
_CONNACK = 0x20
_PUBLISH = 0x30
_PUBACK = 0x40
_SUBSCRIBE = 0x80
_SUBACK = 0x90
_PINGREQ = 0xC0
_PINGRESP = 0xD0
_DISCONNECT = 0xE0


async def _read_remaining_length(reader: asyncio.StreamReader) -> int:
    multiplier = 1
    value = 0
    for _ in range(4):
        b = await reader.readexactly(1)
        value += (b[0] & 0x7F) * multiplier
        if (b[0] & 0x80) == 0:
            return value
        multiplier *= 128
    raise ValueError("malformed remaining length")


@dataclass
class FakeBroker:
    host: str = "127.0.0.1"
    port: int = 0
    connectable: asyncio.Event = field(default_factory=asyncio.Event)
    received: list[tuple[str, bytes]] = field(default_factory=list)
    _server: asyncio.base_events.Server | None = None
    _bound_port: int = 0
    _active_writers: set[asyncio.StreamWriter] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.connectable.set()

    @property
    def actual_port(self) -> int:
        return self._bound_port

    async def __aenter__(self) -> FakeBroker:
        self._server = await asyncio.start_server(
            self._handle, host=self.host, port=self.port
        )
        sockets = self._server.sockets
        assert sockets, "fake broker bound no sockets"
        self._bound_port = sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        # Close all live connections then the server.
        for w in list(self._active_writers):
            try:
                w.close()
            except Exception:
                pass
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def go_offline(self) -> None:
        """Force-close all open connections and refuse new ones.

        Use this from tests to simulate a broker outage. The publish loop
        on the client will see ``MqttError`` on its next operation.
        """
        self.connectable.clear()
        for w in list(self._active_writers):
            try:
                w.close()
            except Exception:
                pass

    def go_online(self) -> None:
        """Resume accepting connections (existing closed ones won't recover)."""
        self.connectable.set()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if not self.connectable.is_set():
            writer.close()
            return
        self._active_writers.add(writer)
        try:
            while True:
                try:
                    header_byte = await reader.readexactly(1)
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    return
                packet_type = header_byte[0] & 0xF0
                qos = (header_byte[0] >> 1) & 0x03
                try:
                    remaining_length = await _read_remaining_length(reader)
                    body = await reader.readexactly(remaining_length) if remaining_length else b""
                except (asyncio.IncompleteReadError, ConnectionResetError):
                    return

                if not self.connectable.is_set():
                    return  # broker went offline mid-packet — drop connection

                if packet_type == _CONNECT:
                    writer.write(bytes([_CONNACK, 0x02, 0x00, 0x00]))
                    try:
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError):
                        return
                elif packet_type == _PUBLISH:
                    topic, payload, packet_id = self._parse_publish(body, qos)
                    self.received.append((topic, payload))
                    if qos == 1 and packet_id is not None:
                        writer.write(
                            bytes([_PUBACK, 0x02])
                            + struct.pack(">H", packet_id)
                        )
                        try:
                            await writer.drain()
                        except (ConnectionResetError, BrokenPipeError):
                            return
                elif packet_type == _SUBSCRIBE:
                    packet_id = struct.unpack(">H", body[:2])[0]
                    suback_payload = b"\x00"
                    writer.write(
                        bytes([_SUBACK, 0x02 + len(suback_payload)])
                        + struct.pack(">H", packet_id)
                        + suback_payload
                    )
                    try:
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError):
                        return
                elif packet_type == _PINGREQ:
                    writer.write(bytes([_PINGRESP, 0x00]))
                    try:
                        await writer.drain()
                    except (ConnectionResetError, BrokenPipeError):
                        return
                elif packet_type == _DISCONNECT:
                    return
                # else: ignore unknown packet types
        finally:
            self._active_writers.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    def _parse_publish(
        body: bytes, qos: int
    ) -> tuple[str, bytes, int | None]:
        topic_len = struct.unpack(">H", body[:2])[0]
        topic = body[2 : 2 + topic_len].decode("utf-8")
        cursor = 2 + topic_len
        packet_id: int | None = None
        if qos > 0:
            packet_id = struct.unpack(">H", body[cursor : cursor + 2])[0]
            cursor += 2
        payload = body[cursor:]
        return topic, payload, packet_id
