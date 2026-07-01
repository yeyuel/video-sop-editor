from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db import get_session
from app.main import app as fastapi_app
from app.migrations.runner import run_migrations
from app.models.entities import LlmCallLogEntity  # noqa: F401 — register SQLModel metadata
from app.services.seed import seed_demo_data
from tests.auth_client import AuthTestClient


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
    monkeypatch.setattr("app.api.sse_stream.db.engine", test_engine)
    monkeypatch.setattr(settings, "storage_dir", str(storage_dir))
    monkeypatch.setattr(settings, "llm_oauth_mock", True)

    SQLModel.metadata.create_all(test_engine)
    run_migrations()
    with Session(test_engine) as session:
        seed_demo_data(session)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    raw_client = TestClient(fastapi_app)

    login_response = raw_client.post(
        "/api/v1/auth/login",
        json={"username": "director", "password": "root123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["sessionToken"]

    client = AuthTestClient(raw_client, token)

    yield {
        "client": client,
        "raw_client": raw_client,
        "token": token,
        "engine": test_engine,
        "storage_dir": storage_dir,
    }

    fastapi_app.dependency_overrides.clear()
    raw_client.close()
