from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from sqlmodel import Session, select

from app.models.entities import AppSettingEntity
from app.services.llm.auth import resolve_authorization_header
from app.services.llm.model_catalog import MODEL_CATALOG, list_models_for_provider, normalize_model_id
from app.services.llm.registry import get_provider
from app.services.llm.types import LlmErrorCode, ModelOption, ResolvedLlmConfig

MODELS_CACHE_TTL_SEC = 3600

_VISION_POSITIVE_PATTERNS = (
    re.compile(r"gpt-4o", re.I),
    re.compile(r"gpt-4-turbo", re.I),
    re.compile(r"gpt-4-vision", re.I),
    re.compile(r"gemini", re.I),
    re.compile(r"kimi-k2\.5", re.I),
    re.compile(r"kimi-k2\.6", re.I),
    re.compile(r"glm-4v", re.I),
    re.compile(r"vision", re.I),
    re.compile(r"multimodal", re.I),
)

_VISION_NEGATIVE_PATTERNS = (
    re.compile(r"moonshot-v1", re.I),
    re.compile(r"deepseek-chat", re.I),
    re.compile(r"deepseek-reasoner", re.I),
    re.compile(r"kimi-k2\.7-code", re.I),
    re.compile(r"glm-4-flash", re.I),
    re.compile(r"glm-4-air", re.I),
    re.compile(r"glm-4-plus", re.I),
    re.compile(r"gpt-4\.1-mini", re.I),
    re.compile(r"gpt-4\.1$", re.I),
)


@dataclass
class LiveModelCapability:
    model_id: str
    supports_vision: bool
    source: str = "live"


def infer_vision_support(model_id: str) -> bool:
    normalized = model_id.strip().lower()
    if not normalized:
        return False
    for pattern in _VISION_NEGATIVE_PATTERNS:
        if pattern.search(normalized):
            return False
    for pattern in _VISION_POSITIVE_PATTERNS:
        if pattern.search(normalized):
            return True
    return False


def _models_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/models"


def _parse_live_model_payload(item: dict[str, Any]) -> LiveModelCapability | None:
    model_id = str(item.get("id") or item.get("name") or "").strip()
    if not model_id:
        return None

    supports = _extract_vision_flag_from_payload(item)
    if supports is None:
        supports = infer_vision_support(model_id)
    return LiveModelCapability(model_id=model_id, supports_vision=supports, source="live")


def _extract_vision_flag_from_payload(item: dict[str, Any]) -> bool | None:
    for key in ("supports_vision", "supportsVision", "vision"):
        if key in item and isinstance(item[key], bool):
            return item[key]

    capabilities = item.get("capabilities")
    if isinstance(capabilities, dict):
        for key in ("vision", "image", "multimodal"):
            if key in capabilities and isinstance(capabilities[key], bool):
                return capabilities[key]

    modalities = item.get("modalities") or item.get("input_modalities") or item.get("inputModalities")
    if isinstance(modalities, list):
        normalized = {str(value).lower() for value in modalities}
        if normalized & {"image", "vision", "multimodal"}:
            return True
        if normalized and normalized <= {"text"}:
            return False

    return None


def fetch_live_model_capabilities(config: ResolvedLlmConfig) -> tuple[list[LiveModelCapability], str]:
    auth_header, auth_error, auth_message = resolve_authorization_header(config)
    if auth_error:
        return [], auth_message or "LLM 未配置或鉴权无效。"

    http_request = request.Request(
        _models_url(config.base_url),
        headers={"Authorization": auth_header or ""},
        method="GET",
    )
    try:
        with request.urlopen(http_request, timeout=min(config.timeout_sec, 30)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        return [], "获取模型列表超时。"
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:240]
        return [], f"模型列表请求失败（HTTP {exc.code}）：{body}"
    except error.URLError as exc:
        return [], f"无法连接模型列表接口：{exc.reason}"
    except json.JSONDecodeError:
        return [], "模型列表响应不是合法 JSON。"

    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = payload if isinstance(payload, list) else []

    capabilities: list[LiveModelCapability] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        parsed = _parse_live_model_payload(item)
        if parsed:
            capabilities.append(parsed)
    if not capabilities:
        return [], "模型列表为空或格式不受支持。"
    return capabilities, ""


def _cache_key(provider_id: str) -> str:
    return f"llm_models_live_cache:{provider_id}"


def _load_cached_capabilities(session: Session, provider_id: str) -> list[LiveModelCapability] | None:
    row = session.get(AppSettingEntity, _cache_key(provider_id))
    if not row or not row.value.strip():
        return None
    try:
        payload = json.loads(row.value)
    except json.JSONDecodeError:
        return None
    fetched_at = float(payload.get("fetchedAt", 0))
    if time.time() - fetched_at > MODELS_CACHE_TTL_SEC:
        return None
    items = payload.get("models")
    if not isinstance(items, list):
        return None
    return [
        LiveModelCapability(
            model_id=str(item.get("modelId", "")),
            supports_vision=bool(item.get("supportsVision")),
            source="cache",
        )
        for item in items
        if item.get("modelId")
    ]


def _save_cached_capabilities(
    session: Session,
    provider_id: str,
    capabilities: list[LiveModelCapability],
) -> None:
    entity = session.get(AppSettingEntity, _cache_key(provider_id))
    if not entity:
        entity = AppSettingEntity(key=_cache_key(provider_id), value="")
    entity.value = json.dumps(
        {
            "fetchedAt": time.time(),
            "models": [
                {"modelId": item.model_id, "supportsVision": item.supports_vision}
                for item in capabilities
            ],
        },
        ensure_ascii=False,
    )
    session.add(entity)
    session.commit()


def resolve_provider_models_with_capabilities(
    session: Session,
    config: ResolvedLlmConfig,
    *,
    live: bool = False,
) -> tuple[list[dict[str, Any]], str, str]:
    provider = get_provider(config.provider_id)
    if not provider:
        return [], "catalog", "Unknown provider"

    catalog_models = list_models_for_provider(config.provider_id)
    live_map: dict[str, LiveModelCapability] = {}
    message = ""
    source = "catalog"

    if live and config.api_key.strip():
        cached = _load_cached_capabilities(session, config.provider_id)
        if cached:
            live_map = {item.model_id: item for item in cached}
            source = "cache"
        else:
            fetched, fetch_message = fetch_live_model_capabilities(config)
            if fetched:
                live_map = {item.model_id: item for item in fetched}
                _save_cached_capabilities(session, config.provider_id, fetched)
                source = "live"
            else:
                message = fetch_message

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_model(model_id: str, label: str, description: str, recommended: bool) -> None:
        normalized_id = normalize_model_id(config.provider_id, model_id)
        if normalized_id in seen:
            return
        seen.add(normalized_id)
        live_info = live_map.get(normalized_id)
        supports_vision = (
            live_info.supports_vision
            if live_info
            else infer_vision_support(normalized_id)
        )
        vision_source = live_info.source if live_info else "catalog"
        merged.append(
            {
                "modelId": normalized_id,
                "label": label,
                "description": description,
                "recommended": recommended,
                "supportsVision": supports_vision,
                "visionSource": vision_source,
            }
        )

    for item in catalog_models:
        append_model(item.model_id, item.label, item.description, item.recommended)

    for model_id, live_info in live_map.items():
        if model_id in seen:
            continue
        append_model(model_id, model_id, "来自 Provider 实时模型列表", False)

    return merged, source, message


def model_supports_vision(
    session: Session,
    config: ResolvedLlmConfig,
    *,
    model_id: str | None = None,
    prefer_live: bool = True,
) -> tuple[bool, str, str]:
    target_model = normalize_model_id(
        config.provider_id,
        model_id or config.model,
    )
    if not target_model:
        return False, "catalog", "未配置模型。"

    if prefer_live and config.api_key.strip():
        models, source, message = resolve_provider_models_with_capabilities(
            session,
            config,
            live=True,
        )
        matched = next((item for item in models if item["modelId"] == target_model), None)
        if matched is not None:
            return bool(matched["supportsVision"]), str(matched.get("visionSource", source)), message
        if message:
            return infer_vision_support(target_model), "catalog", message

    return infer_vision_support(target_model), "catalog", ""


def enrich_catalog_models(provider_id: str) -> list[ModelOption]:
    return [
        ModelOption(
            model_id=item.model_id,
            label=item.label,
            description=item.description,
            recommended=item.recommended,
            supports_vision=infer_vision_support(item.model_id),
        )
        for item in MODEL_CATALOG.get(provider_id, [])
    ]
