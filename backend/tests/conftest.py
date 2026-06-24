from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db import get_session
from app.main import app
from app.migrations.runner import (
    MIGRATIONS,
    _current_version,
    _ensure_schema_version_table,
    _migration_003_rhythm_raw_beats,
    _set_version,
    run_migrations,
)
from app.services.seed import seed_demo_data


@pytest.fixture
def regression_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[dict, None, None]:
    db_file = tmp_path / "regression.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    monkeypatch.setattr("app.db.engine", test_engine)
    monkeypatch.setattr("app.migrations.runner.engine", test_engine)
    monkeypatch.setattr(settings, "storage_dir", str(storage_dir))

    SQLModel.metadata.create_all(test_engine)
    run_migrations()
    with Session(test_engine) as session:
        seed_demo_data(session)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)

    yield {"client": client, "engine": test_engine, "storage_dir": storage_dir}

    app.dependency_overrides.clear()
    client.close()
