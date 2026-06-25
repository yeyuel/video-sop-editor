from __future__ import annotations

import json
from typing import Any

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead
from app.services.llm import LlmCallResult, build_llm_meta, llm_suggestion_service
from app.services.llm.progress import ProgressReporter, emit_progress


def _all_asset_ids(assets: list[AssetRead]) -> list[str]:
    return [asset.assetId for asset in assets]


def _all_locations(assets: list[AssetRead]) -> list[str]:
    return sorted({asset.location for asset in assets if asset.location.strip()})


def _locations_for_asset_ids(assets: list[AssetRead], asset_ids: list[str]) -> list[str]:
    asset_map = {asset.assetId: asset for asset in assets}
    locations: list[str] = []
    seen: set[str] = set()
    for asset_id in asset_ids:
        location = asset_map.get(asset_id, None)
        if not location or not location.location.strip():
            continue
        if location.location in seen:
            continue
        seen.add(location.location)
        locations.append(location.location)
    return locations


def _sanitize_asset_ids(raw_ids: object, assets: list[AssetRead]) -> list[str]:
    if not isinstance(raw_ids, list):
        return []
    allowed = {asset.assetId for asset in assets}
    sanitized: list[str] = []
    for item in raw_ids:
        asset_id = str(item).strip()
        if asset_id and asset_id in allowed and asset_id not in sanitized:
            sanitized.append(asset_id)
    return sanitized


def _theme_evidence(
    assets: list[AssetRead],
    *,
    asset_ids: list[str] | None = None,
    locations: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    used_asset_ids = asset_ids or _all_asset_ids(assets)
    used_locations = locations or _locations_for_asset_ids(assets, used_asset_ids)
    if not used_locations:
        used_locations = _all_locations(assets)
    return used_asset_ids, used_locations


def _enforce_theme_diversity(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_emotions: set[str] = set()
    diversified: list[dict[str, Any]] = []
    for theme in themes:
        emotion = str(theme.get("coreEmotion", "")).strip().lower()
        if emotion and emotion in seen_emotions:
            continue
        if emotion:
            seen_emotions.add(emotion)
        diversified.append(theme)
    return diversified


def build_rule_theme_candidates(
    project: ProjectEntity,
    assets: list[AssetRead],
) -> list[dict[str, Any]]:
    locations = _all_locations(assets)
    location_text = " / ".join(locations) or project.destination
    dominant_emotion = assets[0].emotionTags[0] if assets and assets[0].emotionTags else "沉浸"
    route_locations = (
        [
            item.strip()
            for item in project.route_text.replace("->", "-").replace("—", "-").split("-")
            if item.strip()
        ]
        if project.route_text.strip()
        else []
    )
    route_asset_ids = [
        asset.assetId
        for asset in assets
        if asset.location in route_locations
    ] or _all_asset_ids(assets)
    people_asset_ids = [
        asset.assetId
        for asset in assets
        if any(tag in asset.functionTags for tag in ("opening_hook", "transition_buffer", "supporting"))
    ] or _all_asset_ids(assets)

    candidates: list[dict[str, Any]] = [
        {
            "title": f"{project.destination} 情绪氛围片",
            "summary": (
                f"围绕 {location_text} 的雪景、空镜和人物经过瞬间，组织一支突出"
                f"{dominant_emotion} 气质的旅行情绪短片。"
            ),
            "coreEmotion": dominant_emotion,
            "rhythmProfile": "前段抓人，中段舒展，结尾留白回味。",
            "platformReason": "适合小红书和抖音的氛围型短视频表达，便于后续扩展字幕与口播版本。",
        },
        {
            "title": f"{project.destination} 路线纪实片",
            "summary": (
                (
                    f"按照 {project.route_text} 的路线推进，让地点变化带出行程推进感，"
                    if project.route_text.strip()
                    else f"围绕 {location_text} 的不同区域推进，让地点变化带出行程推进感，"
                )
                + "强调观众跟着镜头一路走完旅程。"
            ),
            "coreEmotion": "纪实",
            "rhythmProfile": "按路线推进，节点提速，地点切换清晰。",
            "platformReason": "适合保留地点层次和游览顺序，后续也容易扩展为轻攻略表达。",
        },
        {
            "title": f"{project.destination} 城市与人物陪伴感",
            "summary": "用人物经过、环境空镜和地点细节，强化旅程里的陪伴感与在场感。",
            "coreEmotion": "陪伴",
            "rhythmProfile": "人物带动节奏，环境镜头负责缓冲和呼吸。",
            "platformReason": "适合做更有代入感的短视频叙事，也方便后续加入第一人称文案。",
        },
    ]

    evidence_specs = [
        (_all_asset_ids(assets), locations),
        (route_asset_ids, route_locations or locations),
        (people_asset_ids, _locations_for_asset_ids(assets, people_asset_ids) or locations),
    ]
    for candidate, (asset_ids, locs) in zip(candidates, evidence_specs, strict=False):
        used_asset_ids, used_locations = _theme_evidence(
            assets,
            asset_ids=asset_ids,
            locations=locs,
        )
        candidate["usedAssetIds"] = used_asset_ids
        candidate["usedLocations"] = used_locations
    return candidates


def build_llm_theme_candidates(
    project: ProjectEntity,
    assets: list[AssetRead],
    count: int,
    on_progress: ProgressReporter | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理「{project.destination}」项目与 {len(assets)} 条素材…",
        progress=10,
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a short-form travel video narrative director. "
            "Return JSON only with a themes array. Each theme must include "
            "title, summary, coreEmotion, rhythmProfile, platformReason, "
            "usedAssetIds, usedLocations. "
            "usedAssetIds must only contain assetId values from the provided assets. "
            "usedLocations must only contain locations present in those assets. "
            "Each theme must use a distinct coreEmotion and a distinct narrative angle. "
            "Do not invent locations outside the provided assets."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "videoType": project.video_type,
                    "routeText": project.route_text,
                    "stylePreference": project.style_preference,
                    "styleNotes": project.style_notes,
                },
                "assets": [
                    {
                        "assetId": asset.assetId,
                        "location": asset.location,
                        "scene": asset.scene,
                        "emotionTags": asset.emotionTags,
                        "functionTags": asset.functionTags,
                    }
                    for asset in assets
                ],
                "count": max(1, min(count, 5)),
            },
            ensure_ascii=False,
        ),
        temperature=0.7,
        max_tokens=1200,
        on_progress=on_progress,
    )
    emit_progress(on_progress, "building", "正在整理候选主题结构…", progress=86)
    normalized = _normalize_theme_payload(result, assets, count)
    if not normalized:
        emit_progress(on_progress, "fallback", "LLM 结果无效，准备回退到规则生成…", progress=88)
    meta = build_llm_meta(result, used_fallback=not normalized).as_dict()
    return normalized, meta


def _normalize_theme_payload(
    result: LlmCallResult,
    assets: list[AssetRead],
    count: int,
) -> list[dict[str, Any]]:
    payload = result.data if result.ok else None
    themes = payload.get("themes") if payload else None
    if not isinstance(themes, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in themes[: max(1, min(count, 5))]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title or not summary:
            continue

        used_asset_ids = _sanitize_asset_ids(item.get("usedAssetIds"), assets)
        raw_locations = item.get("usedLocations")
        used_locations = (
            [str(value).strip() for value in raw_locations if str(value).strip()]
            if isinstance(raw_locations, list)
            else []
        )
        allowed_locations = set(_all_locations(assets))
        used_locations = [loc for loc in used_locations if loc in allowed_locations]
        used_asset_ids, used_locations = _theme_evidence(
            assets,
            asset_ids=used_asset_ids or None,
            locations=used_locations or None,
        )

        normalized.append(
            {
                "title": title,
                "summary": summary,
                "coreEmotion": str(item.get("coreEmotion", "沉浸")).strip() or "沉浸",
                "rhythmProfile": (
                    str(item.get("rhythmProfile", "前段抓人，中段舒展，结尾留白回味。")).strip()
                    or "前段抓人，中段舒展，结尾留白回味。"
                ),
                "platformReason": (
                    str(item.get("platformReason", "")).strip()
                    or "适合当前平台的旅行短视频表达方式。"
                ),
                "usedAssetIds": used_asset_ids,
                "usedLocations": used_locations,
            }
        )
    return _enforce_theme_diversity(normalized)
