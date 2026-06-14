"""Story 10-1 AC17 — ai_quality_degraded flag on GET /api/v1/health."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cloud_backend.database import get_db
from cloud_backend.main import app
from cloud_backend.routes.health import degraded_cache

from .conftest import auth_header

pytestmark = pytest.mark.unit

# E11-S1: /api/v1/health now requires a JWT Bearer token (matching sibling /api/v1/*).
_HEADERS = auth_header()


class _MeanSession:
    def __init__(self, mean: float | None) -> None:
        self._mean = mean
        self.execute_count = 0

    async def execute(self, stmt: Any, params: Any = None) -> MagicMock:
        self.execute_count += 1
        result = MagicMock()
        result.scalar = MagicMock(return_value=self._mean)
        return result


def _override_db(session: _MeanSession) -> None:
    async def _gen() -> AsyncGenerator[Any, None]:
        yield session

    app.dependency_overrides[get_db] = _gen


@pytest.fixture(autouse=True)
def _reset() -> Any:
    degraded_cache.reset()
    yield
    degraded_cache.reset()
    app.dependency_overrides.pop(get_db, None)


def _get_health(client: TestClient) -> dict[str, Any]:
    r = client.get("/api/v1/health", headers=_HEADERS)
    assert r.status_code == 200
    return r.json()


def test_api_health_requires_api_key() -> None:
    """R3 clou-2: missing/wrong X-API-Key → 401, like every other /api/v1/*."""
    _override_db(_MeanSession(None))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/api/v1/health").status_code == 401
        assert client.get(
            "/api/v1/health", headers={"X-API-Key": "wrong"}
        ).status_code == 401


def test_flag_false_when_no_model_alerts_in_window() -> None:
    _override_db(_MeanSession(mean=None))
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get_health(client)
    assert body["ai_quality_degraded"] is False


def test_flag_true_when_mean_below_floor() -> None:
    _override_db(_MeanSession(mean=0.42))
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get_health(client)
    assert body["ai_quality_degraded"] is True


def test_flag_false_when_mean_at_or_above_floor() -> None:
    _override_db(_MeanSession(mean=0.60))
    with TestClient(app, raise_server_exceptions=False) as client:
        body = _get_health(client)
    assert body["ai_quality_degraded"] is False


def test_result_cached_for_30s() -> None:
    session = _MeanSession(mean=0.42)
    _override_db(session)
    with TestClient(app, raise_server_exceptions=False) as client:
        _get_health(client)
        _get_health(client)
    assert session.execute_count == 1
