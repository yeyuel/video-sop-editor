from app.models.schemas import AssetRead, RhythmPlanRead
from app.services.storyboard_generation import (
    _align_storyboard_plan_to_assets,
    _normalize_storyboard_plan,
    _rhythm_context_for_llm,
    _storyboard_max_tokens,
    generate_storyboard_segments,
    generate_storyboard_segments_from_plan,
    resolve_segment_timing,
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
