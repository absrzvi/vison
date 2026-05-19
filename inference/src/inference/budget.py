"""TOPS budget coordination — P2 camera suppression under thermal/compute pressure."""
from __future__ import annotations

import structlog

from inference.config import Settings

log = structlog.get_logger(__name__)


class Budget:
    """Tracks P2 throttle state from context pushes.

    Transitions are logged once; per-frame noise is suppressed.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._p2_throttled: bool = False

    def on_context_update(self, payload: dict[str, object]) -> None:
        """Update throttle state from a context-push payload.

        Only accepts real booleans for `p2_throttled` — string "false" or non-bool
        values are rejected (logged + ignored) so a malformed payload cannot flip
        throttle ON via Python truthiness rules.
        """
        raw = payload.get("p2_throttled", False)
        if not isinstance(raw, bool):
            log.warning(
                "budget.invalid_p2_throttled_type",
                got_type=type(raw).__name__,
                value=str(raw),
            )
            return
        if raw != self._p2_throttled:
            self._p2_throttled = raw
            log.info("budget.p2_throttle_state_changed", throttled=raw)

    def should_process(self, camera_id: str, priority: str) -> bool:
        """Return False for P2 cameras when throttled; P1 always passes.

        camera_id is reserved for future per-camera overrides (e.g. always-on
        priority cameras); current implementation is class-based by priority.
        """
        del camera_id  # currently unused — see docstring
        if priority == "P2" and self._p2_throttled:
            return False
        return True
