from __future__ import annotations


def test_list_llm_providers_merged_openai(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers")
    assert response.status_code == 200
    providers = response.json()["data"]
    provider_ids = [item["providerId"] for item in providers]
    assert "openai" in provider_ids
    assert "openai-compatible" not in provider_ids
    openai = next(item for item in providers if item["providerId"] == "openai")
    assert "oauth" in openai["authTypes"]
    google = next(item for item in providers if item["providerId"] == "google")
    assert "oauth" in google["authTypes"]


def test_openai_compatible_alias_resolves_to_openai(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers/openai-compatible/status")
    assert response.status_code == 200
    assert response.json()["data"]["providerId"] == "openai"


def test_oauth_start_returns_authorization_url(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.post("/api/v1/llm/providers/openai/oauth/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["authorizationUrl"]
    assert payload["data"]["state"]
    assert payload["meta"]["llmStatus"] == "success"


def test_oauth_callback_mock_flow(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post("/api/v1/llm/providers/google/oauth/start").json()["data"]
    callback = client.post(
        "/api/v1/llm/providers/google/oauth/callback",
        json={"code": "mock_authorization_code", "state": start["state"]},
    )
    assert callback.status_code == 200
    status = callback.json()["data"]
    assert status["authType"] == "oauth"
    assert status["configured"] is True
    assert status["status"] == "authorized"


def test_oauth_revoke_disconnects_provider(regression_env: dict) -> None:
    client = regression_env["client"]
    start = client.post("/api/v1/llm/providers/openai/oauth/start").json()["data"]
    client.post(
        "/api/v1/llm/providers/openai/oauth/callback",
        json={"code": "mock_authorization_code", "state": start["state"]},
    )
    revoke = client.post("/api/v1/llm/providers/openai/oauth/revoke")
    assert revoke.status_code == 200
    assert revoke.json()["data"]["revoked"] is True

    status = client.get("/api/v1/llm/providers/openai/status").json()["data"]
    assert status["configured"] is False
