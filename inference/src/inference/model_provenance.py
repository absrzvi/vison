"""Model provenance for story 10-1 AC5.

compute_model_versions() is called once at startup and stamped onto every
detection payload at emit time. detector_arch is read from the HEF itself
(Hailo-authoritative, lie-proof); the code version comes from the GIT_SHA
build arg — building without it is a startup error, not a silent "unknown".
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import structlog

from inference.config import Settings

log = structlog.get_logger(__name__)

# HEF bindings only exist in the TAPPAS Docker image. Module attribute so unit
# tests can patch `inference.model_provenance.HEF` (same pattern as callback.hailo).
try:
    from hailo_platform import HEF  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    HEF = None

_cached: dict[str, str] | None = None


def reset_cache() -> None:
    """Test hook — clear the module-level cache."""
    global _cached
    _cached = None


def compute_model_versions(settings: Settings) -> dict[str, str]:
    """Return the four provenance keys. Cached after first successful call."""
    global _cached
    if _cached is not None:
        return _cached

    if not settings.git_sha:
        raise RuntimeError("model provenance requires GIT_SHA build arg")
    if HEF is None:
        raise RuntimeError("model provenance requires hailo_platform (pyhailort) bindings")

    hef_path = Path(settings.model_hef_path)
    try:
        hef_bytes = hef_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"model provenance: cannot read HEF at {hef_path}: {exc}") from exc

    labels_path = Path(settings.model_labels_path)
    try:
        labels_bytes = labels_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(
            f"model provenance: cannot read labels file at {labels_path}: {exc}"
        ) from exc

    detector_arch = str(HEF(str(hef_path)).get_network_group_names()[0])
    _cached = {
        "detector_arch": detector_arch,
        "detector_hef": f"{hef_path.name}@{hashlib.sha256(hef_bytes).hexdigest()[:12]}",
        "detector_code": f"git:{settings.git_sha[:8]}",
        "detector_labels": f"labels@{hashlib.sha256(labels_bytes).hexdigest()[:12]}",
    }
    return _cached
