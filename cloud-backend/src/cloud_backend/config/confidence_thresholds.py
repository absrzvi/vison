"""Per-class confidence thresholds — story 10-1 AC15, E11-S5 mutable.

The values below are the hardcoded DEFAULTS. As of E11-S5 they are persisted in
the `confidence_thresholds` KV table (Alembic 0012) and editable by an admin via
`PATCH /api/v1/config/confidence-thresholds` — changing a threshold no longer
requires a code deploy. These module constants remain the FAIL-SAFE fallback:
the store reader (`ThresholdStore`) substitutes a hardcoded default for any
missing, NULL, or un-parseable persisted row, so a malformed store can never
disable the confidence gate / degraded banner (it fails SAFE, never open).

Consumers read through `ThresholdStore` (per-evaluation, cached) — NOT the module
constants directly — because a module-level capture would never see an edit.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "unattended_bag":           0.75,  # CALIBRATE — placeholder pending PoC data
    "door_obstruction":         0.85,  # CALIBRATE
    "accessibility_detected":   0.70,  # CALIBRATE
    "slip_fall":                0.75,  # CALIBRATE
    "luggage_rack_saturation":  0.70,  # CALIBRATE
}

DEGRADED_BANNER_FLOOR: float = 0.60  # CALIBRATE — fleet-wide rolling-1h mean trigger

_FLOOR_KEY = "degraded_banner_floor"
_PER_CLASS_PREFIX = "per_class:"


def _valid(value: Any, *, floor: bool = False) -> bool:
    """A persisted value is usable only if it is a finite float in range; anything
    else (None, NaN, Inf, out-of-range, non-numeric) → fall back to the hardcoded
    default (fail SAFE). Per-class values allow [0.0, 1.0]; the degraded-banner
    floor must be STRICTLY > 0.0 (a stored 0.0 floor would make the gate never
    fire — fail-OPEN — so it is treated as malformed and falls back to the default,
    not honoured). E11-S5 code-review R1."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(v) or not (0.0 <= v <= 1.0):
        return False
    if floor and v <= 0.0:
        return False
    return True


class ThresholdStore:
    """In-process cached reader over the confidence_thresholds KV table.

    Mirrors services.fanout_filter.AlertClassFilter: TTL + lock + double-check +
    a generation counter so a load whose query overlapped an admin write does not
    cache a stale snapshot. `invalidate()` is called by the admin PATCH after
    commit so an edit takes effect on the next read. Every value is validated;
    a bad/missing row yields the hardcoded default for that key (never fail-open).
    """

    def __init__(self, ttl_s: float = 60.0) -> None:
        self._ttl = ttl_s
        self._loaded_at: float | None = None
        self._cache: dict[str, dict[str, Any]] = self._defaults()
        self._lock = asyncio.Lock()
        self._generation = 0

    @staticmethod
    def _defaults() -> dict[str, Any]:
        return {
            "per_class": dict(DEFAULT_CONFIDENCE_THRESHOLDS),
            "degraded_banner_floor": DEGRADED_BANNER_FLOOR,
        }

    def invalidate(self) -> None:
        self._loaded_at = None
        self._generation += 1

    async def load(self, db: AsyncSession) -> dict[str, Any]:
        now = time.monotonic()
        if self._loaded_at is not None and now - self._loaded_at < self._ttl:
            return self._cache
        async with self._lock:
            now = time.monotonic()
            if self._loaded_at is not None and now - self._loaded_at < self._ttl:
                return self._cache
            gen_at_start = self._generation
            rows = await db.execute(
                text("SELECT config_key, value FROM confidence_thresholds")
            )
            cfg = self._defaults()
            for r in rows:
                key = r.config_key
                if key == _FLOOR_KEY:
                    if _valid(r.value, floor=True):
                        cfg["degraded_banner_floor"] = float(r.value)
                    # else fail SAFE — a 0.0/malformed floor keeps the hardcoded default
                elif key.startswith(_PER_CLASS_PREFIX):
                    if not _valid(r.value):
                        continue  # fail SAFE — keep the hardcoded default for this key
                    cls = key[len(_PER_CLASS_PREFIX):]
                    # Only accept known classes; an unknown key is ignored (defaults stand).
                    if cls in DEFAULT_CONFIDENCE_THRESHOLDS:
                        cfg["per_class"][cls] = float(r.value)
            if self._generation != gen_at_start:
                # An invalidate() landed during the query — apply but leave stale
                # so the next read re-loads rather than trusting a racy snapshot.
                self._cache = cfg
                self._loaded_at = None
                return cfg
            self._cache = cfg
            self._loaded_at = now
            return cfg


# Process-wide instance shared by the config GET and the degraded-banner gate.
threshold_store = ThresholdStore()
