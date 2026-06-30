from __future__ import annotations

import hashlib
from pathlib import Path


def source_file_fingerprint(source: Path) -> str:
    stat = source.stat()
    payload = f"{source.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def relative_path_fingerprint(project_id: str, relative_path: str) -> str:
    payload = f"{project_id}|{relative_path.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
