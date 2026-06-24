from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
import json

from app.api.meta import merge_response_meta
from app.db import get_session
from app.models.schemas import (
    ApiResponse,
    LlmDeviceCodeStartRead,
    LlmModelOptionRead,
    LlmOAuthStartRead,
    LlmProviderConfigWriteRequest,
    LlmProviderRead,
    LlmProviderTestRead,
    LlmStatusRead,
)
from app.services.llm.auth import evaluate_config_status
from app.services.llm.config_store import (
    get_provider_status,
    list_provider_statuses,
    resolve_active_config,
    resolve_provider_config,
    save_provider_config,
    set_active_provider_id,
)
from app.services.llm.gateway import llm_gateway
from app.services.llm.registry import get_provider, list_models
from app.services.llm.types import LlmProviderStatus

router = APIRouter(prefix="/llm", tags=["llm"])


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def _build_test_response(
    *,
    provider_id: str,
    provider_name: str,
    config_base_url: str,
    config_model: str,
    result,
    latency_ms: int,
    endpoint_url: str,
) -> LlmProviderTestRead:
    if result.ok:
        reply_preview = ""
        if isinstance(result.data, dict):
            reply_preview = str(result.data.get("message", "")).strip() or json.dumps(
                result.data,
                ensure_ascii=False,
            )[:120]
        return LlmProviderTestRead(
            ok=True,
            providerId=provider_id,
            providerName=provider_name,
            model=config_model,
            baseUrl=config_base_url,
            endpointUrl=endpoint_url,
            latencyMs=latency_ms,
            llmStatus="success",
            message=f"LLM 链路连通成功（{latency_ms}ms）。",
            replyPreview=reply_preview,
        )

    status = result.error_code.value if result.error_code else "unknown"
    return LlmProviderTestRead(
        ok=False,
        providerId=provider_id,
        providerName=provider_name,
        model=config_model,
        baseUrl=config_base_url,
        endpointUrl=endpoint_url,
        latencyMs=latency_ms,
        llmStatus=status,
        message=result.message or "LLM 链路测试失败。",
        replyPreview="",
    )


@router.get("/providers", response_model=ApiResponse)
def list_llm_providers(session: Session = Depends(get_session)) -> ApiResponse:
    items = list_provider_statuses(session)
    providers = [
        LlmProviderRead(
            providerId=str(item["providerId"]),
            providerName=str(item["providerName"]),
            authTypes=list(item["authTypes"]),
            defaultBaseUrl=str(item["defaultBaseUrl"]),
            defaultModel=str(item["defaultModel"]),
            openaiCompatible=_parse_bool(str(item.get("openaiCompatible", "true"))),
            status=str(item["status"]),
            isActive=_parse_bool(str(item.get("isActive", "false"))),
            models=[
                LlmModelOptionRead(
                    modelId=str(model["modelId"]),
                    label=str(model["label"]),
                    description=str(model.get("description", "")),
                    recommended=_parse_bool(str(model.get("recommended", "false"))),
                )
                for model in item.get("models", [])
            ],
        )
        for item in items
    ]
    return ApiResponse(data=providers)


@router.get("/providers/{provider_id}/models", response_model=ApiResponse)
def list_llm_provider_models(provider_id: str) -> ApiResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    return ApiResponse(
        data=[
            LlmModelOptionRead(
                modelId=item.model_id,
                label=item.label,
                description=item.description,
                recommended=item.recommended,
            )
            for item in list_models(provider_id)
        ]
    )


@router.get("/providers/{provider_id}/status", response_model=ApiResponse)
def get_llm_provider_status(
    provider_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        status_payload = get_provider_status(session, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ApiResponse(
        data=LlmStatusRead(
            providerId=str(status_payload["providerId"]),
            providerName=str(status_payload["providerName"]),
            authType=str(status_payload["authType"]),
            status=str(status_payload["status"]),
            baseUrl=str(status_payload["baseUrl"]),
            model=str(status_payload["model"]),
            configured=bool(status_payload["configured"]),
            message=str(status_payload["message"]),
        )
    )


@router.get("/status", response_model=ApiResponse)
def get_active_llm_status(session: Session = Depends(get_session)) -> ApiResponse:
    config = resolve_active_config(session)
    status_value = evaluate_config_status(config).value
    message = ""
    if status_value == LlmProviderStatus.NOT_CONFIGURED.value:
        message = "未配置 LLM API Key，请在 LLM 配置页保存并设为生效。"
    return ApiResponse(
        data=LlmStatusRead(
            providerId=config.provider_id,
            providerName=config.provider_name,
            authType=config.auth_type,
            status=status_value,
            baseUrl=config.base_url,
            model=config.model,
            configured=bool(config.api_key.strip()),
            message=message,
        )
    )


@router.post("/providers/{provider_id}/config", response_model=ApiResponse)
def save_llm_provider_config(
    provider_id: str,
    payload: LlmProviderConfigWriteRequest,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        save_provider_config(
            session,
            provider_id,
            auth_type=payload.authType,
            base_url=payload.baseUrl,
            model=payload.model,
            api_key=payload.apiKey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_payload = get_provider_status(session, provider_id)
    return ApiResponse(
        data=LlmStatusRead(
            providerId=str(status_payload["providerId"]),
            providerName=str(status_payload["providerName"]),
            authType=str(status_payload["authType"]),
            status=str(status_payload["status"]),
            baseUrl=str(status_payload["baseUrl"]),
            model=str(status_payload["model"]),
            configured=bool(status_payload["configured"]),
            message="Provider 配置已保存。",
        )
    )


@router.post("/providers/{provider_id}/activate", response_model=ApiResponse)
def activate_llm_provider(
    provider_id: str,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        set_active_provider_id(session, provider_id)
        status_payload = get_provider_status(session, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ApiResponse(
        data=LlmStatusRead(
            providerId=str(status_payload["providerId"]),
            providerName=str(status_payload["providerName"]),
            authType=str(status_payload["authType"]),
            status=str(status_payload["status"]),
            baseUrl=str(status_payload["baseUrl"]),
            model=str(status_payload["model"]),
            configured=bool(status_payload["configured"]),
            message=f"已将 {status_payload['providerName']} 设为当前生效 Provider。",
        )
    )


@router.post("/test", response_model=ApiResponse)
def test_active_llm_provider(session: Session = Depends(get_session)) -> ApiResponse:
    config = resolve_active_config(session)
    provider = get_provider(config.provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")

    result, latency_ms, endpoint_url = llm_gateway.test_connection(config)
    payload = _build_test_response(
        provider_id=config.provider_id,
        provider_name=config.provider_name,
        config_base_url=config.base_url,
        config_model=config.model,
        result=result,
        latency_ms=latency_ms,
        endpoint_url=endpoint_url,
    )
    meta = merge_response_meta(
        {
            "llmStatus": payload.llmStatus,
            "llmMessage": payload.message,
            "llmProviderId": payload.providerId,
            "llmUsedFallback": "false",
        }
    )
    return ApiResponse(data=payload, meta=meta)


@router.post("/providers/{provider_id}/test", response_model=ApiResponse)
def test_llm_provider(
    provider_id: str,
    payload: LlmProviderConfigWriteRequest | None = None,
    session: Session = Depends(get_session),
) -> ApiResponse:
    try:
        overrides = payload or LlmProviderConfigWriteRequest()
        config = resolve_provider_config(
            session,
            provider_id,
            base_url=overrides.baseUrl,
            model=overrides.model,
            api_key=overrides.apiKey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not config.api_key.strip():
        return ApiResponse(
            data=LlmProviderTestRead(
                ok=False,
                providerId=config.provider_id,
                providerName=config.provider_name,
                model=config.model,
                baseUrl=config.base_url,
                endpointUrl=f"{config.base_url.rstrip('/')}/chat/completions",
                latencyMs=0,
                llmStatus="not_configured",
                message="请先填写或保存 API Key 后再测试。",
            ),
            meta=merge_response_meta(
                {
                    "llmStatus": "not_configured",
                    "llmMessage": "请先填写或保存 API Key 后再测试。",
                    "llmProviderId": config.provider_id,
                    "llmUsedFallback": "false",
                }
            ),
        )

    result, latency_ms, endpoint_url = llm_gateway.test_connection(config)
    response_payload = _build_test_response(
        provider_id=config.provider_id,
        provider_name=config.provider_name,
        config_base_url=config.base_url,
        config_model=config.model,
        result=result,
        latency_ms=latency_ms,
        endpoint_url=endpoint_url,
    )
    return ApiResponse(
        data=response_payload,
        meta=merge_response_meta(
            {
                "llmStatus": response_payload.llmStatus,
                "llmMessage": response_payload.message,
                "llmProviderId": response_payload.providerId,
                "llmUsedFallback": "false",
            }
        ),
    )


@router.post("/providers/{provider_id}/oauth/start", response_model=ApiResponse)
def start_oauth(provider_id: str) -> ApiResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    if "oauth" not in provider.auth_types:
        raise HTTPException(status_code=400, detail="该 Provider 不支持 OAuth 授权")

    return ApiResponse(
        data=LlmOAuthStartRead(
            message="OAuth 授权流程尚未接入，当前请使用 API Key 模式。",
        ),
        meta={"llmStatus": "not_implemented", "llmMessage": "OAuth 授权流程尚未接入。"},
    )


@router.get("/providers/{provider_id}/oauth/callback", response_model=ApiResponse)
def oauth_callback(provider_id: str) -> ApiResponse:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth callback 尚未接入。",
    )


@router.post("/providers/{provider_id}/device-code/start", response_model=ApiResponse)
def start_device_code(provider_id: str) -> ApiResponse:
    provider = get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    if "device_code" not in provider.auth_types:
        raise HTTPException(status_code=400, detail="该 Provider 不支持 Device Code 授权")

    return ApiResponse(
        data=LlmDeviceCodeStartRead(
            message="Device Code 授权流程尚未接入，当前请使用 API Key 模式。",
        ),
        meta={"llmStatus": "not_implemented", "llmMessage": "Device Code 授权流程尚未接入。"},
    )
