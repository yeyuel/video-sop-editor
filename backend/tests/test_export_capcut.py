from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from app.services.capcut_draft_export import (
    build_capcut_draft,
    build_text_content,
    deploy_capcut_draft,
    render_capcut_draft,
    seconds_to_microseconds,
)
from app.services.export_generation import render_export_content


def _workspace(*, audio_file_path: str = "", audio_duration_sec: float = 0.0) -> WorkspaceDataRead:
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
            jianyingDraftRoot="",
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
            audioFilePath=audio_file_path,
            analysisSource="manual",
            analysisNotes=[],
            detectedBpm=120,
            audioDurationSec=audio_duration_sec,
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


def test_seconds_to_microseconds() -> None:
    assert seconds_to_microseconds(0.0) == 0
    assert seconds_to_microseconds(1.0) == 1_000_000
    assert seconds_to_microseconds(1.5) == 1_500_000


def test_build_text_content_uses_utf16_byte_range() -> None:
    content = build_text_content("Hello")
    parsed = json.loads(content)
    assert parsed["text"] == "Hello"
    assert parsed["styles"][0]["range"] == [0, 10]

    chinese = build_text_content("你好")
    chinese_parsed = json.loads(chinese)
    assert chinese_parsed["styles"][0]["range"] == [0, 4]


def test_build_capcut_draft_contains_tracks_and_materials() -> None:
    draft = build_capcut_draft(_workspace())

    assert draft["platform"]["app_source"] == "lv"
    assert draft["duration"] == 3_000_000
    assert len(draft["tracks"]) == 2
    assert draft["tracks"][0]["type"] == "video"
    assert len(draft["tracks"][0]["segments"]) == 2
    assert draft["tracks"][1]["type"] == "text"
    assert len(draft["tracks"][1]["segments"]) == 2
    assert len(draft["materials"]["videos"]) == 1
    assert draft["materials"]["videos"][0]["path"] == (
        "D:/media/altay/禾木/wide/HEMU_002.mp4"
    )
    assert len(draft["materials"]["texts"]) == 2


def test_build_capcut_draft_includes_bgm_when_audio_exists(tmp_path: Path) -> None:
    bgm_path = tmp_path / "demo.wav"
    bgm_path.write_bytes(b"RIFF")
    workspace = _workspace(audio_file_path=str(bgm_path), audio_duration_sec=60.0)

    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["bgm_included"] is True
    assert len(draft["tracks"]) == 3
    assert draft["tracks"][1]["type"] == "audio"
    assert len(draft["materials"]["audios"]) == 1
    assert draft["materials"]["audios"][0]["path"] == str(bgm_path).replace("\\", "/")


def test_build_capcut_draft_skips_bgm_when_missing_file() -> None:
    draft = build_capcut_draft(_workspace(audio_file_path=r"C:/missing/demo.wav"))

    assert draft["extra_info"]["bgm_included"] is False
    assert all(track["type"] != "audio" for track in draft["tracks"])


def test_render_capcut_draft_bundle_sections() -> None:
    content = render_capcut_draft(_workspace())
    bundle = json.loads(content)

    assert bundle["targetApp"] == "jianying"
    assert "draft_content.json" in bundle["sections"]
    assert "draft_meta_info.json" in bundle["sections"]
    assert bundle["sections"]["draft_content.json"]["name"] == "阿勒泰冬日氛围"


def test_deploy_capcut_draft_writes_two_json_files(tmp_path: Path) -> None:
    workspace = _workspace()
    result = deploy_capcut_draft(workspace, draft_root=str(tmp_path))

    folder = Path(result.draft_folder_path)
    assert folder.is_dir()
    assert result.files == ["draft_content.json", "draft_meta_info.json"]
    for file_name in result.files:
        payload = json.loads((folder / file_name).read_text(encoding="utf-8"))
        assert payload["name"] == "阿勒泰冬日氛围"


def test_render_export_content_capcut_dispatch() -> None:
    content = render_export_content(_workspace(), "capcut")
    bundle = json.loads(content)
    assert bundle["sections"]["draft_content.json"]["tracks"][0]["segments"][0][
        "target_timerange"
    ]["start"] == 0


def test_deploy_capcut_draft_requires_absolute_root(tmp_path: Path) -> None:
    workspace = _workspace()
    with pytest.raises(ValueError, match="绝对路径"):
        deploy_capcut_draft(workspace, draft_root="relative/path")
