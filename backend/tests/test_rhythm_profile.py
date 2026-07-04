from app.models.entities import ProjectEntity
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
    assert resolve_rhythm_mode("小红书", "攻略片") == "seed_and_guide"
    assert resolve_rhythm_mode("B站", "guide_video") == "chapter_explainer"
    assert resolve_rhythm_mode("B站", "vlog") == "emotional_vlog"


def test_short_video_attention_beats_follow_shot_reel_rule() -> None:
    project = _project("抖音", "情绪片", 60)
    beats = build_attention_beats(project, "highlight_reel")

    assert [beat["time"] for beat in beats] == [0.0, 15.0, 30.0, 45.0, 60.0]
    assert [beat["role"] for beat in beats] == ["hook", "push", "turn", "climax", "ending"]


def test_rhythm_profile_includes_platform_pacing_fields() -> None:
    project = _project("B站", "guide_video", 300)
    profile = build_rhythm_profile(project, [], None)

    assert profile["mode"] == "chapter_explainer"
    assert profile["cutDensity"] == "chaptered"
    assert profile["subtitleDensity"] == "information"
