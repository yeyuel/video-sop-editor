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
from app.services.llm import llm_suggestion_service

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


def build_llm_storyboard_plan(
    *,
    project: ProjectEntity,
    theme: NarrativeThemeRead,
    assets: list[AssetRead],
    rhythm: RhythmPlanRead | None,
    target_duration_sec: int,
    beat_mode: str,
) -> list[dict[str, str]] | None:
    payload = llm_suggestion_service.generate_json(
        system_prompt=(
            "You are a travel short-form video storyboard director. "
            "Return JSON only with a segments array. Each segment must include "
            "assetId, shotDescription, function, rhythm, subtitle. "
            "Only use assetId values from the provided assets. "
            "Do not repeat the same assetId. "
            "function must be one of: opening_hook, supporting, slow_climax, "
            "main_climax, ending, rhythm_hit, transition_buffer."
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
                "theme": theme.model_dump(),
                "rhythm": rhythm.model_dump() if rhythm else None,
                "beatMode": beat_mode,
                "assets": [
                    {
                        "assetId": asset.assetId,
                        "location": asset.location,
                        "scene": asset.scene,
                        "functionTags": asset.functionTags,
                        "emotionTags": asset.emotionTags,
                        "suggestedDurationSec": asset.suggestedDurationSec,
                    }
                    for asset in assets
                ],
            },
            ensure_ascii=False,
        ),
        temperature=0.5,
    )
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
            beat_index = advance_beat_index(safe_beats, current_time, beat_index)
            duration = max(asset.suggestedDurationSec, 0.5)
            interval = safe_beats[1] - safe_beats[0]
            beats_needed = max(1, round(duration / max(interval, 0.25)))
            next_index = min(beat_index + beats_needed, len(safe_beats) - 1)
            end_time = safe_beats[next_index]
            if end_time <= current_time:
                end_time = min(float(target_duration_sec), current_time + duration)
            segment_beats = [point for point in safe_beats if current_time <= point <= end_time]
            beat_index = next_index
        else:
            end_time = min(float(target_duration_sec), current_time + asset.suggestedDurationSec)
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
            beat_index = advance_beat_index(safe_beats, current_time, beat_index)
            duration = max(asset.suggestedDurationSec, 0.5)
            interval = safe_beats[1] - safe_beats[0]
            beats_needed = max(1, round(duration / max(interval, 0.25)))
            next_index = min(beat_index + beats_needed, len(safe_beats) - 1)
            end_time = safe_beats[next_index]
            if end_time <= current_time:
                end_time = min(float(target_duration_sec), current_time + duration)
            segment_beats = [point for point in safe_beats if current_time <= point <= end_time]
            beat_index = next_index
        else:
            end_time = min(float(target_duration_sec), current_time + asset.suggestedDurationSec)
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
