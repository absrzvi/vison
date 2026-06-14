"""Root test conftest — stable JWT config for the whole suite (E11-S1).

`get_settings()` builds a fresh `Settings` from the environment on every call, so
the JWT secret/issuer must be stable across the session or a token minted under
one value fails verification after another test changes the env. Pin them once
here, at import time, before any test module mints a token. Individual tests that
need a DIFFERENT value (e.g. the empty-secret fail-closed test) use
`monkeypatch.setenv`, which restores the pinned value at teardown.
"""
from __future__ import annotations

import os

_JWT_SECRET = "suite-stable-jwt-secret-0123456789abcdef0123456789"
_JWT_ISSUER = "oebb-cloud-backend"

# Force (not setdefault) so the same value holds whether unit or integration
# collection touches the env first.
os.environ["JWT_SECRET"] = _JWT_SECRET
os.environ["JWT_ISSUER"] = _JWT_ISSUER
os.environ["JWT_ALGORITHM"] = "HS256"
