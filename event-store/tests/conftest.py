"""ADR-4: enforce no :memory: SQLite paths in any test file.

WAL mode silently degrades when using :memory: — all test fixtures must
use tmp_path-scoped on-disk files to test real WAL semantics.
"""
from __future__ import annotations

from pathlib import Path


def pytest_collection_finish(session: object) -> None:
    items = getattr(session, "items", [])
    seen: set[str] = set()
    for item in items:
        path = str(getattr(item, "fspath", ""))
        if path in seen:
            continue
        seen.add(path)
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
        import re
        # Match only sqlite3.connect(":memory:") or get_connection(":memory:") calls,
        # not comments or docstrings that mention the string for explanatory purposes.
        if re.search(r"""(?:connect|get_connection)\s*\(\s*['"][^'"]*:memory:[^'"]*['"]\s*\)""", content):
            raise AssertionError(
                f"{path}: forbidden ':memory:' SQLite path — use tmp_path per ADR-4. "
                "WAL mode does not work with :memory: and will silently pass without WAL semantics."
            )
