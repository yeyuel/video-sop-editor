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

STORYBOARD_LLM_BASE_MAX_TOKENS = 2000
STORYBOARD_LLM_TOKENS_PER_ASSET = 80
STORYBOARD_LLM_MAX_TOKENS_CAP = 8000


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
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理主题「{theme.title}」与 {len(ordered_assets)} 条素材…",
        progress=10,
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a travel short-form video storyboard director. "
            "Return JSON only with a segments array. "
            "Each segment must include assetId, shotDescription, subtitle. "
            "Use ruleOrderedAssetIds as the baseline order, but you may reorder segments "
            "when narrative flow improves. Include every asset exactly once. "
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
        llm_order = [item["assetId"] for item in normalized]
        merged_assets = merge_asset_order(llm_order, ordered_assets)
        plan = _align_storyboard_plan_to_assets(merged_assets, normalized)
    else:
        plan = None
    if plan is None:
        emit_progress(on_progress, "fallback", "LLM 分镜无效，准备回退到规则生成…", progress=88)
    meta = build_llm_meta(result, used_fallback=plan is None).as_dict()
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


def generate_storyboard_segments(
    assets: list[AssetRead],
    theme_id: str,
    target_duration_sec: int,
    beat_mode: str,
    beat_points: list[float],
) -> list[StoryboardSegmentWrite]:
    if not assets:
        return []

    ordered_assets = order_assets_for_storyboard(assets)
    segments: list[StoryboardSegmentWrite] = []
    beat_index = 0
    current_time = 0.0
    safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []
    for asset in ordered_assets:
        if current_time >= float(target_duration_sec):
            break

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

        function_name = asset.functionTags[0] if asset.functionTags else "supporting"
        segments.append(
            StoryboardSegmentWrite(
                id=f"seg_{uuid4().hex[:8]}",
                startTime=round(current_time, 2),
                endTime=round(end_time, 2),
                assetId=asset.assetId,
                shotDescription=f"{asset.location} - {asset.scene}",
                function=function_name,
                rhythm=rhythm_label(asset.informationDensity),
                beatMode=beat_mode,
                beatPoints=segment_beats,
                subtitle=subtitle_from_asset(asset),
            )
        )
        current_time = round(end_time, 2)

    return segments


def generate_storyboard_segments_from_plan(
    assets: list[AssetRead],
    theme_id: str,
    target_duration_sec: int,
    beat_mode: str,
    beat_points: list[float],
    llm_plan: list[dict[str, str]],
) -> list[StoryboardSegmentWrite]:
    asset_map = {asset.assetId: asset for asset in assets}
    planned_assets: list[tuple[AssetRead, dict[str, str] | None]] = []
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

        segments.append(
            StoryboardSegmentWrite(
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
            )
        )
        current_time = round(end_time, 2)

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


def build_storyboard_validation(
    project: ProjectEntity | None,
    segments: list[StoryboardSegmentRead],
    rhythm: RhythmPlanRead | None,
    assets: list[AssetRead],
) -> StoryboardValidationRead:
    asset_map = {asset.assetId: asset for asset in assets}
    all_bound = all(bool(segment.assetId) and segment.assetId in asset_map for segment in segments)
    total_duration = round(segments[-1].endTime if segments else 0.0, 2)
    beat_adaptation_enabled = any(segment.beatMode != "none" for segment in segments)
    route_locations = parse_route_locations(project.route_text) if project and project.route_text else []
    location_continuity = check_location_continuity(segments, asset_map, route_locations)
    beat_alignment = (
        check_beat_alignment(segments, rhythm.beatPoints if rhythm else [])
        if beat_adaptation_enabled
        else False
    )
    target_duration_reached = total_duration >= float(project.target_duration_sec if project else 0)

    if not segments:
        message = "当前还没有可用分镜，请先确认素材和主题。"
    elif not all_bound:
        message = "存在未绑定素材的镜头，请检查每个分镜是否都关联了有效素材。"
    elif not location_continuity:
        message = "地点顺序未通过连续性校验，建议按路线或地点递进重新调整镜头顺序。"
    elif beat_adaptation_enabled and not beat_alignment:
        message = "镜头起止点未完全落在节拍点上，可关闭「适配节拍」重生成，或手动微调时间。"
    elif target_duration_reached:
        message = "当前分镜总时长已经落在目标时长范围内。"
    else:
        message = "素材已全部使用完，但当前总时长还未达到目标时长。建议补充素材，或先将长素材切分后分别录入。"

    return StoryboardValidationRead(
        allSegmentsBoundToAsset=all_bound,
        locationContinuityPassed=location_continuity,
        beatAlignmentPassed=beat_alignment,
        beatAdaptationEnabled=beat_adaptation_enabled,
        totalDurationSec=total_duration,
        targetDurationReached=target_duration_reached,
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
    if not segments or len(beat_points) < 2:
        return False

    for segment in segments:
        if not segment.beatPoints:
            return False
        if not is_on_beat(segment.startTime, beat_points, tolerance):
            return False
        if not is_on_beat(segment.endTime, beat_points, tolerance):
            return False
    return True


def is_on_beat(time_point: float, beat_points: list[float], tolerance: float) -> bool:
    return any(abs(point - time_point) <= tolerance for point in beat_points)
