from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from oebb_shared.events.envelope import EventEnvelope
from oebb_shared.events.types import EventType
from oebb_shared.http.retry import DEFAULT_RETRY

from .context_state import ContextStateManager
from .journey_tracker import JourneyTracker
from .models import AlarmEntry
from .snmp_decoder import IM0_ALARM_ENTRY_PREFIX, decode_alarm_table, decode_trip_number

log = structlog.get_logger()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class SnmpPoller:
    """Polls SNMP via GetBulk and dispatches decoded data to journey_tracker and context_state."""

    def __init__(
        self,
        vehicle_id: str,
        snmp_host: str,
        snmp_port: int,
        snmp_community: str,
        snmp_speed_oid: str,
        poll_interval_s: float,
        tracker: JourneyTracker,
        ctx: ContextStateManager,
        event_store_url: str,
        set_snmp_ready_fn: Any,
    ) -> None:
        self._vehicle_id = vehicle_id
        self._snmp_host = snmp_host
        self._snmp_port = snmp_port
        self._snmp_community = snmp_community
        self._snmp_speed_oid = snmp_speed_oid
        self._poll_interval_s = poll_interval_s
        self._tracker = tracker
        self._ctx = ctx
        self._event_store_url = event_store_url
        self._set_snmp_ready = set_snmp_ready_fn
        self._connected = False
        # Track previous alarm states to detect transitions
        self._prev_alarms: dict[str, bool] = {}

    async def run(self) -> None:  # pragma: no cover
        """Main polling loop — runs until cancelled. Covered by integration tests."""
        log.info("snmp_poller_starting", host=self._snmp_host, port=self._snmp_port)
        while True:
            try:
                varbinds = await asyncio.get_event_loop().run_in_executor(
                    None, self._getbulk_sync
                )
                if not self._connected:
                    self._connected = True
                    self._set_snmp_ready(True)
                    log.info("snmp_connected")
                await self._process(varbinds)
            except Exception as exc:
                log.warning("snmp_poll_failed", error=str(exc), recoverable=True)
                if self._connected:
                    self._connected = False
                    self._set_snmp_ready(False)
            await asyncio.sleep(self._poll_interval_s)

    def _getbulk_sync(self) -> list[tuple[str, Any]]:  # pragma: no cover
        """Synchronous GetBulk — run in executor. Covered by integration tests."""
        try:
            from pysnmp.hlapi import (
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                bulkCmd,
            )
        except ImportError:
            log.warning("pysnmp_not_installed", recoverable=True)
            return []

        results: list[tuple[str, Any]] = []
        for error_indication, error_status, _, var_binds in bulkCmd(
            SnmpEngine(),
            CommunityData(self._snmp_community),
            UdpTransportTarget((self._snmp_host, self._snmp_port), timeout=5, retries=2),
            ContextData(),
            0,
            25,
            ObjectType(ObjectIdentity(IM0_ALARM_ENTRY_PREFIX)),
        ):
            if error_indication or error_status:
                raise RuntimeError(str(error_indication or error_status))
            for var_bind in var_binds:
                oid_str = str(var_bind[0])
                raw = var_bind[1]
                val = raw.prettyPrint() if hasattr(raw, "prettyPrint") else str(raw)
                results.append((oid_str, val))
        return results

    async def _process(self, varbinds: list[tuple[str, Any]]) -> None:
        trip_number = decode_trip_number(varbinds)
        if trip_number:
            journey_id = self._tracker.get_journey_id(self._vehicle_id, trip_number)
            with structlog.contextvars.bound_contextvars(journey_id=journey_id):
                await self._ctx.update_journey(journey_id, trip_number, self._vehicle_id)
                await self._process_alarms(varbinds, journey_id)

    async def _process_alarms(
        self, varbinds: list[tuple[str, Any]], journey_id: str
    ) -> None:
        rows = decode_alarm_table(varbinds)
        for row in rows:
            entry = AlarmEntry(**row)
            was_active = self._prev_alarms.get(entry.alarm_id)
            self._prev_alarms[entry.alarm_id] = entry.active

            # Emit event only on state transition
            if was_active is None or was_active != entry.active:
                event_type = EventType.ALARM_ACTIVE if entry.active else EventType.ALARM_CLEARED
                await self._emit_alarm_event(journey_id, event_type, entry)

            await self._ctx.update_alarm(entry)

    async def _emit_alarm_event(
        self, journey_id: str, event_type: EventType, entry: AlarmEntry
    ) -> None:
        if entry.active:
            payload: dict[str, object] = {
                "alarm_id": entry.alarm_id,
                "alarm_type": entry.alarm_type,
                "car_id": entry.car_id or self._vehicle_id,
                "hardware_code": entry.hardware_code,
                "triggered_by": "automatic",
            }
        else:
            payload = {
                "alarm_id": entry.alarm_id,
                "alarm_type": entry.alarm_type,
                "car_id": entry.car_id or self._vehicle_id,
                "cleared_by": "automatic",
                "duration_s": 0.0,
            }
        envelope = EventEnvelope(
            event_id=str(uuid.uuid4()),
            journey_id=journey_id,
            vehicle_id=self._vehicle_id,
            timestamp=_utc_now(),
            event_type=event_type,
            severity=entry.severity,
            source="vlan-pollers",
            schema_version=1,
            payload=payload,
        )
        await _post_event_with_retry(self._event_store_url, envelope.model_dump())
        log.info(
            "alarm_event_emitted",
            event_type=str(event_type),
            alarm_id=entry.alarm_id,
            journey_id=journey_id,
        )

    async def signal_door_release(self, car_id: str, door_id: str) -> None:
        await self._ctx.set_door_release(car_id, door_id)


@DEFAULT_RETRY
async def _post_event_with_retry(url: str, payload: dict[str, Any]) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{url}/api/v1/events", json=payload, timeout=5.0)
        # 409 = duplicate — treat as idempotent success
        if r.status_code == 409:
            return
        r.raise_for_status()
