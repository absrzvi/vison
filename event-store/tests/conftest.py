"""ADR-4: enforce no :memory: SQLite paths in any test file.

WAL mode silently degrades when using :memory: — all test fixtures must
use tmp_path-scoped on-disk files to test real WAL semantics.
"""
from __future__ import annotations

from pathlib import Path

import anyio
import pytest
from starlette.testclient import WebSocketTestSession

# A starlette WebSocketTestSession's ``receive`` blocks the calling test thread
# forever (``portal.call`` has no timeout) if the expected envelope is never
# broadcast — e.g. a seed POST that 422s instead of writing an event. That
# blocks INSIDE the test body, so pytest never reaches its tally: one broken
# fixture wedges the whole worker. Bounding every WS receive turns such a hang
# into a per-test ``TimeoutError`` (a clean failure) that cannot take the suite
# down with it.
_WS_RECEIVE_TIMEOUT_S = 5.0


@pytest.fixture(autouse=True)
def _bounded_ws_receive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cap every WebSocketTestSession.receive so a never-arriving envelope
    raises TimeoutError instead of blocking the test thread indefinitely."""

    def receive(self: WebSocketTestSession) -> dict[str, object]:
        async def _recv() -> dict[str, object]:
            with anyio.fail_after(_WS_RECEIVE_TIMEOUT_S):
                return await self._send_rx.receive()

        return self.portal.call(_recv)

    monkeypatch.setattr(WebSocketTestSession, "receive", receive)


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
        pattern = r"""(?:connect|get_connection)\s*\(\s*['"][^'"]*:memory:[^'"]*['"]\s*\)"""
        if re.search(pattern, content):
            raise AssertionError(
                f"{path}: forbidden ':memory:' SQLite path — use tmp_path per ADR-4. "
                "WAL mode does not work with :memory: and will silently pass without WAL semantics."
            )
