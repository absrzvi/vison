"""Unit tests for the closed-ledger reconciliation engine (E4-S9, ADR-17).

Covers AC1–AC9 and AC11 ledger branches. Uses tmp_path-scoped SQLite (per
architecture line 173 — never :memory:). Fast timer tests use a short
``ledger_pending_timeout_s`` rather than real-time waits.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import structlog.testing
from oebb_shared.events import WagonEntryPayload, WagonExitPayload
from oebb_shared.events.payloads import OccupancyUpdatePayload

from fusion.config import Settings
from fusion.ledger import CoachLedger


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    return Settings(
        event_store_url="http://event-store-test",
        vehicle_id="OBB-TEST",
        ledger_db_path=str(tmp_path / "coach_ledger.db"),
        ledger_pending_timeout_s=0.05,
        ledger_drift_threshold=3,
        ledger_drift_bucket_size=3,
        **overrides,
    )


def _wagon_exit(
    track_id: int = 1,
    coach_from: str = "car-1",
    coach_to: str = "car-2",
    expect_orphan: bool = False,
) -> WagonExitPayload:
    return WagonExitPayload(
        track_id=track_id,
        coach_from=coach_from,
        coach_to=coach_to,
        camera_id="C_FWD",
        traversal="from_to",
        confidence=0.9,
        expect_orphan=expect_orphan,
    )


def _wagon_entry(
    track_id: int = 1, coach_from: str = "car-1", coach_to: str = "car-2"
) -> WagonEntryPayload:
    return WagonEntryPayload(
        track_id=track_id,
        coach_from=coach_from,
        coach_to=coach_to,
        camera_id="C_AFT",
        traversal="from_to",
        confidence=0.9,
    )


def _occupancy(car_id: str, count: int, capacity: int = 200) -> OccupancyUpdatePayload:
    return OccupancyUpdatePayload(
        car_id=car_id,
        zone=None,
        occupancy_count=count,
        occupancy_pct=count / capacity,
        capacity=capacity,
        service_tier="standard",
        model_versions={"detector_arch": "yolox_s_leaky"},
    )


# ---------------------------------------------------------------------------
# AC1 — table init + zero seed + both_seeded gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_table_initialised_with_zero_seed(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        ledger.seed_coach("car-1")
        row = ledger._rows["car-1"]
        assert row.ledger_count == 0
        assert row.unreconciled_exits == 0
        assert row.last_reconciled_utc is None
    finally:
        ledger.close()


@pytest.mark.unit
def test_wal_mode_enabled(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        cur = ledger._conn.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drift_check_gated_until_both_signals_seen(tmp_path: Path) -> None:
    """AC1 — first OCCUPANCY_UPDATE alone must not emit a drift observation."""
    ledger = CoachLedger(_settings(tmp_path))
    try:
        obs = ledger.check_drift(_occupancy("car-1", 50), station_approach=False)
        assert obs is None
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC2 — WAGON_EXIT decrements + arms pending reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wagon_exit_decrements_and_arms_pending(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit(track_id=10))
        assert ledger._rows["car-1"].ledger_count == -1
        assert ledger._rows["car-1"].unreconciled_exits == 1
        assert 10 in ledger._pending_exits
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC3 — expect_orphan=True records but does not reconcile
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_expect_orphan_exit_no_pending_no_unreconciled_bump(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit(track_id=20, expect_orphan=True))
        assert ledger._rows["car-1"].ledger_count == -1
        assert ledger._rows["car-1"].unreconciled_exits == 0
        assert 20 not in ledger._pending_exits
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC4 — WAGON_ENTRY reconciles a pending exit
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wagon_entry_reconciles_pending_exit(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit(track_id=30))
        await ledger.on_wagon_entry(_wagon_entry(track_id=30))

        assert ledger._rows["car-1"].ledger_count == -1
        assert ledger._rows["car-1"].unreconciled_exits == 0
        assert ledger._rows["car-2"].ledger_count == 1
        assert ledger._rows["car-2"].last_reconciled_utc is not None
        assert 30 not in ledger._pending_exits
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_orphan_wagon_entry_increments_and_logs(tmp_path: Path) -> None:
    """AC4 — unmatched WAGON_ENTRY still increments ledger_count[coach_to]."""
    ledger = CoachLedger(_settings(tmp_path))
    try:
        with structlog.testing.capture_logs() as logs:
            await ledger.on_wagon_entry(_wagon_entry(track_id=99))
        assert ledger._rows["car-2"].ledger_count == 1
        assert any(entry.get("reason") == "orphan_entry" for entry in logs)
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC5 — pending-exit timeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pending_exit_timeout_decrement_not_reverted(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        with structlog.testing.capture_logs() as logs:
            await ledger.on_wagon_exit(_wagon_exit(track_id=77))
            # Poll deterministically rather than sleep a fixed margin (review P17).
            # Timeout in fixture is 0.05s; allow up to 2.0s before failing.
            for _ in range(40):
                if not ledger._pending_exits:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("pending exit timer did not fire")
        # Decrement stays; pending dropped; log emitted.
        assert ledger._rows["car-1"].ledger_count == -1
        assert ledger._rows["car-1"].unreconciled_exits == 1
        assert not ledger._pending_exits
        assert any(entry.get("reason") == "exit_unreconciled" for entry in logs)
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC6 — drift detection + state-transition emission
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_within_threshold_no_emit(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())  # seed _seen_wagon
        # ledger_count = -1, camera = 0 → delta = -1 → within threshold (3)
        obs = ledger.check_drift(_occupancy("car-1", 0), station_approach=False)
        assert obs is None
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entering_drift_emits_and_corrects_ledger(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        # Seed both signals.
        await ledger.on_wagon_exit(_wagon_exit())
        # Manually set a large ledger_count to force drift.
        ledger._rows["car-1"].ledger_count = 50
        obs = ledger.check_drift(_occupancy("car-1", 10), station_approach=False)
        assert obs is not None
        assert obs.car_id == "car-1"
        assert obs.delta == 40
        assert obs.camera_count == 10
        assert obs.ledger_count == 50
        # ADR-15: ledger corrected to camera count after emit.
        assert ledger._rows["car-1"].ledger_count == 10
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drift_bucket_change_emits_again(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())
        ledger._rows["car-1"].ledger_count = 10
        # First emit: delta=10, bucket=+3
        obs1 = ledger.check_drift(_occupancy("car-1", 0), station_approach=False)
        assert obs1 is not None
        # Ledger now corrected to 0. Set to 30 for next tick → delta=30, bucket=+10
        ledger._rows["car-1"].ledger_count = 30
        obs2 = ledger.check_drift(_occupancy("car-1", 0), station_approach=False)
        assert obs2 is not None
        assert obs2.delta == 30
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drift_cleared_emits_once_with_delta_zero(tmp_path: Path) -> None:
    """Drift bucket transitioning back to 0 emits one cleared observation,
    then subsequent same-bucket ticks are silent. Also pins
    ``_last_drift_bucket`` to 0 after the cleared emit."""
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())
        ledger._rows["car-1"].ledger_count = 50
        # Tick 1: enters drift bucket +13, ledger corrected to 10.
        obs1 = ledger.check_drift(_occupancy("car-1", 10), station_approach=False)
        assert obs1 is not None
        assert ledger._last_drift_bucket["car-1"] != 0
        # Tick 2: ledger==camera==10 → bucket 0 → transition emits cleared.
        obs2 = ledger.check_drift(_occupancy("car-1", 10), station_approach=False)
        assert obs2 is not None
        assert obs2.delta == 0
        assert ledger._last_drift_bucket["car-1"] == 0
        # Tick 3: still bucket 0 → no emit.
        obs3 = ledger.check_drift(_occupancy("car-1", 10), station_approach=False)
        assert obs3 is None
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_change_tick_no_emit(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())
        obs1 = ledger.check_drift(_occupancy("car-1", 0), station_approach=False)
        # delta = -1 (within threshold), bucket = 0, last = 0 → no emit
        assert obs1 is None
        obs2 = ledger.check_drift(_occupancy("car-1", 0), station_approach=False)
        assert obs2 is None
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC7 — surface_to_operator flag
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_surface_to_operator_true_on_station_approach(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())
        ledger._rows["car-1"].ledger_count = 50
        obs = ledger.check_drift(_occupancy("car-1", 10), station_approach=True)
        assert obs is not None
        assert obs.surface_to_operator is True
    finally:
        ledger.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_surface_to_operator_false_off_approach(tmp_path: Path) -> None:
    ledger = CoachLedger(_settings(tmp_path))
    try:
        await ledger.on_wagon_exit(_wagon_exit())
        ledger._rows["car-1"].ledger_count = 50
        obs = ledger.check_drift(_occupancy("car-1", 10), station_approach=False)
        assert obs is not None
        assert obs.surface_to_operator is False
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC9 — SQLite persistence across simulated restart
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persistence_across_restart(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ledger = CoachLedger(settings)
    await ledger.on_wagon_exit(_wagon_exit(track_id=200))
    await ledger.on_wagon_entry(_wagon_entry(track_id=200))
    # Snapshot state then close and re-open.
    car1_count = ledger._rows["car-1"].ledger_count
    car2_count = ledger._rows["car-2"].ledger_count
    ledger.close()

    ledger2 = CoachLedger(settings)
    try:
        assert ledger2._rows["car-1"].ledger_count == car1_count
        assert ledger2._rows["car-2"].ledger_count == car2_count
    finally:
        ledger2.close()


# ---------------------------------------------------------------------------
# AC4 P10 lesson — timer cancelled BEFORE any further work
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_entry_cancels_timer_before_state_mutation(tmp_path: Path) -> None:
    """Even after waiting longer than the timeout, no exit_unreconciled fires
    because the timer was cancelled by the matching WAGON_ENTRY first.
    """
    ledger = CoachLedger(_settings(tmp_path))
    try:
        with structlog.testing.capture_logs() as logs:
            await ledger.on_wagon_exit(_wagon_exit(track_id=500))
            await ledger.on_wagon_entry(_wagon_entry(track_id=500))
            await asyncio.sleep(0.15)
        unreconciled = [
            e for e in logs if e.get("reason") == "exit_unreconciled"
        ]
        assert unreconciled == []
    finally:
        ledger.close()


# ---------------------------------------------------------------------------
# AC9 — parameterised SQL spot check (defence-in-depth alongside AST test)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sql_injection_attempt_is_safe(tmp_path: Path) -> None:
    """A coach_id with SQL metacharacters must round-trip safely as a literal
    string — the row is created and queryable, the schema is untouched."""
    ledger = CoachLedger(_settings(tmp_path))
    try:
        evil = "car-1'; DROP TABLE coach_ledger; --"
        ledger.seed_coach(evil)
        # Table must still exist.
        cur = ledger._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='coach_ledger'"
        )
        assert cur.fetchone() == ("coach_ledger",)
        assert evil in ledger._rows
    finally:
        ledger.close()


@pytest.mark.unit
def test_close_releases_db_file(tmp_path: Path) -> None:
    """Connection is released — re-opening on the same path works."""
    s = _settings(tmp_path)
    ledger = CoachLedger(s)
    ledger.close()
    # Re-opening on the same path must succeed.
    ledger2 = CoachLedger(s)
    ledger2.close()
