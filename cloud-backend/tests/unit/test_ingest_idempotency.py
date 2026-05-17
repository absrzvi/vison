"""Unit: IngestResponse model — duplicate_ids tracking."""
import pytest
from cloud_backend.routes.ingest import IngestResponse


@pytest.mark.unit
def test_ingest_response_tracks_duplicates() -> None:
    resp = IngestResponse(accepted=3, duplicate_ids=["evt-dup"])
    assert resp.accepted == 3
    assert "evt-dup" in resp.duplicate_ids


@pytest.mark.unit
def test_ingest_response_no_duplicates() -> None:
    resp = IngestResponse(accepted=5)
    assert resp.duplicate_ids == []
