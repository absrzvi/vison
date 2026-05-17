from __future__ import annotations

import sqlite3
from collections.abc import Generator

from .database import get_connection


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
