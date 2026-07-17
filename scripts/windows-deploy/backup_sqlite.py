from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def backup(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as destination_db:
        source_db.backup(destination_db)


def restore(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Backup does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as destination_db:
        source_db.backup(destination_db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or restore a consistent SQLite backup.")
    parser.add_argument("mode", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    if args.mode == "backup":
        backup(args.source, args.destination)
    else:
        restore(args.source, args.destination)


if __name__ == "__main__":
    main()
