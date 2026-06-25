from app.models.entities import ProjectEntity
from app.models.schemas import (
    AssetRead,
    ExportPlanRead,
    NarrativeThemeRead,
    ProjectRead,
    StoryboardSegmentRead,
)
from app.services.export_validation import build_export_validation
from app.services.storyboard_generation import (
    build_storyboard_validation,
    duration_within_target_tolerance,
    find_location_jump_issues,
)


def _segment(
    segment_id: str,
    *,
    start: float,
    end: float,
    asset_id: str,
) -> StoryboardSegmentRead:
    return StoryboardSegmentRead(
        id=segment_id,
        startTime=start,
        endTime=end,
        assetId=asset_id,
        shotDescription="",
        function="supporting",
        rhythm="balanced",
        beatMode="none",
        beatPoints=[],
        subtitle="",
    )


def _asset(asset_id: str, location: str) -> AssetRead:
    return AssetRead(
        assetId=asset_id,
        location=location,
        scene="",
        relativePath="",
        mediaType="video",
        shotType="wide",
        emotionTags=[],
        visualTags=[],
        informationDensity="medium",
        suggestedDurationSec=1.0,
        functionTags=["supporting"],
    )


def test_duration_within_target_tolerance() -> None:
    assert duration_within_target_tolerance(58, 60) is True
    assert duration_within_target_tolerance(45, 60) is False
    assert duration_within_target_tolerance(65, 60) is True


def test_find_location_jump_issues_detects_route_backtrack() -> None:
    segments = [
        _segment("seg_1", start=0, end=1, asset_id="A"),
        _segment("seg_2", start=1, end=2, asset_id="B"),
    ]
    asset_map = {
        "A": _asset("A", "禾木"),
        "B": _asset("B", "喀纳斯"),
    }
    issues = find_location_jump_issues(segments, asset_map, ["喀纳斯", "禾木"])
    assert issues
    assert "回跳" in issues[0]


def test_find_location_jump_issues_dedupes_repeated_backtracks() -> None:
    segments = [
        _segment("seg_1", start=0, end=1, asset_id="A"),
        _segment("seg_2", start=1, end=2, asset_id="B"),
        _segment("seg_3", start=2, end=3, asset_id="A"),
        _segment("seg_4", start=3, end=4, asset_id="B"),
    ]
    asset_map = {
        "A": _asset("A", "禾木"),
        "B": _asset("B", "喀纳斯"),
    }
    issues = find_location_jump_issues(segments, asset_map, ["喀纳斯", "禾木"])
    assert len(issues) == 1
    assert "禾木" in issues[0] and "喀纳斯" in issues[0]


def test_build_storyboard_validation_reports_unbound_and_duration() -> None:
    project = ProjectEntity(
        id="proj_1",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=60,
        video_type="emotion_film",
        style_preference="",
        style_notes="",
        route_text="禾木 -> 喀纳斯",
        media_root="",
        status="draft",
        selected_theme_id="",
        validate_location_order=True,
    )
    segments = [
        _segment("seg_1", start=0, end=2, asset_id="A"),
        _segment("seg_2", start=2, end=4, asset_id=""),
    ]
    assets = [_asset("A", "禾木")]
    validation = build_storyboard_validation(project, segments, None, assets)

    assert validation.unboundSegmentCount == 1
    assert validation.durationDeltaSec == -56
    assert validation.durationWithinTolerance is False
    assert any("未绑定" in issue for issue in validation.issues)


def test_build_storyboard_validation_skips_location_order_when_disabled() -> None:
    project = ProjectEntity(
        id="proj_2",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        target_duration_sec=60,
        video_type="emotion_film",
        style_preference="",
        style_notes="",
        route_text="禾木 -> 喀纳斯",
        media_root="",
        status="draft",
        selected_theme_id="",
        validate_location_order=False,
    )
    segments = [
        _segment("seg_1", start=0, end=1, asset_id="A"),
        _segment("seg_2", start=1, end=2, asset_id="B"),
    ]
    assets = [_asset("A", "禾木"), _asset("B", "喀纳斯")]
    validation = build_storyboard_validation(project, segments, None, assets)

    assert validation.locationOrderValidationEnabled is False
    assert validation.locationContinuityPassed is True
    assert not any("回跳" in issue for issue in validation.issues)


def test_build_export_validation_checks_destination_and_theme() -> None:
    project = ProjectRead(
        id="proj_1",
        name="测试项目",
        destination="阿勒泰",
        platform="xiaohongshu",
        targetDurationSec=60,
        videoType="emotion_film",
        stylePreference="",
        styleNotes="",
        routeText="",
        mediaRoot="",
        status="draft",
        selectedThemeId="theme_1",
    )
    theme = NarrativeThemeRead(
        id="theme_1",
        title="雪国情绪片",
        summary="",
        coreEmotion="沉浸",
        rhythmProfile="",
        platformReason="",
        usedLocations=[],
        usedAssetIds=[],
        isSelected=True,
    )
    export_plan = ExportPlanRead(
        title="这是一段关于杭州的旅行短片",
        shortTitle="",
        description="适合周末放松看看。",
        tags=["旅行"],
        coverSuggestion="",
    )

    validation = build_export_validation(project=project, theme=theme, export_plan=export_plan)

    assert validation.destinationMentioned is False
    assert validation.themeConsistencyPassed is False
    assert validation.issues
