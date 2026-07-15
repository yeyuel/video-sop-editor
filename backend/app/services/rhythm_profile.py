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
    if mode == "highlight_reel":
        return ["hook", "turn_1", "turn_2", "climax", "payoff"]
    if mode == "seed_and_guide":
        return ["hook", "visual_seed", "info_value", "decision_push", "save_cta"]
    if mode == "chapter_explainer":
        return ["hook", "chapter", "proof", "chapter", "summary"]
    if mode == "emotional_vlog":
        return ["hook", "immersion", "inner_turn", "emotional_climax", "aftertaste"]
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
        "turn_1": "第一次反转",
        "turn_2": "第二次反转",
        "climax": "高潮",
        "ending": "收尾",
        "payoff": "记忆点回收",
        "visual_seed": "视觉种草",
        "info_value": "信息价值",
        "decision_push": "决策推动",
        "save_cta": "收藏提示",
        "chapter": "章节节点",
        "proof": "信息证明",
        "summary": "总结回收",
        "promise": "开头承诺",
        "setup": "铺垫",
        "highlight": "强看点",
        "immersion": "沉浸铺陈",
        "inner_turn": "情绪转折",
        "emotional_climax": "情绪高潮",
        "aftertaste": "留白回味",
    }
    return labels.get(role, role)


def _role_description(mode: str, role: str, time_point: float) -> str:
    label = _role_label(role)
    time_label = round(float(time_point), 2)
    if mode == "highlight_reel":
        descriptions = {
            "hook": "前 3 秒必须给出高识别画面或强情绪问题，让用户知道为什么要继续看。",
            "turn_1": "第一处“射门点”，用地点变化、反差画面或意外信息制造第一次注意力回拉。",
            "turn_2": "第二处“射门点”，避免平铺路线，优先安排更强画面或新的情绪反差。",
            "climax": "主高潮位置，用最强视觉素材或最有记忆点的瞬间完成情绪抬升。",
            "payoff": "用一句可记住的字幕、回望镜头或目的地符号做收束，降低突然结束感。",
        }
    elif mode == "seed_and_guide":
        descriptions = {
            "hook": "先给结果感或利益点，让用户知道这条内容值得收藏。",
            "visual_seed": "用高颜值画面建立向往感，适合放景别完整、色彩明确的素材。",
            "info_value": "放路线、避坑、机位或花费等具体信息，避免只有氛围没有价值。",
            "decision_push": "用体验对比或关键建议推动用户做选择。",
            "save_cta": "结尾回收核心信息，适合提示收藏、路线总结或封面标题呼应。",
        }
    elif mode == "chapter_explainer":
        descriptions = {
            "hook": "先交代视频能解决什么问题，适合放路线总览或结果预告。",
            "chapter": "切入新章节，优先保证地点、路线或攻略信息清晰。",
            "proof": "用实际画面证明前面的攻略判断，例如排队、路况、价格或体验细节。",
            "summary": "总结章节结论，方便用户暂停、截图或按章节回看。",
        }
    elif mode == "emotional_vlog":
        descriptions = {
            "hook": "用人物状态或氛围画面建立陪伴感，不一定追求强反转。",
            "immersion": "保留环境声和呼吸感，让观众进入当下场景。",
            "inner_turn": "用人物反应、天气变化或路线转折带出情绪变化。",
            "emotional_climax": "把最强情绪或最完整的体验放在这里，不宜切太碎。",
            "aftertaste": "用留白画面或轻字幕收束，保留余味。",
        }
    else:
        descriptions = {}
    detail = descriptions.get(role, "安排强信息或强画面，避免节奏平均化。")
    return f"{label}：{time_label}s 附近，{detail}"


def build_attention_beats(project: ProjectEntity, mode: str) -> list[dict[str, Any]]:
    target = max(float(project.target_duration_sec), 1.0)
    roles = _attention_roles(mode)

    if target <= 20:
        if mode == "highlight_reel":
            times = [
                0.0,
                round(target * 0.25, 2),
                round(target * 0.55, 2),
                round(target * 0.8, 2),
                target,
            ]
            roles = ["hook", "turn_1", "turn_2", "climax", "payoff"]
        elif mode == "seed_and_guide":
            times = [0.0, round(target * 0.3, 2), round(target * 0.65, 2), target]
            roles = ["hook", "visual_seed", "info_value", "save_cta"]
        elif mode in {"chapter_explainer", "chapter_story"}:
            times = [0.0, round(target * 0.35, 2), round(target * 0.72, 2), target]
            roles = ["hook", "chapter", "proof", "summary"]
        elif mode == "emotional_vlog":
            times = [0.0, round(target * 0.35, 2), round(target * 0.72, 2), target]
            roles = ["hook", "immersion", "emotional_climax", "aftertaste"]
        else:
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
                "description": _role_description(mode, role, float(time_point)),
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
