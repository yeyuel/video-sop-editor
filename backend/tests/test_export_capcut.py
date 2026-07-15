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
    CAPTION_FONT_SIZE,
    DEFAULT_BGM_FADE_IN_SEC,
    DEFAULT_BGM_FADE_OUT_SEC,
    CapcutDraftFolderExistsError,
    JIANYING_FONT_YOURAN,
    build_capcut_draft,
    build_native_voiceover_blocks,
    build_native_voiceover_preview,
    build_text_content,
    clear_draft_folder_contents,
    deploy_capcut_draft,
    render_capcut_draft,
    seconds_to_microseconds,
)
from app.services.export_generation import render_export_content


def _workspace(
    *,
    audio_file_path: str = "",
    audio_duration_sec: float = 0.0,
    voiceover_audio_path: str = "",
    voiceover_duration_sec: float = 0.0,
    voiceover_provider: str = "",
    voiceover_script: str = "",
    voiceover_density: str = "standard",
) -> WorkspaceDataRead:
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
            voiceoverScript=voiceover_script,
            voiceoverProvider=voiceover_provider,
            voiceoverDensity=voiceover_density,
            voiceoverGenerationStatus="generated" if voiceover_audio_path else "not_generated",
            voiceoverAudioPath=voiceover_audio_path,
            voiceoverDurationSec=voiceover_duration_sec,
        ),
    )


def test_seconds_to_microseconds() -> None:
    assert seconds_to_microseconds(0.0) == 0
    assert seconds_to_microseconds(1.0) == 1_000_000
    assert seconds_to_microseconds(1.5) == 1_500_000


def test_build_text_content_uses_jianying_char_range_and_youran_font() -> None:
    content = build_text_content("Hello")
    parsed = json.loads(content)
    assert parsed["text"] == "Hello"
    assert parsed["styles"][0]["range"] == [0, 5]
    assert parsed["styles"][0]["size"] == CAPTION_FONT_SIZE
    assert parsed["styles"][0]["font"]["id"] == JIANYING_FONT_YOURAN["resource_id"]
    assert parsed["styles"][0]["font"]["path"] == JIANYING_FONT_YOURAN["path"]
    assert parsed["styles"][0]["font"]["id"] == "6740436145831678467"

    chinese = build_text_content("你好")
    chinese_parsed = json.loads(chinese)
    assert chinese_parsed["styles"][0]["range"] == [0, 2]


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
    text_material = draft["materials"]["texts"][0]
    assert text_material["type"] == "text"
    assert text_material["global_alpha"] == 1.0
    content = json.loads(text_material["content"])
    assert content["styles"][0]["font"]["id"] == JIANYING_FONT_YOURAN["resource_id"]
    assert content["styles"][0]["size"] == pytest.approx(CAPTION_FONT_SIZE * 1.2)
    assert content["styles"][0]["bold"] is True


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
    assert len(draft["materials"]["audio_fades"]) == 1
    fade = draft["materials"]["audio_fades"][0]
    assert fade["fade_in_duration"] == seconds_to_microseconds(DEFAULT_BGM_FADE_IN_SEC)
    assert fade["fade_out_duration"] == seconds_to_microseconds(DEFAULT_BGM_FADE_OUT_SEC)
    audio_segment = draft["tracks"][1]["segments"][0]
    assert fade["id"] in audio_segment["extra_material_refs"]
    assert audio_segment["volume"] == 0.8


def test_build_capcut_draft_maps_buffer_transition_to_dissolve() -> None:
    workspace = _workspace()
    workspace.storyboard[0].transitionPolicy = "fade_or_match_cut"

    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["transition_count"] == 1
    assert len(draft["materials"]["transitions"]) == 1
    transition = draft["materials"]["transitions"][0]
    assert transition["name"] == "叠化"
    assert transition["duration"] == 500_000
    first_video_segment = draft["tracks"][0]["segments"][0]
    assert transition["id"] in first_video_segment["extra_material_refs"]


def test_build_capcut_draft_adds_photo_motion_keyframes() -> None:
    workspace = _workspace()
    workspace.assets[0].mediaType = "photo"
    workspace.storyboard[0].motionPolicy = "slow_push"

    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["motion_keyframe_segment_count"] == 1
    first_video_segment = draft["tracks"][0]["segments"][0]
    keyframe_list = first_video_segment["common_keyframes"][0]
    assert keyframe_list["property_type"] == "UNIFORM_SCALE"
    assert keyframe_list["keyframe_list"][0]["values"] == [1.0]
    assert keyframe_list["keyframe_list"][1]["values"] == [1.12]


def test_build_capcut_draft_honors_explicit_minimal_subtitle_policy() -> None:
    workspace = _workspace()
    workspace.storyboard[0].subtitlePolicy = "minimal"

    draft = build_capcut_draft(workspace)

    text_material = draft["materials"]["texts"][0]
    content = json.loads(text_material["content"])
    assert text_material["global_alpha"] == pytest.approx(0.78)
    assert content["styles"][0]["size"] == pytest.approx(CAPTION_FONT_SIZE * 0.88)
    assert content["styles"][0]["bold"] is False


def test_build_capcut_draft_includes_voiceover_when_audio_exists(tmp_path: Path) -> None:
    voice_path = tmp_path / "voiceover.wav"
    voice_path.write_bytes(b"RIFF")
    workspace = _workspace(voiceover_audio_path=str(voice_path), voiceover_duration_sec=2.0)

    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["voiceover_included"] is True
    assert draft["extra_info"]["bgm_ducking_applied"] is False
    audio_tracks = [track for track in draft["tracks"] if track["type"] == "audio"]
    assert len(audio_tracks) == 1
    assert audio_tracks[0]["name"] == "口播"
    assert audio_tracks[0]["segments"][0]["volume"] == 1.0
    assert audio_tracks[0]["segments"][0]["target_timerange"]["duration"] == 2_000_000
    assert draft["materials"]["audios"][0]["path"] == str(voice_path).replace("\\", "/")


def test_build_capcut_draft_ducks_bgm_when_voiceover_exists(tmp_path: Path) -> None:
    bgm_path = tmp_path / "demo.wav"
    voice_path = tmp_path / "voiceover.wav"
    bgm_path.write_bytes(b"RIFF")
    voice_path.write_bytes(b"RIFF")
    workspace = _workspace(
        audio_file_path=str(bgm_path),
        audio_duration_sec=60.0,
        voiceover_audio_path=str(voice_path),
        voiceover_duration_sec=3.0,
    )

    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["bgm_included"] is True
    assert draft["extra_info"]["voiceover_included"] is True
    assert draft["extra_info"]["bgm_ducking_applied"] is True
    audio_tracks = [track for track in draft["tracks"] if track["type"] == "audio"]
    assert len(audio_tracks) == 2
    assert audio_tracks[0]["name"] == "BGM"
    assert audio_tracks[0]["segments"][0]["volume"] == 0.35
    assert audio_tracks[1]["name"] == "口播"
    assert audio_tracks[1]["segments"][0]["volume"] == 1.0


def test_build_capcut_draft_uses_compressed_voiceover_as_final_subtitle_track() -> None:
    workspace = _workspace(voiceover_provider="jianying_native_tts")
    expected_blocks = build_native_voiceover_blocks(workspace)
    draft = build_capcut_draft(workspace)

    assert draft["extra_info"]["jianying_native_tts_text_track_included"] is True
    assert draft["extra_info"]["final_subtitles_use_compressed_voiceover"] is True
    assert draft["extra_info"]["voiceover_density"] == "standard"
    native_tracks = [track for track in draft["tracks"] if track["name"] == "最终字幕（剪映朗读源）"]
    assert len(native_tracks) == 1
    assert native_tracks[0]["type"] == "text"
    assert len(native_tracks[0]["segments"]) == 1
    assert len([track for track in draft["tracks"] if track["type"] == "text"]) == 1

    native_material_id = native_tracks[0]["segments"][0]["material_id"]
    native_material = next(
        item for item in draft["materials"]["texts"] if item["id"] == native_material_id
    )
    native_content = json.loads(native_material["content"])
    assert native_content["text"] == expected_blocks[0].text
    assert native_material["global_alpha"] == 1.0
    assert native_content["text"] != workspace.storyboard[0].subtitle or len(expected_blocks) > 1


def test_native_tts_light_density_merges_and_compacts_voiceover_blocks() -> None:
    workspace = _workspace(
        voiceover_provider="jianying_native_tts",
        voiceover_density="light",
    )

    blocks = build_native_voiceover_blocks(workspace)

    assert len(blocks) == 1
    assert blocks[0].start_sec == 0
    assert 2.0 <= blocks[0].end_sec <= 3.0
    assert len(blocks[0].text) <= 12
    assert blocks[0].text.endswith("。")


def test_native_tts_compaction_prefers_complete_short_clause() -> None:
    workspace = _workspace(
        voiceover_provider="jianying_native_tts",
        voiceover_density="light",
    )
    workspace.storyboard[0].voiceoverText = "这一句很长不适合快速朗读。短句。"
    workspace.storyboard[1].voiceoverText = "补充信息也很长不应抢占口播时长。"

    blocks = build_native_voiceover_blocks(workspace)

    assert blocks[0].text == "短句。"


def test_native_tts_preview_reports_compression_and_blocks() -> None:
    workspace = _workspace(
        voiceover_provider="jianying_native_tts",
        voiceover_density="standard",
    )

    preview = build_native_voiceover_preview(workspace)

    assert preview["density"] == "standard"
    assert preview["sourceChars"] > 0
    assert 0 < preview["outputChars"] <= preview["sourceChars"]
    assert 0 < preview["compressionRatio"] <= 1
    assert preview["blockCount"] == len(preview["blocks"])
    assert preview["estimatedReadingSec"] > 0
    assert preview["timingRiskCount"] == 0


def test_native_tts_last_block_borrows_previous_idle_time() -> None:
    workspace = _workspace(
        voiceover_provider="jianying_native_tts",
        voiceover_density="info",
    )
    workspace.storyboard[0].startTime = 0.0
    workspace.storyboard[0].endTime = 9.2
    workspace.storyboard[0].voiceoverText = "宝山的日落，先落在海面上，你以为港口只有冷硬。"
    workspace.storyboard[1].startTime = 9.2
    workspace.storyboard[1].endTime = 10.0
    workspace.storyboard[1].voiceoverText = "但余晖一直留到了最后。"

    blocks = build_native_voiceover_blocks(workspace)
    preview = build_native_voiceover_preview(workspace)

    assert len(blocks) == 2
    assert blocks[1].start_sec < 9.2
    assert blocks[1].end_sec == 10.0
    assert blocks[0].end_sec <= blocks[1].start_sec
    assert "…" not in blocks[1].text
    assert blocks[1].text == "但余晖一直留到了最后。"
    assert preview["timingRiskCount"] == 0
    assert preview["alignmentRiskCount"] == 1
    assert preview["blocks"][1]["alignmentShiftSec"] > 0
    assert preview["blocks"][1]["alignmentStatus"] == "needs_trim_or_extend"


def test_native_tts_track_name_exposes_selected_speed() -> None:
    workspace = _workspace(voiceover_provider="jianying_native_tts")
    workspace.exportPlan.voiceoverSpeed = 1.2

    draft = build_capcut_draft(workspace)

    native_track = next(track for track in draft["tracks"] if track["type"] == "text" and track["name"].startswith("最终字幕（剪映朗读源）"))
    assert native_track["name"] == "最终字幕（剪映朗读源）（按1.2x校准）"
    assert draft["extra_info"]["voiceover_speed"] == 1.2


def test_build_capcut_draft_uses_voiceover_script_when_no_segment_text() -> None:
    workspace = _workspace(voiceover_provider="jianying_native_tts", voiceover_script="整段口播稿")
    workspace.storyboard[0].subtitle = ""
    workspace.storyboard[1].subtitle = ""

    draft = build_capcut_draft(workspace)

    native_tracks = [track for track in draft["tracks"] if track["name"] == "最终字幕（剪映朗读源）"]
    assert len(native_tracks) == 1
    assert len(native_tracks[0]["segments"]) == 1
    native_material_id = native_tracks[0]["segments"][0]["material_id"]
    native_material = next(
        item for item in draft["materials"]["texts"] if item["id"] == native_material_id
    )
    assert json.loads(native_material["content"])["text"] == "整段口播稿。"


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


def test_deploy_capcut_draft_raises_when_folder_exists(tmp_path: Path) -> None:
    workspace = _workspace()
    folder_name = f"{workspace.project.id}-阿勒泰冬日氛围"
    existing = tmp_path / folder_name
    existing.mkdir(parents=True)
    (existing / "draft_content.json").write_text("{}", encoding="utf-8")

    with pytest.raises(CapcutDraftFolderExistsError):
        deploy_capcut_draft(workspace, draft_root=str(tmp_path))


def test_deploy_capcut_draft_clears_existing_folder_when_requested(tmp_path: Path) -> None:
    workspace = _workspace()
    folder_name = f"{workspace.project.id}-阿勒泰冬日氛围"
    existing = tmp_path / folder_name
    existing.mkdir(parents=True)
    stale = existing / "stale.txt"
    stale.write_text("old", encoding="utf-8")
    (existing / "draft_content.json").write_text("{}", encoding="utf-8")

    result = deploy_capcut_draft(workspace, draft_root=str(tmp_path), clear_existing=True)

    folder = Path(result.draft_folder_path)
    assert not stale.exists()
    assert (folder / "draft_content.json").exists()
    payload = json.loads((folder / "draft_content.json").read_text(encoding="utf-8"))
    assert payload["name"] == "阿勒泰冬日氛围"


def test_clear_draft_folder_contents_removes_files_and_subfolders(tmp_path: Path) -> None:
    folder = tmp_path / "draft"
    folder.mkdir()
    (folder / "draft_content.json").write_text("{}", encoding="utf-8")
    nested = folder / "assets"
    nested.mkdir()
    (nested / "clip.mp4").write_bytes(b"demo")

    clear_draft_folder_contents(folder)

    assert folder.is_dir()
    assert not any(folder.iterdir())


def test_build_text_content_matches_pyjianyingdraft_font_id() -> None:
    pytest.importorskip("pyJianYingDraft")
    from pyJianYingDraft import FontType

    meta = FontType.悠然体.value
    content = build_text_content("测试悠然体")
    parsed = json.loads(content)
    assert parsed["styles"][0]["font"]["id"] == meta.resource_id
