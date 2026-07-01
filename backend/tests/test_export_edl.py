from __future__ import annotations

from app.models.schemas import (
    AssetRead,
    ExportPlanRead,
    ExportValidationRead,
    ProjectRead,
    RhythmPlanRead,
    StoryboardSegmentRead,
    StoryboardValidationRead,
    WorkspaceDataRead,
)
from app.services.export_generation import render_export_content
from app.services.rough_cut_export import (
    edl_reel_name,
    render_edl,
    resolve_clip_path,
    seconds_to_edl_timecode,
)


def _workspace() -> WorkspaceDataRead:
    return WorkspaceDataRead(
        project=ProjectRead(
            id="proj_demo",
            name="阿勒泰雪国片",
            destination="阿勒泰",
            platform="xiaohongshu",
            targetDurationSec=60,
            videoType="emotion_film",
            stylePreference="情绪氛围片",
            styleNotes="",
            routeText="将军山 - 喀纳斯 - 禾木",
            mediaRoot=r"D:/media/altay",
            status="draft",
            selectedThemeId="theme_001",
            validateLocationOrder=False,
            allowAssetReuse=False,
        ),
        assets=[
            AssetRead(
                assetId="HEMU_002",
                location="禾木",
                scene="木屋群远景",
                relativePath=r"禾木/wide/HEMU_002.mp4",
                mediaType="video",
                shotType="wide",
                emotionTags=["童话"],
                visualTags=["蓝调"],
                informationDensity="high",
                suggestedDurationSec=1.0,
                functionTags=["opening_hook"],
            )
        ],
        themes=[],
        storyboard=[
            StoryboardSegmentRead(
                id="seg_001",
                startTime=0.0,
                endTime=1.5,
                assetId="HEMU_002",
                shotDescription="禾木远景开场",
                function="opening_hook",
                rhythm="tight_cut",
                beatMode="beat_1",
                beatPoints=[0.0, 1.5],
                subtitle="像一脚走进了雪国童话",
            ),
            StoryboardSegmentRead(
                id="seg_002",
                startTime=1.5,
                endTime=3.0,
                assetId="HEMU_002",
                shotDescription="同一素材复用段",
                function="supporting",
                rhythm="balanced",
                beatMode="none",
                beatPoints=[1.5, 3.0],
                subtitle="继续推进情绪",
            ),
        ],
        storyboardValidation=StoryboardValidationRead(
            allSegmentsBoundToAsset=True,
            locationContinuityPassed=True,
            beatAlignmentPassed=True,
            beatAdaptationEnabled=False,
            totalDurationSec=3.0,
            targetDurationSec=60,
            durationDeltaSec=-57.0,
            durationWithinTolerance=False,
            targetDurationReached=False,
            issues=[],
        ),
        exportValidation=ExportValidationRead(
            destinationMentioned=True,
            themeConsistencyPassed=True,
            issues=[],
        ),
        rhythmPlan=RhythmPlanRead(
            bgmStyle="ambient",
            selectedTrackName="demo-track",
            audioFileName="demo.wav",
            analysisSource="manual",
            analysisNotes=[],
            detectedBpm=120,
            audioDurationSec=60.0,
            rawBeatPoints=[],
            coarseBeatPoints=[],
            beatMode="none",
            beatPoints=[],
            rhythmNotes=[],
            darkCutSuggestions=[],
            photoMotionSuggestions=[],
            recommendedBgm=[],
            selectedBgmId="",
            bgmPhase="ready",
        ),
        exportPlan=ExportPlanRead(
            title="阿勒泰冬日氛围",
            shortTitle="雪国童话",
            description="测试导出",
            tags=["阿勒泰", "冬日"],
            coverSuggestion="禾木远景",
        ),
    )


def test_seconds_to_edl_timecode() -> None:
    assert seconds_to_edl_timecode(0.0) == "00:00:00:00"
    assert seconds_to_edl_timecode(1.0) == "00:00:01:00"
    assert seconds_to_edl_timecode(61.5) == "00:01:01:15"


def test_edl_reel_name_truncates_to_eight_chars() -> None:
    assert edl_reel_name("HEMU_002") == "HEMU_002"
    assert edl_reel_name("very-long-asset-id") == "VERY-LON"


def test_resolve_clip_path_joins_media_root() -> None:
    assert resolve_clip_path(r"D:\media\altay", r"禾木\wide\HEMU_002.mp4") == (
        "D:/media/altay/禾木/wide/HEMU_002.mp4"
    )


def test_render_edl_contains_events_paths_and_subtitles() -> None:
    content = render_edl(_workspace())

    assert "TITLE: 阿勒泰雪国片" in content
    assert "001  HEMU_002 V     C" in content
    assert "002  HEMU_002 V     C" in content
    assert "* FROM CLIP NAME: D:/media/altay/禾木/wide/HEMU_002.mp4" in content
    assert "* COMMENT: 像一脚走进了雪国童话" in content
    assert "* COMMENT: 继续推进情绪" in content
    assert "00:00:00:00 00:00:01:15 00:00:00:00 00:00:01:15" in content


def test_render_export_content_edl_dispatch() -> None:
    content = render_export_content(_workspace(), "edl")
    assert content.startswith("TITLE:")
    assert "001  HEMU_002" in content
