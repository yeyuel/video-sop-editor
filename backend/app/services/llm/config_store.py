from __future__ import annotations

from sqlmodel import Session, select

from app.core.config import settings
from app.models.entities import AppSettingEntity, LlmProviderConfigEntity
from app.services.llm.auth import enrich_config_with_auth, evaluate_config_status, is_provider_configured
from app.services.llm.model_catalog import normalize_model_id
from app.services.llm.oauth.modes import is_subscription_auth_type
from app.services.llm.oauth.service import oauth_connection_status
from app.services.llm.subscription_oauth.service import subscription_connection_status
from app.services.llm.provider_ids import normalize_provider_id
from app.services.llm.registry import get_provider, list_providers
from app.services.llm.types import LlmProviderStatus, ResolvedLlmConfig
from app.services.secret_vault import decrypt_api_key_if_needed, encrypt_api_key_if_needed


ACTIVE_LLM_PROVIDER_SETTING_KEY = "llm_active_provider_id"


def resolve_active_provider_id(session: Session | None = None) -> str:
    if session:
        stored = session.get(AppSettingEntity, ACTIVE_LLM_PROVIDER_SETTING_KEY)
        if stored and stored.value.strip() and get_provider(stored.value.strip()):
            return normalize_provider_id(stored.value.strip())
    return settings.resolved_llm_provider


def set_active_provider_id(session: Session, provider_id: str) -> str:
    canonical = normalize_provider_id(provider_id)
    provider = get_provider(canonical)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")

    entity = session.get(AppSettingEntity, ACTIVE_LLM_PROVIDER_SETTING_KEY)
    if not entity:
        entity = AppSettingEntity(key=ACTIVE_LLM_PROVIDER_SETTING_KEY, value=provider.provider_id)
    else:
        entity.value = provider.provider_id
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity.value


def _resolve_timeout_sec(provider_id: str) -> int:
    timeout = settings.resolved_llm_timeout_sec or 120
    if provider_id == "kimi":
        return max(timeout, 120)
    return timeout


def _build_config(
    *,
    provider_id: str,
    auth_type: str,
    base_url: str,
    model: str,
    api_key: str,
    status: LlmProviderStatus,
) -> ResolvedLlmConfig:
    provider = get_provider(provider_id)
    assert provider is not None
    return ResolvedLlmConfig(
        provider_id=provider.provider_id,
        provider_name=provider.provider_name,
        auth_type=auth_type,
        base_url=base_url or provider.default_base_url,
        model=normalize_model_id(provider.provider_id, model or provider.default_model),
        api_key=api_key,
        timeout_sec=_resolve_timeout_sec(provider.provider_id),
        max_retries=settings.resolved_llm_max_retries,
        status=status,
    )


def resolve_active_config(session: Session | None = None) -> ResolvedLlmConfig:
    provider_id = resolve_active_provider_id(session) if session else settings.resolved_llm_provider
    provider = get_provider(provider_id) or get_provider("openai")
    assert provider is not None

    stored = _load_stored_config(session, provider.provider_id) if session else None
    api_key = settings.resolved_llm_api_key
    base_url = settings.resolved_llm_base_url
    model = settings.resolved_llm_model
    auth_type = "api_key"
    status = LlmProviderStatus.NOT_CONFIGURED

    if stored:
        auth_type = stored.auth_type or "api_key"
        base_url = stored.base_url or base_url
        model = normalize_model_id(provider.provider_id, stored.model or model)
        if stored.api_key:
            api_key = decrypt_api_key_if_needed(stored.api_key)
        if stored.status in LlmProviderStatus:
            status = LlmProviderStatus(stored.status)

    config = _build_config(
        provider_id=provider.provider_id,
        auth_type=auth_type,
        base_url=base_url,
        model=model,
        api_key=api_key,
        status=status,
    )
    if auth_type == "api_key" and api_key.strip() and config.status == LlmProviderStatus.NOT_CONFIGURED:
        config.status = LlmProviderStatus.CONFIGURED
    if session and config.auth_type in {"oauth", "codex_oauth", "gemini_subscription"}:
        config = enrich_config_with_auth(session, config)
    return config


def resolve_provider_config(
    session: Session,
    provider_id: str,
    *,
    base_url: str = "",
    model: str = "",
    api_key: str = "",
    auth_type: str = "",
) -> ResolvedLlmConfig:
    canonical = normalize_provider_id(provider_id)
    provider = get_provider(canonical)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")

    active = resolve_active_config(session)
    stored = _load_stored_config(session, canonical)

    if canonical == active.provider_id:
        resolved_base = active.base_url
        resolved_model = active.model
        resolved_key = active.api_key
        resolved_auth = active.auth_type
        status = active.status
    else:
        resolved_base = stored.base_url if stored and stored.base_url else provider.default_base_url
        resolved_model = stored.model if stored and stored.model else provider.default_model
        resolved_key = decrypt_api_key_if_needed(stored.api_key) if stored else ""
        resolved_auth = stored.auth_type if stored and stored.auth_type else "api_key"
        status = (
            LlmProviderStatus(stored.status)
            if stored and stored.status in LlmProviderStatus
            else LlmProviderStatus.NOT_CONFIGURED
        )

    if base_url.strip():
        resolved_base = base_url.strip()
    if model.strip():
        resolved_model = normalize_model_id(canonical, model.strip())
    elif resolved_model:
        resolved_model = normalize_model_id(canonical, resolved_model)
    if api_key.strip():
        resolved_key = api_key.strip()
    if auth_type.strip():
        resolved_auth = auth_type.strip()

    config = _build_config(
        provider_id=canonical,
        auth_type=resolved_auth,
        base_url=resolved_base,
        model=resolved_model,
        api_key=resolved_key,
        status=status,
    )
    if resolved_auth == "api_key" and resolved_key.strip():
        config.status = LlmProviderStatus.CONFIGURED
    if resolved_auth == "oauth":
        config = enrich_config_with_auth(session, config)
    elif is_subscription_auth_type(resolved_auth):
        config = enrich_config_with_auth(session, config)
    return config


def save_provider_config(
    session: Session,
    provider_id: str,
    *,
    auth_type: str,
    base_url: str,
    model: str,
    api_key: str = "",
) -> ResolvedLlmConfig:
    canonical = normalize_provider_id(provider_id)
    provider = get_provider(canonical)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")
    if auth_type not in provider.auth_types:
        raise ValueError(f"Provider {canonical} does not support auth type {auth_type}")

    existing = session.exec(
        select(LlmProviderConfigEntity).where(LlmProviderConfigEntity.provider_id == canonical)
    ).first()
    entity = existing or LlmProviderConfigEntity(
        id=f"llm_{canonical}",
        provider_id=canonical,
    )
    entity.auth_type = auth_type
    entity.base_url = base_url.strip() or provider.default_base_url
    entity.model = normalize_model_id(canonical, model.strip() or provider.default_model)
    if auth_type == "api_key" and api_key.strip():
        entity.api_key = encrypt_api_key_if_needed(api_key.strip())
    elif auth_type == "oauth" and api_key.strip():
        entity.api_key = encrypt_api_key_if_needed(api_key.strip())

    if auth_type == "oauth":
        oauth_status, _ = oauth_connection_status(session, provider_id=canonical)
        entity.status = oauth_status.value
    elif is_subscription_auth_type(auth_type):
        oauth_status, _ = subscription_connection_status(session, provider_id=canonical, auth_type=auth_type)
        entity.status = oauth_status.value
    elif decrypt_api_key_if_needed(entity.api_key).strip():
        entity.status = LlmProviderStatus.CONFIGURED.value
    else:
        entity.status = LlmProviderStatus.NOT_CONFIGURED.value

    session.add(entity)
    session.commit()
    session.refresh(entity)
    return resolve_provider_config(session, canonical)


def list_provider_statuses(session: Session) -> list[dict[str, str | list[str]]]:
    configs = {
        normalize_provider_id(item.provider_id): item
        for item in session.exec(select(LlmProviderConfigEntity)).all()
    }
    active = resolve_active_config(session)
    items: list[dict[str, str | list[str]]] = []
    for provider in list_providers():
        stored = configs.get(provider.provider_id)
        if provider.provider_id == active.provider_id:
            status = evaluate_config_status(active).value
        elif stored and stored.auth_type == "oauth":
            oauth_status, _ = oauth_connection_status(session, provider_id=provider.provider_id)
            status = oauth_status.value
        elif stored and is_subscription_auth_type(stored.auth_type):
            oauth_status, _ = subscription_connection_status(
                session,
                provider_id=provider.provider_id,
                auth_type=stored.auth_type,
            )
            status = oauth_status.value
        elif stored and decrypt_api_key_if_needed(stored.api_key).strip():
            status = LlmProviderStatus.CONFIGURED.value
        else:
            status = stored.status if stored else LlmProviderStatus.NOT_CONFIGURED.value
        items.append(
            {
                "providerId": provider.provider_id,
                "providerName": provider.provider_name,
                "authTypes": provider.auth_types,
                "defaultBaseUrl": provider.default_base_url,
                "defaultModel": provider.default_model,
                "openaiCompatible": str(provider.openai_compatible).lower(),
                "status": status,
                "isActive": str(provider.provider_id == active.provider_id).lower(),
                "subtitle": provider.subtitle,
                "models": [
                    {
                        "modelId": item.model_id,
                        "label": item.label,
                        "description": item.description,
                        "recommended": str(item.recommended).lower(),
                    }
                    for item in provider.supported_models
                ],
            }
        )
    return items


def get_provider_status(session: Session, provider_id: str) -> dict[str, str | bool]:
    canonical = normalize_provider_id(provider_id)
    provider = get_provider(canonical)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")

    config = resolve_provider_config(session, canonical)
    stored = _load_stored_config(session, canonical)
    active = resolve_active_config(session)
    is_active = provider.provider_id == active.provider_id
    configured = is_provider_configured(config)
    status = evaluate_config_status(config).value
    message = ""
    if config.auth_type == "oauth" and not configured:
        _, message = oauth_connection_status(session, provider_id=canonical)
    elif is_subscription_auth_type(config.auth_type) and not configured:
        _, message = subscription_connection_status(
            session,
            provider_id=canonical,
            auth_type=config.auth_type,
        )

    return {
        "providerId": provider.provider_id,
        "providerName": provider.provider_name,
        "authType": stored.auth_type if stored and stored.auth_type else config.auth_type,
        "status": status,
        "baseUrl": config.base_url,
        "model": config.model,
        "configured": configured,
        "isActive": is_active,
        "message": message,
    }


def _load_stored_config(
    session: Session,
    provider_id: str,
) -> LlmProviderConfigEntity | None:
    canonical = normalize_provider_id(provider_id)
    entity = session.exec(
        select(LlmProviderConfigEntity).where(LlmProviderConfigEntity.provider_id == canonical)
    ).first()
    if entity:
        return entity
    if canonical != provider_id:
        legacy = session.exec(
            select(LlmProviderConfigEntity).where(
                LlmProviderConfigEntity.provider_id == provider_id.strip().lower()
            )
        ).first()
        return legacy
    return None
