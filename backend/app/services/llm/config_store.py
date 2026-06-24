from __future__ import annotations

from sqlmodel import Session, select

from app.core.config import settings
from app.models.entities import AppSettingEntity, LlmProviderConfigEntity
from app.services.llm.model_catalog import normalize_model_id
from app.services.llm.registry import get_provider, list_providers
from app.services.llm.auth import evaluate_config_status
from app.services.llm.types import LlmProviderStatus, ResolvedLlmConfig


ACTIVE_LLM_PROVIDER_SETTING_KEY = "llm_active_provider_id"


def resolve_active_provider_id(session: Session | None = None) -> str:
    if session:
        stored = session.get(AppSettingEntity, ACTIVE_LLM_PROVIDER_SETTING_KEY)
        if stored and stored.value.strip() and get_provider(stored.value.strip()):
            return stored.value.strip()
    return settings.resolved_llm_provider


def set_active_provider_id(session: Session, provider_id: str) -> str:
    provider = get_provider(provider_id)
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


def resolve_active_config(session: Session | None = None) -> ResolvedLlmConfig:
    provider_id = resolve_active_provider_id(session) if session else settings.resolved_llm_provider
    provider = get_provider(provider_id) or get_provider("openai-compatible")
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
            api_key = stored.api_key
        status = LlmProviderStatus(stored.status) if stored.status in LlmProviderStatus else LlmProviderStatus.NOT_CONFIGURED

    config = ResolvedLlmConfig(
        provider_id=provider.provider_id,
        provider_name=provider.provider_name,
        auth_type=auth_type,
        base_url=base_url or provider.default_base_url,
        model=model or provider.default_model,
        api_key=api_key,
        timeout_sec=_resolve_timeout_sec(provider.provider_id),
        max_retries=settings.resolved_llm_max_retries,
        status=status,
    )
    if api_key.strip() and config.status == LlmProviderStatus.NOT_CONFIGURED:
        config.status = LlmProviderStatus.CONFIGURED
    return config


def resolve_provider_config(
    session: Session,
    provider_id: str,
    *,
    base_url: str = "",
    model: str = "",
    api_key: str = "",
) -> ResolvedLlmConfig:
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")

    active = resolve_active_config(session)
    stored = _load_stored_config(session, provider_id)

    if provider_id == active.provider_id:
        resolved_base = active.base_url
        resolved_model = active.model
        resolved_key = active.api_key
        auth_type = active.auth_type
    else:
        resolved_base = stored.base_url if stored and stored.base_url else provider.default_base_url
        resolved_model = stored.model if stored and stored.model else provider.default_model
        resolved_key = stored.api_key if stored else ""
        auth_type = stored.auth_type if stored and stored.auth_type else "api_key"

    if base_url.strip():
        resolved_base = base_url.strip()
    if model.strip():
        resolved_model = normalize_model_id(provider_id, model.strip())
    elif resolved_model:
        resolved_model = normalize_model_id(provider_id, resolved_model)
    if api_key.strip():
        resolved_key = api_key.strip()

    return ResolvedLlmConfig(
        provider_id=provider.provider_id,
        provider_name=provider.provider_name,
        auth_type=auth_type,
        base_url=resolved_base or provider.default_base_url,
        model=resolved_model or provider.default_model,
        api_key=resolved_key,
        timeout_sec=_resolve_timeout_sec(provider.provider_id),
        max_retries=0,
        status=LlmProviderStatus.CONFIGURED if resolved_key.strip() else LlmProviderStatus.NOT_CONFIGURED,
    )


def save_provider_config(
    session: Session,
    provider_id: str,
    *,
    auth_type: str,
    base_url: str,
    model: str,
    api_key: str = "",
) -> ResolvedLlmConfig:
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")
    if auth_type not in provider.auth_types:
        raise ValueError(f"Provider {provider_id} does not support auth type {auth_type}")

    existing = session.exec(
        select(LlmProviderConfigEntity).where(LlmProviderConfigEntity.provider_id == provider_id)
    ).first()
    entity = existing or LlmProviderConfigEntity(
        id=f"llm_{provider_id}",
        provider_id=provider_id,
    )
    entity.auth_type = auth_type
    entity.base_url = base_url.strip() or provider.default_base_url
    entity.model = normalize_model_id(provider_id, model.strip() or provider.default_model)
    if api_key.strip():
        entity.api_key = api_key.strip()
    entity.status = (
        LlmProviderStatus.CONFIGURED.value
        if entity.api_key.strip()
        else LlmProviderStatus.NOT_CONFIGURED.value
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return resolve_active_config(session)


def list_provider_statuses(session: Session) -> list[dict[str, str | list[str]]]:
    configs = {
        item.provider_id: item
        for item in session.exec(select(LlmProviderConfigEntity)).all()
    }
    active = resolve_active_config(session)
    items: list[dict[str, str | list[str]]] = []
    for provider in list_providers():
        stored = configs.get(provider.provider_id)
        status = stored.status if stored else LlmProviderStatus.NOT_CONFIGURED.value
        if provider.provider_id == active.provider_id and active.api_key.strip():
            status = LlmProviderStatus.CONFIGURED.value
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
    provider = get_provider(provider_id)
    if not provider:
        raise ValueError(f"Unknown provider: {provider_id}")

    active = resolve_active_config(session)
    stored = _load_stored_config(session, provider_id)
    is_active = provider.provider_id == active.provider_id

    if is_active:
        base_url = active.base_url
        model = normalize_model_id(provider_id, active.model)
        configured = bool(active.api_key.strip())
        status = evaluate_config_status(active).value if configured else LlmProviderStatus.NOT_CONFIGURED.value
    else:
        base_url = stored.base_url if stored and stored.base_url else provider.default_base_url
        raw_model = stored.model if stored and stored.model else provider.default_model
        model = normalize_model_id(provider_id, raw_model)
        configured = bool(stored and stored.api_key.strip())
        status = (
            LlmProviderStatus.CONFIGURED.value
            if configured
            else (stored.status if stored else LlmProviderStatus.NOT_CONFIGURED.value)
        )

    return {
        "providerId": provider.provider_id,
        "providerName": provider.provider_name,
        "authType": stored.auth_type if stored and stored.auth_type else "api_key",
        "status": status,
        "baseUrl": base_url,
        "model": model,
        "configured": configured,
        "isActive": is_active,
        "message": "",
    }


def _load_stored_config(
    session: Session,
    provider_id: str,
) -> LlmProviderConfigEntity | None:
    return session.exec(
        select(LlmProviderConfigEntity).where(LlmProviderConfigEntity.provider_id == provider_id)
    ).first()
