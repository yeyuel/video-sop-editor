from __future__ import annotations

import json

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, ExportPlanRead, NarrativeThemeRead, StoryboardSegmentRead, WorkspaceDataRead
from app.services.llm import LlmCallResult, build_llm_meta, llm_suggestion_service
from app.services.llm.progress import ProgressReporter, emit_progress


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
    result = llm_suggestion_service.generate_json_result(
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
    return payload


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
    }

    if fmt == "json":
        return json.dumps(export_payload, ensure_ascii=False, indent=2)
    if fmt == "yaml":
        return to_yaml(export_payload)
    return to_markdown(workspace)


def to_markdown(workspace: WorkspaceDataRead) -> str:
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
    return "\n".join(lines)


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
