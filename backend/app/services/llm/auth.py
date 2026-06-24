from __future__ import annotations

from app.services.llm.types import LlmErrorCode, LlmProviderStatus, ResolvedLlmConfig


def resolve_authorization_header(config: ResolvedLlmConfig) -> tuple[str | None, LlmErrorCode | None, str]:
    if config.auth_type == "api_key":
        if not config.api_key.strip():
            return None, LlmErrorCode.NOT_CONFIGURED, "未配置 LLM API Key，请在环境变量或 Provider 配置中设置。"
        return f"Bearer {config.api_key.strip()}", None, ""

    if config.auth_type == "oauth":
        return None, LlmErrorCode.NOT_IMPLEMENTED, "OAuth 授权流程尚未接入，当前请使用 API Key 模式。"

    if config.auth_type == "device_code":
        return None, LlmErrorCode.NOT_IMPLEMENTED, "Device Code 授权流程尚未接入，当前请使用 API Key 模式。"

    return None, LlmErrorCode.UNSUPPORTED_AUTH, f"不支持的认证类型：{config.auth_type}"


def evaluate_config_status(config: ResolvedLlmConfig) -> LlmProviderStatus:
    if config.auth_type == "api_key":
        if config.api_key.strip():
            return LlmProviderStatus.CONFIGURED
        return LlmProviderStatus.NOT_CONFIGURED

    if config.auth_type in {"oauth", "device_code"}:
        return LlmProviderStatus.NOT_CONFIGURED

    return LlmProviderStatus.INVALID
