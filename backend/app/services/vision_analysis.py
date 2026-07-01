from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.models.schemas import AssetVisionPrefillRead
from app.services.llm.auth import enrich_config_with_auth, is_provider_configured
from app.services.llm.config_store import resolve_active_config
from app.services.llm.gateway import llm_gateway
from app.services.llm.model_capabilities import model_supports_vision
from app.services.llm.oauth.modes import is_subscription_auth_type
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.llm.types import LlmCallResult, LlmErrorCode
from app.services.repository import repository
from app.services.file_fingerprint import relative_path_fingerprint, source_file_fingerprint
from app.services.video_frames import VideoFrameError, encode_image_base64, extract_video_frames

VISION_SYSTEM_PROMPT = """
你是视频素材分析助手。根据提供的视频关键帧，输出 JSON 对象，字段如下：
- scene: 画面内容描述（中文，20-80字）
- shotType: 镜头类型，只能是 wide / medium / subject_medium / close_up / human / animal / transition 之一
- emotionTags: 情绪标签数组（中文，2-5个）
- visualTags: 视觉标签数组（中文，2-6个）
- informationDensity: 只能是 low / medium / high
- suggestedDurationSec: 建议使用时长（秒，0.5-8.0 的数字）

只返回 JSON，不要 markdown 代码块。
""".strip()

MOCK_VISION_RESULT: dict[str, Any] = {
    "scene": "蓝冰河流特写，前景带雪面纹理与冷色调光影",
    "shotType": "close_up",
    "emotionTags": ["冷", "静", "童话"],
    "visualTags": ["冷蓝", "白雪", "河流"],
    "informationDensity": "medium",
    "suggestedDurationSec": 2.5,
}


def _vision_not_configured_message(config) -> str:
    if is_subscription_auth_type(config.auth_type):
        return "尚未完成订阅登录，请先在 LLM 设置页连接 ChatGPT (Codex) 或 Google 订阅账号。"
    if config.auth_type == "oauth":
        return "尚未完成 OAuth 授权，请先在 LLM 设置页连接账号。"
    return "未配置 LLM API Key，请先在 LLM 设置页保存并设为生效。"


def resolve_asset_video_path(media_root: str, relative_path: str) -> Path | None:
    if not media_root.strip() or not relative_path.strip():
        return None
    candidate = Path(media_root) / relative_path
    if candidate.is_file():
        return candidate
    return None


def _normalize_vision_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """将模型返回的 snake_case / 嵌套结构归一化为素材预填字段。"""
    source = raw
    for nested_key in ("analysis", "result", "data", "output"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            source = nested
            break

    alias_map = {
        "scene": ("scene", "画面内容", "画面描述", "description"),
        "shotType": ("shotType", "shot_type", "镜头类型", "shot"),
        "emotionTags": ("emotionTags", "emotion_tags", "情绪标签", "emotions"),
        "visualTags": ("visualTags", "visual_tags", "视觉标签", "visuals"),
        "informationDensity": (
            "informationDensity",
            "information_density",
            "信息量",
            "density",
        ),
        "suggestedDurationSec": (
            "suggestedDurationSec",
            "suggested_duration_sec",
            "duration_sec",
            "建议时长",
        ),
    }

    normalized: dict[str, Any] = {}
    for target, aliases in alias_map.items():
        for alias in aliases:
            if alias not in source:
                continue
            value = source[alias]
            if target.endswith("Tags") and isinstance(value, str):
                value = [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
            normalized[target] = value
            break

    return normalized


def _collect_prefilled_fields(payload: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    if str(payload.get("scene", "")).strip():
        fields.append("scene")
    if str(payload.get("shotType", "")).strip():
        fields.append("shotType")
    if payload.get("emotionTags"):
        fields.append("emotionTags")
    if payload.get("visualTags"):
        fields.append("visualTags")
    if str(payload.get("informationDensity", "")).strip():
        fields.append("informationDensity")
    duration = payload.get("suggestedDurationSec")
    if isinstance(duration, (int, float)) and float(duration) > 0:
        fields.append("suggestedDurationSec")
    return fields


def _build_prefill(payload: dict[str, Any], *, message: str = "") -> AssetVisionPrefillRead:
    prefilled_fields = _collect_prefilled_fields(payload)
    return AssetVisionPrefillRead(
        scene=str(payload.get("scene", "")).strip(),
        shotType=str(payload.get("shotType", "")).strip(),
        emotionTags=[str(item).strip() for item in payload.get("emotionTags", []) if str(item).strip()],
        visualTags=[str(item).strip() for item in payload.get("visualTags", []) if str(item).strip()],
        informationDensity=str(payload.get("informationDensity", "")).strip(),
        suggestedDurationSec=float(payload.get("suggestedDurationSec") or 0),
        prefilledFields=prefilled_fields,
        visionAnalysisStatus="ready" if prefilled_fields else "failed",
        message=message or f"已预填 {len(prefilled_fields)} 个字段，请确认后保存。",
    )


def _llm_meta_from_result(result: LlmCallResult) -> dict[str, str]:
    status = "success" if result.ok else (result.error_code.value if result.error_code else "error")
    return {
        "llmStatus": status,
        "llmMessage": result.message,
        "llmProviderId": result.provider_id,
        "llmUsedFallback": "false",
    }


def resolve_vision_file_fingerprint(
    project_id: str,
    media_root: str,
    relative_path: str,
) -> str:
    video_path = resolve_asset_video_path(media_root, relative_path)
    if video_path is not None:
        return source_file_fingerprint(video_path)
    return relative_path_fingerprint(project_id, relative_path)


VISION_PAYLOAD_KEYS = (
    "scene",
    "shotType",
    "emotionTags",
    "visualTags",
    "informationDensity",
    "suggestedDurationSec",
)


def _vision_payload_from_cache(cached: dict[str, Any]) -> dict[str, Any]:
    return {key: cached[key] for key in VISION_PAYLOAD_KEYS if key in cached}


class VisionAnalysisService:
    def analyze_asset(
        self,
        session: Session,
        project_id: str,
        asset_id: str,
        *,
        on_progress: ProgressReporter | None = None,
    ) -> tuple[AssetVisionPrefillRead | None, dict[str, str]]:
        project = repository.get_project(session, project_id)
        if not project:
            return None, {}

        asset_entity = repository.get_asset_entity(session, asset_id)
        if not asset_entity or asset_entity.project_id != project_id:
            return None, {}

        asset_entity.vision_analysis_status = "pending"
        session.add(asset_entity)
        session.commit()

        file_fingerprint = resolve_vision_file_fingerprint(
            project_id,
            project.mediaRoot,
            asset_entity.relative_path,
        )
        cached_hit = repository.find_cached_vision_analysis(
            session,
            project_id,
            file_fingerprint=file_fingerprint,
            exclude_asset_id=asset_id,
        )
        if cached_hit is not None:
            cached_asset_id, cached_payload = cached_hit
            payload = _vision_payload_from_cache(cached_payload)
            prefill = _build_prefill(
                payload,
                message=(
                    f"命中同文件 Vision 缓存（来源素材 {cached_asset_id[:8]}…），"
                    f"已预填 {len(_collect_prefilled_fields(payload))} 个字段。"
                ),
            )
            config = resolve_active_config(session)
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status=prefill.visionAnalysisStatus,
                analysis_json={
                    **payload,
                    "fileFingerprint": file_fingerprint,
                    "cachedFromAssetId": cached_asset_id,
                    "providerId": cached_payload.get("providerId") or config.provider_id,
                    "model": cached_payload.get("model") or config.model,
                    "analyzedAt": datetime.now(UTC).isoformat(),
                    "cacheHit": True,
                },
                prefilled_fields=prefill.prefilledFields,
            )
            emit_progress(
                on_progress,
                "cache_hit",
                prefill.message,
                progress=92,
            )
            result = LlmCallResult.success(
                payload,
                provider_id=config.provider_id,
                model=config.model,
            )
            emit_progress(on_progress, "complete", prefill.message, progress=95)
            return prefill, _llm_meta_from_result(result)

        if settings.vision_use_mock:
            emit_progress(on_progress, "mock", "使用 Mock Vision 响应（测试模式）", progress=40)
            config = resolve_active_config(session)
            payload = dict(MOCK_VISION_RESULT)
            prefill = _build_prefill(payload)
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status=prefill.visionAnalysisStatus,
                analysis_json={
                    **payload,
                    "fileFingerprint": file_fingerprint,
                    "providerId": config.provider_id,
                    "model": config.model,
                    "analyzedAt": datetime.now(UTC).isoformat(),
                    "mock": True,
                },
                prefilled_fields=prefill.prefilledFields,
            )
            result = LlmCallResult.success(
                payload,
                provider_id=config.provider_id,
                model=config.model,
            )
            emit_progress(on_progress, "complete", prefill.message, progress=95)
            return prefill, _llm_meta_from_result(result)

        config = enrich_config_with_auth(session, resolve_active_config(session))
        if not is_provider_configured(config):
            result = LlmCallResult.failure(
                LlmErrorCode.NOT_CONFIGURED,
                _vision_not_configured_message(config),
                provider_id=config.provider_id,
                model=config.model,
            )
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": result.message},
                prefilled_fields=[],
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=result.message,
            ), _llm_meta_from_result(result)

        supports_vision, vision_source, capability_message = model_supports_vision(
            session,
            config,
            prefer_live=True,
        )
        emit_progress(
            on_progress,
            "checking_model",
            f"检查 {config.model} 是否支持图像输入…",
            progress=8,
            detail=f"能力来源：{vision_source}",
        )
        if not supports_vision:
            hint = (
                f"当前模型 {config.model} 不支持图像分析。"
                "请切换到支持 Vision 的模型（如 gpt-4o、gemini-2.0-flash、kimi-k2.5/k2.6）。"
            )
            if capability_message:
                hint = f"{hint} {capability_message}"
            result = LlmCallResult.failure(
                LlmErrorCode.VISION_UNSUPPORTED,
                hint,
                provider_id=config.provider_id,
                model=config.model,
            )
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": hint},
                prefilled_fields=[],
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=hint,
            ), _llm_meta_from_result(result)

        video_path = resolve_asset_video_path(project.mediaRoot, asset_entity.relative_path)
        if video_path is None:
            message = (
                "找不到视频文件。请确认项目 mediaRoot 与素材相对路径正确，且文件可在服务端访问。"
            )
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": message},
                prefilled_fields=[],
            )
            result = LlmCallResult.failure(
                LlmErrorCode.NOT_CONFIGURED,
                message,
                provider_id=config.provider_id,
                model=config.model,
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=message,
            ), _llm_meta_from_result(result)

        emit_progress(
            on_progress,
            "extracting_frames",
            "正在使用 ffmpeg 抽取关键帧…",
            progress=18,
            detail=str(video_path.name),
        )
        try:
            frame_paths = extract_video_frames(
                video_path,
                interval_sec=settings.vision_frame_interval_sec,
                max_frames=settings.vision_max_frames,
            )
        except VideoFrameError as exc:
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": str(exc)},
                prefilled_fields=[],
            )
            result = LlmCallResult.failure(
                LlmErrorCode.NOT_IMPLEMENTED,
                str(exc),
                provider_id=config.provider_id,
                model=config.model,
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=str(exc),
            ), _llm_meta_from_result(result)

        image_urls = [encode_image_base64(path) for path in frame_paths]
        emit_progress(
            on_progress,
            "calling_vision",
            f"正在调用 {config.provider_name} 分析 {len(image_urls)} 帧…",
            progress=35,
        )
        llm_result = llm_gateway.generate_vision_json_with_config(
            config=config,
            system_prompt=VISION_SYSTEM_PROMPT,
            user_prompt="请分析这些视频关键帧并返回 JSON。",
            image_urls=image_urls,
            on_progress=on_progress,
        )
        if not llm_result.ok or not llm_result.data:
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": llm_result.message},
                prefilled_fields=[],
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=llm_result.message or "Vision 分析失败。",
            ), _llm_meta_from_result(llm_result)

        payload = _normalize_vision_payload(llm_result.data)
        if str(payload.get("message", "")).strip() and not _collect_prefilled_fields(payload):
            error_message = str(payload.get("message", "")).strip()
            repository.update_asset_vision_status(
                session,
                project_id,
                asset_id,
                status="failed",
                analysis_json={"message": error_message, "raw": llm_result.data},
                prefilled_fields=[],
            )
            return AssetVisionPrefillRead(
                visionAnalysisStatus="failed",
                message=error_message,
            ), _llm_meta_from_result(llm_result)

        prefill = _build_prefill(payload)
        if prefill.prefilledFields:
            completion_message = (
                f"Vision 分析完成，已预填 {len(prefill.prefilledFields)} 个字段。"
            )
        else:
            completion_message = (
                "模型已返回结果，但无法映射到素材字段。"
                "请确认使用的是 Vision 模型，或稍后重试。"
            )
        prefill = prefill.model_copy(update={"message": completion_message})
        repository.update_asset_vision_status(
            session,
            project_id,
            asset_id,
            status=prefill.visionAnalysisStatus,
            analysis_json={
                **payload,
                "fileFingerprint": file_fingerprint,
                "providerId": config.provider_id,
                "model": config.model,
                "analyzedAt": datetime.now(UTC).isoformat(),
                "frameCount": len(image_urls),
            },
            prefilled_fields=prefill.prefilledFields,
        )
        emit_progress(on_progress, "complete", prefill.message, progress=95)
        return prefill, _llm_meta_from_result(llm_result)


vision_analysis_service = VisionAnalysisService()
