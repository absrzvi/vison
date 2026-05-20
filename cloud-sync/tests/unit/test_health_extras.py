"""Health endpoint — degraded path when app.state not populated."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cloud_sync.health import router as health_router


@pytest.mark.unit
def test_health_returns_starting_when_app_state_missing() -> None:
    """If lifespan hasn't populated app.state, /health returns a 'starting'
    response with safe defaults instead of raising AttributeError → 500."""
    app = FastAPI()
    app.include_router(health_router)
    # NOTE: no lifespan; app.state.mqtt + app.state.queue_db_path NEVER set.
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "starting"
    assert body["broker_connected"] is False
    assert body["queue_depth"] == 0
    assert body["last_publish_utc"] is None
