from __future__ import annotations

import json

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead
from app.services.llm import llm_suggestion_service


def build_rule_theme_candidates(
    project: ProjectEntity,
    assets: list[AssetRead],
) -> list[dict[str, str]]:
    location_text = " / ".join(sorted({asset.location for asset in assets})) or project.destination
    dominant_emotion = assets[0].emotionTags[0] if assets and assets[0].emotionTags else "沉浸"

    return [
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
                f"按照 {project.route_text} 的路线推进，让地点变化带出行程推进感，"
                "强调观众跟着镜头一路走完旅程。"
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


def build_llm_theme_candidates(
    project: ProjectEntity,
    assets: list[AssetRead],
    count: int,
) -> list[dict[str, str]]:
    payload = llm_suggestion_service.generate_json(
        system_prompt=(
            "You are a short-form travel video narrative director. "
            "Return JSON only with a themes array. Each theme must include "
            "title, summary, coreEmotion, rhythmProfile, platformReason. "
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
    )
    themes = payload.get("themes") if payload else None
    if not isinstance(themes, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in themes[: max(1, min(count, 5))]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title or not summary:
            continue

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
            }
        )
    return normalized
