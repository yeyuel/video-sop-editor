def test_list_llm_providers(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    providers = payload["data"]
    assert isinstance(providers, list)
    assert any(item["providerId"] == "openai-compatible" for item in providers)


def test_get_llm_status(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/status")
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
    save_response = client.post(
        "/api/v1/llm/providers/kimi/config",
        json={
            "authType": "api_key",
            "baseUrl": "https://api.moonshot.cn/v1",
            "model": "moonshot-v1-8k",
            "apiKey": "test-kimi-key",
        },
    )
    assert save_response.status_code == 200

    activate_response = client.post("/api/v1/llm/providers/kimi/activate")
    assert activate_response.status_code == 200
    payload = activate_response.json()
    assert "kimi" in payload["data"]["message"].lower() or payload["data"]["providerId"] == "kimi"

    status_response = client.get("/api/v1/llm/status")
    assert status_response.json()["data"]["providerId"] == "kimi"


def test_llm_provider_without_api_key(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.post("/api/v1/llm/providers/kimi/test", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["ok"] is False
    assert payload["data"]["llmStatus"] == "not_configured"


def test_oauth_start_not_implemented(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.post("/api/v1/llm/providers/openai/oauth/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["llmStatus"] == "not_implemented"
