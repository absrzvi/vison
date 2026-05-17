"""Contract tests: schema_version=1 is always accepted (ADR-5)."""
import pytest

from event_store.database import SUPPORTED_SCHEMA_VERSIONS
from oebb_shared.events.envelope import SUPPORTED_SCHEMA_VERSIONS as SHARED_VERSIONS


@pytest.mark.contract
def test_schema_version_1_supported_in_event_store() -> None:
    assert 1 in SUPPORTED_SCHEMA_VERSIONS


@pytest.mark.contract
def test_shared_and_event_store_versions_agree() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS == SHARED_VERSIONS
