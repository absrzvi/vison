"""Contract tests: schema_version compatibility (ADR-5, AC19)."""
import sqlite3
from pathlib import Path

import pytest
from oebb_shared.events.envelope import SUPPORTED_SCHEMA_VERSIONS as SHARED_VERSIONS

from event_store.database import SUPPORTED_SCHEMA_VERSIONS, get_connection, init_db, insert_event
from event_store.exceptions import UnsupportedSchemaVersionError


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(str(tmp_path / "contract_test.db"))
    init_db(conn)
    return conn


@pytest.mark.contract
def test_schema_version_1_supported_in_event_store() -> None:
    assert 1 in SUPPORTED_SCHEMA_VERSIONS


@pytest.mark.contract
def test_shared_and_event_store_versions_agree() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS == SHARED_VERSIONS


@pytest.mark.contract
def test_unknown_schema_version_raises_and_logs_warning(
    db: sqlite3.Connection, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC19: schema_version=999 raises UnsupportedSchemaVersionError (logged at WARNING).

    Consumer logs WARNING and does not silently accept unknown versions.
    structlog writes to stdout with JSONRenderer — captured via capsys.
    """
    bad_event = {
        "event_id": "test-uuid-999",
        "journey_id": "R5001C-031_RJ-0847_20260516",
        "vehicle_id": "R5001C-031",
        "timestamp": "2026-05-17T10:00:00Z",
        "event_type": "OCCUPANCY_UPDATE",
        "severity": "info",
        "source": "inference",
        "schema_version": 999,
        "payload": {},
    }
    with pytest.raises(UnsupportedSchemaVersionError):
        insert_event(db, bad_event)

    captured = capsys.readouterr()
    assert "schema_version" in captured.out or "999" in captured.out
