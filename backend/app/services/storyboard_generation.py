from __future__ import annotations

from difflib import SequenceMatcher
import json
import re
from dataclasses import dataclass
from typing import Any
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
from app.services.beat_grid import (
    apply_beat_calibration,
    filter_beats_for_capcut_mode,
    normalize_beat_times,
)
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

STORYBOARD_LLM_BASE_MAX_TOKENS = 1400
STORYBOARD_LLM_TOKENS_PER_ASSET = 55
STORYBOARD_LLM_MAX_TOKENS_CAP = 6000
STORYBOARD_BEAM_WIDTH = 4
STORYBOARD_SLOT_CANDIDATE_LIMIT = 5
REUSE_MAX_BRIDGE_PER_GAP = 2
REUSE_MAX_BRIDGE_REPEAT_PER_ASSET = 2
DURATION_FILL_MAX_CONSECUTIVE_ROUTE = 2

NARRATIVE_HIGH_ATTENTION_ROLES = {
    "hook",
    "turn",
    "turn_1",
    "turn_2",
    "climax",
    "emotional_climax",
    "highlight",
}

NARRATIVE_SETUP_ROLES = {
    "setup",
    "chapter_setup",
    "visual_seed",
    "immersion",
    "chapter",
    "promise",
    "develop_1",
    "develop_2",
    "emotion_build",
    "afterglow",
}

NARRATIVE_INFO_ROLES = {
    "info_value",
    "proof",
    "chapter",
    "summary",
    "decision_push",
    "save_cta",
    "detail",
    "experience",
    "chapter_bridge",
}

NARRATIVE_PAYOFF_ROLES = {"payoff", "ending", "aftertaste", "summary", "save_cta"}

NARRATIVE_STRONG_WORDS = {
    "雪山",
    "日落",
    "航拍",
    "人像",
    "动物",
    "冲突",
    "反转",
    "蓝调",
    "金色",
    "云海",
    "全景",
    "夜景",
}


@dataclass(frozen=True)
class NarrativeSlot:
    id: str
    role: str
    time: float
    route_policy: str


@dataclass(frozen=True)
class PlannedAsset:
    asset: AssetRead
    attention_role: str
    selection_trace: str = ""


@dataclass
class StoryboardPlanningState:
    selected_assets: list[PlannedAsset]
    unused_assets: list[AssetRead]
    current_route_index: int
    score: float


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


def infer_subtitle_policy(attention_role: str) -> str:
    if attention_role in {
        "hook",
        "turning_point",
        "turn_1",
        "turn_2",
        "climax",
        "emotional_climax",
        "payoff",
        "ending",
    }:
        return "emphasis"
    if attention_role in {"chapter", "proof", "detail", "summary", "route_info"}:
        return "info"
    if attention_role in {"buffer", "afterglow", "aftertaste"}:
        return "minimal"
    return "standard"


def infer_attention_role_from_timing(
    attention_beats: list[dict[str, Any]] | None,
    start_time: float,
    end_time: float,
    fallback_role: str,
) -> str:
    if not attention_beats:
        return fallback_role

    midpoint = (start_time + end_time) / 2
    valid_beats = [
        beat
        for beat in attention_beats
        if isinstance(beat, dict) and isinstance(beat.get("time"), (int, float))
    ]
    if not valid_beats:
        return fallback_role

    nearest = min(valid_beats, key=lambda beat: abs(float(beat["time"]) - midpoint))
    role = str(nearest.get("role", "")).strip()
    return role or fallback_role


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


def build_narrative_slots(
    *,
    rhythm_profile: dict[str, Any] | None,
    attention_beats: list[dict[str, Any]] | None,
    target_duration_sec: int,
) -> list[NarrativeSlot]:
    mode = str((rhythm_profile or {}).get("mode", "")).strip()
    valid_beats = sorted(
        [
            beat
            for beat in (attention_beats or [])
            if isinstance(beat, dict) and isinstance(beat.get("time"), (int, float))
        ],
        key=lambda beat: float(beat["time"]),
    )
    if valid_beats:
        slots = [
            NarrativeSlot(
                id=f"attention_{index + 1}",
                role=str(beat.get("role", "")).strip() or "supporting",
                time=max(float(beat["time"]), 0.0),
                route_policy=_route_policy_for_role(
                    str(beat.get("role", "")).strip() or "supporting",
                    mode,
                ),
            )
            for index, beat in enumerate(valid_beats)
        ]
        return slots

    target = max(float(target_duration_sec), 1.0)
    if mode == "chapter_explainer":
        roles = ["hook", "chapter", "proof", "chapter", "summary"]
        ratios = [0.0, 0.2, 0.45, 0.7, 0.92]
    elif mode == "seed_and_guide":
        roles = ["hook", "visual_seed", "info_value", "decision_push", "save_cta"]
        ratios = [0.0, 0.18, 0.42, 0.7, 0.92]
    elif mode == "emotional_vlog":
        roles = ["hook", "immersion", "inner_turn", "emotional_climax", "aftertaste"]
        ratios = [0.0, 0.2, 0.48, 0.72, 0.92]
    elif mode == "stable_story":
        roles = ["hook", "setup", "turn", "climax", "ending"]
        ratios = [0.0, 0.22, 0.5, 0.76, 0.92]
    else:
        roles = ["hook", "turn_1", "turn_2", "climax", "payoff"]
        ratios = [0.0, 0.25, 0.5, 0.75, 0.92]

    return [
        NarrativeSlot(
            id=f"slot_{index + 1}",
            role=role,
            time=round(target * ratio, 2),
            route_policy=_route_policy_for_role(role, mode),
        )
        for index, (role, ratio) in enumerate(zip(roles, ratios, strict=True))
    ]


def build_storyboard_sequence_slots(
    *,
    rhythm_profile: dict[str, Any] | None,
    attention_beats: list[dict[str, Any]] | None,
    target_duration_sec: int,
) -> list[NarrativeSlot]:
    key_slots = build_narrative_slots(
        rhythm_profile=rhythm_profile,
        attention_beats=attention_beats,
        target_duration_sec=target_duration_sec,
    )
    if len(key_slots) <= 1:
        return key_slots

    mode = str((rhythm_profile or {}).get("mode", "")).strip()
    expanded: list[NarrativeSlot] = []
    for index, slot in enumerate(key_slots):
        expanded.append(slot)
        next_slot = key_slots[index + 1] if index + 1 < len(key_slots) else None
        filler_role = _filler_role_between(slot.role, next_slot.role if next_slot else "", mode)
        if not next_slot or not filler_role:
            continue
        midpoint = round((slot.time + next_slot.time) / 2, 2)
        expanded.append(
            NarrativeSlot(
                id=f"{slot.id}_to_{next_slot.id}",
                role=filler_role,
                time=midpoint,
                route_policy=_route_policy_for_role(filler_role, mode),
            )
        )
    return expanded


def build_route_anchors_for_slots(slots: list[NarrativeSlot], route_count: int) -> dict[str, int]:
    if route_count <= 0:
        return {}

    route_slots = [slot for slot in slots if slot.route_policy != "preview"]
    if not route_slots:
        return {}

    if len(route_slots) == 1:
        return {route_slots[0].id: 0}

    last_route_index = route_count - 1
    last_slot_index = len(route_slots) - 1
    anchors: dict[str, int] = {}
    for index, slot in enumerate(route_slots):
        if slot.route_policy == "flex_tail":
            anchor = last_route_index
        else:
            anchor = round(index / last_slot_index * last_route_index)
        anchors[slot.id] = min(max(anchor, 0), last_route_index)
    return anchors


def _filler_role_between(current_role: str, next_role: str, mode: str) -> str:
    if mode == "chapter_explainer":
        if current_role == "hook":
            return "chapter_setup"
        if next_role == "proof":
            return "detail"
        if next_role == "summary":
            return "chapter_bridge"
        return "proof"
    if mode == "seed_and_guide":
        if current_role == "hook":
            return "visual_seed"
        if next_role == "info_value":
            return "experience"
        if next_role == "save_cta":
            return "decision_push"
        return "detail"
    if mode == "emotional_vlog":
        if current_role == "hook":
            return "immersion"
        if next_role == "emotional_climax":
            return "emotion_build"
        if next_role == "aftertaste":
            return "afterglow"
        return "inner_turn"
    if current_role == "hook":
        return "setup"
    if current_role in {"turn_1", "turn"}:
        return "develop_1"
    if current_role == "turn_2":
        return "develop_2"
    if next_role in {"payoff", "ending", "summary", "save_cta"}:
        return "climax_build"
    return "supporting"


def _route_policy_for_role(role: str, mode: str) -> str:
    if mode in {"chapter_explainer", "chapter_story", "stable_story"}:
        return "strict"
    if role == "hook":
        return "preview"
    if role in NARRATIVE_PAYOFF_ROLES:
        return "flex_tail"
    return "forward"


def route_index_map_for_assets(
    assets: list[AssetRead],
    route_locations: list[str] | None,
) -> dict[str, int]:
    cleaned_route = [item.strip() for item in (route_locations or []) if item.strip()]
    if cleaned_route:
        return {location: index for index, location in enumerate(cleaned_route)}

    first_seen: dict[str, int] = {}
    for asset in assets:
        location = asset.location.strip()
        if location and location not in first_seen:
            first_seen[location] = len(first_seen)
    return first_seen


def asset_route_index(asset: AssetRead, route_index_map: dict[str, int]) -> int:
    index, _route_location, _match_method, _score = asset_route_match(asset, route_index_map)
    return index


def asset_route_match(
    asset: AssetRead,
    route_index_map: dict[str, int],
) -> tuple[int, str, str, float]:
    location = asset.location.strip()
    if not location:
        return 10**6, "", "empty", 0.0

    if location in route_index_map:
        return route_index_map[location], location, "exact", 1.0

    normalized_location = normalize_route_text(location)
    if not normalized_location:
        return 10**6, "", "empty", 0.0

    best: tuple[tuple[float, int, int], int, str, str, float] | None = None
    for route_location, route_index in route_index_map.items():
        normalized_route = normalize_route_text(route_location)
        if not normalized_route:
            continue

        match_method = ""
        score = 0.0
        occurrence_index = -1
        if normalized_location == normalized_route:
            match_method = "normalized"
            score = 0.98
            occurrence_index = 0
        elif normalized_route in normalized_location or normalized_location in normalized_route:
            match_method = "partial"
            score = 0.9
            occurrence_index = max(normalized_location.find(normalized_route), 0)
        else:
            ratio = SequenceMatcher(None, normalized_location, normalized_route).ratio()
            if ratio >= 0.72:
                match_method = "fuzzy"
                score = ratio
                occurrence_index = 0

        if not match_method:
            continue

        route_specificity = len(normalized_route)
        rank = (score, route_specificity, occurrence_index)
        if best is None or rank > best[0]:
            best = (rank, route_index, route_location, match_method, score)

    if not best:
        return 10**6, "", "unmatched", 0.0
    _rank, route_index, route_location, match_method, score = best
    return route_index, route_location, match_method, round(score, 3)


def normalize_route_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.strip().lower())


def plan_assets_for_narrative_slots(
    assets: list[AssetRead],
    *,
    target_duration_sec: int,
    rhythm_profile: dict[str, Any] | None = None,
    attention_beats: list[dict[str, Any]] | None = None,
    route_locations: list[str] | None = None,
    duration_fill_max_consecutive_route: int = DURATION_FILL_MAX_CONSECUTIVE_ROUTE,
) -> list[AssetRead]:
    return [
        item.asset
        for item in plan_storyboard_asset_sequence(
            assets,
            target_duration_sec=target_duration_sec,
            rhythm_profile=rhythm_profile,
            attention_beats=attention_beats,
            route_locations=route_locations,
            duration_fill_max_consecutive_route=duration_fill_max_consecutive_route,
        )
    ]


def plan_storyboard_asset_sequence(
    assets: list[AssetRead],
    *,
    target_duration_sec: int,
    rhythm_profile: dict[str, Any] | None = None,
    attention_beats: list[dict[str, Any]] | None = None,
    route_locations: list[str] | None = None,
    duration_fill_max_consecutive_route: int = DURATION_FILL_MAX_CONSECUTIVE_ROUTE,
) -> list[PlannedAsset]:
    slots = build_storyboard_sequence_slots(
        rhythm_profile=rhythm_profile,
        attention_beats=attention_beats,
        target_duration_sec=target_duration_sec,
    )
    if not slots:
        return [
            PlannedAsset(
                asset=asset,
                attention_role=infer_attention_role(
                    asset.functionTags[0] if asset.functionTags else "supporting"
                ),
                selection_trace=build_selection_trace(
                    asset=asset,
                    slot=None,
                    candidates=assets,
                    route_index_map=route_index_map_for_assets(assets, route_locations),
                    current_route_index=0,
                    score=0,
                    source="基础排序",
                ),
            )
            for asset in order_assets_for_storyboard(assets)
        ]

    route_map = route_index_map_for_assets(assets, route_locations)
    route_anchor_by_slot_id = build_route_anchors_for_slots(slots, len(route_map))
    initial_assets = order_assets_for_storyboard(assets)
    states = [
        StoryboardPlanningState(
            selected_assets=[],
            unused_assets=initial_assets,
            current_route_index=0,
            score=0,
        )
    ]

    for slot in slots:
        next_states: list[StoryboardPlanningState] = []
        target_route_index = route_anchor_by_slot_id.get(slot.id)
        for state in states:
            if not state.unused_assets:
                next_states.append(state)
                continue
            candidates = candidate_assets_for_slot(
                state.unused_assets,
                slot,
                route_map,
                current_route_index=state.current_route_index,
                target_route_index=target_route_index,
            )
            if not candidates:
                next_states.append(state)
                continue

            ranked_candidates = rank_candidates_for_slot(
                candidates,
                slot,
                route_map,
                current_route_index=state.current_route_index,
                target_route_index=target_route_index,
            )
            for candidate, candidate_score in ranked_candidates[:STORYBOARD_SLOT_CANDIDATE_LIMIT]:
                candidate_route_index = asset_route_index(candidate, route_map)
                next_route_index = state.current_route_index
                if slot.route_policy != "preview" and candidate_route_index < 10**6:
                    next_route_index = max(state.current_route_index, candidate_route_index)
                next_states.append(
                    StoryboardPlanningState(
                        selected_assets=[
                            *state.selected_assets,
                            PlannedAsset(
                                asset=candidate,
                                attention_role=slot.role,
                                selection_trace=build_selection_trace(
                                    asset=candidate,
                                    slot=slot,
                                    candidates=candidates,
                                    route_index_map=route_map,
                                    current_route_index=state.current_route_index,
                                    target_route_index=target_route_index,
                                    score=candidate_score,
                                    source="Beam Search 规则生成",
                                ),
                            ),
                        ],
                        unused_assets=[
                            asset for asset in state.unused_assets if asset.assetId != candidate.assetId
                        ],
                        current_route_index=next_route_index,
                        score=state.score + candidate_score,
                    )
                )
        if not next_states:
            break
        states = sorted(
            next_states,
            key=lambda state: (
                state.score,
                len(state.selected_assets),
                state.current_route_index,
            ),
            reverse=True,
        )[:STORYBOARD_BEAM_WIDTH]

    best_state = max(
        states,
        key=lambda state: (
            state.score,
            len(state.selected_assets),
            state.current_route_index,
        ),
    )
    selected_assets = best_state.selected_assets
    current_route_index = best_state.current_route_index

    selected_ids = {item.asset.assetId for item in selected_assets}
    ordered_unused_assets = [
        asset
        for asset in order_assets_for_storyboard(assets)
        if asset.assetId not in selected_ids
    ]
    remaining_assets = [
        asset
        for asset in ordered_unused_assets
        if asset_route_index(asset, route_map) >= current_route_index
    ]
    remaining_assets.sort(
        key=lambda asset: (
            asset_route_index(asset, route_map),
            asset_storyboard_chapter_priority(asset),
            asset_storyboard_modifier_priority(asset),
            asset_sequence_number(asset.assetId),
        )
    )
    filler_role = _default_remaining_role(str((rhythm_profile or {}).get("mode", "")).strip())
    planned_assets = selected_assets + [
        PlannedAsset(
            asset=asset,
            attention_role=filler_role,
            selection_trace=build_selection_trace(
                asset=asset,
                slot=None,
                candidates=remaining_assets,
                route_index_map=route_map,
                current_route_index=current_route_index,
                score=0,
                source="剩余素材补齐",
            ),
        )
        for asset in remaining_assets
    ]

    fill_unused_assets_by_duration(
        planned_assets=planned_assets,
        ordered_unused_assets=ordered_unused_assets,
        target_duration_sec=target_duration_sec,
        filler_role=filler_role,
        route_index_map=route_map,
        current_route_index=current_route_index,
        max_consecutive_route_count=normalize_duration_fill_max_consecutive_route(
            duration_fill_max_consecutive_route
        ),
    )
    remaining_shortfall = float(target_duration_sec) - sum(
        estimated_planned_duration(item) for item in planned_assets
    )
    return planned_assets


def normalize_duration_fill_max_consecutive_route(value: int | None) -> int:
    if value is None:
        return DURATION_FILL_MAX_CONSECUTIVE_ROUTE
    return min(max(int(value), 1), 8)


def fill_unused_assets_by_duration(
    *,
    planned_assets: list[PlannedAsset],
    ordered_unused_assets: list[AssetRead],
    target_duration_sec: int,
    filler_role: str,
    route_index_map: dict[str, int],
    current_route_index: int,
    max_consecutive_route_count: int,
) -> None:
    planned_asset_ids = {item.asset.assetId for item in planned_assets}
    estimated_duration = sum(estimated_planned_duration(item) for item in planned_assets)
    if estimated_duration >= float(target_duration_sec):
        return

    duration_fill_assets = [
        asset for asset in ordered_unused_assets if asset.assetId not in planned_asset_ids
    ]
    duration_fill_assets.sort(
        key=lambda asset: (
            asset_storyboard_chapter_priority(asset),
            asset_storyboard_modifier_priority(asset),
            asset_route_index(asset, route_index_map),
            asset_sequence_number(asset.assetId),
        )
    )
    for asset in duration_fill_assets:
        if estimated_duration >= float(target_duration_sec):
            break
        planned_asset = PlannedAsset(
            asset=asset,
            attention_role=filler_role,
            selection_trace=build_selection_trace(
                asset=asset,
                slot=None,
                candidates=duration_fill_assets,
                route_index_map=route_index_map,
                current_route_index=current_route_index,
                score=0,
                source="时长不足，未使用素材补齐",
            ),
        )
        inserted = insert_duration_fill_planned_asset(
            planned_assets,
            planned_asset,
            route_index_map,
            max_consecutive_route_count=max_consecutive_route_count,
        )
        if inserted:
            planned_asset_ids.add(asset.assetId)
            estimated_duration += estimated_planned_duration(planned_asset)


def insert_duration_fill_planned_asset(
    planned_assets: list[PlannedAsset],
    planned_asset: PlannedAsset,
    route_index_map: dict[str, int],
    *,
    max_consecutive_route_count: int = DURATION_FILL_MAX_CONSECUTIVE_ROUTE,
) -> bool:
    fill_route_index = asset_route_index(planned_asset.asset, route_index_map)
    if fill_route_index >= 10**6:
        planned_assets.append(planned_asset)
        return True

    insert_at = len(planned_assets)
    for index, existing in enumerate(planned_assets):
        if index == 0 and existing.attention_role == "hook":
            continue
        existing_route_index = asset_route_index(existing.asset, route_index_map)
        if existing_route_index >= 10**6:
            continue
        if fill_route_index < existing_route_index:
            insert_at = index
            break
    candidate_sequence = [
        *planned_assets[:insert_at],
        planned_asset,
        *planned_assets[insert_at:],
    ]
    if max_route_run_count(candidate_sequence, route_index_map) > max_consecutive_route_count:
        return False
    planned_assets.insert(insert_at, planned_asset)
    return True


def max_route_run_count(
    planned_assets: list[PlannedAsset],
    route_index_map: dict[str, int],
) -> int:
    max_count = 0
    last_route_index: int | None = None
    current_count = 0
    for index, planned_asset in enumerate(planned_assets):
        route_index = asset_route_index(planned_asset.asset, route_index_map)
        if index == 0 and planned_asset.attention_role == "hook":
            last_route_index = None
            current_count = 0
            continue
        if route_index >= 10**6:
            last_route_index = None
            current_count = 0
            continue
        if route_index == last_route_index:
            current_count += 1
        else:
            last_route_index = route_index
            current_count = 1
        max_count = max(max_count, current_count)
    return max_count


def build_selection_trace(
    *,
    asset: AssetRead,
    slot: NarrativeSlot | None,
    candidates: list[AssetRead],
    route_index_map: dict[str, int],
    current_route_index: int,
    target_route_index: int | None = None,
    score: float,
    source: str,
) -> str:
    route_index, matched_route, match_method, match_score = asset_route_match(asset, route_index_map)
    route_text = (
        f"{asset.location} / 匹配 {matched_route} / 路线序号 {route_index + 1} / {route_match_method_label(match_method)} {match_score}"
        if route_index < 10**6
        else f"{asset.location or '未填写地点'} / 未匹配项目路线"
    )
    slot_text = (
        f"{slot.id} · {slot.role} · {_route_policy_label(slot.route_policy)}"
        if slot
        else "无叙事槽位 · 按剩余顺序补齐"
    )
    pool_text = _candidate_pool_label(
        slot=slot,
        route_index=route_index,
        candidate_count=len(candidates),
        current_route_index=current_route_index,
        target_route_index=target_route_index,
    )
    reason_text = _asset_reason_label(asset)
    score_text = f"，评分 {round(score, 2)}" if score else ""
    return (
        f"{source}：槽位={slot_text}；候选池={pool_text}；"
        f"选中={asset.assetId}（{route_text}）；依据={reason_text}{score_text}"
    )


def _route_policy_label(route_policy: str) -> str:
    return {
        "preview": "开头预告可跨路线",
        "strict": "严格按路线",
        "forward": "只向后推进",
        "flex_tail": "收尾可用当前位置或后段",
    }.get(route_policy, route_policy or "未设置")


def route_match_method_label(match_method: str) -> str:
    return {
        "exact": "精确匹配",
        "normalized": "规范化匹配",
        "partial": "部分匹配",
        "fuzzy": "模糊匹配",
    }.get(match_method, "未匹配")


def _candidate_pool_label(
    *,
    slot: NarrativeSlot | None,
    route_index: int,
    candidate_count: int,
    current_route_index: int,
    target_route_index: int | None = None,
) -> str:
    anchor_text = (
        f"锚点路线节点 {target_route_index + 1}，" if target_route_index is not None else ""
    )
    if slot and slot.route_policy == "preview":
        return f"全片强画面候选，共 {candidate_count} 条"
    if route_index >= 10**6:
        return f"路线未匹配候选，共 {candidate_count} 条"
    if slot and slot.route_policy in {"strict", "forward"}:
        return f"{anchor_text}实际候选路线节点 {route_index + 1}，共 {candidate_count} 条"
    if slot and slot.route_policy == "flex_tail":
        return f"{anchor_text}当前位置 {current_route_index + 1} 到后段候选，共 {candidate_count} 条"
    return f"剩余可用素材，共 {candidate_count} 条"


def _asset_reason_label(asset: AssetRead) -> str:
    parts = [
        f"景别={asset.shotType or '未填'}",
        f"信息量={asset.informationDensity or '未填'}",
        f"视觉强度={infer_visual_strength(asset)}",
    ]
    if asset.functionTags:
        parts.append(f"功能={','.join(asset.functionTags[:3])}")
    if asset.visualTags:
        parts.append(f"视觉={','.join(asset.visualTags[:3])}")
    return " / ".join(parts)


def candidate_assets_for_slot(
    assets: list[AssetRead],
    slot: NarrativeSlot,
    route_index_map: dict[str, int],
    *,
    current_route_index: int,
    target_route_index: int | None = None,
) -> list[AssetRead]:
    if slot.route_policy == "preview":
        return assets

    known_assets = [
        asset for asset in assets if asset_route_index(asset, route_index_map) < 10**6
    ]
    if not known_assets:
        return assets

    forward_assets = [
        asset
        for asset in known_assets
        if asset_route_index(asset, route_index_map) >= current_route_index
    ]
    if not forward_assets:
        return []

    forward_route_indexes = sorted({asset_route_index(asset, route_index_map) for asset in forward_assets})
    target_index = max(current_route_index, target_route_index or current_route_index)

    if slot.route_policy in {"strict", "forward"}:
        nearest_route_index = min(
            forward_route_indexes,
            key=lambda route_index: (abs(route_index - target_index), route_index),
        )
        return [
            asset
            for asset in forward_assets
            if asset_route_index(asset, route_index_map) == nearest_route_index
        ]

    if slot.route_policy == "flex_tail":
        tail_route_assets = [
            asset
            for asset in forward_assets
            if asset_route_index(asset, route_index_map) >= target_index
        ]
        if tail_route_assets:
            return tail_route_assets
        target_route_assets = [
            asset
            for asset in forward_assets
            if asset_route_index(asset, route_index_map) == target_index
        ]
        if target_route_assets:
            return target_route_assets
        current_route_assets = [
            asset
            for asset in forward_assets
            if asset_route_index(asset, route_index_map) == current_route_index
        ]
        return current_route_assets or forward_assets

    return forward_assets


def rank_candidates_for_slot(
    candidates: list[AssetRead],
    slot: NarrativeSlot,
    route_index_map: dict[str, int],
    *,
    current_route_index: int,
    target_route_index: int | None = None,
) -> list[tuple[AssetRead, float]]:
    scored = [
        (
            asset,
            score_asset_for_planning(
                asset,
                slot,
                route_index_map,
                current_route_index=current_route_index,
                target_route_index=target_route_index,
            ),
        )
        for asset in candidates
    ]
    return sorted(
        scored,
        key=lambda item: (
            item[1],
            -asset_route_index(item[0], route_index_map),
            -asset_sequence_number(item[0].assetId),
        ),
        reverse=True,
    )


def _default_remaining_role(mode: str) -> str:
    if mode == "chapter_explainer":
        return "detail"
    if mode == "seed_and_guide":
        return "experience"
    if mode == "emotional_vlog":
        return "immersion"
    return "supporting"


def score_asset_for_narrative_slot(
    asset: AssetRead,
    slot: NarrativeSlot,
    route_index_map: dict[str, int],
    *,
    current_route_index: int,
) -> float:
    score = 0.0
    role = slot.role
    function_tags = set(asset.functionTags)
    tag_text = " ".join([*asset.functionTags, *asset.emotionTags, *asset.visualTags, asset.scene])
    route_index = asset_route_index(asset, route_index_map)

    score += _base_asset_quality_score(asset)

    if role in NARRATIVE_HIGH_ATTENTION_ROLES:
        if function_tags & {"opening_hook", "rhythm_hit", "main_climax", "slow_climax"}:
            score += 6
        if infer_visual_strength(asset) == "strong":
            score += 5
        if any(word in tag_text for word in NARRATIVE_STRONG_WORDS):
            score += 2
    elif role in NARRATIVE_SETUP_ROLES:
        if asset.shotType in {"wide", "aerial", "medium", "大景", "航拍", "中景"}:
            score += 5
        if function_tags & {"supporting", "transition_buffer", "opening_hook"}:
            score += 2
        if "rhythm_hit" in function_tags:
            score -= 8
    elif role in NARRATIVE_INFO_ROLES:
        if asset.informationDensity == "high":
            score += 5
        if function_tags & {"supporting", "transition_buffer"}:
            score += 2
    elif role in NARRATIVE_PAYOFF_ROLES:
        if function_tags & {"ending", "main_climax", "slow_climax"}:
            score += 6
        if infer_visual_strength(asset) != "weak":
            score += 2
    else:
        if function_tags & {"supporting", "transition_buffer"}:
            score += 2

    if slot.route_policy == "strict" and route_index < current_route_index:
        score -= 100
    elif slot.route_policy == "forward" and route_index < current_route_index:
        score -= 30
    elif slot.route_policy == "preview":
        if infer_visual_strength(asset) == "strong":
            score += 3
    elif slot.route_policy == "flex_tail":
        if route_index >= current_route_index:
            score += 1

    if route_index < 10**6:
        score -= max(route_index - current_route_index, 0) * 0.2

    return score


def score_asset_for_planning(
    asset: AssetRead,
    slot: NarrativeSlot,
    route_index_map: dict[str, int],
    *,
    current_route_index: int,
    target_route_index: int | None = None,
) -> float:
    score = score_asset_for_narrative_slot(
        asset,
        slot,
        route_index_map,
        current_route_index=current_route_index,
    )
    route_index = asset_route_index(asset, route_index_map)
    if route_index >= 10**6 or slot.route_policy == "preview":
        if (
            slot.route_policy == "preview"
            and route_index == current_route_index
            and "rhythm_hit" in asset.functionTags
        ):
            score -= 12
        if slot.route_policy == "preview" and "ending" in asset.functionTags:
            score -= 10
        if (
            slot.route_policy == "preview"
            and route_index > current_route_index
            and "opening_hook" in asset.functionTags
        ):
            score += min(route_index, 3) * 2
        return score

    if target_route_index is not None:
        score -= abs(route_index - target_route_index) * 0.7
        if route_index == target_route_index:
            score += 1.2
    if route_index == current_route_index:
        score += 0.2
    return score


def _base_asset_quality_score(asset: AssetRead) -> float:
    score = 0.0
    if infer_visual_strength(asset) == "strong":
        score += 3
    elif infer_visual_strength(asset) == "medium":
        score += 1.5
    if asset.informationDensity == "high":
        score += 1
    if asset.mediaType == "video":
        score += 0.5
    return score


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
        resolved = filter_beats_for_capcut_mode(
            normalize_beat_times(raw_source, float(target_duration_sec)),
            beat_mode,
            float(target_duration_sec),
            coarse_beats=rhythm.coarseBeatPoints or None,
        )
    else:
        resolved = rhythm.beatPoints

    beat_offset = float(rhythm.beatCalibration.get("beatOffsetSec", 0) or 0)
    beat_scale = float(rhythm.beatCalibration.get("beatScale", 1) or 1)
    return apply_beat_calibration(
        resolved,
        float(target_duration_sec),
        offset_sec=beat_offset,
        scale=beat_scale,
    )


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
    route_locations = parse_route_locations(project.route_text)
    ordered_assets = plan_assets_for_narrative_slots(
        assets,
        target_duration_sec=target_duration_sec,
        rhythm_profile=rhythm.rhythmProfile if rhythm else None,
        attention_beats=rhythm.attentionBeats if rhythm else None,
        route_locations=route_locations,
        duration_fill_max_consecutive_route=getattr(
            project, "duration_fill_max_consecutive_route", DURATION_FILL_MAX_CONSECUTIVE_ROUTE
        ),
    )
    allow_asset_reuse = bool(getattr(project, "allow_asset_reuse", False))
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理主题「{theme.title}」与 {len(ordered_assets)} 条素材…",
        progress=10,
    )
    reuse_instruction = (
        "You may include the same assetId in multiple segments when pacing or narrative "
        "benefits from reuse. Prefer a distinct structural purpose for each reuse instance."
        if allow_asset_reuse
        else "Include every asset exactly once."
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are a travel short-form video storyboard director. "
            "Return JSON only with a segments array. "
            "This is the STRUCTURE pass, not the copywriting pass. "
            "Each segment must include assetId and shotDescription; function and rhythm are optional. "
            "Do not generate subtitle or release copy. Those are produced by a later copywriting pass. "
            "Use ruleOrderedAssetIds as the baseline order, but you may reorder segments "
            f"when narrative flow improves. {reuse_instruction} "
            "The segments array order is your preferred timeline order. "
            "Do not invent assetId values outside ruleOrderedAssetIds. "
            "Use routeLocations as the travel axis. Match asset.location to routeLocations "
            "with exact, partial, or fuzzy semantic matching, but avoid jumping backward "
            "unless a hook/preview explicitly benefits from a later highlight."
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "destination": project.destination,
                    "platform": project.platform,
                    "routeText": project.route_text,
                    "routeLocations": route_locations,
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
            plan = _align_storyboard_plan_to_assets(ordered_assets, normalized)
    else:
        plan = None
    if plan is None:
        emit_progress(on_progress, "fallback", "LLM 分镜无效，准备回退到规则生成…", progress=88)
    meta = build_llm_meta(result, used_fallback=plan is None).as_dict()
    meta["promptMode"] = "structure_only"
    meta["assetReuseEnabled"] = "true" if allow_asset_reuse else "false"
    if allow_asset_reuse and plan is not None:
        meta["llmMessage"] = f"{meta.get('llmMessage', '')} 项目已启用镜头复用。".strip()
    return plan, meta


def build_llm_partial_storyboard_plan(
    *,
    project: ProjectEntity,
    theme: NarrativeThemeRead,
    assets: list[AssetRead],
    selected_segments: list[StoryboardSegmentRead],
    previous_segment: StoryboardSegmentRead | None,
    next_segment: StoryboardSegmentRead | None,
    rhythm: RhythmPlanRead | None,
    instruction: str = "",
    on_progress: ProgressReporter | None = None,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Regenerate a fixed storyboard interval without changing its narrative skeleton."""
    slot_count = len(selected_segments)
    allowed_asset_ids = {asset.assetId for asset in assets}
    allow_asset_reuse = bool(getattr(project, "allow_asset_reuse", False))
    emit_progress(
        on_progress,
        "preparing",
        f"正在整理连续 {slot_count} 个镜头的局部上下文…",
        progress=12,
    )
    result = llm_suggestion_service.generate_json_result(
        system_prompt=(
            "You are revising one CONTIGUOUS interval of a travel-video storyboard. "
            "Return JSON only with a segments array containing exactly slotCount items. "
            "Each item must contain assetId, shotDescription, rhythm and subtitle. "
            "Keep the supplied slot roles and timeline boundaries unchanged; only choose assets "
            "and rewrite shot copy for each slot. Preserve route continuity between previousContext, "
            "selectedSlots and nextContext. Do not invent asset IDs. "
            + (
                "Asset reuse is allowed when it has a distinct purpose."
                if allow_asset_reuse
                else "Use each candidate asset at most once."
            )
        ),
        user_prompt=json.dumps(
            {
                "project": {
                    "name": project.name,
                    "platform": project.platform,
                    "routeText": project.route_text,
                },
                "theme": _theme_context_for_llm(theme),
                "rhythm": _rhythm_context_for_llm(
                    rhythm,
                    selected_segments[0].beatMode if selected_segments else "none",
                ),
                "slotCount": slot_count,
                "instruction": instruction.strip(),
                "previousContext": (
                    {
                        "assetId": previous_segment.assetId,
                        "description": previous_segment.shotDescription,
                        "role": previous_segment.attentionRole,
                    }
                    if previous_segment
                    else None
                ),
                "selectedSlots": [
                    {
                        "startTime": segment.startTime,
                        "endTime": segment.endTime,
                        "role": segment.attentionRole,
                        "function": segment.function,
                        "currentAssetId": segment.assetId,
                    }
                    for segment in selected_segments
                ],
                "nextContext": (
                    {
                        "assetId": next_segment.assetId,
                        "description": next_segment.shotDescription,
                        "role": next_segment.attentionRole,
                    }
                    if next_segment
                    else None
                ),
                "candidateAssets": [
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
        temperature=0.45,
        max_tokens=min(1400 + slot_count * 180, 3200),
        on_progress=on_progress,
    )
    emit_progress(on_progress, "building", "正在校验局部分镜与路线连续性…", progress=86)
    normalized = _normalize_storyboard_plan(result, assets) or []
    plan: list[dict[str, str]] = []
    used_asset_ids: set[str] = set()
    for item in normalized:
        asset_id = item["assetId"]
        if asset_id not in allowed_asset_ids:
            continue
        if not allow_asset_reuse and asset_id in used_asset_ids:
            continue
        plan.append(item)
        used_asset_ids.add(asset_id)
        if len(plan) == slot_count:
            break

    fallback_asset_ids = [segment.assetId for segment in selected_segments] + [
        asset.assetId for asset in assets
    ]
    for asset_id in fallback_asset_ids:
        if len(plan) == slot_count:
            break
        if asset_id not in allowed_asset_ids:
            continue
        if not allow_asset_reuse and asset_id in used_asset_ids:
            continue
        plan.append(
            {
                "assetId": asset_id,
                "shotDescription": "",
                "function": "",
                "rhythm": "",
                "subtitle": "",
            }
        )
        used_asset_ids.add(asset_id)

    if len(plan) != slot_count:
        raise ValueError("可用素材不足，无法在不破坏时间线的前提下重跑该区间。")
    used_fallback = not result.ok or len(normalized) < slot_count
    meta = build_llm_meta(result, used_fallback=used_fallback).as_dict()
    meta["promptMode"] = "partial_storyboard"
    meta["rangeSegmentCount"] = str(slot_count)
    return plan, meta


def apply_partial_storyboard_plan(
    *,
    selected_segments: list[StoryboardSegmentRead],
    assets: list[AssetRead],
    plan: list[dict[str, str]],
) -> list[StoryboardSegmentWrite]:
    """Apply an LLM plan while preserving fixed IDs, timing, beats and narrative slots."""
    asset_by_id = {asset.assetId: asset for asset in assets}
    updated: list[StoryboardSegmentWrite] = []
    for segment, item in zip(selected_segments, plan, strict=True):
        asset = asset_by_id[item["assetId"]]
        visual_strength = infer_visual_strength(asset)
        subtitle = item.get("subtitle", "").strip() or subtitle_from_asset(asset)
        updated.append(
            segment_read_to_write(segment).model_copy(
                update={
                    "assetId": asset.assetId,
                    "shotDescription": item.get("shotDescription", "").strip()
                    or f"{asset.location} - {asset.scene}",
                    "rhythm": item.get("rhythm", "").strip()
                    or rhythm_label(asset.informationDensity),
                    "subtitle": subtitle,
                    "visualStrength": visual_strength,
                    "motionPolicy": infer_motion_policy(asset, visual_strength),
                    "selectionTrace": (
                        f"局部重跑：保留 {segment.startTime}s-{segment.endTime}s、"
                        f"{segment.attentionRole or segment.function} 叙事槽位，改选素材 {asset.assetId}。"
                    ),
                    "voiceoverText": subtitle if segment.voiceoverText.strip() else "",
                }
            )
        )
    return updated


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
    attention_beats: list[dict[str, Any]] | None = None,
    attention_role_override: str = "",
    selection_trace: str = "",
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

    attention_role = attention_role_override.strip() or infer_attention_role_from_timing(
        attention_beats,
        current_time,
        end_time,
        infer_attention_role(function_name),
    )
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
        subtitlePolicy=infer_subtitle_policy(attention_role),
        selectionTrace=selection_trace,
        voiceoverText=subtitle,
        voiceoverRole="",
        voiceoverTiming="follow_segment",
    )
    return segment, round(end_time, 2), beat_index


def reuse_attention_role(mode: str, original_role: str = "") -> str:
    if mode == "chapter_explainer":
        return "detail"
    if mode == "seed_and_guide":
        return "experience"
    if mode == "emotional_vlog":
        return "afterglow"
    if mode == "chapter_story":
        return "proof"
    if mode == "stable_story":
        return "supporting"
    if original_role in {"payoff", "ending", "summary", "save_cta", "aftertaste"}:
        return "afterglow"
    return "supporting"


def estimated_planned_duration(item: PlannedAsset) -> float:
    return max(item.asset.suggestedDurationSec, 0.5)


def is_low_risk_reuse_item(item: PlannedAsset) -> bool:
    protected_roles = {
        "hook",
        "turn",
        "turn_1",
        "turn_2",
        "climax",
        "emotional_climax",
        "highlight",
        "payoff",
        "ending",
        "summary",
        "save_cta",
    }
    protected_tags = {"opening_hook", "rhythm_hit", "main_climax", "slow_climax", "ending"}
    return item.attention_role not in protected_roles and not (set(item.asset.functionTags) & protected_tags)


def build_reuse_bridge_sequence(
    planned_assets: list[PlannedAsset],
    *,
    target_duration_sec: int,
    mode: str,
) -> list[PlannedAsset]:
    if len(planned_assets) <= 1:
        return planned_assets

    base_duration = sum(estimated_planned_duration(item) for item in planned_assets)
    target_duration = float(target_duration_sec)
    if target_duration - base_duration <= 0:
        return planned_assets

    reusable_pool = [item for item in planned_assets if is_low_risk_reuse_item(item)]
    if not reusable_pool:
        reusable_pool = [
            item
            for item in planned_assets
            if item.attention_role not in {"hook", "payoff", "ending", "summary", "save_cta"}
        ]
    if not reusable_pool:
        reusable_pool = planned_assets

    anchor_durations = [estimated_planned_duration(item) for item in planned_assets]
    remaining_anchor_durations: list[float] = []
    remaining_duration = sum(anchor_durations)
    for duration in anchor_durations:
        remaining_duration -= duration
        remaining_anchor_durations.append(remaining_duration)

    used_duration = 0.0
    bridge_cursor = 0
    bridge_counts: dict[str, int] = {}
    expanded: list[PlannedAsset] = []
    allow_adjacent_fallback = len(planned_assets) <= 2

    for index, item in enumerate(planned_assets):
        expanded.append(item)
        used_duration += anchor_durations[index]

        if index >= len(planned_assets) - 1:
            continue

        fillers_added = 0
        while fillers_added < REUSE_MAX_BRIDGE_PER_GAP:
            if used_duration + remaining_anchor_durations[index] >= target_duration:
                break

            source: PlannedAsset | None = None
            adjacent_asset_ids = {item.asset.assetId, planned_assets[index + 1].asset.assetId}
            for prefer_non_adjacent in (True, False):
                if not prefer_non_adjacent and not allow_adjacent_fallback:
                    break
                for offset in range(len(reusable_pool)):
                    candidate = reusable_pool[(bridge_cursor + offset) % len(reusable_pool)]
                    asset_id = candidate.asset.assetId
                    if prefer_non_adjacent and asset_id in adjacent_asset_ids:
                        continue
                    if bridge_counts.get(asset_id, 0) < REUSE_MAX_BRIDGE_REPEAT_PER_ASSET:
                        source = candidate
                        bridge_cursor += offset + 1
                        break
                if source is not None:
                    break

            if source is None:
                break

            source_duration = estimated_planned_duration(source)
            if used_duration + source_duration + remaining_anchor_durations[index] > target_duration:
                break

            pass_index = bridge_counts.get(source.asset.assetId, 0)
            expanded.append(
                PlannedAsset(
                    asset=source.asset,
                    attention_role=reuse_attention_role(mode, source.attention_role),
                    selection_trace=reuse_selection_trace(source.selection_trace, pass_index),
                )
            )
            bridge_counts[source.asset.assetId] = pass_index + 1
            used_duration += source_duration
            fillers_added += 1

    return expanded


def reuse_selection_trace(original_trace: str, pass_index: int) -> str:
    prefix = (
        f"[reuse-bridge] 素材复用桥段：第 {pass_index + 1} 次复用，"
        "仅复用素材，不重启主叙事骨架。"
    )
    return f"{prefix} 原选择依据：{original_trace}" if original_trace else prefix


def generate_storyboard_segments(
    assets: list[AssetRead],
    theme_id: str,
    target_duration_sec: int,
    beat_mode: str,
    beat_points: list[float],
    allow_asset_reuse: bool = False,
    attention_beats: list[dict[str, Any]] | None = None,
    rhythm_profile: dict[str, Any] | None = None,
    route_locations: list[str] | None = None,
    duration_fill_max_consecutive_route: int = DURATION_FILL_MAX_CONSECUTIVE_ROUTE,
) -> list[StoryboardSegmentWrite]:
    if not assets:
        return []

    planned_assets = plan_storyboard_asset_sequence(
        assets,
        target_duration_sec=target_duration_sec,
        rhythm_profile=rhythm_profile,
        attention_beats=attention_beats,
        route_locations=route_locations,
        duration_fill_max_consecutive_route=duration_fill_max_consecutive_route,
    )
    mode = str((rhythm_profile or {}).get("mode", "")).strip()
    if allow_asset_reuse:
        planned_assets = build_reuse_bridge_sequence(
            planned_assets,
            target_duration_sec=target_duration_sec,
            mode=mode,
        )
    segments: list[StoryboardSegmentWrite] = []
    beat_index = 0
    current_time = 0.0
    safe_beats = beat_points if len(beat_points) >= 2 and beat_mode != "none" else []

    for planned_asset in planned_assets:
        if current_time >= float(target_duration_sec):
            break
        segment, current_time, beat_index = _build_segment_write(
            asset=planned_asset.asset,
            attention_beats=attention_beats,
            attention_role_override=planned_asset.attention_role,
            selection_trace=planned_asset.selection_trace,
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
    attention_beats: list[dict[str, Any]] | None = None,
    rhythm_profile: dict[str, Any] | None = None,
    route_locations: list[str] | None = None,
) -> list[StoryboardSegmentWrite]:
    asset_map = {asset.assetId: asset for asset in assets}
    planned_assets: list[tuple[AssetRead, dict[str, str] | None]] = []
    rule_planned_assets = plan_storyboard_asset_sequence(
        assets,
        target_duration_sec=target_duration_sec,
        rhythm_profile=rhythm_profile,
        attention_beats=attention_beats,
        route_locations=route_locations,
    )
    planned_role_by_asset_id = {
        item.asset.assetId: item.attention_role for item in rule_planned_assets
    }
    planned_trace_by_asset_id = {
        item.asset.assetId: item.selection_trace for item in rule_planned_assets
    }
    rule_ordered_assets = [item.asset for item in rule_planned_assets]

    if allow_asset_reuse:
        for item in llm_plan:
            asset_id = str(item.get("assetId", "")).strip()
            asset = asset_map.get(asset_id)
            if asset:
                planned_assets.append((asset, item))
        seen_asset_ids = {asset.assetId for asset, _ in planned_assets}
        for asset in rule_ordered_assets:
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

        for asset in rule_ordered_assets:
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
            attention_beats=attention_beats,
            attention_role_override=planned_role_by_asset_id.get(asset.assetId, ""),
            selection_trace=planned_trace_by_asset_id.get(asset.assetId, ""),
            plan_item=plan_item,
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
        subtitlePolicy=segment.subtitlePolicy,
        selectionTrace=segment.selectionTrace,
        voiceoverText=segment.voiceoverText,
        voiceoverRole=segment.voiceoverRole,
        voiceoverTiming=segment.voiceoverTiming,
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

    segment_assets: list[AssetRead] = []
    for segment in segments:
        asset = asset_map.get(segment.assetId)
        if not asset or not asset.location:
            return [f"镜头 {segment.id} 缺少地点信息，无法校验地点连续性"]
        segment_assets.append(asset)

    issues: list[str] = []
    if route_locations:
        route_index_map = route_index_map_for_assets(list(asset_map.values()), route_locations)
        route_indexes = [asset_route_index(asset, route_index_map) for asset in segment_assets]
        if all(index < 10**6 for index in route_indexes):
            last_index = -1
            last_location = ""
            for index, asset in zip(route_indexes, segment_assets, strict=True):
                if index < last_index:
                    issues.append(
                        f"地点顺序回跳：{last_location} → {asset.location}，与路线顺序不一致"
                    )
                last_index = index
                last_location = asset.location
            return dedupe_issue_messages(issues)

    seen_order: dict[str, int] = {}
    last_seen_index = -1
    last_location = ""
    for asset in segment_assets:
        location = asset.location
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

    segment_assets: list[AssetRead] = []
    for segment in segments:
        asset = asset_map.get(segment.assetId)
        if not asset or not asset.location:
            return False
        segment_assets.append(asset)

    if route_locations:
        route_index_map = route_index_map_for_assets(list(asset_map.values()), route_locations)
        route_indexes = [asset_route_index(asset, route_index_map) for asset in segment_assets]
        if all(index < 10**6 for index in route_indexes):
            last_index = -1
            for index in route_indexes:
                if index < last_index:
                    return False
                last_index = index
            return True

    seen_order: dict[str, int] = {}
    last_seen_index = -1
    for asset in segment_assets:
        location = asset.location
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
