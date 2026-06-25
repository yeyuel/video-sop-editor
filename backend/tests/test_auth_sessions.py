from __future__ import annotations


def _login(client, *, username: str = "director", password: str = "root123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sessionToken"]
    assert payload["user"]["username"] == username
    return payload["sessionToken"]


def test_login_returns_session_token(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)
    assert len(token) > 20


def test_auth_me_requires_token(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_auth_me_with_valid_token(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)
    response = client.get("/api/v1/auth/me", headers={"X-Session-Token": token})
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "director"


def test_logout_revokes_session(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)

    logout_response = client.post("/api/v1/auth/logout", headers={"X-Session-Token": token})
    assert logout_response.status_code == 200

    me_response = client.get("/api/v1/auth/me", headers={"X-Session-Token": token})
    assert me_response.status_code == 401


def test_list_users_requires_director_session(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/auth/users")
    assert response.status_code == 401

    token = _login(client)
    users_response = client.get("/api/v1/auth/users", headers={"X-Session-Token": token})
    assert users_response.status_code == 200
    users = users_response.json()["data"]
    assert any(item["username"] == "director" for item in users)


def test_create_user_reserved_for_director(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)

    create_response = client.post(
        "/api/v1/auth/users",
        headers={"X-Session-Token": token},
        json={
            "username": "editor_a",
            "password": "secret12",
            "displayName": "剪辑 A",
            "role": "editor",
            "uiEnabled": False,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["username"] == "editor_a"
    assert created["uiEnabled"] is False

    blocked_login = client.post(
        "/api/v1/auth/login",
        json={"username": "editor_a", "password": "secret12"},
    )
    assert blocked_login.status_code == 401


def test_update_user_enables_login(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)

    create_response = client.post(
        "/api/v1/auth/users",
        headers={"X-Session-Token": token},
        json={
            "username": "editor_b",
            "password": "secret12",
            "displayName": "剪辑 B",
            "role": "editor",
            "uiEnabled": False,
        },
    )
    user_id = create_response.json()["data"]["id"]

    update_response = client.put(
        f"/api/v1/auth/users/{user_id}",
        headers={"X-Session-Token": token},
        json={"uiEnabled": True, "displayName": "剪辑 B 更新"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["uiEnabled"] is True
    assert updated["displayName"] == "剪辑 B 更新"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "editor_b", "password": "secret12"},
    )
    assert login_response.status_code == 200


def test_delete_user(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)

    create_response = client.post(
        "/api/v1/auth/users",
        headers={"X-Session-Token": token},
        json={
            "username": "editor_c",
            "password": "secret12",
            "displayName": "剪辑 C",
            "role": "editor",
            "uiEnabled": True,
        },
    )
    user_id = create_response.json()["data"]["id"]

    delete_response = client.delete(
        f"/api/v1/auth/users/{user_id}",
        headers={"X-Session-Token": token},
    )
    assert delete_response.status_code == 200

    users = client.get("/api/v1/auth/users", headers={"X-Session-Token": token}).json()["data"]
    assert all(item["id"] != user_id for item in users)


def test_cannot_delete_current_user(regression_env: dict) -> None:
    client = regression_env["client"]
    token = _login(client)
    me = client.get("/api/v1/auth/me", headers={"X-Session-Token": token}).json()["data"]

    response = client.delete(
        f"/api/v1/auth/users/{me['id']}",
        headers={"X-Session-Token": token},
    )
    assert response.status_code == 400
