from __future__ import annotations

from app.services.llm.model_catalog import MODEL_CATALOG, default_model_for_provider
from app.services.llm.types import ModelOption, ProviderDefinition


def _provider(
    *,
    provider_id: str,
    provider_name: str,
    auth_types: list[str],
    default_base_url: str,
    default_model: str,
    openai_compatible: bool = True,
    docs_url: str = "",
) -> ProviderDefinition:
    models = list(MODEL_CATALOG.get(provider_id, []))
    resolved_default = default_model_for_provider(provider_id, default_model)
    return ProviderDefinition(
        provider_id=provider_id,
        provider_name=provider_name,
        auth_types=auth_types,
        default_base_url=default_base_url,
        default_model=resolved_default,
        openai_compatible=openai_compatible,
        docs_url=docs_url,
        supported_models=models,
    )


PROVIDER_REGISTRY: dict[str, ProviderDefinition] = {
    "openai-compatible": _provider(
        provider_id="openai-compatible",
        provider_name="OpenAI Compatible",
        auth_types=["api_key"],
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
    ),
    "openai": _provider(
        provider_id="openai",
        provider_name="OpenAI",
        auth_types=["api_key", "oauth", "device_code"],
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        docs_url="https://platform.openai.com/docs",
    ),
    "deepseek": _provider(
        provider_id="deepseek",
        provider_name="DeepSeek",
        auth_types=["api_key"],
        default_base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        docs_url="https://platform.deepseek.com/docs",
    ),
    "kimi": _provider(
        provider_id="kimi",
        provider_name="Kimi (Moonshot)",
        auth_types=["api_key"],
        default_base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k2.6",
        docs_url="https://platform.moonshot.cn/docs",
    ),
    "glm": _provider(
        provider_id="glm",
        provider_name="智谱 GLM",
        auth_types=["api_key"],
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-flash",
        docs_url="https://open.bigmodel.cn/dev/api",
    ),
    "google": _provider(
        provider_id="google",
        provider_name="Google Gemini",
        auth_types=["api_key"],
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.0-flash",
        docs_url="https://ai.google.dev/gemini-api/docs",
    ),
}


def get_provider(provider_id: str) -> ProviderDefinition | None:
    normalized = provider_id.strip().lower()
    return PROVIDER_REGISTRY.get(normalized)


def list_providers() -> list[ProviderDefinition]:
    return list(PROVIDER_REGISTRY.values())


def list_models(provider_id: str) -> list[ModelOption]:
    provider = get_provider(provider_id)
    if not provider:
        return []
    return list(provider.supported_models)
