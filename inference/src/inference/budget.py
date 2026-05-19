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
        """Update throttle state from a context-push payload."""
        new_state = bool(payload.get("p2_throttled", False))
        if new_state != self._p2_throttled:
            self._p2_throttled = new_state
            log.info("budget.p2_throttle_state_changed", throttled=new_state)

    def should_process(self, camera_id: str, priority: str) -> bool:
        """Return False for P2 cameras when throttled; P1 always passes."""
        if priority == "P2" and self._p2_throttled:
            return False
        return True
