"""Story 10-1 AC15/AC16 — confidence thresholds config + read-only endpoint."""
from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from cloud_backend.config import get_settings
from cloud_backend.main import app

pytestmark = pytest.mark.unit

_HEADERS = {"X-API-Key": get_settings().api_key}

_EXPECTED_CLASSES = {
    "unattended_bag",
    "door_obstruction",
    "accessibility_detected",
    "slip_fall",
    "luggage_rack_saturation",
}


def test_endpoint_returns_expected_shape() -> None:
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.get("/api/v1/config/confidence-thresholds", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert set(body["per_class"].keys()) == _EXPECTED_CLASSES
    for v in body["per_class"].values():
        assert 0.0 <= v <= 1.0
    assert body["degraded_banner_floor"] == 0.6


def test_no_post_endpoint_exists() -> None:
    """Mutability is deferred to Epic 11 — POST must 405."""
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post(
            "/api/v1/config/confidence-thresholds",
            headers=_HEADERS,
            json={"per_class": {}},
        )
    assert r.status_code == 405


def test_every_threshold_carries_calibrate_comment() -> None:
    from cloud_backend.config import confidence_thresholds

    src = inspect.getsource(confidence_thresholds)
    threshold_lines = [
        line
        for line in src.splitlines()
        if ":" in line and ("0." in line) and not line.strip().startswith("#")
    ]
    assert threshold_lines, "no threshold value lines found"
    for line in threshold_lines:
        assert "# CALIBRATE" in line, f"missing CALIBRATE comment: {line.strip()}"
