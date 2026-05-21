"""Closed-ledger reconciliation engine — Story 4-9 (ADR-17).

Per-coach passenger count maintained from WAGON_EXIT / WAGON_ENTRY events;
reconciled against camera-derived OCCUPANCY_UPDATE counts. On drift-bucket
state transition, emits a LEDGER_DRIFT_OBSERVATION (telemetry-only, not an
operator alert — see D5 in the story).

Persistence: single owned sqlite3.Connection in WAL mode (ADR-4). All SQL is
parameterised; no string formatting.

Async/sync boundary: methods are ``async`` since they're called from FastAPI
handlers. The SQLite calls themselves are blocking but small, matching the
fusion convention used by other handlers.

Decisions folded in:
  * AC1 — zero-seed + ``_both_seeded`` gate.
  * AC2/AC3 — ``expect_orphan`` branch differs from regular EXIT.
  * AC4 — WAGON_ENTRY cancels pending timer FIRST (P10 lesson from E4-S8).
  * AC5 — pending-exit timeout matches E4-S8 orphan window; decrement NOT
    reverted (ledger reflects observed crossing).
  * AC6 — three-layer check / emit / surface; ledger corrected to camera per
    ADR-15.
  * AC7 — ``surface_to_operator`` flag set on ``station_approach`` edge only.
  * AC8 — suppression-gate compliance handled at handler layer; ledger still
    mutates so state remains consistent.
  * AC9 — WAL mode, parameterised SQL, single owned connection.
"""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import structlog
from oebb_shared.events import WagonEntryPayload, WagonExitPayload
from oebb_shared.events.payloads import (
    LedgerDriftObservationPayload,
    OccupancyUpdatePayload,
)

from fusion.config import Settings

log = structlog.get_logger(__name__)


@dataclass
class CoachLedgerRow:
    """In-memory + persisted state for one coach."""

    coach_id: str
    ledger_count: int = 0
    last_reconciled_utc: str | None = None
    unreconciled_exits: int = 0


@dataclass
class _PendingExit:
    """Tracks a WAGON_EXIT waiting for a paired WAGON_ENTRY within the window."""

    track_id: int
    coach_from: str
    coach_to: str
    ts_utc: str
    timer_handle: asyncio.TimerHandle | None = field(default=None, repr=False)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class CoachLedger:
    """Per-coach closed-ledger reconciliation against camera-authoritative counts.

    Owned by the fusion FastAPI lifespan. One instance per container.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pending_timeout_s = settings.ledger_pending_timeout_s
        self._drift_threshold = settings.ledger_drift_threshold
        self._bucket_size = max(1, settings.ledger_drift_bucket_size)

        # Ensure parent dir exists for non-:memory: paths.
        db_path = settings.ledger_db_path
        if db_path != ":memory:":
            parent = Path(db_path).parent
            if parent and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)

        # isolation_level=None + explicit BEGIN/COMMIT — keeps writes atomic
        # without auto-begin surprises. check_same_thread=False is required so
        # the connection survives across async task hops on the same event loop.
        self._conn = sqlite3.connect(
            db_path,
            isolation_level=None,
            check_same_thread=False,
        )
        # WAL mode per ADR-4. PRAGMA returns the new mode as a row.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_table()

        # In-memory state.
        self._rows: dict[str, CoachLedgerRow] = {}
        self._pending_exits: dict[int, _PendingExit] = {}
        # AC1: drift checks gated until BOTH first OCCUPANCY_UPDATE AND first
        # WAGON_*/ledger-modifying event have arrived for a given car_id.
        self._seen_occupancy: set[str] = set()
        self._seen_wagon: set[str] = set()
        self._last_drift_bucket: dict[str, int] = {}

        # Load any prior rows from the table (restart-safe).
        self._load_rows()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_table(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS coach_ledger ("
            "  coach_id TEXT PRIMARY KEY,"
            "  ledger_count INTEGER NOT NULL DEFAULT 0,"
            "  last_reconciled_utc TEXT,"
            "  unreconciled_exits INTEGER NOT NULL DEFAULT 0"
            ")"
        )

    def _load_rows(self) -> None:
        cur = self._conn.execute(
            "SELECT coach_id, ledger_count, last_reconciled_utc, unreconciled_exits "
            "FROM coach_ledger"
        )
        for coach_id, ledger_count, last_reconciled_utc, unreconciled_exits in cur:
            self._rows[coach_id] = CoachLedgerRow(
                coach_id=coach_id,
                ledger_count=int(ledger_count),
                last_reconciled_utc=last_reconciled_utc,
                unreconciled_exits=int(unreconciled_exits),
            )

    def seed_coach(self, coach_id: str) -> None:
        """Initialise a coach row at zero if not already present (AC1)."""
        if coach_id in self._rows:
            return
        self._rows[coach_id] = CoachLedgerRow(coach_id=coach_id)
        self._persist(coach_id)

    def close(self) -> None:
        # Cancel any outstanding timers so they don't fire after shutdown.
        for pending in self._pending_exits.values():
            if pending.timer_handle is not None:
                pending.timer_handle.cancel()
        self._pending_exits.clear()
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row(self, coach_id: str) -> CoachLedgerRow:
        row = self._rows.get(coach_id)
        if row is None:
            row = CoachLedgerRow(coach_id=coach_id)
            self._rows[coach_id] = row
            self._persist(coach_id)
        return row

    def _persist(self, coach_id: str) -> None:
        row = self._rows[coach_id]
        # Parameterised — never f-string into SQL.
        self._conn.execute(
            "INSERT INTO coach_ledger (coach_id, ledger_count, last_reconciled_utc, "
            "unreconciled_exits) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(coach_id) DO UPDATE SET "
            "ledger_count=excluded.ledger_count, "
            "last_reconciled_utc=excluded.last_reconciled_utc, "
            "unreconciled_exits=excluded.unreconciled_exits",
            (row.coach_id, row.ledger_count, row.last_reconciled_utc, row.unreconciled_exits),
        )

    def _drift_bucket(self, delta: int) -> int:
        """Sign(delta) * (|delta| // bucket_size). Bucket 0 means within threshold."""
        magnitude = abs(delta) // self._bucket_size
        if delta < 0:
            return -magnitude
        return magnitude

    # ------------------------------------------------------------------
    # Public API — called by health.py candidate handlers
    # ------------------------------------------------------------------

    async def on_wagon_exit(self, payload: WagonExitPayload) -> None:
        """AC2 + AC3 — decrement ledger, arm pending reconciliation unless orphan."""
        coach_from = payload.coach_from
        coach_to = payload.coach_to
        self._seen_wagon.add(coach_from)
        self._seen_wagon.add(coach_to)

        row = self._row(coach_from)
        row.ledger_count -= 1

        if payload.expect_orphan:
            # AC3 — ledger decrement applied, no pending entry, no unreconciled bump.
            self._persist(coach_from)
            log.info(
                "ledger.wagon_exit",
                track_id=payload.track_id,
                coach_from=coach_from,
                coach_to=coach_to,
                expect_orphan=True,
            )
            return

        row.unreconciled_exits += 1
        self._persist(coach_from)

        ts_utc = _utc_now_iso()
        pending = _PendingExit(
            track_id=payload.track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            ts_utc=ts_utc,
        )

        # Replace any prior pending for the same track_id (stale crossing —
        # cancel its timer first, then overwrite).
        prior = self._pending_exits.pop(payload.track_id, None)
        if prior is not None and prior.timer_handle is not None:
            prior.timer_handle.cancel()

        # Schedule timeout — capture track_id in closure (E3 retro A3).
        loop = asyncio.get_running_loop()
        _tid = payload.track_id
        handle = loop.call_later(
            self._pending_timeout_s,
            lambda: loop.create_task(self._handle_pending_timeout(_tid)),
        )
        pending.timer_handle = handle
        self._pending_exits[payload.track_id] = pending

        log.info(
            "ledger.wagon_exit",
            track_id=payload.track_id,
            coach_from=coach_from,
            coach_to=coach_to,
            expect_orphan=False,
        )

    async def on_wagon_entry(self, payload: WagonEntryPayload) -> None:
        """AC4 — reconcile matching exit; cancel timer BEFORE state mutation (P10)."""
        coach_from = payload.coach_from
        coach_to = payload.coach_to
        self._seen_wagon.add(coach_from)
        self._seen_wagon.add(coach_to)

        pending = self._pending_exits.pop(payload.track_id, None)
        if pending is not None and pending.timer_handle is not None:
            # P10: cancel BEFORE any further work.
            pending.timer_handle.cancel()

        if pending is None:
            # Orphan WAGON_ENTRY — no prior EXIT seen. Still increments ledger
            # at the destination per AC4.
            row_to = self._row(coach_to)
            row_to.ledger_count += 1
            row_to.last_reconciled_utc = _utc_now_iso()
            self._persist(coach_to)
            log.info(
                "ledger.wagon_entry_orphan",
                track_id=payload.track_id,
                coach_from=coach_from,
                coach_to=coach_to,
                reason="orphan_entry",
            )
            return

        row_to = self._row(coach_to)
        row_to.ledger_count += 1
        row_to.last_reconciled_utc = _utc_now_iso()
        self._persist(coach_to)

        # Decrement unreconciled_exits on the originating coach.
        row_from = self._row(pending.coach_from)
        if row_from.unreconciled_exits > 0:
            row_from.unreconciled_exits -= 1
            self._persist(pending.coach_from)

        log.info(
            "ledger.wagon_entry_reconciled",
            track_id=payload.track_id,
            coach_from=coach_from,
            coach_to=coach_to,
        )

    async def _handle_pending_timeout(self, track_id: int) -> None:
        """AC5 — timeout fires; ledger decrement is NOT reverted, log + drop entry."""
        pending = self._pending_exits.pop(track_id, None)
        if pending is None:
            # Stale-closure guard — concurrent WAGON_ENTRY already popped it.
            return
        log.info(
            "ledger.exit_unreconciled",
            track_id=track_id,
            coach_from=pending.coach_from,
            coach_to=pending.coach_to,
            reason="exit_unreconciled",
        )

    def check_drift(
        self,
        payload: OccupancyUpdatePayload,
        *,
        station_approach: bool,
    ) -> LedgerDriftObservationPayload | None:
        """AC6 + AC7 — return a payload to emit only on drift-bucket transition.

        Always mutates ``_last_drift_bucket[car_id]`` and ``_both_seeded[car_id]``.
        On drift detected (bucket != 0), per ADR-15 the ledger count is corrected
        to match the camera count and a structured INFO log is emitted.
        """
        car_id = payload.car_id
        self._seen_occupancy.add(car_id)

        # AC1: gate — drift checks no-op until both signals seen for this car.
        if car_id not in self._seen_wagon:
            return None

        row = self._row(car_id)
        camera_count = payload.occupancy_count
        ledger_count = row.ledger_count
        delta = ledger_count - camera_count

        within_threshold = abs(delta) <= self._drift_threshold
        if within_threshold:
            bucket = 0
        else:
            bucket = self._drift_bucket(delta)

        last_bucket = self._last_drift_bucket.get(car_id, 0)
        if bucket == last_bucket:
            return None

        # Bucket transition — build observation.
        self._last_drift_bucket[car_id] = bucket

        if bucket == 0:
            # Drift cleared — emit one "cleared" observation (delta=0).
            obs = LedgerDriftObservationPayload(
                car_id=car_id,
                camera_count=camera_count,
                ledger_count=camera_count,  # corrected
                delta=0,
                threshold=self._drift_threshold,
                surface_to_operator=station_approach,
            )
        else:
            obs = LedgerDriftObservationPayload(
                car_id=car_id,
                camera_count=camera_count,
                ledger_count=ledger_count,
                delta=delta,
                threshold=self._drift_threshold,
                surface_to_operator=station_approach,
            )

        # ADR-15: camera is authoritative — correct ledger to match.
        if row.ledger_count != camera_count:
            row.ledger_count = camera_count
            self._persist(car_id)
            log.info(
                "ledger.ledger_corrected_to_camera",
                car_id=car_id,
                reason="ledger_corrected_to_camera",
                delta=delta,
            )
        return obs

