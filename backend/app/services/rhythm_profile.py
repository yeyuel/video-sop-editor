from __future__ import annotations

from typing import Any

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, NarrativeThemeRead


PLATFORM_ALIASES = {
    "douyin": "douyin",
    "抖音": "douyin",
    "kuaishou": "kuaishou",
    "快手": "kuaishou",
    "xiaohongshu": "xiaohongshu",
    "小红书": "xiaohongshu",
    "bilibili": "bilibili",
    "b站": "bilibili",
    "B站": "bilibili",
    "shipinhao": "shipinhao",
    "视频号": "shipinhao",
    "youtube": "youtube",
    "YouTube": "youtube",
}


def _platform_key(platform: str) -> str:
    normalized = platform.strip()
    return PLATFORM_ALIASES.get(normalized, normalized.lower() or "generic")


def _video_type_key(video_type: str) -> str:
    return video_type.strip().lower() or "travel"


def resolve_rhythm_mode(platform: str, video_type: str) -> str:
    platform_key = _platform_key(platform)
    video_type_key = _video_type_key(video_type)

    if platform_key in {"douyin", "kuaishou"}:
        return "highlight_reel"
    if platform_key == "xiaohongshu":
        return "seed_and_guide"
    if platform_key == "bilibili" and ("guide" in video_type_key or "攻略" in video_type):
        return "chapter_explainer"
    if platform_key == "bilibili":
        return "emotional_vlog"
    if platform_key == "shipinhao":
        return "stable_story"
    if platform_key == "youtube":
        return "chapter_story"
    return "seed_and_guide"


def _attention_interval(mode: str, target_duration_sec: int) -> float:
    if mode == "highlight_reel":
        return 12.0
    if mode == "seed_and_guide":
        return 15.0
    if mode in {"chapter_explainer", "chapter_story"}:
        return 45.0 if target_duration_sec >= 180 else 25.0
    if mode == "emotional_vlog":
        return 20.0
    return 18.0


def _attention_roles(mode: str) -> list[str]:
    if mode == "chapter_explainer":
        return ["hook", "chapter", "proof", "chapter", "summary"]
    if mode == "chapter_story":
        return ["promise", "chapter", "turn", "highlight", "summary"]
    if mode == "stable_story":
        return ["hook", "setup", "turn", "climax", "ending"]
    return ["hook", "push", "turn", "climax", "ending"]


def _role_label(role: str) -> str:
    labels = {
        "hook": "开头钩子",
        "push": "推进",
        "turn": "反转",
        "climax": "高潮",
        "ending": "收尾",
        "chapter": "章节节点",
        "proof": "信息证明",
        "summary": "总结回收",
        "promise": "开头承诺",
        "setup": "铺垫",
        "highlight": "强看点",
    }
    return labels.get(role, role)


def build_attention_beats(project: ProjectEntity, mode: str) -> list[dict[str, Any]]:
    target = max(float(project.target_duration_sec), 1.0)
    roles = _attention_roles(mode)

    if target <= 20:
        times = [0.0, round(target * 0.35, 2), round(target * 0.7, 2), target]
        roles = ["hook", "push", "climax", "ending"]
    elif mode in {"chapter_explainer", "chapter_story"} and target >= 120:
        interval = _attention_interval(mode, int(target))
        times = [0.0]
        current = interval
        while current < target:
            times.append(round(current, 2))
            current += interval
        if times[-1] != target:
            times.append(target)
    else:
        times = [0.0, round(target * 0.25, 2), round(target * 0.5, 2), round(target * 0.75, 2), target]

    attention_beats: list[dict[str, Any]] = []
    for index, time_point in enumerate(times):
        role = roles[min(index, len(roles) - 1)]
        attention_beats.append(
            {
                "time": round(float(time_point), 2),
                "role": role,
                "label": _role_label(role),
                "description": f"{_role_label(role)}：在 {round(float(time_point), 2)}s 附近安排强信息或强画面。",
            }
        )
    return attention_beats


def build_rhythm_profile(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
) -> dict[str, Any]:
    mode = resolve_rhythm_mode(project.platform, project.video_type)
    target = max(project.target_duration_sec, 1)
    asset_count = len(assets)
    photo_count = sum(1 for asset in assets if asset.mediaType == "photo")

    if mode == "highlight_reel":
        cut_density = "fast"
        subtitle_density = "strong_hook"
        motion_policy = "快切为主，照片只用于强视觉定格或轻微推拉。"
    elif mode == "chapter_explainer":
        cut_density = "chaptered"
        subtitle_density = "information"
        motion_policy = "章节段落优先，信息镜头保留更长阅读时间。"
    elif mode == "emotional_vlog":
        cut_density = "medium_slow"
        subtitle_density = "light"
        motion_policy = "保留呼吸感，照片可用慢推和横移。"
    elif mode == "stable_story":
        cut_density = "medium"
        subtitle_density = "clear"
        motion_policy = "叙事稳定，少用过碎快切。"
    else:
        cut_density = "medium_fast"
        subtitle_density = "seed_and_info"
        motion_policy = "视觉种草段加强慢推，信息段保持清晰节奏。"

    return {
        "mode": mode,
        "platform": project.platform,
        "videoType": project.video_type,
        "targetDurationSec": target,
        "cutDensity": cut_density,
        "subtitleDensity": subtitle_density,
        "motionPolicy": motion_policy,
        "attentionIntervalSec": _attention_interval(mode, target),
        "assetCount": asset_count,
        "photoCount": photo_count,
        "themeTitle": theme.title if theme else "",
    }
