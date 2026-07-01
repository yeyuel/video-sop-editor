from __future__ import annotations

from app.services.llm.provider_ids import normalize_provider_id
from app.services.llm.oauth.modes import is_subscription_auth_type
from app.services.llm.types import ModelOption

MODEL_CATALOG: dict[str, list[ModelOption]] = {
    "openai": [
        ModelOption("gpt-4.1-mini", "GPT-4.1 Mini", "通用轻量，适合大多数 JSON 任务", recommended=True),
        ModelOption("gpt-4.1", "GPT-4.1", "更强推理与生成质量"),
        ModelOption("gpt-4o-mini", "GPT-4o Mini", "多模态轻量模型"),
        ModelOption("gpt-4o", "GPT-4o", "多模态旗舰模型"),
    ],
    "deepseek": [
        ModelOption("deepseek-chat", "DeepSeek Chat", "通用对话与 JSON 生成", recommended=True),
        ModelOption("deepseek-reasoner", "DeepSeek Reasoner", "深度推理任务"),
    ],
    "kimi": [
        ModelOption("kimi-k2.6", "Kimi K2.6", "当前通用推荐，256K 上下文", recommended=True),
        ModelOption("kimi-k2.5", "Kimi K2.5", "多模态 Agent，成本更低"),
        ModelOption("kimi-k2.7-code", "Kimi K2.7 Code", "代码与软件工程场景"),
        ModelOption("moonshot-v1-8k", "Moonshot V1 8K", "短文本，8K 上下文"),
        ModelOption("moonshot-v1-32k", "Moonshot V1 32K", "长文本，32K 上下文"),
        ModelOption("moonshot-v1-128k", "Moonshot V1 128K", "超长文本，128K 上下文"),
    ],
    "glm": [
        ModelOption("glm-4-flash", "GLM-4 Flash", "轻量快速，适合高频调用", recommended=True),
        ModelOption("glm-4-air", "GLM-4 Air", "平衡质量与成本"),
        ModelOption("glm-4-plus", "GLM-4 Plus", "更高质量生成"),
    ],
    "google": [
        ModelOption("gemini-2.0-flash", "Gemini 2.0 Flash", "多模态，性价比高", recommended=True),
        ModelOption("gemini-1.5-flash", "Gemini 1.5 Flash", "多模态轻量"),
        ModelOption("gemini-1.5-pro", "Gemini 1.5 Pro", "多模态高质量"),
    ],
}

AUTH_TYPE_MODEL_CATALOG: dict[str, dict[str, list[ModelOption]]] = {
    "openai": {
        "codex_oauth": [
            ModelOption("gpt-5.5", "GPT-5.5", "Codex 默认推荐，复杂推理、编程与 Vision", recommended=True),
            ModelOption("gpt-5.4", "GPT-5.4", "Codex 通用编程与 Vision，与 ChatGPT 5.4 一致"),
            ModelOption("gpt-5.4-mini", "GPT-5.4 Mini", "轻量快速，支持 Vision 的高频 JSON 任务"),
        ],
    },
    "google": {
        "gemini_subscription": [
            ModelOption("gemini-2.5-pro", "Gemini 2.5 Pro", "订阅默认，高质量多模态", recommended=True),
            ModelOption("gemini-2.5-flash", "Gemini 2.5 Flash", "快速响应，性价比高"),
            ModelOption("gemini-2.0-flash", "Gemini 2.0 Flash", "轻量多模态"),
        ],
    },
}

# 常见误填别名（如 OpenClaw / 文档简写）→ 官方 model id
MODEL_ALIASES: dict[str, dict[str, str]] = {
    "kimi": {
        "k2.6": "kimi-k2.6",
        "k2.5": "kimi-k2.5",
        "k2.7": "kimi-k2.7-code",
        "k2.7-code": "kimi-k2.7-code",
        "kimi-k2.7": "kimi-k2.7-code",
    },
}


def list_models_for_provider(provider_id: str, auth_type: str = "api_key") -> list[ModelOption]:
    canonical = normalize_provider_id(provider_id)
    if is_subscription_auth_type(auth_type):
        auth_models = AUTH_TYPE_MODEL_CATALOG.get(canonical, {}).get(auth_type)
        if auth_models:
            return list(auth_models)
    return list(MODEL_CATALOG.get(canonical, []))


def default_model_for_auth_type(provider_id: str, auth_type: str, fallback: str) -> str:
    models = list_models_for_provider(provider_id, auth_type)
    for item in models:
        if item.recommended:
            return item.model_id
    return fallback


def normalize_model_id(provider_id: str, model: str) -> str:
    canonical = normalize_provider_id(provider_id)
    normalized = model.strip()
    if not normalized:
        return normalized
    aliases = MODEL_ALIASES.get(canonical, {})
    return aliases.get(normalized.lower(), normalized)


def default_model_for_provider(provider_id: str, fallback: str) -> str:
    models = list_models_for_provider(provider_id)
    for item in models:
        if item.recommended:
            return item.model_id
    return fallback


def resolve_temperature(model_id: str, requested: float) -> float:
    """Kimi K2 系列仅允许固定 temperature（当前 API 要求 0.6）。"""
    normalized = model_id.strip().lower()
    if normalized.startswith("kimi-k2."):
        return 0.6
    return requested


def supports_json_response_format(provider_id: str, model_id: str) -> bool:
    """Kimi K2 在 response_format=json_object 下可能长时间无响应。"""
    normalized = model_id.strip().lower()
    if provider_id == "kimi" and normalized.startswith("kimi-k2."):
        return False
    return True


def should_disable_kimi_thinking(provider_id: str, model_id: str) -> bool:
    """K2.5/K2.6 默认 thinking 会占用 max_tokens，导致 content 为空。"""
    if provider_id != "kimi":
        return False
    normalized = model_id.strip().lower()
    return normalized.startswith("kimi-k2.5") or normalized.startswith("kimi-k2.6")
