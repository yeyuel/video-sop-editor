from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, RhythmPlanRead, StoryboardSegmentRead
from app.services.storyboard_generation import (
    _align_storyboard_plan_to_assets,
    _normalize_storyboard_plan,
    _rhythm_context_for_llm,
    _storyboard_max_tokens,
    build_storyboard_validation,
    check_beat_alignment,
    generate_storyboard_segments,
    generate_storyboard_segments_from_plan,
    merge_asset_order,
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
    assert _storyboard_max_tokens(3) == 2240
    assert _storyboard_max_tokens(100) == 8000


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


def test_generate_storyboard_segments_with_reuse_cycles_assets() -> None:
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
    )

    asset_ids = [segment.assetId for segment in segments]
    assert len(asset_ids) > len(set(asset_ids))
    assert round(segments[-1].endTime, 2) >= 6.0


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
