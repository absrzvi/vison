"""Tests for the health endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vlan_pollers import health as health_module
from vlan_pollers.health import router


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.unit
def test_health_ready_when_connected() -> None:
    health_module.set_snmp_ready(True)
    client = _make_client()
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["snmp_connected"] is True


@pytest.mark.unit
def test_health_503_when_not_connected() -> None:
    health_module.set_snmp_ready(False)
    client = _make_client()
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "starting"
    assert body["snmp_connected"] is False
    assert body["recoverable"] is True


@pytest.mark.unit
def test_health_transitions_back_to_ready() -> None:
    health_module.set_snmp_ready(False)
    client = _make_client()
    assert client.get("/health/ready").status_code == 503
    health_module.set_snmp_ready(True)
    assert client.get("/health/ready").status_code == 200
