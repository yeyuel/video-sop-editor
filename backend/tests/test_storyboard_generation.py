from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, RhythmPlanRead, StoryboardSegmentRead
from app.services.storyboard_generation import (
    _align_storyboard_plan_to_assets,
    _normalize_storyboard_plan,
    _rhythm_context_for_llm,
    _storyboard_max_tokens,
    asset_route_match,
    build_narrative_slots,
    build_route_anchors_for_slots,
    build_storyboard_validation,
    check_beat_alignment,
    generate_storyboard_segments,
    generate_storyboard_segments_from_plan,
    merge_asset_order,
    plan_storyboard_asset_sequence,
    resolve_segment_timing,
    resolve_storyboard_beat_points,
    resolve_validation_beat_points,
)
from app.services.llm.types import LlmCallResult


def _asset(asset_id: str, suggested_duration_sec: float) -> AssetRead:
    return AssetRead(
        assetId=asset_id,
        location="禾木",
        scene="测试镜头",
        relativePath=f"{asset_id}.mp4",
        mediaType="video",
        shotType="wide",
        emotionTags=["静"],
        visualTags=["蓝调"],
        informationDensity="medium",
        suggestedDurationSec=suggested_duration_sec,
        functionTags=["supporting"],
    )


def _route_asset(
    asset_id: str,
    *,
    location: str,
    function_tags: list[str] | None = None,
    visual_tags: list[str] | None = None,
    emotion_tags: list[str] | None = None,
    shot_type: str = "wide",
    information_density: str = "medium",
    suggested_duration_sec: float = 1.0,
) -> AssetRead:
    return AssetRead(
        assetId=asset_id,
        location=location,
        scene=f"{location} scene",
        relativePath=f"{asset_id}.mp4",
        mediaType="video",
        shotType=shot_type,
        emotionTags=emotion_tags or [],
        visualTags=visual_tags or [],
        informationDensity=information_density,
        suggestedDurationSec=suggested_duration_sec,
        functionTags=function_tags or ["supporting"],
    )


def test_resolve_segment_timing_caps_at_suggested_duration_with_sparse_beats() -> None:
    sparse_beats = [0.0, 11.05, 22.1, 33.15, 44.2, 52.0]

    end_time, beat_index, segment_beats = resolve_segment_timing(
        current_time=0.0,
        suggested_duration_sec=1.0,
        target_duration_sec=60,
        beat_points=sparse_beats,
        beat_index=0,
    )

    assert end_time == 1.0
    assert beat_index == 0
    assert segment_beats == [0.0, 1.0]


def test_resolve_segment_timing_snaps_to_beat_within_clip_length() -> None:
    dense_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    end_time, beat_index, _ = resolve_segment_timing(
        current_time=0.0,
        suggested_duration_sec=1.5,
        target_duration_sec=60,
        beat_points=dense_beats,
        beat_index=0,
    )

    assert end_time == 1.5
    assert beat_index == 3


def test_generate_storyboard_segments_respects_asset_duration_with_strong_weak_beats() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
        _asset("KANAS_001", 1.5),
    ]
    sparse_beats = [0.0, 11.05, 22.1, 33.15, 44.2, 52.0]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=60,
        beat_mode="strong_weak",
        beat_points=sparse_beats,
    )

    assert len(segments) == 3
    asset_map = {asset.assetId: asset for asset in assets}
    for segment in segments:
        asset = asset_map[segment.assetId]
        duration = round(segment.endTime - segment.startTime, 2)
        assert duration <= max(asset.suggestedDurationSec, 0.5) + 0.01


def test_generate_storyboard_segments_reads_attention_beats() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.0),
        _asset("KANAS_004", 1.0),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=10,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook", "label": "开头钩子"},
            {"time": 1.0, "role": "turn_1", "label": "第一次反转"},
        ],
    )

    assert [segment.attentionRole for segment in segments] == ["hook", "setup", "turn_1"]
    assert segments[0].transitionPolicy == "hard_cut"
    assert segments[0].subtitlePolicy == "emphasis"
    assert segments[1].subtitlePolicy == "standard"
    assert segments[2].subtitlePolicy == "emphasis"


def test_generate_storyboard_segments_uses_hook_preview_then_route_axis() -> None:
    assets = [
        _route_asset("GENERAL_001", location="General"),
        _route_asset("KANAS_001", location="Kanas"),
        _route_asset("HEMU_001", location="Hemu", function_tags=["ending"]),
        _route_asset(
            "HEMU_999",
            location="Hemu",
            function_tags=["opening_hook"],
            visual_tags=["sunset"],
            shot_type="aerial",
        ),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=5,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "turn_2"},
            {"time": 3.0, "role": "climax"},
            {"time": 4.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General", "Kanas", "Hemu"],
    )

    assert [segment.assetId for segment in segments[:4]] == [
        "HEMU_999",
        "GENERAL_001",
        "KANAS_001",
        "HEMU_001",
    ]
    assert "开头预告可跨路线" in segments[0].selectionTrace
    assert "实际候选路线节点" in segments[1].selectionTrace
    assert "HEMU_999" in segments[0].selectionTrace


def test_generate_storyboard_segments_prefers_rhythm_hit_for_turn_slot() -> None:
    assets = [
        _route_asset(
            "GENERAL_000",
            location="General",
            function_tags=["opening_hook"],
            visual_tags=["sunset"],
            shot_type="wide",
        ),
        _route_asset("GENERAL_001", location="General"),
        _route_asset(
            "GENERAL_002",
            location="General",
            function_tags=["rhythm_hit"],
            visual_tags=["contrast"],
            shot_type="closeup",
        ),
        _route_asset("GENERAL_003", location="General"),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=4,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General"],
    )

    assert segments[0].assetId == "GENERAL_000"
    assert segments[1].attentionRole == "setup"
    assert segments[2].assetId == "GENERAL_002"
    assert segments[2].attentionRole == "turn_1"


def test_generate_storyboard_segments_inserts_development_between_turns() -> None:
    assets = [
        _route_asset("GENERAL_000", location="General", function_tags=["opening_hook"]),
        _route_asset("GENERAL_001", location="General"),
        _route_asset("GENERAL_002", location="General", function_tags=["rhythm_hit"]),
        _route_asset("KANAS_001", location="Kanas"),
        _route_asset("KANAS_002", location="Kanas", function_tags=["rhythm_hit"]),
        _route_asset("HEMU_001", location="Hemu", function_tags=["main_climax"]),
        _route_asset("HEMU_002", location="Hemu", function_tags=["ending"]),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=7,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "turn_2"},
            {"time": 5.0, "role": "climax"},
            {"time": 6.5, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General", "Kanas", "Hemu"],
    )

    roles = [segment.attentionRole for segment in segments]
    assert roles[:7] == [
        "hook",
        "setup",
        "turn_1",
        "develop_1",
        "turn_2",
        "develop_2",
        "climax",
    ]
    assert "turn_1" not in roles[3:4]
    assert "turn_2" not in roles[5:6]


def test_generate_storyboard_segments_does_not_jump_to_later_location_for_turn() -> None:
    assets = [
        _route_asset("GENERAL_000", location="General", function_tags=["opening_hook"]),
        _route_asset("GENERAL_001", location="General"),
        _route_asset("GENERAL_002", location="General"),
        _route_asset(
            "HEMU_999",
            location="Hemu",
            function_tags=["rhythm_hit", "main_climax"],
            visual_tags=["sunset"],
            shot_type="aerial",
        ),
        _route_asset("KANAS_001", location="Kanas"),
        _route_asset("HEMU_001", location="Hemu"),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=4,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "turn_2"},
            {"time": 4.5, "role": "climax"},
            {"time": 5.5, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General", "Kanas", "Hemu"],
    )

    asset_locations = {asset.assetId: asset.location for asset in assets}
    body_locations = [asset_locations[segment.assetId] for segment in segments[1:]]

    assert body_locations[:2] == ["General", "General"]
    route_index = {"General": 0, "Kanas": 1, "Hemu": 2}
    assert [route_index[location] for location in body_locations] == sorted(
        route_index[location] for location in body_locations
    )
    assert all(segment.selectionTrace for segment in segments)


def test_route_anchors_spread_body_slots_over_route_axis() -> None:
    slots = build_narrative_slots(
        rhythm_profile={"mode": "highlight_reel"},
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "turn_2"},
            {"time": 3.0, "role": "climax"},
            {"time": 4.0, "role": "payoff"},
        ],
        target_duration_sec=5,
    )

    anchors = build_route_anchors_for_slots(slots, 3)

    assert [anchors[slot.id] for slot in slots if slot.route_policy != "preview"] == [0, 1, 1, 2]


def test_generate_storyboard_segments_uses_route_anchors_instead_of_exhausting_first_location() -> None:
    assets = [
        _route_asset("HOOK_999", location="Hemu", function_tags=["opening_hook"], shot_type="aerial"),
        _route_asset("GENERAL_001", location="General"),
        _route_asset("GENERAL_002", location="General"),
        _route_asset("GENERAL_003", location="General", function_tags=["rhythm_hit"]),
        _route_asset("KANAS_001", location="Kanas"),
        _route_asset("HEMU_001", location="Hemu", function_tags=["main_climax"]),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=6,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "turn_2"},
            {"time": 3.0, "role": "climax"},
            {"time": 4.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General", "Kanas", "Hemu"],
    )

    route_index_by_asset_id = {
        "GENERAL_001": 0,
        "GENERAL_002": 0,
        "GENERAL_003": 0,
        "KANAS_001": 1,
        "HEMU_001": 2,
        "HOOK_999": 2,
    }
    body_route_indexes = [route_index_by_asset_id[segment.assetId] for segment in segments[1:]]

    assert 1 in body_route_indexes[:3]
    assert body_route_indexes == sorted(body_route_indexes)
    assert any("锚点路线节点" in segment.selectionTrace for segment in segments[1:])


def test_beam_search_keeps_strong_asset_for_later_turn_slot() -> None:
    assets = [
        _route_asset(
            "HEMU_HOOK",
            location="Hemu",
            function_tags=["opening_hook", "main_climax"],
            visual_tags=["sunset"],
            shot_type="aerial",
            information_density="high",
        ),
        _route_asset("GENERAL_SETUP", location="General", function_tags=["supporting"]),
        _route_asset(
            "GENERAL_TURN",
            location="General",
            function_tags=["opening_hook", "rhythm_hit"],
            visual_tags=["contrast"],
            shot_type="aerial",
        ),
        _route_asset("HEMU_END", location="Hemu", function_tags=["ending"]),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=5,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 4.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["General", "Hemu"],
    )

    assert [segment.assetId for segment in segments[:3]] == [
        "HEMU_HOOK",
        "GENERAL_SETUP",
        "GENERAL_TURN",
    ]
    assert "Beam Search" in segments[1].selectionTrace


def test_asset_route_match_supports_partial_and_specific_route_nodes() -> None:
    asset = _route_asset("SCENIC_001", location="神仙居卧龙桥")
    route_map = {"神仙居": 0, "卧龙桥": 1, "南天顶": 2}

    route_index, matched_route, method, score = asset_route_match(asset, route_map)

    assert route_index == 1
    assert matched_route == "卧龙桥"
    assert method == "partial"
    assert score >= 0.9


def test_asset_route_match_supports_fuzzy_location_spellings() -> None:
    asset = _route_asset("HEMU_001", location="Hemu Vllage")
    route_map = {"General": 0, "Kanas": 1, "Hemu Village": 2}

    route_index, matched_route, method, score = asset_route_match(asset, route_map)

    assert route_index == 2
    assert matched_route == "Hemu Village"
    assert method == "fuzzy"
    assert score >= 0.72


def test_generate_storyboard_segments_uses_partial_route_match_for_location_order() -> None:
    assets = [
        _route_asset("HOOK_999", location="南天顶", function_tags=["opening_hook"]),
        _route_asset("A_001", location="神仙居卧龙桥"),
        _route_asset("B_001", location="南天顶观景台"),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=3,
        beat_mode="none",
        beat_points=[],
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["神仙居", "卧龙桥", "南天顶"],
    )

    assert segments[1].assetId == "A_001"
    assert "部分匹配" in segments[1].selectionTrace
    assert "匹配 卧龙桥" in segments[1].selectionTrace


def test_generate_storyboard_segments_from_plan_respects_asset_duration() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
    ]
    sparse_beats = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    llm_plan = [
        {
            "assetId": "HEMU_002",
            "shotDescription": "禾木晨雾",
            "function": "opening_hook",
            "rhythm": "linger",
            "subtitle": "开场",
        },
        {
            "assetId": "GENERAL_003",
            "shotDescription": "将军山跟拍",
            "function": "supporting",
            "rhythm": "balanced",
            "subtitle": "过渡",
        },
    ]

    segments = generate_storyboard_segments_from_plan(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=60,
        beat_mode="strong_weak",
        beat_points=sparse_beats,
        llm_plan=llm_plan,
    )

    asset_map = {asset.assetId: asset for asset in assets}
    for segment in segments:
        asset = asset_map[segment.assetId]
        duration = round(segment.endTime - segment.startTime, 2)
        assert duration <= max(asset.suggestedDurationSec, 0.5) + 0.01


def test_rhythm_context_for_llm_omits_beat_arrays() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="氛围电子",
        selectedTrackName="demo-track",
        beatMode="beat_1",
        beatPoints=[0.0, 0.5, 1.0],
        rawBeatPoints=[0.0, 0.25, 0.5, 0.75, 1.0],
        coarseBeatPoints=[0.0, 0.5, 1.0],
        rhythmNotes=["前段抓人", "中段留白"],
        darkCutSuggestions=[15.0, 30.0],
        photoMotionSuggestions=["轻推"],
    )

    context = _rhythm_context_for_llm(rhythm, "strong_weak")

    assert context is not None
    assert context["beatMode"] == "strong_weak"
    assert context["detectedBpm"] == 0
    assert "beatPoints" not in context
    assert "rawBeatPoints" not in context
    assert context["rhythmNotesSummary"] == ["前段抓人", "中段留白"]


def test_storyboard_max_tokens_scales_with_assets() -> None:
    assert _storyboard_max_tokens(3) == 1565
    assert _storyboard_max_tokens(100) == 6000


def test_normalize_storyboard_plan_accepts_copy_only_segments() -> None:
    assets = [_asset("HEMU_002", 1.0)]
    result = LlmCallResult.success(
        {
            "segments": [
                {
                    "assetId": "HEMU_002",
                    "shotDescription": "晨雾木屋群",
                    "subtitle": "像童话一样",
                }
            ]
        },
        provider_id="kimi",
        model="kimi-k2.6",
    )

    plan = _normalize_storyboard_plan(result, assets)

    assert plan == [
        {
            "assetId": "HEMU_002",
            "shotDescription": "晨雾木屋群",
            "function": "",
            "rhythm": "",
            "subtitle": "像童话一样",
        }
    ]


def test_merge_asset_order_prefers_llm_sequence() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
        _asset("KANAS_001", 1.5),
    ]

    merged = merge_asset_order(["KANAS_001", "HEMU_002"], assets)

    assert [asset.assetId for asset in merged] == ["KANAS_001", "HEMU_002", "GENERAL_003"]


def test_resolve_storyboard_beat_points_uses_raw_beats_for_capcut_mode() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="氛围电子",
        selectedTrackName="demo-track",
        beatMode="beat_1",
        beatPoints=[0.0, 2.0, 4.0],
        rawBeatPoints=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        coarseBeatPoints=[0.0, 1.0, 2.0, 3.0, 4.0],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
    )

    beat_points = resolve_storyboard_beat_points(
        rhythm,
        beat_mode="beat_2",
        target_duration_sec=4,
        align_to_beat=True,
    )

    assert beat_points == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]


def test_resolve_storyboard_beat_points_disabled_when_not_aligned() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="氛围电子",
        selectedTrackName="demo-track",
        beatMode="beat_1",
        beatPoints=[0.0, 2.0, 4.0],
        rawBeatPoints=[0.0, 0.5, 1.0, 1.5, 2.0],
        coarseBeatPoints=[],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
    )

    beat_points = resolve_storyboard_beat_points(
        rhythm,
        beat_mode="beat_1",
        target_duration_sec=4,
        align_to_beat=False,
    )

    assert beat_points == []


def test_resolve_storyboard_beat_points_applies_calibration_offset() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="",
        selectedTrackName="",
        beatMode="beat_2",
        beatPoints=[0.0, 1.0, 2.0, 3.0],
        rawBeatPoints=[0.0, 1.0, 2.0, 3.0],
        coarseBeatPoints=[],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
        beatCalibration={"beatOffsetSec": 0.2},
    )

    beat_points = resolve_storyboard_beat_points(
        rhythm,
        beat_mode="beat_2",
        target_duration_sec=3,
        align_to_beat=True,
    )

    assert beat_points == [0.0, 0.2, 1.2, 2.2, 3.0]


def test_align_storyboard_plan_preserves_asset_order() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
    ]
    plan = [
        {
            "assetId": "GENERAL_003",
            "shotDescription": "将军山",
            "function": "",
            "rhythm": "",
            "subtitle": "过渡",
        }
    ]

    aligned = _align_storyboard_plan_to_assets(assets, plan)

    assert [item["assetId"] for item in aligned] == ["HEMU_002", "GENERAL_003"]
    assert aligned[0]["shotDescription"] == ""
    assert aligned[1]["subtitle"] == "过渡"


def test_resolve_segment_timing_snaps_tail_end_to_last_beat_before_target() -> None:
    beats = [0.0, 1.0, 2.0, 58.5, 59.0]

    end_time, _, segment_beats = resolve_segment_timing(
        current_time=59.0,
        suggested_duration_sec=1.0,
        target_duration_sec=60,
        beat_points=beats,
        beat_index=4,
    )

    assert end_time == 59.0
    assert segment_beats[-1] == 59.0


def test_resolve_segment_timing_snaps_hard_end_to_nearest_beat() -> None:
    beats = [0.0, 1.0, 2.0, 3.0, 58.0]

    end_time, _, _ = resolve_segment_timing(
        current_time=58.0,
        suggested_duration_sec=2.0,
        target_duration_sec=60,
        beat_points=beats,
        beat_index=4,
    )

    assert end_time == 58.0


def _segment_on_beats(
    segment_id: str,
    *,
    start: float,
    end: float,
    beat_mode: str = "beat_2",
    beat_points: list[float] | None = None,
) -> StoryboardSegmentRead:
    scoped = beat_points or [start, end]
    return StoryboardSegmentRead(
        id=segment_id,
        startTime=start,
        endTime=end,
        assetId="A",
        shotDescription="",
        function="supporting",
        rhythm="balanced",
        beatMode=beat_mode,
        beatPoints=scoped,
        subtitle="",
    )


def test_check_beat_alignment_uses_fine_grid_and_segment_beats() -> None:
    coarse = [0.0, 2.0, 4.0]
    fine = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    segments = [
        _segment_on_beats("seg_1", start=0.5, end=2.5, beat_points=[0.5, 1.0, 1.5, 2.0, 2.5]),
    ]

    assert check_beat_alignment(segments, coarse) is True
    assert check_beat_alignment(segments, fine) is True


def test_build_storyboard_validation_passes_beat_2_segments() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="氛围电子",
        selectedTrackName="demo-track",
        beatMode="beat_1",
        beatPoints=[0.0, 2.0, 4.0, 6.0],
        rawBeatPoints=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
        coarseBeatPoints=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
    )
    project = ProjectEntity(
        id="proj_1",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=6,
        video_type="emotion_film",
        style_preference="",
        style_notes="",
        route_text="",
        media_root="",
        status="draft",
        selected_theme_id="",
        validate_location_order=False,
    )
    segments = [
        _segment_on_beats("seg_1", start=0.0, end=2.5, beat_points=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5]),
        _segment_on_beats("seg_2", start=2.5, end=6.0, beat_points=[2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]),
    ]
    assets = [_asset("A", 2.5)]

    validation = build_storyboard_validation(project, segments, rhythm, assets)

    assert validation.beatAlignmentPassed is True
    assert not any("节拍点" in issue for issue in validation.issues)


def test_resolve_validation_beat_points_matches_generation_grid() -> None:
    rhythm = RhythmPlanRead(
        bgmStyle="氛围电子",
        selectedTrackName="demo-track",
        beatMode="beat_1",
        beatPoints=[0.0, 2.0, 4.0],
        rawBeatPoints=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        coarseBeatPoints=[0.0, 1.0, 2.0, 3.0, 4.0],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
    )
    segments = [_segment_on_beats("seg_1", start=0.5, end=2.5)]

    validation_beats = resolve_validation_beat_points(rhythm, segments, 4.0)
    generation_beats = resolve_storyboard_beat_points(
        rhythm,
        beat_mode="beat_2",
        target_duration_sec=4,
        align_to_beat=True,
    )

    assert validation_beats == generation_beats


def test_generate_storyboard_segments_from_plan_uses_llm_copy_only() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
    ]
    llm_plan = [
        {
            "assetId": "HEMU_002",
            "shotDescription": "禾木晨雾",
            "function": "",
            "rhythm": "",
            "subtitle": "开场",
        },
        {
            "assetId": "GENERAL_003",
            "shotDescription": "将军山跟拍",
            "function": "",
            "rhythm": "",
            "subtitle": "过渡",
        },
    ]

    segments = generate_storyboard_segments_from_plan(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=60,
        beat_mode="none",
        beat_points=[],
        llm_plan=llm_plan,
    )

    assert segments[0].shotDescription == "禾木晨雾"
    assert segments[0].subtitle == "开场"
    assert segments[0].function == "supporting"
    assert segments[1].shotDescription == "将军山跟拍"


def test_generate_storyboard_segments_without_reuse_stops_after_one_pass() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=60,
        beat_mode="none",
        beat_points=[],
        allow_asset_reuse=False,
    )

    assert len(segments) == 2
    assert len({segment.assetId for segment in segments}) == 2


def test_generate_storyboard_segments_with_reuse_inserts_bridge_segments() -> None:
    assets = [
        _asset("HEMU_002", 1.0),
        _asset("GENERAL_003", 1.2),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=6,
        beat_mode="none",
        beat_points=[],
        allow_asset_reuse=True,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.0, "role": "turn_1"},
            {"time": 2.0, "role": "climax"},
            {"time": 3.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
    )

    asset_ids = [segment.assetId for segment in segments]
    bridge_segments = [
        segment for segment in segments if segment.selectionTrace.startswith("[reuse-bridge]")
    ]

    assert len(asset_ids) > len(set(asset_ids))
    assert round(segments[-1].endTime, 2) >= 4.0
    assert bridge_segments
    assert not {"hook", "turn", "turn_1", "turn_2", "climax"} & {
        segment.attentionRole for segment in bridge_segments
    }
    assert max(segments.index(segment) for segment in bridge_segments) < len(segments) - 1
    assert not segments[-1].selectionTrace.startswith("[reuse-bridge]")


def test_duration_shortfall_uses_unused_assets_before_reuse_bridge() -> None:
    assets = [
        _route_asset("C_HOOK", location="C", function_tags=["opening_hook"], shot_type="aerial"),
        _route_asset("A_001", location="A", function_tags=["supporting"]),
        _route_asset("A_UNUSED", location="A", function_tags=["supporting"], suggested_duration_sec=2.0),
        _route_asset("B_001", location="B", function_tags=["rhythm_hit"]),
        _route_asset("C_END", location="C", function_tags=["ending"]),
    ]

    planned_assets = plan_storyboard_asset_sequence(
        assets,
        target_duration_sec=6,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["A", "B", "C"],
    )
    planned_ids = [item.asset.assetId for item in planned_assets]

    assert {"A_001", "A_UNUSED"}.issubset(set(planned_ids))
    assert any("未使用素材补齐" in item.selection_trace for item in planned_assets)

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=6,
        beat_mode="none",
        beat_points=[],
        allow_asset_reuse=True,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["A", "B", "C"],
    )

    segment_ids = [segment.assetId for segment in segments]
    assert {"A_001", "A_UNUSED"}.issubset(set(segment_ids))
    assert not any(segment.selectionTrace.startswith("[reuse-bridge]") for segment in segments)


def test_duration_fill_max_consecutive_route_controls_extra_same_location_fill() -> None:
    assets = [
        _route_asset("C_HOOK", location="C", function_tags=["opening_hook"], shot_type="aerial"),
        _route_asset("A_001", location="A", function_tags=["supporting"], suggested_duration_sec=1.0),
        _route_asset("A_002", location="A", function_tags=["supporting"], suggested_duration_sec=1.0),
        _route_asset("A_FILL", location="A", function_tags=["supporting"], suggested_duration_sec=1.0),
        _route_asset("B_001", location="B", function_tags=["rhythm_hit"], suggested_duration_sec=1.0),
        _route_asset("C_END", location="C", function_tags=["ending"], suggested_duration_sec=0.5),
    ]

    conservative_assets = plan_storyboard_asset_sequence(
        assets,
        target_duration_sec=7,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["A", "B", "C"],
    )
    conservative_ids = [item.asset.assetId for item in conservative_assets]

    assert "A_FILL" not in conservative_ids

    planned_assets = plan_storyboard_asset_sequence(
        assets,
        target_duration_sec=7,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 1.5, "role": "turn_1"},
            {"time": 3.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["A", "B", "C"],
        duration_fill_max_consecutive_route=3,
    )
    planned_ids = [item.asset.assetId for item in planned_assets]

    assert "A_FILL" in planned_ids
    assert planned_ids.index("A_FILL") < planned_ids.index("B_001")
    assert sum(max(item.asset.suggestedDurationSec, 0.5) for item in planned_assets) >= 5.5


def test_reuse_bridge_keeps_final_anchor_and_caps_buffer_repeats() -> None:
    assets = [
        _route_asset("HOOK_001", location="将军山", function_tags=["opening_hook"]),
        _route_asset(
            "BUFFER_001",
            location="将军山",
            function_tags=["transition_buffer"],
            suggested_duration_sec=0.5,
        ),
        _route_asset("TURN_001", location="喀纳斯", function_tags=["rhythm_hit"]),
        _route_asset("CLIMAX_001", location="禾木", function_tags=["main_climax"]),
        _route_asset("ENDING_001", location="禾木", function_tags=["ending"]),
    ]

    segments = generate_storyboard_segments(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=12,
        beat_mode="none",
        beat_points=[],
        allow_asset_reuse=True,
        attention_beats=[
            {"time": 0.0, "role": "hook"},
            {"time": 2.0, "role": "turn_1"},
            {"time": 5.0, "role": "turn_2"},
            {"time": 8.0, "role": "climax"},
            {"time": 10.0, "role": "payoff"},
        ],
        rhythm_profile={"mode": "highlight_reel"},
        route_locations=["将军山", "喀纳斯", "禾木"],
    )

    asset_ids = [segment.assetId for segment in segments]
    bridge_segments = [
        segment for segment in segments if segment.selectionTrace.startswith("[reuse-bridge]")
    ]

    assert bridge_segments
    assert not segments[-1].selectionTrace.startswith("[reuse-bridge]")
    assert asset_ids.count("BUFFER_001") <= 1 + 2
    assert asset_ids[-1] != "BUFFER_001"


def test_generate_storyboard_segments_from_plan_allows_duplicate_asset_ids() -> None:
    assets = [_asset("HEMU_002", 1.0)]
    llm_plan = [
        {
            "assetId": "HEMU_002",
            "shotDescription": "第一次",
            "function": "opening_hook",
            "rhythm": "linger",
            "subtitle": "开场",
        },
        {
            "assetId": "HEMU_002",
            "shotDescription": "第二次",
            "function": "supporting",
            "rhythm": "balanced",
            "subtitle": "复用",
        },
    ]

    segments = generate_storyboard_segments_from_plan(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=60,
        beat_mode="none",
        beat_points=[],
        llm_plan=llm_plan,
        allow_asset_reuse=True,
    )

    assert len(segments) >= 2
    assert segments[0].shotDescription == "第一次"
    assert segments[1].shotDescription == "第二次"


def test_generate_storyboard_segments_from_plan_does_not_append_reuse_bridge_tail() -> None:
    assets = [_asset("HEMU_002", 1.0), _asset("GENERAL_003", 1.2)]
    llm_plan = [
        {"assetId": "HEMU_002", "shotDescription": "第一段"},
        {"assetId": "GENERAL_003", "shotDescription": "第二段"},
    ]

    segments = generate_storyboard_segments_from_plan(
        assets=assets,
        theme_id="theme_001",
        target_duration_sec=10,
        beat_mode="none",
        beat_points=[],
        llm_plan=llm_plan,
        allow_asset_reuse=True,
    )

    assert [segment.assetId for segment in segments] == ["HEMU_002", "GENERAL_003"]
    assert not any(segment.selectionTrace.startswith("[reuse-bridge]") for segment in segments)


def test_build_storyboard_validation_reports_asset_reuse_warnings() -> None:
    project = ProjectEntity(
        id="proj_1",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=4,
        video_type="emotion_film",
        style_preference="",
        style_notes="",
        route_text="",
        media_root="",
        status="draft",
        selected_theme_id="",
        validate_location_order=False,
        allow_asset_reuse=True,
    )
    assets = [_asset("HEMU_002", 1.0)]
    segments = [
        StoryboardSegmentRead(
            id="seg_1",
            startTime=0.0,
            endTime=1.0,
            assetId="HEMU_002",
            shotDescription="A",
            function="supporting",
            rhythm="balanced",
            beatMode="none",
            beatPoints=[0.0, 1.0],
            subtitle="A",
        ),
        StoryboardSegmentRead(
            id="seg_2",
            startTime=1.0,
            endTime=2.0,
            assetId="HEMU_002",
            shotDescription="B",
            function="supporting",
            rhythm="balanced",
            beatMode="none",
            beatPoints=[1.0, 2.0],
            subtitle="B",
        ),
    ]

    validation = build_storyboard_validation(project, segments, None, assets)

    assert validation.assetReuseEnabled is True
    assert validation.reusedAssetCount == 1
    assert validation.reusedSegmentCount == 1
    assert any("复用" in issue for issue in validation.issues)
