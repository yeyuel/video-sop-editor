from __future__ import annotations

from app.services.llm.model_catalog import MODEL_CATALOG, default_model_for_provider, list_models_for_provider
from app.services.llm.provider_ids import CANONICAL_PROVIDER_ORDER, normalize_provider_id
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
    subtitle: str = "",
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
        subtitle=subtitle,
    )


PROVIDER_REGISTRY: dict[str, ProviderDefinition] = {
    "openai": _provider(
        provider_id="openai",
        provider_name="OpenAI",
        auth_types=["api_key", "oauth", "codex_oauth", "device_code"],
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-mini",
        docs_url="https://platform.openai.com/docs",
        subtitle="官方 API · ChatGPT 登录 (Codex) · OAuth",
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
        auth_types=["api_key", "oauth", "gemini_subscription"],
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        default_model="gemini-2.0-flash",
        docs_url="https://ai.google.dev/gemini-api/docs",
        subtitle="Gemini API · Google 订阅登录 · OAuth",
    ),
}


def get_provider(provider_id: str) -> ProviderDefinition | None:
    canonical = normalize_provider_id(provider_id)
    return PROVIDER_REGISTRY.get(canonical)


def list_providers() -> list[ProviderDefinition]:
    return [
        PROVIDER_REGISTRY[provider_id]
        for provider_id in CANONICAL_PROVIDER_ORDER
        if provider_id in PROVIDER_REGISTRY
    ]


def list_models(provider_id: str, auth_type: str = "api_key") -> list[ModelOption]:
    provider = get_provider(provider_id)
    if not provider:
        return []
    return list_models_for_provider(provider.provider_id, auth_type)
