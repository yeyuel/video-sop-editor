from __future__ import annotations


def _login(client, *, username: str = "director", password: str = "root123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["data"]["sessionToken"]


def test_login_options_lists_enabled_users(regression_env: dict) -> None:
    raw_client = regression_env["raw_client"]
    response = raw_client.get("/api/v1/auth/login-options")
    assert response.status_code == 200
    options = response.json()["data"]
    usernames = {item["username"] for item in options}
    assert "director" in usernames
    assert "editor" in usernames


def test_project_routes_require_auth(regression_env: dict) -> None:
    raw_client = regression_env["raw_client"]
    response = raw_client.get("/api/v1/projects")
    assert response.status_code == 401


def test_editor_can_access_project_workspace(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client, username="editor", password="edit123")
    headers = {"X-Session-Token": token}

    workspace = client.get("/api/v1/projects/proj_001/workspace", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["data"]["project"]["id"] == "proj_001"


def test_editor_cannot_delete_project(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client, username="editor", password="edit123")
    headers = {"X-Session-Token": token}

    response = client.delete("/api/v1/projects/proj_001", headers=headers)
    assert response.status_code == 403


def test_editor_cannot_manage_users(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client, username="editor", password="edit123")
    headers = {"X-Session-Token": token}

    response = client.get("/api/v1/auth/users", headers=headers)
    assert response.status_code == 403


def test_editor_cannot_read_llm_audit_logs(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client, username="editor", password="edit123")
    headers = {"X-Session-Token": token}

    response = client.get("/api/v1/llm/audit-logs", headers=headers)
    assert response.status_code == 403


def test_director_can_read_llm_audit_logs(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/audit-logs")
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_theme_llm_call_writes_audit_log(regression_env: dict) -> None:
    client = regression_env["client"]
    projects = client.get("/api/v1/projects").json()["data"]
    project_id = projects[0]["id"]

    generate = client.post(
        f"/api/v1/projects/{project_id}/themes/generate-llm",
        json={"count": 2},
    )
    assert generate.status_code == 200

    logs = client.get("/api/v1/llm/audit-logs?limit=5").json()["data"]
    assert any("themes/generate-llm" in item["endpoint"] for item in logs)


def test_disabled_user_cannot_login(regression_env: dict) -> None:
    client = regression_env["client"]
    director_token = _login(client)
    create_response = client.post(
        "/api/v1/auth/users",
        headers={"X-Session-Token": director_token},
        json={
            "username": "editor_disabled_s12",
            "password": "secret12",
            "displayName": "禁用剪辑",
            "role": "editor",
            "uiEnabled": False,
        },
    )
    assert create_response.status_code == 201

    raw_client = regression_env["raw_client"]
    blocked = raw_client.post(
        "/api/v1/auth/login",
        json={"username": "editor_disabled_s12", "password": "secret12"},
    )
    assert blocked.status_code == 401
