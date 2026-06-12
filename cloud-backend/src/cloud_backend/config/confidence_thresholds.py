"""Per-class confidence thresholds — story 10-1 AC15.

All values are placeholders pending PoC calibration data. Mutability is
deferred to Epic 11 — changing a threshold requires a code deploy.
"""
from __future__ import annotations

DEFAULT_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "unattended_bag":           0.75,  # CALIBRATE — placeholder pending PoC data
    "door_obstruction":         0.85,  # CALIBRATE
    "accessibility_detected":   0.70,  # CALIBRATE
    "slip_fall":                0.75,  # CALIBRATE
    "luggage_rack_saturation":  0.70,  # CALIBRATE
}

DEGRADED_BANNER_FLOOR: float = 0.60  # CALIBRATE — fleet-wide rolling-1h mean trigger
