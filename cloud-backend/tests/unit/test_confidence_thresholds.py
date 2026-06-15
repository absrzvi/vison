"""Story 10-1 AC15/AC16 — confidence thresholds config + read-only endpoint.

E11-S5 — thresholds are now persisted + admin-mutable (PATCH). Security tests
written RED-first: operator cannot mutate (403), out-of-range/NaN rejected (422),
a malformed STORED value fails SAFE to the hardcoded default (never fail-open),
and the read stays operator-visible (the shipped UnifiedFeed contract).
"""
from __future__ import annotations

import inspect
import math
import re
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.database import get_db
from cloud_backend.main import app

from .conftest import auth_header

pytestmark = pytest.mark.unit

_HEADERS = auth_header()
_ADMIN_HEADERS = auth_header(role="admin")

_EXPECTED_CLASSES = {
    "unattended_bag",
    "door_obstruction",
    "accessibility_detected",
    "slip_fall",
    "luggage_rack_saturation",
}


class _StubSession:
    """Minimal AsyncSession stub: records execute() calls, serves canned rows for
    the threshold-store SELECT, and is a no-op on commit. Used for the PATCH
    validation / 403 tests (which must reject BEFORE any write) and the store-read
    fallback test."""

    def __init__(self, rows: list[Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self._rows = rows or []
        self.commit = AsyncMock()

    async def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> MagicMock:
        self.calls.append((str(stmt), params))
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter(self._rows))
        return result


def _override_db(session: _StubSession) -> None:
    async def _gen() -> AsyncGenerator[Any, None]:
        yield session

    app.dependency_overrides[get_db] = _gen


@pytest.fixture(autouse=True)
def _clean_db_override() -> Any:
    yield
    app.dependency_overrides.pop(get_db, None)


def test_endpoint_returns_expected_shape() -> None:
    # E11-S5: the GET now reads the persisted store; an empty store returns the
    # hardcoded defaults (behaviour unchanged on a fresh deploy).
    _override_db(_StubSession(rows=[]))
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/config/confidence-thresholds", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert set(body["per_class"].keys()) == _EXPECTED_CLASSES
    for v in body["per_class"].values():
        assert 0.0 <= v <= 1.0
    assert body["degraded_banner_floor"] == 0.6


def test_no_post_endpoint_exists() -> None:
    """E11-S5 mutation is via PATCH, not POST — POST must still 405."""
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/config/confidence-thresholds",
            headers=_HEADERS,
            json={"per_class": {}},
        )
    assert r.status_code == 405


def test_every_threshold_carries_calibrate_comment() -> None:
    """Every DEFAULT threshold value line carries a # CALIBRATE marker (the values
    are placeholders pending PoC data). Scoped to the default-definition block so
    unrelated module code (the ThresholdStore reader added in E11-S5) is excluded."""
    from cloud_backend.config import confidence_thresholds

    src = inspect.getsource(confidence_thresholds)
    # Match only DEFAULT-value lines: a dict entry (`"key": 0.NN,`) or the floor
    # constant (`DEGRADED_BANNER_FLOOR: float = 0.NN`). Use a regex so docstrings /
    # the ThresholdStore reader (added in E11-S5) that merely mention `0.` are excluded.
    threshold_lines = [
        line
        for line in src.splitlines()
        if re.search(r'("[a-z_]+":\s+0\.\d+,)|(DEGRADED_BANNER_FLOOR.*=\s*0\.\d+)', line)
    ]
    assert len(threshold_lines) == 6, f"expected 6 default lines, got {len(threshold_lines)}"
    for line in threshold_lines:
        assert "# CALIBRATE" in line, f"missing CALIBRATE comment: {line.strip()}"


# ---------------------------------------------------------------------------
# E11-S5 Security Tests (RED-first) — admin-mutable thresholds
# ---------------------------------------------------------------------------


# ST1 — operator cannot mutate (403), distinct from a no-token 401.
@pytest.mark.parametrize(
    "body",
    [
        {"per_class": {"unattended_bag": 0.80}},
        {"degraded_banner_floor": 0.55},
    ],
)
def test_operator_cannot_patch_thresholds_403(body: dict[str, Any]) -> None:
    _override_db(_StubSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds", headers=_HEADERS, json=body
        )
    assert r.status_code == 403


def test_no_token_patch_is_401() -> None:
    _override_db(_StubSession())
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            json={"degraded_banner_floor": 0.55},
        )
    assert r.status_code == 401


# ST2 — out-of-range / non-numeric over the wire rejected at the boundary (422),
# nothing written. (NaN/Inf cannot be encoded as JSON numbers, so they can't
# arrive over the wire; they're covered at the validator level below.)
# R1: 0.0 is now ALSO rejected for the floor (fail-open guard) — see the dedicated
# test below; here we keep the out-of-range/non-numeric cases.
@pytest.mark.parametrize("bad", [1.5, -0.1, "abc"])
def test_out_of_range_floor_rejected_422(bad: Any) -> None:
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"degraded_banner_floor": bad},
        )
    assert r.status_code == 422
    # No upsert (INSERT/UPDATE) reached the DB.
    assert not any(
        "insert" in sql.lower() or "update" in sql.lower() for sql, _ in session.calls
    )


# R1 (code-review) — a floor of 0.0 is a fail-OPEN (gate `mean < floor` never
# fires) and must be rejected, even though it's "in [0,1]". Per-class 0.0 is fine.
def test_floor_zero_rejected_422_fail_open_guard() -> None:
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"degraded_banner_floor": 0.0},
        )
    assert r.status_code == 422
    body = r.json()
    # R1 — the 422 uses the ADR-10 envelope (not FastAPI's default body).
    assert body["detail"]["error"] == "UNPROCESSABLE"
    assert "degraded_banner_floor" in body["detail"]["detail"]
    assert not any(
        "insert" in sql.lower() or "update" in sql.lower() for sql, _ in session.calls
    )


def test_per_class_zero_allowed() -> None:
    """Per-class 0.0 is valid (display-only, not a gate) — distinguishes the floor
    rule from the per-class rule."""
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"per_class": {"unattended_bag": 0.0}},
        )
    assert r.status_code == 200


def test_invalid_patch_uses_adr10_envelope() -> None:
    """R1 — every PATCH validation 422 carries the ADR-10 envelope
    {error, detail, recoverable}, mirroring preferences.py (NOT FastAPI's default
    RequestValidationError body)."""
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"per_class": {"unattended_bag": 1.5}},
        )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "UNPROCESSABLE"
    assert detail["recoverable"] is True
    assert isinstance(detail["detail"], str)


def test_store_read_rejects_zero_floor_falls_back_to_default() -> None:
    """R1 — a PERSISTED floor of 0.0 (e.g. a legacy/raw write) must fail SAFE to the
    hardcoded default, never be honoured (which would disable the gate)."""
    from cloud_backend.config.confidence_thresholds import _valid

    assert _valid(0.0, floor=True) is False  # floor: 0.0 rejected
    assert _valid(0.0) is True  # per-class: 0.0 allowed
    assert _valid(0.60, floor=True) is True


@pytest.mark.parametrize("bad", [1.5, -0.1])
def test_out_of_range_per_class_rejected_422(bad: float) -> None:
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"per_class": {"unattended_bag": bad}},
        )
    assert r.status_code == 422
    assert not any(
        "insert" in sql.lower() or "update" in sql.lower() for sql, _ in session.calls
    )


def test_unknown_alert_class_rejected_422() -> None:
    """A per_class key that isn't a known alert class is rejected (422)."""
    session = _StubSession()
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.patch(
            "/api/v1/config/confidence-thresholds",
            headers=_ADMIN_HEADERS,
            json={"per_class": {"made_up_class": 0.5}},
        )
    assert r.status_code == 422
    assert not any(
        "insert" in sql.lower() or "update" in sql.lower() for sql, _ in session.calls
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, 1.5])
def test_validator_rejects_nonfinite_and_out_of_range(bad: float) -> None:
    """NaN/Inf/out-of-range are rejected by the unit-interval validator directly
    (NaN/Inf can't ride JSON, so this is the boundary guard for any non-wire path)."""
    from cloud_backend.routes.config import _check_unit_interval

    with pytest.raises(ValueError):
        _check_unit_interval(bad)


# ST3 — a malformed STORED value fails SAFE (hardcoded default), never fail-open.
@pytest.mark.asyncio
async def test_store_read_falls_back_to_hardcoded_on_bad_rows() -> None:
    """If the persisted store has a missing/NULL/un-parseable value, the reader
    returns the hardcoded default — it must NEVER yield a gate-disabling value."""
    from cloud_backend.config.confidence_thresholds import (
        DEFAULT_CONFIDENCE_THRESHOLDS,
        DEGRADED_BANNER_FLOOR,
        ThresholdStore,
    )

    # A row whose value is NULL/None for the floor + a junk per_class key value.
    bad_floor = MagicMock(config_key="degraded_banner_floor", value=None)
    bad_class = MagicMock(config_key="per_class:unattended_bag", value=None)
    session = _StubSession(rows=[bad_floor, bad_class])

    store = ThresholdStore()
    store.invalidate()
    cfg = await store.load(session)

    # Fail-safe: the malformed rows are ignored, hardcoded defaults stand.
    assert cfg["degraded_banner_floor"] == DEGRADED_BANNER_FLOOR
    assert (
        cfg["per_class"]["unattended_bag"]
        == DEFAULT_CONFIDENCE_THRESHOLDS["unattended_bag"]
    )
    # And the floor is never 0.0 (which would mean "never degraded" — fail-open).
    assert cfg["degraded_banner_floor"] > 0.0
    assert math.isfinite(cfg["degraded_banner_floor"])


@pytest.mark.asyncio
async def test_store_read_empty_table_is_all_defaults() -> None:
    """An empty store (fresh deploy before any edit) returns exactly the hardcoded
    defaults so behaviour is unchanged."""
    from cloud_backend.config.confidence_thresholds import (
        DEFAULT_CONFIDENCE_THRESHOLDS,
        DEGRADED_BANNER_FLOOR,
        ThresholdStore,
    )

    store = ThresholdStore()
    store.invalidate()
    cfg = await store.load(_StubSession(rows=[]))
    assert cfg["degraded_banner_floor"] == DEGRADED_BANNER_FLOOR
    assert cfg["per_class"] == dict(DEFAULT_CONFIDENCE_THRESHOLDS)


# ST4 — read exposure unchanged: an operator token can still GET (UnifiedFeed
# contract). Covered by test_endpoint_returns_expected_shape using _HEADERS
# (operator), re-asserted here explicitly for the security envelope.
def test_operator_can_still_read_thresholds_200() -> None:
    _override_db(_StubSession(rows=[]))
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/config/confidence-thresholds", headers=_HEADERS)
    assert r.status_code == 200
