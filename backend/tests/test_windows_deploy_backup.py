from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "windows-deploy"
    / "backup_sqlite.py"
)
SPEC = importlib.util.spec_from_file_location("windows_deploy_backup", SCRIPT_PATH)
assert SPEC and SPEC.loader
BACKUP_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BACKUP_MODULE)


def read_value(database: Path) -> str:
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT value FROM deployment_test WHERE id = 1").fetchone()
    assert row is not None
    return str(row[0])


def test_sqlite_backup_and_restore(tmp_path: Path) -> None:
    database = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE deployment_test (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO deployment_test (id, value) VALUES (1, 'before')")
        connection.commit()

    BACKUP_MODULE.backup(database, backup)
    assert read_value(backup) == "before"

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE deployment_test SET value = 'after' WHERE id = 1")
        connection.commit()
    assert read_value(database) == "after"

    BACKUP_MODULE.restore(backup, database)
    assert read_value(database) == "before"
