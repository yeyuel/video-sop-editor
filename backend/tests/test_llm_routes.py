from __future__ import annotations


def _login(client, *, username: str = "director", password: str = "root123") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["sessionToken"]
    return payload["sessionToken"]


def _director_headers(client) -> dict[str, str]:
    return {"X-Session-Token": _login(client)}


def test_list_llm_providers(regression_env: dict) -> None:
    raw_client = regression_env["raw_client"]
    response = raw_client.get("/api/v1/llm/providers")
    assert response.status_code == 401

    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers", headers=_director_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    providers = payload["data"]
    assert isinstance(providers, list)
    assert any(item["providerId"] == "openai" for item in providers)


def test_get_llm_status(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/status", headers=_director_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["providerId"]
    assert payload["data"]["status"] in {"configured", "not_configured", "authorized"}


def test_generate_themes_with_llm_returns_meta(regression_env: dict) -> None:
    client = regression_env["client"]
    projects = client.get("/api/v1/projects").json()["data"]
    project_id = projects[0]["id"]
    for path_suffix in ("generate-llm", "generate:llm"):
        response = client.post(
            f"/api/v1/projects/{project_id}/themes/{path_suffix}",
            json={"count": 3},
        )
        assert response.status_code == 200, path_suffix
        payload = response.json()
        assert "llmStatus" in payload["meta"]
        assert payload["meta"]["llmStatus"] in {
            "success",
            "fallback_rule",
            "not_configured",
            "timeout",
            "network",
        }


def test_activate_llm_provider(regression_env: dict) -> None:
    client = regression_env["client"]
    headers = _director_headers(client)
    save_response = client.post(
        "/api/v1/llm/providers/kimi/config",
        headers=headers,
        json={
            "authType": "api_key",
            "baseUrl": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "apiKey": "test-kimi-key",
        },
    )
    assert save_response.status_code == 200

    activate_response = client.post("/api/v1/llm/providers/kimi/activate", headers=headers)
    assert activate_response.status_code == 200
    payload = activate_response.json()
    assert "kimi" in payload["data"]["message"].lower() or payload["data"]["providerId"] == "kimi"

    status_response = client.get("/api/v1/llm/status", headers=headers)
    assert status_response.json()["data"]["providerId"] == "kimi"


def test_llm_provider_without_api_key(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.post(
        "/api/v1/llm/providers/kimi/test",
        headers=_director_headers(client),
        json={},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is False
    assert payload["data"]["llmStatus"] == "not_configured"


def test_oauth_start_returns_redirect(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.post(
        "/api/v1/llm/providers/openai/oauth/start",
        headers=_director_headers(client),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["authorizationUrl"]
    assert payload["meta"]["llmStatus"] == "success"


def test_editor_cannot_manage_llm_config(regression_env: dict) -> None:
    client = regression_env["client"]
    director_token = _login(client)
    create_response = client.post(
        "/api/v1/auth/users",
        headers={"X-Session-Token": director_token},
        json={
            "username": "editor_llm",
            "password": "secret12",
            "displayName": "剪辑 LLM",
            "role": "editor",
            "uiEnabled": True,
        },
    )
    assert create_response.status_code == 201

    editor_token = _login(client, username="editor_llm", password="secret12")
    editor_headers = {"X-Session-Token": editor_token}

    list_response = client.get("/api/v1/llm/providers", headers=editor_headers)
    assert list_response.status_code == 403

    save_response = client.post(
        "/api/v1/llm/providers/kimi/config",
        headers=editor_headers,
        json={
            "authType": "api_key",
            "baseUrl": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "apiKey": "blocked-key",
        },
    )
    assert save_response.status_code == 403
