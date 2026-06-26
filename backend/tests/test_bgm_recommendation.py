from app.models.entities import ProjectEntity
from app.models.schemas import BgmRecommendationRead, NarrativeThemeRead
from app.services.bgm_recommendation import (
    build_rule_bgm_recommendations,
    format_bgm_track_name,
)
from app.services.rhythm_readiness import rhythm_ready_for_storyboard, rhythm_requirement_message


def test_build_rule_bgm_recommendations_returns_realistic_tracks() -> None:
    project = ProjectEntity(
        id="proj_1",
        name="阿勒泰雪国片",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=60,
        video_type="emotion_film",
        style_preference="情绪氛围片",
        style_notes="",
        route_text="",
        media_root="",
        status="draft",
        selected_theme_id="",
    )
    theme = NarrativeThemeRead(
        id="theme_1",
        title="阿勒泰情绪氛围片",
        summary="",
        coreEmotion="沉浸",
        rhythmProfile="前段抓人，中段舒展",
        platformReason="",
        usedLocations=[],
        usedAssetIds=[],
        isSelected=True,
    )

    recommendations, bgm_style, rhythm_notes = build_rule_bgm_recommendations(project, theme)

    assert len(recommendations) >= 2
    assert bgm_style
    assert len(rhythm_notes) >= 2
    assert all(item.title for item in recommendations)
    assert all(item.searchHint for item in recommendations)


def test_format_bgm_track_name_with_artist() -> None:
    recommendation = BgmRecommendationRead(
        id="bgm_1",
        title="Snow Dream",
        artist="Demo Artist",
        styleTags=[],
        mood="",
        bpmRange="",
        fitReason="",
        searchHint="",
        platformTips="",
        isSelected=False,
    )
    assert format_bgm_track_name(recommendation) == "Demo Artist - Snow Dream"


def test_rhythm_ready_for_storyboard_requires_audio_upload() -> None:
    from app.models.schemas import RhythmPlanRead

    incomplete = RhythmPlanRead(
        bgmStyle="氛围",
        selectedTrackName="Artist - Song",
        beatMode="beat_1",
        beatPoints=[0, 1, 2],
        rhythmNotes=[],
        darkCutSuggestions=[],
        photoMotionSuggestions=[],
        recommendedBgm=[],
        selectedBgmId="bgm_1",
        bgmPhase="recommended",
        analysisSource="manual",
    )
    assert rhythm_ready_for_storyboard(incomplete) is False
    assert "上传" in rhythm_requirement_message(incomplete)

    complete = incomplete.model_copy(
        update={
            "bgmPhase": "analyzed",
            "analysisSource": "audio_upload",
            "audioFileName": "song.mp3",
        }
    )
    assert rhythm_ready_for_storyboard(complete) is True
    assert rhythm_requirement_message(complete) == ""
