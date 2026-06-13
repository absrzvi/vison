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

Round-1 review patches (2026-05-21):
  * Duplicate WAGON_EXIT for the same ``track_id`` is idempotent — second
    non-orphan arrival short-circuits before mutating ledger state (review P2).
  * Pending exits are keyed by ``track_id`` alone — the gangway-fwd camera emits
    WAGON_EXIT and the gangway-aft camera emits WAGON_ENTRY with the SAME
    hailotracker ``track_id``, so a composite ``(camera_id, track_id)`` key
    would break the cross-camera correlation. Cross-coach track_id collisions
    remain a known limitation (see deferred-work).
  * Restart drops ``_pending_exits``; on startup we log a WARNING when
    ``unreconciled_exits > 0`` is loaded and zero those counters so the
    monotonic counter starts clean (review P4).
  * ``_seen_occupancy`` removed; AC1 gate is one-sided by design — ``check_drift``
    is the sole entry point that observes OCCUPANCY_UPDATE, so a no-op return
    when ``car_id`` is absent from ``_seen_wagon`` is sufficient (review P5).
  * ``_closed`` flag guards ``_handle_pending_timeout`` and the timer lambda
    against post-shutdown firing (review P8, P9).
  * WAL ``PRAGMA`` return is checked at startup; non-``wal`` modes log WARNING
    (review P11).
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
    camera_id: str
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
        self._closed = False

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
        # WAL mode per ADR-4. Verify the PRAGMA actually applied — silent fallback
        # to DELETE journal mode on tmpfs/NFS is a known SQLite footgun.
        mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
        if mode_row is not None and str(mode_row[0]).lower() != "wal":
            log.warning(
                "ledger.wal_mode_unavailable",
                requested="wal",
                actual=mode_row[0],
                db_path=db_path,
            )
        self._init_table()

        # In-memory state.
        self._rows: dict[str, CoachLedgerRow] = {}
        # Keyed by track_id (shared across the fwd/aft gangway camera pair by
        # the hailotracker). Cross-coach track_id collisions are a known
        # limitation tracked in deferred-work.
        self._pending_exits: dict[int, _PendingExit] = {}
        # AC1: drift checks gated until a WAGON_*/ledger-modifying event has
        # been observed for a car_id. _seen_occupancy is implicit (the only
        # call site for the gate IS the OCCUPANCY_UPDATE handler).
        self._seen_wagon: set[str] = set()
        self._last_drift_bucket: dict[str, int] = {}

        # Load any prior rows from the table (restart-safe). Pending-exit state
        # is not persisted; if any coach loads with unreconciled_exits > 0 the
        # counter is stale (lost timers, lost pending map). Log a WARNING and
        # zero the counter so it starts clean — review P4.
        self._load_rows_and_clean_stale_pendings()

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

    def _load_rows_and_clean_stale_pendings(self) -> None:
        cur = self._conn.execute(
            "SELECT coach_id, ledger_count, last_reconciled_utc, unreconciled_exits "
            "FROM coach_ledger"
        )
        stale: list[str] = []
        for coach_id, ledger_count, last_reconciled_utc, unreconciled_exits in cur:
            ue = int(unreconciled_exits)
            if ue > 0:
                stale.append(coach_id)
            self._rows[coach_id] = CoachLedgerRow(
                coach_id=coach_id,
                ledger_count=int(ledger_count),
                last_reconciled_utc=last_reconciled_utc,
                unreconciled_exits=0 if ue > 0 else ue,
            )
        if stale:
            log.warning(
                "ledger.pending_exits_lost_on_restart",
                reason="pending_exits_lost_on_restart",
                affected_coaches=stale,
            )
            for coach_id in stale:
                self._persist(coach_id)

    def seed_coach(self, coach_id: str) -> None:
        """Initialise a coach row at zero if not already present (AC1)."""
        if coach_id in self._rows:
            return
        self._rows[coach_id] = CoachLedgerRow(coach_id=coach_id)
        self._persist(coach_id)

    def close(self) -> None:
        # Cancel any outstanding timers so they don't fire after shutdown.
        self._closed = True
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

    def _schedule_timeout(self, track_id: int) -> asyncio.TimerHandle:
        """Schedule a timeout firing for ``track_id``; safe against closed loops."""
        loop = asyncio.get_running_loop()

        def _fire() -> None:
            # Guard against the loop having been closed between schedule and
            # fire (e.g. ledger.close() racing with the timeout — review P9).
            try:
                loop.create_task(self._handle_pending_timeout(track_id))
            except RuntimeError as exc:
                log.warning(
                    "ledger.timeout_schedule_failed",
                    reason="loop_closed_at_fire",
                    track_id=track_id,
                    error=str(exc),
                )

        return loop.call_later(self._pending_timeout_s, _fire)

    # ------------------------------------------------------------------
    # Public API — called by health.py candidate handlers
    # ------------------------------------------------------------------

    async def on_wagon_exit(self, payload: WagonExitPayload) -> None:
        """AC2 + AC3 — decrement ledger, arm pending reconciliation unless orphan.

        Idempotent on duplicate ``track_id`` arrivals — second non-orphan EXIT
        for an already-pending track_id is dropped with a DEBUG log to defend
        against at-least-once inference retries (review P2).
        """
        # Fusion is on-train, upstream of egress anonymisation: track_id is the
        # raw int from the producer and camera_id is always present. The shared
        # payload widened these (int|str / Optional) only for the redacted cloud
        # copy, which never reaches fusion. Narrow here so the ledger's int-keyed
        # machinery stays type-safe; a redacted event arriving is a wiring bug —
        # skip it rather than corrupt the ledger.
        if not isinstance(payload.track_id, int) or payload.camera_id is None:
            log.warning(
                "ledger.wagon_exit_unexpected_redacted",
                track_id=payload.track_id,
                camera_id=payload.camera_id,
            )
            return
        track_id: int = payload.track_id
        camera_id: str = payload.camera_id

        coach_from = payload.coach_from
        coach_to = payload.coach_to
        self._seen_wagon.add(coach_from)
        self._seen_wagon.add(coach_to)

        # Idempotency guard (review P2). Only applies to non-orphan exits because
        # expect_orphan exits arm no pending entry — duplicate orphan exits are
        # still a bug but harder to detect at this layer without a separate
        # "recently-seen orphan" cache; deferred.
        if not payload.expect_orphan and track_id in self._pending_exits:
            log.debug(
                "ledger.wagon_exit_duplicate",
                reason="duplicate_pending_exit",
                track_id=track_id,
                camera_id=camera_id,
                coach_from=coach_from,
            )
            return

        row = self._row(coach_from)
        row.ledger_count -= 1

        if payload.expect_orphan:
            # AC3 — ledger decrement applied, no pending entry, no unreconciled bump.
            self._persist(coach_from)
            log.info(
                "ledger.wagon_exit",
                track_id=track_id,
                camera_id=camera_id,
                coach_from=coach_from,
                coach_to=coach_to,
                expect_orphan=True,
            )
            return

        row.unreconciled_exits += 1
        self._persist(coach_from)

        ts_utc = _utc_now_iso()
        pending = _PendingExit(
            track_id=track_id,
            camera_id=camera_id,
            coach_from=coach_from,
            coach_to=coach_to,
            ts_utc=ts_utc,
        )

        # Schedule timeout — see _schedule_timeout for closed-loop safety.
        pending.timer_handle = self._schedule_timeout(track_id)
        self._pending_exits[track_id] = pending

        log.info(
            "ledger.wagon_exit",
            track_id=track_id,
            camera_id=camera_id,
            coach_from=coach_from,
            coach_to=coach_to,
            expect_orphan=False,
        )

    async def on_wagon_entry(self, payload: WagonEntryPayload) -> None:
        """AC4 — reconcile matching exit; cancel timer BEFORE state mutation (P10)."""
        # Narrow the egress-widened fields — see on_wagon_exit for the rationale.
        if not isinstance(payload.track_id, int) or payload.camera_id is None:
            log.warning(
                "ledger.wagon_entry_unexpected_redacted",
                track_id=payload.track_id,
                camera_id=payload.camera_id,
            )
            return
        track_id: int = payload.track_id
        camera_id: str = payload.camera_id

        coach_from = payload.coach_from
        coach_to = payload.coach_to
        self._seen_wagon.add(coach_from)
        self._seen_wagon.add(coach_to)

        pending = self._pending_exits.pop(track_id, None)
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
                track_id=track_id,
                camera_id=camera_id,
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
            track_id=track_id,
            camera_id=camera_id,
            coach_from=coach_from,
            coach_to=coach_to,
        )

    async def _handle_pending_timeout(self, track_id: int) -> None:
        """AC5 — timeout fires; ledger decrement is NOT reverted, log + drop entry.

        Closed-flag guard (review P8): if the ledger has shut down between
        scheduling and firing, return without touching state.
        """
        if self._closed:
            return
        pending = self._pending_exits.pop(track_id, None)
        if pending is None:
            # Stale-closure guard — concurrent WAGON_ENTRY already popped it.
            return
        log.info(
            "ledger.exit_unreconciled",
            track_id=track_id,
            camera_id=pending.camera_id,
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

        Always mutates ``_last_drift_bucket[car_id]`` on transition. On drift
        detected (bucket != 0), per ADR-15 the ledger count is corrected to
        match the camera count and a structured INFO log is emitted.

        AC1 gate (review P5): drift checks no-op when ``car_id`` has not yet
        been observed in a WAGON_* event. Since this method is the sole entry
        point that observes OCCUPANCY_UPDATE for the ledger, the OCCUPANCY half
        of the gate is implicit — by reaching this code we already have the
        camera signal.
        """
        car_id = payload.car_id

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
