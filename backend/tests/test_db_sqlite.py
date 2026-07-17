from __future__ import annotations

import sqlite3

from app.core.config import settings
from app.db import configure_sqlite_connection


def test_sqlite_connection_uses_small_team_pragmas(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "pragmas.db")
    try:
        configure_sqlite_connection(connection, object())
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert journal_mode.lower() == "wal"
    assert synchronous == 1
    assert busy_timeout == max(1000, settings.sqlite_busy_timeout_ms)
    assert foreign_keys == 1
