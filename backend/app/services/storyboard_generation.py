from __future__ import annotations

import json
import re
from uuid import uuid4

from app.models.entities import ProjectEntity
from app.models.schemas import (
    AssetRead,
    NarrativeThemeRead,
    RhythmPlanRead,
    StoryboardSegmentRead,
    StoryboardSegmentWrite,
    StoryboardValidationRead,
)
from app.services.beat_grid import filter_beats_for_capcut_mode, normalize_beat_times
from app.services.llm import LlmCallResult, build_llm_meta, llm_suggestion_service
from app.services.llm.progress import ProgressReporter, emit_progress

STORYBOARD_CHAPTER_PRIORITY = {
    "opening_hook": 0,
    "supporting": 1,
    "slow_climax": 2,
    "main_climax": 3,
    "ending": 4,
}

STORYBOARD_MODIFIER_PRIORITY = {
    "base": 0,
    "rhythm_hit": 1,
    "transition_buffer": 2,
}

DURATION_TOLERANCE_RATIO = 0.15
DURATION_TOLERANCE_MIN_SEC = 3.0

STORYBOARD_LLM_BASE_MAX_TOKENS = 2000
STORYBOARD_LLM_TOKENS_PER_ASSET = 80
STORYBOARD_LLM_MAX_TOKENS_CAP = 8000


def infer_visual_strength(asset: AssetRead) -> str:
    score = 0
    shot_type = asset.shotType.lower()
    if shot_type in {"wide", "aerial", "closeup", "大景", "航拍", "特写"}:
        score += 2
    if asset.informationDensity == "high":
        score += 1
    if any(tag in {"main_climax", "slow_climax", "opening_hook", "主高潮", "慢高潮", "开头钩子"} for tag in asset.functionTags):
        score += 2
    strong_words = {"雪山", "日落", "航拍", "人像", "动物", "冲突", "反转", "蓝调", "金色"}
    if any(tag in strong_words for tag in [*asset.visualTags, *asset.emotionTags]):
        score += 1
    if score >= 4:
        return "strong"
    if score >= 2:
        return "medium"
    return "weak"


def infer_attention_role(function_name: str) -> str:
    role_map = {
        "opening_hook": "hook",
        "rhythm_hit": "push",
        "slow_climax": "climax",
        "main_climax": "climax",
        "transition_buffer": "buffer",
        "ending": "ending",
    }
    return role_map.get(function_name, "supporting")


def infer_motion_policy(asset: AssetRead, visual_strength: str) -> str:
    if asset.mediaType == "photo":
        return "slow_push" if visual_strength != "weak" else "gentle_zoom"
    if visual_strength == "strong":
        return "hold_or_speed_ramp"
    return "natural_cut"


def infer_transition_policy(attention_role: str) -> str:
    if attention_role in {"hook", "climax"}:
        return "hard_cut"
    if attention_role == "buffer":
        return "fade_or_match_cut"
    return "clean_cut"


def _theme_context_for_llm(theme: NarrativeThemeRead) -> dict[str, str]:
    return {
        "title": theme.title,
        "summary": theme.summary,
        "coreEmotion": theme.coreEmotion,
        "rhythmProfile": theme.rhythmProfile,
    }


def _rhythm_context_for_llm(rhythm: RhythmPlanRead | None, beat_mode: str) -> dict[str, object] | None:
    if not rhythm:
        return None
    notes = [note.strip() for note in rhythm.rhythmNotes if note.strip()][:3]
    return {
        "beatMode": beat_mode or rhythm.beatMode,
        "detectedBpm": rhythm.detectedBpm,
        "bgmStyle": rhythm.bgmStyle,
        "selectedTrackName": rhythm.selectedTrackName,
        "rhythmProfile": rhythm.rhythmProfile,
        "attentionBeats": rhythm.attentionBeats,
        "rhythmNotesSummary": notes,
    }


def _storyboard_max_tokens(asset_count: int) -> int:
    return min(
        STORYBOARD_LLM_MAX_TOKENS_CAP,
        STORYBOARD_LLM_BASE_MAX_TOKENS + max(asset_count, 1) * STORYBOARD_LLM_TOKENS_PER_ASSET,
    )


def merge_asset_order(
    llm_asset_ids: list[str],
    rule_ordered_assets: list[AssetRead],
) -> list[AssetRead]:
    """LLM 排序优先，缺失素材按规则顺序补齐。"""
    asset_map = {asset.assetId: asset for asset in rule_ordered_assets}
    merged: list[AssetRead] = []
    seen: set[str] = set()

    for asset_id in llm_asset_ids:
        asset = asset_map.get(asset_id)
        if not asset or asset.assetId in seen:
            continue
        merged.append(asset)
        seen.add(asset.assetId)

    for asset in rule_ordered_assets:
        if asset.assetId in seen:
            continue
        merged.append(asset)
        seen.add(asset.assetId)
    return merged


def resolve_storyboard_beat_points(
    rhythm: RhythmPlanRead | None,
    *,
    beat_mode: str,
    target_duration_sec: int,
    align_to_beat: bool,
) -> list[float]:
    if not align_to_beat or beat_mode == "none" or not rhythm:
        return []

    raw_source = rhythm.rawBeatPoints or rhythm.beatPoints
    if raw_source:
        return filter_beats_for_capcut_mode(
            normalize_beat_times(raw_source, float(target_duration_sec)),
            beat_mode,
            float(target_duration_sec),
            coarse_beats=rhythm.coarseBeatPoints or None,
        )
    return rhythm.beatPoints


def _dominant_beat_mode(
    segments: list[StoryboardSegmentRead],
    rhythm: RhythmPlanRead | None,
) -> str:
    for segment in segments:
        if segment.beatMode and segment.beatMode != "none":
            return segment.beatMode
    if rhythm and rhythm.beatMode:
        return rhythm.beatMode
    return "none"


def resolve_validation_beat_points(
    rhythm: RhythmPlanRead | None,
    segments: list[StoryboardSegmentRead],
    target_duration_sec: float,
) -> list[float]:
    """与分镜生成使用同一套节拍网格，避免 coarse beatPoints 误报对齐失败。"""
    if not rhythm:
        collected: set[float] = set()
        for segment in segments:
            if segment.beatMode == "none":
                continue
            collected.update(segment.beatPoints)
            collected.add(segment.startTime)
            collected.add(segment.endTime)
        return sorted(collected)

    beat_mode = _dominant_beat_mode(segments, rhythm)
    if beat_mode != "none":
        resolved = resolve_storyboard_beat_points(
            rhythm,
            beat_mode=beat_mode,
            target_duration_sec=max(int(round(target_duration_sec)), 1),
            align_to_beat=True,
        )
        if resolved:
            return resolved

    return rhythm.beatPoints


def _align_storyboard_plan_to_assets(
    ordered_assets: list[AssetRead],
    plan: list[dict[str, str]],
) -> list[dict[str, str]]:
    plan_by_asset = {item["assetId"]: item for item in plan}
    aligned: list[dict[str, str]] = []
    for asset in ordered_assets:
        item = plan_by_asset.get(asset.assetId)
        if item:
            aligned.append(item)
            continue
        aligned.append(
            {
                "assetId": asset.assetId,
                "shotDescription": "",
                "function": "",
                "rhythm": "",
                "subtitle": "",
            }
        )
    return aligned


def build_llm_storyboard_plan(
    *,
    project: ProjectEntity,
    theme: NarrativeThemeRead,
    assets: list[AssetRead],
    rhythm: RhythmPlanRead | None,
    target_duration_sec: int,
    beat_mode: str,
    on_progress: ProgressReporter | None = None,
) -> tuple[list[dict[str, str]] | None, dict[str, str]]:
    ordered_assets = order_assets_for_storyboard(assets)
    allow_asset_reuse = bool(getattr(project, "allow_asset_reuse", False))
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理主题「{theme.title}」与 {len(ordered_assets)} 条素材…",
        progress=10,
    )
    reuse_instruction = (
        "You may include the same assetId in multiple segments when pacing or narrative "
        "benefits from reuse. Prefer varied shotDescription/subtitle across reuse instances."
        if allow_asset_reuse
        else "Include every asset exactly once."
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a travel short-form video storyboard director. "
            "Return JSON only with a segments array. "
            "Each segment must include assetId, shotDescription, subtitle. "
            "Use ruleOrderedAssetIds as the baseline order, but you may reorder segments "
            f"when narrative flow improves. {reuse_instruction} "
            "The segments array order is your preferred timeline order. "
            "Do not invent assetId values outside ruleOrderedAssetIds."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "routeText": project.route_text,
                    "targetDurationSec": target_duration_sec,
                    "allowAssetReuse": allow_asset_reuse,
                },
                "theme": _theme_context_for_llm(theme),
                "rhythm": _rhythm_context_for_llm(rhythm, beat_mode),
                "ruleOrderedAssetIds": [asset.assetId for asset in ordered_assets],
                "assets": [
                    {
                        "assetId": asset.assetId,
                        "location": asset.location,
                        "scene": asset.scene,
                        "functionTags": asset.functionTags,
                        "emotionTags": asset.emotionTags,
                        "suggestedDurationSec": asset.suggestedDurationSec,
                    }
                    for asset in ordered_assets
                ],
            },
            ensure_ascii=False,
        ),
        temperature=0.5,
        max_tokens=_storyboard_max_tokens(len(ordered_assets)),
        on_progress=on_progress,
    )
    emit_progress(on_progress, "building", "正在解析分镜脚本结构…", progress=86)
    normalized = _normalize_storyboard_plan(result, assets)
    if normalized:
        if allow_asset_reuse:
            plan = normalized
        else:
            llm_order = [item["assetId"] for item in normalized]
            merged_assets = merge_asset_order(llm_order, ordered_assets)
            plan = _align_storyboard_plan_to_assets(merged_assets, normalized)
    else:
        plan = None
    if plan is None:
        emit_progress(on_progress, "fallback", "LLM 分镜无效，准备回退到规则生成…", progress=88)
    meta = build_llm_meta(result, used_fallback=plan is None).as_dict()
    meta["assetReuseEnabled"] = "true" if allow_asset_reuse else "false"
    if allow_asset_reuse and plan is not None:
        meta["llmMessage"] = f"{meta.get('llmMessage', '')} 项目已启用镜头复用。".strip()
    return plan, meta


def _normalize_storyboard_plan(
    result: LlmCallResult,
    assets: list[AssetRead],
) -> list[dict[str, str]] | None:
    payload = result.data if result.ok else None
    segments = payload.get("segments") if payload else None
    if not isinstance(segments, list):
        return None

    allowed_asset_ids = {asset.assetId for asset in assets}
    normalized: list[dict[str, str]] = []
    for item in segments:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("assetId", "")).strip()
        if not asset_id or asset_id not in allowed_asset_ids:
            continue
        normalized.append(
            {
                "assetId": asset_id,
                "shotDescription": str(item.get("shotDescription", "")).strip(),
                "function": str(item.get("function", "")).strip(),
                "rhythm": str(item.get("rhythm", "")).strip(),
                "subtitle": str(item.get("subtitle", "")).strip(),
            }
        )
    return normalized or None


def _build_segment_write(
    *,
    asset: AssetRead,
    plan_item: dict[str, str] | None,
    current_time: float,
    target_duration_sec: int,
    beat_mode: str,
    safe_beats: list[float],
    beat_index: int,
) -> tuple[StoryboardSegmentWrite, float, int]:
    if safe_beats:
        end_time, beat_index, segment_beats = resolve_segment_timing(
            current_time=current_time,
            suggested_duration_sec=asset.suggestedDurationSec,
            target_duration_sec=target_duration_sec,
            beat_points=safe_beats,
            beat_index=beat_index,
        )
    else:
        end_time = min(
            float(target_duration_sec),
            current_time + max(asset.suggestedDurationSec, 0.5),
        )
        segment_beats = [round(current_time, 2), round(end_time, 2)]

    fallback_function = asset.functionTags[0] if asset.functionTags else "supporting"
    fallback_rhythm = rhythm_label(asset.informationDensity)
    fallback_subtitle = subtitle_from_asset(asset)
    shot_description = (
        str(plan_item.get("shotDescription", "")).strip() if plan_item else ""
    ) or f"{asset.location} - {asset.scene}"
    function_name = normalize_storyboard_function(
        str(plan_item.get("function", "")).strip() if plan_item else fallback_function,
        fallback_function,
    )
    rhythm_text = (
        str(plan_item.get("rhythm", "")).strip() if plan_item else ""
    ) or fallback_rhythm
    subtitle = (
        str(plan_item.get("subtitle", "")).strip() if plan_item else ""
    ) or fallback_subtitle

    attention_role = infer_attention_role(function_name)
    visual_strength = infer_visual_strength(asset)

    segment = StoryboardSegmentWrite(
        id=f"seg_{uuid4().hex[:8]}",
        startTime=round(current_time, 2),
        endTime=round(end_time, 2),
        assetId=asset.assetId,
        shotDescription=shot_description,
        function=function_name,
        rhythm=rhythm_text,
        beatMode=beat_mode,
        beatPoints=segment_beats,
        subtitle=subtitle,
        attentionRole=attention_role,
        visualStrength=visual_strength,
        motionPolicy=infer_motion_policy(asset, visual_strength),
        transitionPolicy=infer_transition_policy(attention_role),
    )
    return segment, round(end_time, 2), beat_index


def generate_storyboard_segments(
    assets: list[AssetRead],
    theme_id: str,
    target_duration_sec: int,
    beat_mode: str,
    beat_points: list[float],
    allow_asset_reuse: bool = False,
) -> list[StoryboardSegmentWrite]:
    if not assets:
        return []

    ordered_assets = order_assets_for_storyboard(assets)
    segments: list[StoryboardSegmentWrite] = []
    beat_index = 0
    current_time = 0.0
    safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []
    asset_index = 0

    while current_time < float(target_duration_sec):
        if asset_index >= len(ordered_assets):
            if not allow_asset_reuse:
                break
            asset_index = 0

        asset = ordered_assets[asset_index]
        asset_index += 1
        segment, current_time, beat_index = _build_segment_write(
            asset=asset,
            plan_item=None,
            current_time=current_time,
            target_duration_sec=target_duration_sec,
            beat_mode=beat_mode,
            safe_beats=safe_beats,
            beat_index=beat_index,
        )
        segments.append(segment)

    return segments


def generate_storyboard_segments_from_plan(
    assets: list[AssetRead],
    theme_id: str,
    target_duration_sec: int,
    beat_mode: str,
    beat_points: list[float],
    llm_plan: list[dict[str, str]],
    allow_asset_reuse: bool = False,
) -> list[StoryboardSegmentWrite]:
    asset_map = {asset.assetId: asset for asset in assets}
    planned_assets: list[tuple[AssetRead, dict[str, str] | None]] = []

    if allow_asset_reuse:
        for item in llm_plan:
            asset_id = str(item.get("assetId", "")).strip()
            asset = asset_map.get(asset_id)
            if asset:
                planned_assets.append((asset, item))
        seen_asset_ids = {asset.assetId for asset, _ in planned_assets}
        for asset in order_assets_for_storyboard(assets):
            if asset.assetId not in seen_asset_ids:
                planned_assets.append((asset, None))
    else:
        used_asset_ids: set[str] = set()
        for item in llm_plan:
            asset_id = str(item.get("assetId", "")).strip()
            asset = asset_map.get(asset_id)
            if not asset or asset.assetId in used_asset_ids:
                continue
            planned_assets.append((asset, item))
            used_asset_ids.add(asset.assetId)

        for asset in order_assets_for_storyboard(assets):
            if asset.assetId not in used_asset_ids:
                planned_assets.append((asset, None))

    segments: list[StoryboardSegmentWrite] = []
    beat_index = 0
    current_time = 0.0
    safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []

    for asset, plan_item in planned_assets:
        if current_time >= float(target_duration_sec):
            break
        segment, current_time, beat_index = _build_segment_write(
            asset=asset,
            plan_item=plan_item,
            current_time=current_time,
            target_duration_sec=target_duration_sec,
            beat_mode=beat_mode,
            safe_beats=safe_beats,
            beat_index=beat_index,
        )
        segments.append(segment)

    if allow_asset_reuse:
        ordered_assets = order_assets_for_storyboard(assets)
        cycle_index = 0
        while current_time < float(target_duration_sec) and ordered_assets:
            asset = ordered_assets[cycle_index % len(ordered_assets)]
            cycle_index += 1
            segment, current_time, beat_index = _build_segment_write(
                asset=asset,
                plan_item=None,
                current_time=current_time,
                target_duration_sec=target_duration_sec,
                beat_mode=beat_mode,
                safe_beats=safe_beats,
                beat_index=beat_index,
            )
            segments.append(segment)

    return segments


def segment_read_to_write(segment: StoryboardSegmentRead) -> StoryboardSegmentWrite:
    return StoryboardSegmentWrite(
        id=segment.id,
        startTime=segment.startTime,
        endTime=segment.endTime,
        assetId=segment.assetId,
        shotDescription=segment.shotDescription,
        function=segment.function,
        rhythm=segment.rhythm,
        beatMode=segment.beatMode,
        beatPoints=segment.beatPoints,
        subtitle=segment.subtitle,
        attentionRole=segment.attentionRole,
        visualStrength=segment.visualStrength,
        motionPolicy=segment.motionPolicy,
        transitionPolicy=segment.transitionPolicy,
    )


def normalize_storyboard_segments(
    segments: list[StoryboardSegmentWrite],
    rhythm: RhythmPlanRead | None,
) -> list[StoryboardSegmentWrite]:
    normalized: list[StoryboardSegmentWrite] = []
    current_time = 0.0
    for segment in segments:
        duration = max(round(segment.endTime - segment.startTime, 2), 0.5)
        start_time = round(current_time, 2)
        end_time = round(start_time + duration, 2)
        beat_mode = rhythm.beatMode if rhythm and rhythm.beatMode != "none" else segment.beatMode
        beat_points = slice_beat_points(
            rhythm.beatPoints if rhythm else [],
            start_time,
            end_time,
        )
        normalized.append(
            segment.model_copy(
                update={
                    "startTime": start_time,
                    "endTime": end_time,
                    "beatMode": beat_mode,
                    "beatPoints": beat_points,
                }
            )
        )
        current_time = end_time
    return normalized


def dedupe_issue_messages(issues: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for issue in issues:
        if issue in seen:
            continue
        seen.add(issue)
        deduped.append(issue)
    return deduped


def build_storyboard_validation(
    project: ProjectEntity | None,
    segments: list[StoryboardSegmentRead],
    rhythm: RhythmPlanRead | None,
    assets: list[AssetRead],
) -> StoryboardValidationRead:
    asset_map = {asset.assetId: asset for asset in assets}
    unbound_segment_count = sum(
        1 for segment in segments if not segment.assetId or segment.assetId not in asset_map
    )
    all_bound = unbound_segment_count == 0
    total_duration = round(segments[-1].endTime if segments else 0.0, 2)
    target_duration = float(project.target_duration_sec if project else 0)
    duration_delta = round(total_duration - target_duration, 2)
    duration_within_tolerance = duration_within_target_tolerance(total_duration, target_duration)
    beat_adaptation_enabled = any(segment.beatMode != "none" for segment in segments)
    validate_location_order = bool(project and project.validate_location_order)
    allow_asset_reuse = bool(project and getattr(project, "allow_asset_reuse", False))
    asset_usage: dict[str, int] = {}
    asset_duration: dict[str, float] = {}
    for segment in segments:
        if not segment.assetId or segment.assetId not in asset_map:
            continue
        asset_usage[segment.assetId] = asset_usage.get(segment.assetId, 0) + 1
        duration = max(segment.endTime - segment.startTime, 0.0)
        asset_duration[segment.assetId] = asset_duration.get(segment.assetId, 0.0) + duration
    reused_asset_count = sum(1 for count in asset_usage.values() if count > 1)
    reused_segment_count = sum(count - 1 for count in asset_usage.values() if count > 1)
    if validate_location_order:
        route_locations = parse_route_locations(project.route_text) if project and project.route_text else []
        location_continuity = check_location_continuity(segments, asset_map, route_locations)
        location_jump_issues = find_location_jump_issues(segments, asset_map, route_locations)
    else:
        location_continuity = True
        location_jump_issues = []
    beat_alignment = False
    if beat_adaptation_enabled:
        validation_beats = resolve_validation_beat_points(rhythm, segments, target_duration)
        beat_alignment = check_beat_alignment(segments, validation_beats)
    target_duration_reached = total_duration >= target_duration
    issues: list[str] = []

    if not segments:
        issues.append("当前还没有可用分镜")
    if unbound_segment_count:
        issues.append(f"有 {unbound_segment_count} 个镜头未绑定有效素材")
    if location_jump_issues:
        issues.extend(location_jump_issues)
    if beat_adaptation_enabled and not beat_alignment:
        issues.append("镜头起止点未完全落在节拍点上")
    if target_duration > 0 and not duration_within_tolerance:
        if duration_delta < 0:
            issues.append(
                f"总时长 {total_duration}s 低于目标 {target_duration}s（差 {abs(duration_delta)}s）"
            )
        else:
            issues.append(
                f"总时长 {total_duration}s 超出目标 {target_duration}s（多 {duration_delta}s）"
            )
    if allow_asset_reuse and reused_asset_count:
        for asset_id, count in sorted(asset_usage.items()):
            if count <= 1:
                continue
            share_pct = (
                round(asset_duration[asset_id] / total_duration * 100, 1)
                if total_duration > 0
                else 0.0
            )
            issues.append(
                f"素材 {asset_id} 复用 {count} 段，合计时长占比 {share_pct}%"
            )

    issues = dedupe_issue_messages(issues)

    if not segments:
        message = "当前还没有可用分镜，请先确认素材和主题。"
    elif issues:
        message = "；".join(issues)
    elif target_duration_reached or duration_within_tolerance:
        if allow_asset_reuse and reused_asset_count:
            message = (
                f"当前分镜总时长已经落在目标时长范围内；"
                f"共 {reused_asset_count} 个素材被复用（额外 {reused_segment_count} 段）。"
            )
        else:
            message = "当前分镜总时长已经落在目标时长范围内。"
    elif allow_asset_reuse:
        message = (
            "素材已全部轮用，但当前总时长还未达到目标时长。"
            "建议补充素材，或先将长素材切分后分别录入。"
        )
    else:
        message = "素材已全部使用完，但当前总时长还未达到目标时长。建议补充素材，或先将长素材切分后分别录入。"

    return StoryboardValidationRead(
        allSegmentsBoundToAsset=all_bound,
        locationContinuityPassed=location_continuity,
        locationOrderValidationEnabled=validate_location_order,
        beatAlignmentPassed=beat_alignment,
        beatAdaptationEnabled=beat_adaptation_enabled,
        totalDurationSec=total_duration,
        targetDurationSec=target_duration,
        durationDeltaSec=duration_delta,
        durationWithinTolerance=duration_within_tolerance,
        targetDurationReached=target_duration_reached,
        unboundSegmentCount=unbound_segment_count,
        assetReuseEnabled=allow_asset_reuse,
        reusedAssetCount=reused_asset_count,
        reusedSegmentCount=reused_segment_count,
        issues=issues,
        message=message,
    )


def order_assets_for_storyboard(assets: list[AssetRead]) -> list[AssetRead]:
    indexed_assets = list(enumerate(assets))
    indexed_assets.sort(
        key=lambda item: (
            asset_storyboard_chapter_priority(item[1]),
            asset_storyboard_modifier_priority(item[1]),
            asset_sequence_number(item[1].assetId),
            item[0],
        )
    )
    return [asset for _, asset in indexed_assets]


def asset_order_key(asset: AssetRead) -> tuple[int, str]:
    match = re.search(r"_(\d+)$", asset.assetId)
    if match:
        return (int(match.group(1)), asset.assetId)
    return (10**9, asset.assetId)


def asset_storyboard_chapter_priority(asset: AssetRead) -> int:
    priorities = [
        STORYBOARD_CHAPTER_PRIORITY[tag]
        for tag in asset.functionTags
        if tag in STORYBOARD_CHAPTER_PRIORITY
    ]
    if priorities:
        return min(priorities)
    return STORYBOARD_CHAPTER_PRIORITY["supporting"]


def asset_storyboard_modifier_priority(asset: AssetRead) -> int:
    if "transition_buffer" in asset.functionTags:
        return STORYBOARD_MODIFIER_PRIORITY["transition_buffer"]
    if "rhythm_hit" in asset.functionTags:
        return STORYBOARD_MODIFIER_PRIORITY["rhythm_hit"]
    return STORYBOARD_MODIFIER_PRIORITY["base"]


def asset_sequence_number(asset_id: str) -> int:
    if "_" not in asset_id:
        return 10**9
    suffix = asset_id.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else 10**9


def advance_beat_index(beat_points: list[float], current_time: float, beat_index: int) -> int:
    while beat_index < len(beat_points) - 1 and beat_points[beat_index] < current_time:
        beat_index += 1
    return beat_index


def resolve_segment_timing(
    *,
    current_time: float,
    suggested_duration_sec: float,
    target_duration_sec: float,
    beat_points: list[float],
    beat_index: int,
) -> tuple[float, int, list[float]]:
    """分配镜头时长：不超过素材建议时长，并尽量在节拍点上切。"""
    max_duration = max(suggested_duration_sec, 0.5)
    hard_end = min(current_time + max_duration, float(target_duration_sec))

    if not beat_points or len(beat_points) < 2:
        end_time = hard_end
        return (
            round(end_time, 2),
            beat_index,
            [round(current_time, 2), round(end_time, 2)],
        )

    beat_index = advance_beat_index(beat_points, current_time, beat_index)
    end_time = hard_end
    snapped_index = beat_index

    for idx in range(beat_index + 1, len(beat_points)):
        point = beat_points[idx]
        if point > hard_end + 0.001:
            break
        end_time = point
        snapped_index = idx

    if end_time <= current_time + 0.001:
        end_time = hard_end

    if beat_points and not is_on_beat(end_time, beat_points, 0.001):
        in_range = [
            point
            for point in beat_points
            if point > current_time + 0.001 and point <= hard_end + 0.001
        ]
        if in_range:
            end_time = in_range[-1]
        elif end_time > beat_points[-1] + 0.001 and beat_points[-1] > current_time + 0.001:
            end_time = beat_points[-1]
        elif end_time > beat_points[-1] + 0.001 and is_on_beat(current_time, beat_points, 0.001):
            end_time = beat_points[-1]
        snapped_index = next(
            (
                idx
                for idx, point in enumerate(beat_points)
                if abs(point - end_time) <= 0.001
            ),
            snapped_index,
        )

    segment_beats = [
        round(point, 2) for point in beat_points if current_time <= point <= end_time + 0.001
    ]
    start = round(current_time, 2)
    end = round(end_time, 2)
    if not segment_beats:
        segment_beats = [start, end]
    else:
        if segment_beats[0] != start:
            segment_beats.insert(0, start)
        if segment_beats[-1] != end:
            segment_beats.append(end)

    return end, snapped_index, segment_beats


def rhythm_label(information_density: str) -> str:
    return {
        "high": "tight_cut",
        "medium": "balanced",
        "low": "linger",
    }.get(information_density, "balanced")


def subtitle_from_asset(asset: AssetRead) -> str:
    return f"{asset.location} / {asset.scene}"


def normalize_storyboard_function(candidate: str, fallback: str) -> str:
    allowed = set(STORYBOARD_CHAPTER_PRIORITY) | set(STORYBOARD_MODIFIER_PRIORITY)
    if candidate in allowed:
        return candidate
    return fallback if fallback in allowed else "supporting"


def slice_beat_points(beat_points: list[float], start_time: float, end_time: float) -> list[float]:
    scoped_points = [round(point, 2) for point in beat_points if start_time <= point <= end_time]
    if scoped_points:
        return scoped_points
    return [start_time, end_time]


def parse_route_locations(route_text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(
            r"\s*(?:->|\u2192|\u2014|-|,|\uff0c|\u3001|\r?\n)\s*",
            route_text,
        )
        if item.strip()
    ]


def duration_within_target_tolerance(total_duration: float, target_duration: float) -> bool:
    if target_duration <= 0:
        return total_duration > 0
    tolerance = max(target_duration * DURATION_TOLERANCE_RATIO, DURATION_TOLERANCE_MIN_SEC)
    delta = total_duration - target_duration
    return abs(delta) <= tolerance or total_duration >= target_duration


def find_location_jump_issues(
    segments: list[StoryboardSegmentRead],
    asset_map: dict[str, AssetRead],
    route_locations: list[str],
) -> list[str]:
    if not segments:
        return []

    segment_locations: list[str] = []
    for segment in segments:
        asset = asset_map.get(segment.assetId)
        if not asset or not asset.location:
            return [f"镜头 {segment.id} 缺少地点信息，无法校验地点连续性"]
        segment_locations.append(asset.location)

    issues: list[str] = []
    if route_locations:
        route_index_map = {location: index for index, location in enumerate(route_locations)}
        route_indexes = [route_index_map.get(location) for location in segment_locations]
        if all(index is not None for index in route_indexes):
            last_index = -1
            last_location = ""
            for index, location in zip(route_indexes, segment_locations, strict=True):
                if index is not None and index < last_index:
                    issues.append(
                        f"地点顺序回跳：{last_location} → {location}，与路线顺序不一致"
                    )
                if index is not None:
                    last_index = index
                    last_location = location
            return dedupe_issue_messages(issues)

    seen_order: dict[str, int] = {}
    last_seen_index = -1
    last_location = ""
    for location in segment_locations:
        if location not in seen_order:
            seen_order[location] = len(seen_order)
        current_index = seen_order[location]
        if current_index < last_seen_index:
            issues.append(f"地点顺序回跳：{last_location} → {location}")
        last_seen_index = current_index
        last_location = location
    return dedupe_issue_messages(issues)


def check_location_continuity(
    segments: list[StoryboardSegmentRead],
    asset_map: dict[str, AssetRead],
    route_locations: list[str],
) -> bool:
    if not segments:
        return False

    segment_locations: list[str] = []
    for segment in segments:
        asset = asset_map.get(segment.assetId)
        if not asset or not asset.location:
            return False
        segment_locations.append(asset.location)

    if route_locations:
        route_index_map = {location: index for index, location in enumerate(route_locations)}
        route_indexes = [route_index_map.get(location) for location in segment_locations]
        if all(index is not None for index in route_indexes):
            last_index = -1
            for index in route_indexes:
                if index is not None and index < last_index:
                    return False
                if index is not None:
                    last_index = index
            return True

    seen_order: dict[str, int] = {}
    last_seen_index = -1
    for location in segment_locations:
        if location not in seen_order:
            seen_order[location] = len(seen_order)
        current_index = seen_order[location]
        if current_index < last_seen_index:
            return False
        last_seen_index = current_index
    return True


def check_beat_alignment(
    segments: list[StoryboardSegmentRead],
    beat_points: list[float],
    tolerance: float = 0.05,
) -> bool:
    beat_segments = [segment for segment in segments if segment.beatMode != "none"]
    if not beat_segments:
        return True

    for segment in beat_segments:
        reference = sorted(set(beat_points) | set(segment.beatPoints))
        if not reference:
            return False
        if not is_on_beat(segment.startTime, reference, tolerance):
            return False
        if not is_on_beat(segment.endTime, reference, tolerance):
            return False
    return True


def is_on_beat(time_point: float, beat_points: list[float], tolerance: float) -> bool:
    return any(abs(point - time_point) <= tolerance for point in beat_points)
