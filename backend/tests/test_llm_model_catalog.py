from app.services.llm.model_catalog import normalize_model_id
from app.services.llm.registry import get_provider, list_models


def test_kimi_models_include_k2_6() -> None:
    models = list_models("kimi")
    ids = {item.model_id for item in models}
    assert "kimi-k2.6" in ids
    assert "moonshot-v1-8k" in ids


def test_kimi_default_model_is_k2_6() -> None:
    provider = get_provider("kimi")
    assert provider is not None
    assert provider.default_model == "kimi-k2.6"


def test_normalize_kimi_model_alias() -> None:
    assert normalize_model_id("kimi", "k2.6") == "kimi-k2.6"
    assert normalize_model_id("kimi", "kimi-k2.6") == "kimi-k2.6"


def test_resolve_temperature_for_kimi_k2_models() -> None:
    from app.services.llm.model_catalog import resolve_temperature

    assert resolve_temperature("kimi-k2.6", 0) == 0.6
    assert resolve_temperature("kimi-k2.6", 0.4) == 0.6
    assert resolve_temperature("kimi-k2.5", 0.7) == 0.6
    assert resolve_temperature("kimi-k2.7-code", 0.7) == 0.6
    assert resolve_temperature("gpt-4.1-mini", 0.4) == 0.4


def test_kimi_k2_does_not_use_json_response_format() -> None:
    from app.services.llm.model_catalog import (
        should_disable_kimi_thinking,
        supports_json_response_format,
    )

    assert supports_json_response_format("kimi", "kimi-k2.6") is False
    assert supports_json_response_format("kimi", "moonshot-v1-8k") is True
    assert supports_json_response_format("openai", "gpt-4.1-mini") is True
    assert should_disable_kimi_thinking("kimi", "kimi-k2.6") is True
    assert should_disable_kimi_thinking("kimi", "kimi-k2.5") is True
    assert should_disable_kimi_thinking("kimi", "kimi-k2.7-code") is False
    assert should_disable_kimi_thinking("kimi", "moonshot-v1-8k") is False


def test_list_llm_providers_include_models(regression_env: dict) -> None:
    client = regression_env["client"]
    response = client.get("/api/v1/llm/providers")
    assert response.status_code == 200
    providers = response.json()["data"]
    kimi = next(item for item in providers if item["providerId"] == "kimi")
    assert len(kimi["models"]) >= 3
    assert any(model["modelId"] == "kimi-k2.6" for model in kimi["models"])
