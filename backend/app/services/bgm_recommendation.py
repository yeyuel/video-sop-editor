from __future__ import annotations

import json
from uuid import uuid4

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, BgmRecommendationRead, NarrativeThemeRead
from app.services.llm import LlmCallResult, build_llm_meta, llm_suggestion_service
from app.services.llm.progress import ProgressReporter, emit_progress


def build_llm_bgm_recommendations(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    *,
    on_progress: ProgressReporter | None = None,
) -> tuple[list[BgmRecommendationRead], str, list[str], dict[str, str]]:
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理「{project.destination}」的 BGM 推荐上下文…",
        progress=10,
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a travel short-video music supervisor. "
            "Return JSON only with keys bgmStyle (string), rhythmNotes (array of 2-4 short Chinese strings), "
            "and recommendations (array of 2-3 objects). "
            "Each recommendation object must include: title (real song name in Chinese or English), "
            "artist (string), styleTags (array), mood (string), bpmRange (string like '90-110'), "
            "fitReason (why it fits this project), searchHint (keywords for NetEase/QQ Music search), "
            "platformTips (how to find it on mainstream music apps). "
            "Do not provide download URLs or piracy instructions. Real song names are allowed."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "videoType": project.video_type,
                    "targetDurationSec": project.target_duration_sec,
                    "stylePreference": project.style_preference,
                    "styleNotes": project.style_notes,
                    "routeText": project.route_text,
                },
                "theme": theme.model_dump() if theme else None,
                "assetsSummary": [
                    {
                        "location": asset.location,
                        "scene": asset.scene,
                        "emotionTags": asset.emotionTags,
                        "mediaType": asset.mediaType,
                    }
                    for asset in assets[:10]
                ],
            },
            ensure_ascii=False,
        ),
        temperature=0.65,
        on_progress=on_progress,
    )
    emit_progress(on_progress, "building", "正在整理 BGM 推荐列表…", progress=86)
    parsed = _normalize_bgm_recommendations(result, project, theme)
    if parsed is None:
        emit_progress(on_progress, "fallback", "LLM BGM 推荐无效，准备回退到规则推荐…", progress=88)
        recommendations, bgm_style, rhythm_notes = build_rule_bgm_recommendations(project, theme)
        meta = build_llm_meta(result, used_fallback=True).as_dict()
        return recommendations, bgm_style, rhythm_notes, meta

    recommendations, bgm_style, rhythm_notes = parsed
    meta = build_llm_meta(result, used_fallback=False).as_dict()
    return recommendations, bgm_style, rhythm_notes, meta


def build_rule_bgm_recommendations(
    project: ProjectEntity,
    theme: NarrativeThemeRead | None,
) -> tuple[list[BgmRecommendationRead], str, list[str]]:
    emotion = theme.coreEmotion if theme else "沉浸"
    destination = project.destination
    bgm_style = theme.rhythmProfile if theme else "快起快收，中段稳节奏"
    rhythm_notes = [
        f"先选定 BGM 并上传音频，平台会基于真实 BPM 生成节拍点。",
        f"前 3 秒建议卡强拍，配合 {destination} 的高识别度镜头。",
        f"整体保持 {emotion} 气质，避免平均切镜。",
    ]
    recommendations = [
        BgmRecommendationRead(
            id=_new_bgm_id(),
            title=f"{destination} 氛围纯音乐",
            artist="可搜索同类版权音乐",
            styleTags=["氛围", "旅行", emotion],
            mood=emotion,
            bpmRange="85-100",
            fitReason=f"适合 {destination} 旅行短片的情绪铺陈与空镜节奏。",
            searchHint=f"{destination} 旅行 纯音乐 氛围",
            platformTips="在网易云音乐或 QQ 音乐搜索关键词，选择可商用的版本。",
            isSelected=False,
        ),
        BgmRecommendationRead(
            id=_new_bgm_id(),
            title=f"{destination} 轻电子旅行曲",
            artist="可搜索同类版权音乐",
            styleTags=["电子", "轻鼓点", "Vlog"],
            mood="轻快",
            bpmRange="100-120",
            fitReason=f"适合 {project.platform} 平台偏快切、信息密度更高的路线片。",
            searchHint=f"{destination} vlog 背景音乐 电子",
            platformTips="优先选择无强烈人声、鼓点清晰的版本，便于剪映踩点。",
            isSelected=False,
        ),
    ]
    return recommendations, bgm_style, rhythm_notes


def format_bgm_track_name(recommendation: BgmRecommendationRead) -> str:
    title = recommendation.title.strip()
    artist = recommendation.artist.strip()
    if artist and artist not in title:
        return f"{artist} - {title}"
    return title


def _normalize_bgm_recommendations(
    result: LlmCallResult,
    project: ProjectEntity,
    theme: NarrativeThemeRead | None,
) -> tuple[list[BgmRecommendationRead], str, list[str]] | None:
    payload = result.data if result.ok else None
    if not payload:
        return None

    bgm_style = str(payload.get("bgmStyle", "")).strip()
    rhythm_notes_raw = payload.get("rhythmNotes")
    recommendations_raw = payload.get("recommendations")
    if not bgm_style or not isinstance(recommendations_raw, list):
        return None

    rhythm_notes = [
        str(item).strip() for item in (rhythm_notes_raw or []) if str(item).strip()
    ]
    if len(rhythm_notes) < 2:
        rhythm_notes = build_rule_bgm_recommendations(project, theme)[2]

    recommendations: list[BgmRecommendationRead] = []
    for item in recommendations_raw[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        style_tags_raw = item.get("styleTags")
        style_tags = (
            [str(tag).strip() for tag in style_tags_raw if str(tag).strip()]
            if isinstance(style_tags_raw, list)
            else []
        )
        recommendations.append(
            BgmRecommendationRead(
                id=_new_bgm_id(),
                title=title,
                artist=str(item.get("artist", "")).strip(),
                styleTags=style_tags,
                mood=str(item.get("mood", "")).strip(),
                bpmRange=str(item.get("bpmRange", "")).strip(),
                fitReason=str(item.get("fitReason", "")).strip(),
                searchHint=str(item.get("searchHint", "")).strip(),
                platformTips=str(item.get("platformTips", "")).strip(),
                isSelected=False,
            )
        )

    if len(recommendations) < 2:
        return None

    return recommendations, bgm_style, rhythm_notes


def _new_bgm_id() -> str:
    return f"bgm_{uuid4().hex[:8]}"
