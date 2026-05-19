from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass
class CameraConfig:
    camera_id: str
    coach_id: str
    rtsp_url: str
    zone: str
    priority: Priority


@dataclass
class CameraState:
    camera_id: str
    active: bool = True
    current_fps: float = 0.0
    override_until: float | None = None  # epoch seconds; None = no override


def load_cameras(path: str) -> list[CameraConfig]:
    raw = json.loads(Path(path).read_text())
    cameras_raw = raw.get("cameras", raw) if isinstance(raw, dict) else raw
    result: list[CameraConfig] = []
    for entry in cameras_raw:
        for required in ("camera_id", "coach_id", "rtsp_url", "zone", "priority"):
            if required not in entry:
                raise ValueError(f"Camera entry missing required field '{required}': {entry}")
        result.append(
            CameraConfig(
                camera_id=entry["camera_id"],
                coach_id=entry["coach_id"],
                rtsp_url=entry["rtsp_url"],
                zone=entry["zone"],
                priority=Priority(entry["priority"]),
            )
        )
    seen_ids = {c.camera_id for c in result}
    if len(seen_ids) != len(result):
        from collections import Counter
        dupes = [cid for cid, n in Counter(c.camera_id for c in result).items() if n > 1]
        raise ValueError(f"Duplicate camera_id entries in {path}: {dupes}")
    return result
