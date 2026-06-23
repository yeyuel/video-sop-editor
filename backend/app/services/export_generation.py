from __future__ import annotations

import json

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, ExportPlanRead, NarrativeThemeRead, StoryboardSegmentRead
from app.services.llm import llm_suggestion_service


def build_llm_export_plan(
    *,
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    storyboard: list[StoryboardSegmentRead],
    current_plan: ExportPlanRead | None,
) -> dict[str, object] | None:
    return llm_suggestion_service.generate_json(
        system_prompt=(
            "You are a release-copy assistant for travel short videos. "
            "Return JSON only with title, shortTitle, description, tags, coverSuggestion. "
            "Tags must be an array of short strings."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "routeText": project.route_text,
                    "stylePreference": project.style_preference,
                    "styleNotes": project.style_notes,
                },
                "theme": theme.model_dump() if theme else None,
                "storyboard": [segment.model_dump() for segment in storyboard],
                "assets": [
                    {
                        "assetId": asset.assetId,
                        "location": asset.location,
                        "scene": asset.scene,
                    }
                    for asset in assets
                ],
                "currentPlan": current_plan.model_dump() if current_plan else None,
            },
            ensure_ascii=False,
        ),
        temperature=0.7,
    )


def build_rule_export_fallback(
    *,
    project: ProjectEntity,
    theme: NarrativeThemeRead | None,
) -> dict[str, object]:
    fallback_title = (
        f"{project.destination} {theme.title}"
        if theme
        else f"{project.destination} 旅行短视频导出方案"
    )
    return {
        "title": fallback_title,
        "shortTitle": project.destination,
        "description": "围绕当前项目地点、节奏和分镜结构整理导出文案，便于后续直接发布或继续微调。",
        "tags": [project.destination, project.platform, "旅行短视频"],
        "coverSuggestion": "优先选择识别度最高的地点镜头做封面，标题尽量避开主体区域，保留画面留白。",
    }
