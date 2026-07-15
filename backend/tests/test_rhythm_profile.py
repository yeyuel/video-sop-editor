from app.models.entities import ProjectEntity
from app.models.entities import RhythmPlanEntity
from app.models.schemas import RhythmPlanWriteRequest
from app.services.repository import repository
from app.services.rhythm_profile import (
    build_attention_beats,
    build_rhythm_profile,
    resolve_rhythm_mode,
)


def _project(platform: str, video_type: str, duration: int) -> ProjectEntity:
    return ProjectEntity(
        id="proj_test",
        name="测试项目",
        destination="阿勒泰",
        platform=platform,
        target_duration_sec=duration,
        video_type=video_type,
        style_preference="情绪氛围片",
        status="draft",
    )


def test_resolve_rhythm_mode_matches_platform_ecology() -> None:
    assert resolve_rhythm_mode("抖音", "情绪片") == "highlight_reel"
    assert resolve_rhythm_mode("快手", "情绪片") == "highlight_reel"
    assert resolve_rhythm_mode("小红书", "攻略片") == "seed_and_guide"
    assert resolve_rhythm_mode("B站", "guide_video") == "chapter_explainer"
    assert resolve_rhythm_mode("B站", "vlog") == "emotional_vlog"
    assert resolve_rhythm_mode("视频号", "旅行故事") == "stable_story"


def test_short_video_attention_beats_follow_shot_reel_rule() -> None:
    project = _project("抖音", "情绪片", 60)
    beats = build_attention_beats(project, "highlight_reel")

    assert [beat["time"] for beat in beats] == [0.0, 15.0, 30.0, 45.0, 60.0]
    assert [beat["role"] for beat in beats] == ["hook", "turn_1", "turn_2", "climax", "payoff"]
    assert "射门点" in beats[1]["description"]


def test_platform_attention_roles_are_distinct() -> None:
    project = _project("小红书", "攻略片", 60)
    seed_beats = build_attention_beats(project, "seed_and_guide")
    vlog_beats = build_attention_beats(project, "emotional_vlog")
    stable_beats = build_attention_beats(project, "stable_story")

    assert [beat["role"] for beat in seed_beats] == [
        "hook",
        "visual_seed",
        "info_value",
        "decision_push",
        "save_cta",
    ]
    assert [beat["role"] for beat in vlog_beats] == [
        "hook",
        "immersion",
        "inner_turn",
        "emotional_climax",
        "aftertaste",
    ]
    assert [beat["role"] for beat in stable_beats] == [
        "hook",
        "setup",
        "turn",
        "climax",
        "ending",
    ]


def test_short_duration_attention_beats_keep_platform_specific_roles() -> None:
    douyin_project = _project("douyin", "travel", 10)
    xhs_project = _project("xiaohongshu", "guide", 10)
    bilibili_project = _project("bilibili", "guide_video", 10)
    vlog_project = _project("bilibili", "vlog", 10)

    assert [beat["role"] for beat in build_attention_beats(douyin_project, "highlight_reel")] == [
        "hook",
        "turn_1",
        "turn_2",
        "climax",
        "payoff",
    ]
    assert [beat["role"] for beat in build_attention_beats(xhs_project, "seed_and_guide")] == [
        "hook",
        "visual_seed",
        "info_value",
        "save_cta",
    ]
    assert [beat["role"] for beat in build_attention_beats(bilibili_project, "chapter_explainer")] == [
        "hook",
        "chapter",
        "proof",
        "summary",
    ]
    assert [beat["role"] for beat in build_attention_beats(vlog_project, "emotional_vlog")] == [
        "hook",
        "immersion",
        "emotional_climax",
        "aftertaste",
    ]


def test_bilibili_long_guide_uses_chapter_nodes() -> None:
    project = _project("B站", "guide_video", 180)
    beats = build_attention_beats(project, "chapter_explainer")

    assert [beat["time"] for beat in beats] == [0.0, 45.0, 90.0, 135.0, 180.0]
    assert [beat["role"] for beat in beats] == ["hook", "chapter", "proof", "chapter", "summary"]


def test_rhythm_profile_includes_platform_pacing_fields() -> None:
    project = _project("B站", "guide_video", 300)
    profile = build_rhythm_profile(project, [], None)

    assert profile["mode"] == "chapter_explainer"
    assert profile["cutDensity"] == "chaptered"
    assert profile["subtitleDensity"] == "information"


def _rhythm_payload(fingerprint: str) -> RhythmPlanWriteRequest:
    return RhythmPlanWriteRequest(
        bgmStyle="舒展氛围",
        selectedTrackName="测试曲目",
        audioFileName="song.wav",
        analysisSource="audio_upload",
        analysisNotes=["识别完成"],
        detectedBpm=90,
        audioDurationSec=30,
        rawBeatPoints=[0, 1, 2],
        coarseBeatPoints=[0, 2],
        beatMode="beat_1",
        beatPoints=[0, 2],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
        beatCalibration={
            "source": "audio_upload",
            "beatOffsetSec": 0,
            "densityMode": "beat_1",
            "referenceBeatPoints": [],
            "confidence": "auto",
        },
        audioFingerprint=fingerprint,
        audioAnalysisVersion="energy",
    )


def test_reuse_calibration_for_same_audio_keeps_previous_capcut_reference() -> None:
    existing = RhythmPlanEntity(
        id="rhythm_001",
        project_id="proj_test",
        bgm_style="舒展氛围",
        selected_track_name="测试曲目",
        audio_file_name="song.wav",
        audio_file_path="song.wav",
        analysis_source="audio_upload",
        analysis_notes="[]",
        detected_bpm=90,
        audio_duration_sec=30,
        raw_beat_points="[]",
        coarse_beat_points="[]",
        beat_mode="beat_1",
        beat_points="[]",
        rhythm_notes="[]",
        dark_cut_suggestions="[]",
        photo_motion_suggestions="[]",
        beat_calibration_json='{"source":"capcut_reference","beatOffsetSec":0.12,"beatScale":1.01,"referenceBeatPoints":[0.12,1.12]}',
        audio_fingerprint="same-hash:30:90:energy",
        audio_analysis_version="energy",
    )

    reused = repository._reuse_calibration_for_same_audio(
        _rhythm_payload("same-hash:30:90:energy"),
        existing,
    )
    unchanged = repository._reuse_calibration_for_same_audio(
        _rhythm_payload("other-hash:30:90:energy"),
        existing,
    )

    assert reused.beatCalibration["beatOffsetSec"] == 0.12
    assert reused.beatCalibration["beatScale"] == 1.01
    assert reused.beatCalibration["referenceBeatPoints"] == [0.12, 1.12]
    assert reused.beatCalibration["confidence"] == "reused_same_audio"
    assert any("复用" in note for note in reused.analysisNotes)
    assert unchanged.beatCalibration["beatOffsetSec"] == 0
    assert unchanged.beatCalibration["referenceBeatPoints"] == []
