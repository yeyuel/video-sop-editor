from fastapi.testclient import TestClient

from app.main import app
from app.runtime.shutdown import reset_shutdown_state


def test_app_lifespan_boots_and_seeds_demo_data() -> None:
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["data"]["status"] == "ok"

        login = client.post(
            "/api/v1/auth/login",
            json={"username": "director", "password": "root123"},
        )
        assert login.status_code == 200
        token = login.json()["data"]["sessionToken"]

        workspace = client.get(
            "/api/v1/projects/proj_001/workspace",
            headers={"X-Session-Token": token},
        )
        assert workspace.status_code == 200
        payload = workspace.json()["data"]
        assert payload["project"]["name"] == "五月的台州"
        assert len(payload["storyboard"]) >= 1

        projects = client.get(
            "/api/v1/projects",
            headers={"X-Session-Token": token},
        )
        assert projects.status_code == 200
        assert len(projects.json()["data"]) == 1
    reset_shutdown_state()
