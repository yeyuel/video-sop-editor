from __future__ import annotations


def test_list_llm_providers_subscription_auth_types(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers")
    assert response.status_code == 200
    providers = response.json()["data"]
    openai = next(item for item in providers if item["providerId"] == "openai")
    google = next(item for item in providers if item["providerId"] == "google")
    assert "codex_oauth" in openai["authTypes"]
    assert "gemini_subscription" in google["authTypes"]


def test_codex_model_catalog(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers/openai/models?auth_type=codex_oauth")
    assert response.status_code == 200
    model_ids = [item["modelId"] for item in response.json()["data"]]
    assert "gpt-5.5" in model_ids
    assert "gpt-5.4" in model_ids
    assert "gpt-4.1-mini" not in model_ids


def test_codex_subscription_oauth_mock_flow(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/start?auth_type=codex_oauth"
    )
    assert start.status_code == 200
    payload = start.json()["data"]
    assert payload["authorizationUrl"]
    assert payload["state"]

    callback = client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/callback?auth_type=codex_oauth",
        json={"code": "mock_subscription_code", "state": payload["state"]},
    )
    assert callback.status_code == 200
    status = callback.json()["data"]
    assert status["authType"] == "codex_oauth"
    assert status["configured"] is True
    assert status["status"] == "authorized"


def test_gemini_subscription_oauth_mock_flow(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post(
        "/api/v1/llm/providers/google/subscription-oauth/start?auth_type=gemini_subscription"
    )
    assert start.status_code == 200
    payload = start.json()["data"]
    callback = client.post(
        "/api/v1/llm/providers/google/subscription-oauth/callback?auth_type=gemini_subscription",
        json={"code": "mock_subscription_code", "state": payload["state"]},
    )
    assert callback.status_code == 200
    status = callback.json()["data"]
    assert status["authType"] == "gemini_subscription"
    assert status["configured"] is True


def test_codex_subscription_test_connection_mock(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/start?auth_type=codex_oauth"
    ).json()["data"]
    client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/callback?auth_type=codex_oauth",
        json={"code": "mock_subscription_code", "state": start["state"]},
    )
    client.post(
        "/api/v1/llm/providers/openai/config",
        json={
            "authType": "codex_oauth",
            "baseUrl": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini",
        },
    )
    test = client.post(
        "/api/v1/llm/providers/openai/test",
        json={"authType": "codex_oauth", "baseUrl": "https://api.openai.com/v1", "model": "gpt-4.1-mini"},
    )
    assert test.status_code == 200
    assert test.json()["data"]["ok"] is True


def test_codex_vision_skips_api_key_gate(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/start?auth_type=codex_oauth"
    ).json()["data"]
    client.post(
        "/api/v1/llm/providers/openai/subscription-oauth/callback?auth_type=codex_oauth",
        json={"code": "mock_subscription_code", "state": start["state"]},
    )
    client.post(
        "/api/v1/llm/providers/openai/config",
        json={
            "authType": "codex_oauth",
            "baseUrl": "https://api.openai.com/v1",
            "model": "gpt-5.4",
        },
    )
    activate = client.post("/api/v1/llm/providers/openai/activate")
    assert activate.status_code == 200

    project_id = client.get("/api/v1/projects").json()["data"][0]["id"]
    capability = client.get(f"/api/v1/projects/{project_id}/assets/vision-capability")
    assert capability.status_code == 200
    assert capability.json()["data"]["configured"] is True
    assert capability.json()["data"]["supportsVision"] is True

    asset_id = client.get(f"/api/v1/projects/{project_id}/assets").json()["data"][0]["assetId"]
    response = client.post(
        f"/api/v1/projects/{project_id}/assets/{asset_id}/vision-analyze/stream",
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert "未配置 LLM API Key" not in response.text


def test_subscription_oauth_revoke(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post(
        "/api/v1/llm/providers/google/subscription-oauth/start?auth_type=gemini_subscription"
    ).json()["data"]
    client.post(
        "/api/v1/llm/providers/google/subscription-oauth/callback?auth_type=gemini_subscription",
        json={"code": "mock_subscription_code", "state": start["state"]},
    )
    revoke = client.post(
        "/api/v1/llm/providers/google/subscription-oauth/revoke?auth_type=gemini_subscription"
    )
    assert revoke.status_code == 200
    assert revoke.json()["data"]["revoked"] is True
