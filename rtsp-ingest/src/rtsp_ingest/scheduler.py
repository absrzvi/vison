from __future__ import annotations

import time

import structlog

from .config import Settings
from .models import CameraConfig, CameraState, Priority

log = structlog.get_logger()


class Scheduler:
    def __init__(self, cameras: list[CameraConfig], settings: Settings) -> None:
        self._settings = settings
        self._cameras: dict[str, CameraConfig] = {c.camera_id: c for c in cameras}
        self._states: dict[str, CameraState] = {
            c.camera_id: CameraState(camera_id=c.camera_id) for c in cameras
        }
        self._p2_throttled: bool = False
        self._p3_active: bool = False

    def apply_fps(self, camera_id: str) -> float:
        cfg = self._cameras.get(camera_id)
        state = self._states.get(camera_id)
        if cfg is None or state is None:
            return 0.0

        # Check active override window
        if state.override_until is not None:
            if time.monotonic() < state.override_until:
                return self._settings.p1_fps
            else:
                state.override_until = None  # expired

        if cfg.priority == Priority.P1:
            return self._settings.p1_fps
        elif cfg.priority == Priority.P2:
            return self._settings.p2_throttled_fps if self._p2_throttled else self._settings.p2_fps
        else:  # P3
            return self._settings.p3_fps if self._p3_active else 0.0

    def report_tops(self, tops_used: float) -> None:
        if self._settings.tops_total == 0.0:
            return
        pct = tops_used / self._settings.tops_total
        if pct > self._settings.tops_budget_pct_threshold and not self._p2_throttled:
            self._p2_throttled = True
            log.warning(
                "budget_pressure",
                tops_used_pct=round(pct * 100, 1),
                throttled_tier="P2",
                recoverable=True,
            )
        elif pct <= self._settings.tops_budget_pct_threshold and self._p2_throttled:
            self._p2_throttled = False
            log.info("budget_recovered", tops_used_pct=round(pct * 100, 1))

    def gate_p3(self, active: bool) -> None:
        self._p3_active = active

    def override_to_p1(self, camera_ids: list[str], duration_s: float) -> None:
        deadline = time.monotonic() + duration_s
        for cid in camera_ids:
            if cid in self._states:
                self._states[cid].override_until = deadline

    def active_p1_count(self) -> int:
        return sum(
            1
            for cid, cfg in self._cameras.items()
            if cfg.priority == Priority.P1 and self._states[cid].active
        )
