from __future__ import annotations

import json

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, ExportPlanRead, NarrativeThemeRead, StoryboardSegmentRead, StoryboardSegmentWrite, WorkspaceDataRead
from app.services.llm import LlmCallResult, build_llm_meta, llm_suggestion_service
from app.services.llm.progress import ProgressReporter, emit_progress
from app.services.storyboard_generation import segment_read_to_write

PLATFORM_EXPORT_GUIDES: dict[str, dict[str, str]] = {
    "xiaohongshu": {
        "label": "小红书",
        "titleStyle": "情绪种草 + 轻攻略，标题 18 字内，可带 1 个情绪词",
        "tagStyle": "3-5 个话题标签，偏目的地、季节、氛围、旅行体验",
        "descriptionStyle": "第一人称或陪伴感叙述，强调画面感与可收藏价值",
        "coverStyle": "封面留标题安全区，优先高识别度空镜或人物情绪瞬间",
    },
    "douyin": {
        "label": "抖音",
        "titleStyle": "强钩子开头，标题 15 字内，突出反差、速度感或第一秒信息",
        "tagStyle": "2-4 个短标签，偏热点场景、目的地、旅行 vlog",
        "descriptionStyle": "短句口播感，前两句给出观看理由，结尾可留互动提问",
        "coverStyle": "封面主体居中，标题短且对比强，避免遮挡人物面部",
    },
    "default": {
        "label": "通用短视频",
        "titleStyle": "简洁明确，突出目的地与核心情绪",
        "tagStyle": "3-5 个短标签",
        "descriptionStyle": "说明视频看点与适合平台",
        "coverStyle": "优先使用识别度最高的镜头，标题避开主体",
    },
}


def resolve_platform_export_guide(platform: str) -> dict[str, str]:
    normalized = platform.strip().lower()
    if "douyin" in normalized or "抖音" in normalized:
        return PLATFORM_EXPORT_GUIDES["douyin"]
    if "xiaohongshu" in normalized or "小红书" in normalized:
        return PLATFORM_EXPORT_GUIDES["xiaohongshu"]
    return PLATFORM_EXPORT_GUIDES["default"]


def build_llm_export_plan(
    *,
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    storyboard: list[StoryboardSegmentRead],
    current_plan: ExportPlanRead | None,
    on_progress: ProgressReporter | None = None,
) -> tuple[dict[str, object] | None, dict[str, str]]:
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理「{project.destination}」导出上下文（{len(storyboard)} 个镜头）…",
        progress=10,
    )
    platform_guide = resolve_platform_export_guide(project.platform)
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a release-copy assistant for travel short videos. "
            "Return JSON only with title, shortTitle, description, tags, coverSuggestion. "
            "Optionally include segmentCaptions: an array of {segmentId, subtitle} to refine "
            "on-screen copy for storyboard segments that match the export description. "
            "Only use segmentId values from storyboardSummary. "
            "Tags must be an array of short strings. "
            f"Write for platform style: {platform_guide['label']}."
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
                "platformGuide": platform_guide,
                "theme": theme.model_dump() if theme else None,
                "storyboardSummary": [
                    {
                        "segmentId": segment.id,
                        "startTime": segment.startTime,
                        "endTime": segment.endTime,
                        "assetId": segment.assetId,
                        "function": segment.function,
                        "subtitle": segment.subtitle,
                    }
                    for segment in storyboard
                ],
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
        max_tokens=1600,
        on_progress=on_progress,
    )
    emit_progress(on_progress, "building", "正在整理导出文案字段…", progress=86)
    suggestion = _normalize_export_payload(result)
    if not suggestion:
        emit_progress(on_progress, "fallback", "LLM 结果无效，准备回退到规则生成…", progress=88)
    meta = build_llm_meta(result, used_fallback=suggestion is None).as_dict()
    return suggestion, meta


def _normalize_export_payload(result: LlmCallResult) -> dict[str, object] | None:
    payload = result.data if result.ok else None
    if not payload or not str(payload.get("title", "")).strip():
        return None
    tags = payload.get("tags")
    if tags is not None and not isinstance(tags, list):
        return None
    captions = payload.get("segmentCaptions")
    if captions is not None:
        if not isinstance(captions, list):
            return None
        normalized_captions: list[dict[str, str]] = []
        for item in captions:
            if not isinstance(item, dict):
                continue
            segment_id = str(item.get("segmentId", "")).strip()
            subtitle = str(item.get("subtitle", "")).strip()
            if segment_id and subtitle:
                normalized_captions.append({"segmentId": segment_id, "subtitle": subtitle})
        payload = {**payload, "segmentCaptions": normalized_captions}
    return payload


def apply_export_captions_to_segments(
    segments: list[StoryboardSegmentRead],
    captions: list[object],
) -> tuple[list[StoryboardSegmentWrite], int]:
    caption_map: dict[str, str] = {}
    for item in captions:
        if not isinstance(item, dict):
            continue
        segment_id = str(item.get("segmentId", "")).strip()
        subtitle = str(item.get("subtitle", "")).strip()
        if segment_id and subtitle:
            caption_map[segment_id] = subtitle

    if not caption_map:
        return [], 0

    updated_segments: list[StoryboardSegmentWrite] = []
    updated_count = 0
    for segment in segments:
        next_subtitle = caption_map.get(segment.id)
        if not next_subtitle or next_subtitle == segment.subtitle:
            continue
        write = segment_read_to_write(segment)
        write.subtitle = next_subtitle
        updated_segments.append(write)
        updated_count += 1
    return updated_segments, updated_count


def merge_storyboard_subtitle_updates(
    segments: list[StoryboardSegmentRead],
    updates: list[StoryboardSegmentWrite],
) -> list[StoryboardSegmentWrite]:
    update_map = {item.id: item for item in updates}
    merged: list[StoryboardSegmentWrite] = []
    for segment in segments:
        merged.append(update_map.get(segment.id, segment_read_to_write(segment)))
    return merged


def build_rule_export_fallback(
    *,
    project: ProjectEntity,
    theme: NarrativeThemeRead | None,
) -> dict[str, object]:
    guide = resolve_platform_export_guide(project.platform)
    fallback_title = (
        f"{project.destination} {theme.title}"
        if theme
        else f"{project.destination} 旅行短视频导出方案"
    )
    if guide["label"] == "抖音":
        fallback_title = f"{project.destination}，这一趟真的值得"
    elif guide["label"] == "小红书":
        fallback_title = f"原来{project.destination}可以这么拍"
    return {
        "title": fallback_title,
        "shortTitle": project.destination,
        "description": (
            f"围绕{project.destination}的路线与分镜结构整理{guide['label']}发布文案，"
            f"{guide['descriptionStyle']}。"
        ),
        "tags": [project.destination, guide["label"], "旅行短视频"],
        "coverSuggestion": guide["coverStyle"],
    }


def render_export_content(workspace: WorkspaceDataRead, fmt: str) -> str:
    export_payload = {
        "project": workspace.project.model_dump(),
        "selectedTheme": next(
            (theme.model_dump() for theme in workspace.themes if theme.isSelected),
            None,
        ),
        "rhythmPlan": workspace.rhythmPlan.model_dump(),
        "exportPlan": workspace.exportPlan.model_dump(),
        "storyboard": [segment.model_dump() for segment in workspace.storyboard],
        "storyboardValidation": workspace.storyboardValidation.model_dump(),
        "exportValidation": workspace.exportValidation.model_dump(),
    }

    if fmt == "json":
        return json.dumps(export_payload, ensure_ascii=False, indent=2)
    if fmt == "yaml":
        return to_yaml(export_payload)
    if fmt == "csv":
        return to_csv(workspace)
    return to_markdown(workspace)


def to_markdown(workspace: WorkspaceDataRead) -> str:
    storyboard_validation = workspace.storyboardValidation
    export_validation = workspace.exportValidation
    lines = [
        f"# {workspace.project.name} 导出脚本",
        "",
        "## 导出信息",
        f"- 标题：{workspace.exportPlan.title}",
        f"- 短标题：{workspace.exportPlan.shortTitle or '未填写'}",
        f"- 标签：{', '.join(workspace.exportPlan.tags) if workspace.exportPlan.tags else '未填写'}",
        f"- 描述：{workspace.exportPlan.description}",
        f"- 封面建议：{workspace.exportPlan.coverSuggestion or '未填写'}",
        "",
        "## 校验摘要",
        f"- 分镜绑定：{'通过' if storyboard_validation.allSegmentsBoundToAsset else '未通过'}",
        f"- 地点连续性：{'通过' if storyboard_validation.locationContinuityPassed else '未通过'}",
        f"- 时长：{storyboard_validation.totalDurationSec}s / 目标 {storyboard_validation.targetDurationSec}s"
        f"（偏差 {storyboard_validation.durationDeltaSec:+.2f}s）",
        f"- 导出目的地提及：{'是' if export_validation.destinationMentioned else '否'}",
        f"- 导出主题一致：{'通过' if export_validation.themeConsistencyPassed else '未通过'}",
        "",
        "## 节奏信息",
        f"- BGM 风格：{workspace.rhythmPlan.bgmStyle}",
        f"- 参考曲目：{workspace.rhythmPlan.selectedTrackName}",
        f"- 节拍模式：{workspace.rhythmPlan.beatMode}",
        f"- 节拍点：{', '.join(str(point) for point in workspace.rhythmPlan.beatPoints)}",
        "",
        "## 分镜时间线",
        "",
        "| 开始 | 结束 | 素材 ID | 功能标签 | 节奏 | 字幕 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for segment in workspace.storyboard:
        lines.append(
            f"| {segment.startTime:.2f} | {segment.endTime:.2f} | {segment.assetId} | "
            f"{segment.function} | {segment.rhythm} | {segment.subtitle} |"
        )

    if storyboard_validation.issues or export_validation.issues:
        lines.extend(["", "## 待处理项", ""])
        for issue in storyboard_validation.issues + export_validation.issues:
            lines.append(f"- {issue}")
    return "\n".join(lines)


def to_csv(workspace: WorkspaceDataRead) -> str:
    import csv
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "segmentId",
            "startTime",
            "endTime",
            "assetId",
            "function",
            "rhythm",
            "beatMode",
            "subtitle",
        ]
    )
    for segment in workspace.storyboard:
        writer.writerow(
            [
                segment.id,
                f"{segment.startTime:.2f}",
                f"{segment.endTime:.2f}",
                segment.assetId,
                segment.function,
                segment.rhythm,
                segment.beatMode,
                segment.subtitle,
            ]
        )
    return buffer.getvalue()


def to_yaml(value: object, indent: int = 0) -> str:
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(to_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(to_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{yaml_scalar(value)}"


def yaml_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace('"', '\\"')
    return f'"{text}"'
