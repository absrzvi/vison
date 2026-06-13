"""Unit tests for story 10-1 AC5 — model provenance computation."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from inference import model_provenance
from inference.config import Settings

pytestmark = pytest.mark.unit

_HEF_BYTES = b"fake-hef-bytes"
_LABELS_BYTES = b"person\nsuitcase\nbicycle\n"


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    model_provenance.reset_cache()


@pytest.fixture
def fixture_files(tmp_path: Path) -> tuple[str, str]:
    hef = tmp_path / "yolox_s_leaky.hef"
    hef.write_bytes(_HEF_BYTES)
    labels = tmp_path / "yolox.labels"
    labels.write_bytes(_LABELS_BYTES)
    return str(hef), str(labels)


@pytest.fixture
def settings(fixture_files: tuple[str, str]) -> Settings:
    hef, labels = fixture_files
    return Settings(
        model_hef_path=hef,
        model_labels_path=labels,
        git_sha="9d4a60dff0597b0d598c99c7fa6ed60bcb7f294f",
    )


@pytest.fixture
def fake_hef(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    hef_cls = MagicMock()
    hef_cls.return_value.get_network_group_names.return_value = ["yolox_s_leaky"]
    monkeypatch.setattr(model_provenance, "HEF", hef_cls)
    return hef_cls


def test_four_keys_produced(settings: Settings, fake_hef: MagicMock) -> None:
    versions = model_provenance.compute_model_versions(settings)
    assert set(versions) == {
        "detector_arch",
        "detector_hef",
        "detector_code",
        "detector_labels",
    }
    assert versions["detector_arch"] == "yolox_s_leaky"
    hef_sha = hashlib.sha256(_HEF_BYTES).hexdigest()[:12]
    assert versions["detector_hef"] == f"yolox_s_leaky.hef@{hef_sha}"
    assert versions["detector_code"] == "git:9d4a60df"
    labels_sha = hashlib.sha256(_LABELS_BYTES).hexdigest()[:12]
    assert versions["detector_labels"] == f"labels@{labels_sha}"


def test_result_is_cached(settings: Settings, fake_hef: MagicMock) -> None:
    first = model_provenance.compute_model_versions(settings)
    second = model_provenance.compute_model_versions(settings)
    assert first is second
    assert fake_hef.call_count == 1


def test_missing_git_sha_raises(
    fixture_files: tuple[str, str], fake_hef: MagicMock
) -> None:
    hef, labels = fixture_files
    settings = Settings(model_hef_path=hef, model_labels_path=labels, git_sha="")
    with pytest.raises(RuntimeError, match="GIT_SHA"):
        model_provenance.compute_model_versions(settings)


def test_missing_labels_file_raises(
    fixture_files: tuple[str, str], fake_hef: MagicMock
) -> None:
    hef, _ = fixture_files
    settings = Settings(
        model_hef_path=hef,
        model_labels_path="/nonexistent/yolox.labels",
        git_sha="9d4a60dff0597b0d598c99c7fa6ed60bcb7f294f",
    )
    with pytest.raises(RuntimeError, match="labels"):
        model_provenance.compute_model_versions(settings)


def test_empty_network_group_list_raises(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    hef_cls = MagicMock()
    hef_cls.return_value.get_network_group_names.return_value = []
    monkeypatch.setattr(model_provenance, "HEF", hef_cls)
    with pytest.raises(RuntimeError, match="no network groups"):
        model_provenance.compute_model_versions(settings)


def test_corrupt_hef_parse_raises_runtime_error(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    hef_cls = MagicMock(side_effect=ValueError("corrupt HEF magic bytes"))
    monkeypatch.setattr(model_provenance, "HEF", hef_cls)
    with pytest.raises(RuntimeError, match="cannot parse HEF"):
        model_provenance.compute_model_versions(settings)


def test_missing_hef_file_raises(
    fixture_files: tuple[str, str], fake_hef: MagicMock
) -> None:
    _, labels = fixture_files
    settings = Settings(
        model_hef_path="/nonexistent/model.hef",
        model_labels_path=labels,
        git_sha="9d4a60dff0597b0d598c99c7fa6ed60bcb7f294f",
    )
    with pytest.raises(RuntimeError):
        model_provenance.compute_model_versions(settings)
