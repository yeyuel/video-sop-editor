from __future__ import annotations

from sqlmodel import Session

from app.services.llm.oauth.modes import is_subscription_auth_type
from app.services.llm.oauth.service import get_valid_access_token
from app.services.llm.subscription_oauth.service import get_valid_subscription_access_token
from app.services.llm.types import LlmErrorCode, LlmProviderStatus, ResolvedLlmConfig


def enrich_config_with_auth(session: Session, config: ResolvedLlmConfig) -> ResolvedLlmConfig:
    if config.auth_type == "oauth":
        access_token, status, message = get_valid_access_token(
            session,
            provider_id=config.provider_id,
        )
        config.access_token = access_token
        config.status = status
        if message and status != LlmProviderStatus.AUTHORIZED:
            config.status = status
        return config

    if is_subscription_auth_type(config.auth_type):
        access_token, status, message, account_id, project_id = get_valid_subscription_access_token(
            session,
            provider_id=config.provider_id,
            auth_type=config.auth_type,
        )
        config.access_token = access_token
        config.account_id = account_id
        config.project_id = project_id
        config.status = status
        if message and status != LlmProviderStatus.AUTHORIZED:
            config.status = status
        return config

    return config


def resolve_authorization_header(
    config: ResolvedLlmConfig,
) -> tuple[str | None, LlmErrorCode | None, str]:
    if config.auth_type == "api_key":
        if not config.api_key.strip():
            return None, LlmErrorCode.NOT_CONFIGURED, "未配置 LLM API Key，请在环境变量或 Provider 配置中设置。"
        return f"Bearer {config.api_key.strip()}", None, ""

    if config.auth_type in {"oauth", "codex_oauth", "gemini_subscription"}:
        if config.access_token.strip():
            return f"Bearer {config.access_token.strip()}", None, ""
        if config.status == LlmProviderStatus.EXPIRED:
            label = "订阅登录" if is_subscription_auth_type(config.auth_type) else "OAuth"
            return None, LlmErrorCode.AUTH_INVALID, f"{label} 授权已过期，请在 LLM 设置页重新连接。"
        label = "订阅登录" if is_subscription_auth_type(config.auth_type) else "OAuth"
        return None, LlmErrorCode.NOT_CONFIGURED, f"尚未完成 {label} 授权，请在 LLM 设置页连接账号。"

    if config.auth_type == "device_code":
        return None, LlmErrorCode.NOT_IMPLEMENTED, "Device Code 授权尚未接入，请改用 API Key 或 OAuth。"

    return None, LlmErrorCode.UNSUPPORTED_AUTH, f"不支持的认证类型：{config.auth_type}"


def evaluate_config_status(config: ResolvedLlmConfig) -> LlmProviderStatus:
    if config.auth_type == "api_key":
        if config.api_key.strip():
            return LlmProviderStatus.CONFIGURED
        return LlmProviderStatus.NOT_CONFIGURED

    if config.auth_type in {"oauth", "codex_oauth", "gemini_subscription"}:
        if config.access_token.strip():
            return LlmProviderStatus.AUTHORIZED
        if config.status in {LlmProviderStatus.EXPIRED, LlmProviderStatus.AUTHORIZED}:
            return config.status
        return LlmProviderStatus.NOT_CONFIGURED

    if config.auth_type == "device_code":
        return LlmProviderStatus.NOT_CONFIGURED

    return LlmProviderStatus.INVALID


def is_provider_configured(config: ResolvedLlmConfig) -> bool:
    status = evaluate_config_status(config)
    return status in {LlmProviderStatus.CONFIGURED, LlmProviderStatus.AUTHORIZED}
