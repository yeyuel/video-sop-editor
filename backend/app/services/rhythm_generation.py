from __future__ import annotations

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, NarrativeThemeRead, RhythmPlanWriteRequest
from app.services.audio_analysis import BeatAnalysisResult
from app.services.audio_structure import suggest_dark_cuts_from_energy
from app.services.beat_grid import filter_beats_for_capcut_mode, normalize_beat_times
from app.services.rhythm_copy import resolve_rhythm_copy
from app.services.rhythm_profile import build_attention_beats, build_rhythm_profile
from app.services.rhythm_track import resolve_selected_track_name
from app.services.llm.progress import ProgressReporter, emit_progress


def recommend_beat_mode(video_type: str) -> str:
    """规则生成时的默认踩点模式（无音频时，语义对齐剪映）。"""
    if video_type in {"guide_video", "travel_montage"}:
        return "beat_2"
    if video_type == "vlog":
        return "strong_weak"
    return "beat_1"


def build_beat_points(target_duration_sec: int, interval: float) -> list[float]:
    beat_points: list[float] = []
    current = 0.0
    while current <= float(target_duration_sec):
        beat_points.append(round(current, 2))
        current += interval
    if beat_points and beat_points[-1] < float(target_duration_sec):
        beat_points.append(float(target_duration_sec))
    return beat_points or [0.0, float(target_duration_sec)]


def build_rule_dark_cuts(target_duration_sec: int) -> list[float]:
    return suggest_dark_cuts_from_energy([], float(target_duration_sec))


def build_photo_motion_suggestions(assets: list[AssetRead]) -> list[str]:
    if any(asset.mediaType == "photo" for asset in assets):
        return [
            "照片镜头建议保留 1 到 2 个节拍的停留，再配合轻微慢推或缩放，避免和视频镜头同频快切。",
            "如果当前段落以照片为主，可在 0.5 到 0.8 倍速度感的转场中保持节奏呼吸。",
        ]
    return ["当前以视频素材为主，可在情绪段落加入轻微速度变化，不必额外补照片动效。"]


def build_rhythm_notes(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
) -> list[str]:
    opening_asset = assets[0].scene if assets else "开场识别镜头"
    climax_asset = assets[-1].scene if assets else "高潮镜头"
    rhythm_profile = theme.rhythmProfile if theme else "按路线推进，节点提速，中段稳节奏"

    return [
        f"前 3 秒用 {opening_asset} 作为开头钩子，优先卡前 2 到 4 个主拍。",
        f"中段按“{rhythm_profile}”组织节奏，避免平均分配镜头。",
        f"在 {climax_asset} 所在段落预留 3/4 位置高潮，保证总时长接近 {project.target_duration_sec} 秒。",
    ]


def build_rule_rhythm_payload(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    on_progress: ProgressReporter | None = None,
) -> tuple[RhythmPlanWriteRequest, dict[str, str]]:
    emit_progress(on_progress, "building_beats", "正在按项目时长生成节拍点…", progress=18)
    beat_mode = recommend_beat_mode(project.video_type)
    fine_beats = normalize_beat_times(
        build_beat_points(project.target_duration_sec, 0.25),
        float(project.target_duration_sec),
    )
    coarse_beats = normalize_beat_times(
        [fine_beats[index] for index in range(0, len(fine_beats), 2)],
        float(project.target_duration_sec),
    )
    beat_points = filter_beats_for_capcut_mode(
        fine_beats,
        beat_mode,
        float(project.target_duration_sec),
        coarse_beats=coarse_beats,
    )
    bgm_style_fallback = theme.rhythmProfile if theme else "快起快收，中段稳节奏"
    rhythm_notes_fallback = build_rhythm_notes(project, assets, theme)
    bgm_style, rhythm_notes, llm_meta = resolve_rhythm_copy(
        project,
        assets,
        theme,
        bpm=0,
        beat_mode=beat_mode,
        beat_point_count=len(beat_points),
        analysis_source="rule",
        bgm_style_fallback=bgm_style_fallback,
        rhythm_notes_fallback=rhythm_notes_fallback,
        on_progress=on_progress,
    )
    rhythm_profile = build_rhythm_profile(project, assets, theme)
    attention_beats = build_attention_beats(project, rhythm_profile["mode"])

    return RhythmPlanWriteRequest(
        bgmStyle=bgm_style,
        selectedTrackName=resolve_selected_track_name(project, theme),
        audioFileName="",
        analysisSource="rule",
        analysisNotes=["当前为规则生成节拍点，依据项目时长、视频类型和剪映踩点语义进行估算。"],
        detectedBpm=0,
        audioDurationSec=0.0,
        rawBeatPoints=fine_beats,
        coarseBeatPoints=coarse_beats,
        beatMode=beat_mode,
        beatPoints=beat_points,
        rhythmNotes=rhythm_notes,
        darkCutSuggestions=build_rule_dark_cuts(project.target_duration_sec),
        photoMotionSuggestions=build_photo_motion_suggestions(assets),
        rhythmProfile=rhythm_profile,
        attentionBeats=attention_beats,
        beatCalibration={
            "source": "rule",
            "beatOffsetSec": 0,
            "densityMode": beat_mode,
            "referenceBeatPoints": [],
        },
        audioFingerprint="",
        audioAnalysisVersion="rule_v1",
    ), llm_meta


def build_audio_rhythm_payload(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    audio_file_name: str,
    analysis: BeatAnalysisResult,
    audio_file_fingerprint: str = "",
    on_progress: ProgressReporter | None = None,
) -> tuple[RhythmPlanWriteRequest, dict[str, str]]:
    bgm_style, rhythm_notes, llm_meta = resolve_rhythm_copy(
        project,
        assets,
        theme,
        bpm=analysis.bpm,
        beat_mode=analysis.beat_mode,
        beat_point_count=len(analysis.beat_points),
        analysis_source="audio_upload",
        bgm_style_fallback=analysis.bgm_style,
        rhythm_notes_fallback=build_rhythm_notes(project, assets, theme),
        on_progress=on_progress,
    )
    rhythm_profile = build_rhythm_profile(project, assets, theme)
    attention_beats = build_attention_beats(project, rhythm_profile["mode"])

    return RhythmPlanWriteRequest(
        bgmStyle=bgm_style,
        selectedTrackName=resolve_selected_track_name(
            project,
            theme,
            audio_file_name=audio_file_name,
        ),
        audioFileName=audio_file_name,
        analysisSource="audio_upload",
        analysisNotes=analysis.analysis_notes,
        detectedBpm=analysis.bpm,
        audioDurationSec=analysis.audio_duration_sec,
        rawBeatPoints=analysis.raw_beat_times,
        coarseBeatPoints=analysis.coarse_beat_times,
        beatMode=analysis.beat_mode,
        beatPoints=analysis.beat_points,
        rhythmNotes=rhythm_notes
        + [f"当前节拍点来自音频分析（{analysis.analysis_engine}），识别 BPM 为 {analysis.bpm}。"],
        darkCutSuggestions=analysis.dark_cut_suggestions,
        photoMotionSuggestions=build_photo_motion_suggestions(assets),
        rhythmProfile=rhythm_profile,
        attentionBeats=attention_beats,
        beatCalibration={
            "source": "audio_upload",
            "beatOffsetSec": 0,
            "densityMode": analysis.beat_mode,
            "referenceBeatPoints": [],
            "confidence": "auto",
        },
        audioFingerprint=(
            f"{audio_file_fingerprint}:{analysis.audio_duration_sec}:"
            f"{analysis.bpm}:{analysis.analysis_engine}"
            if audio_file_fingerprint
            else f"{audio_file_name}:{analysis.audio_duration_sec}:{analysis.bpm}"
        ),
        audioAnalysisVersion=analysis.analysis_engine,
    ), llm_meta


def build_rule_fallback_rhythm_payload(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    *,
    audio_file_name: str = "",
    failure_reason: str,
    on_progress: ProgressReporter | None = None,
) -> tuple[RhythmPlanWriteRequest, dict[str, str]]:
    payload, llm_meta = build_rule_rhythm_payload(
        project, assets, theme, on_progress=on_progress
    )
    return payload.model_copy(
        update={
            "selectedTrackName": resolve_selected_track_name(
                project,
                theme,
                audio_file_name=audio_file_name,
                existing_name=payload.selectedTrackName,
            ),
            "audioFileName": "",
            "analysisSource": "rule_fallback",
            "analysisNotes": [
                f"音频识别失败（{audio_file_name or '未命名文件'}）：{failure_reason}",
                "请重新下载所选 BGM 并上传有效音频文件，完成节拍识别后再进入分镜。",
            ],
            "detectedBpm": 0,
            "audioDurationSec": 0.0,
            "beatMode": "none",
            "beatPoints": [],
            "rawBeatPoints": [],
            "coarseBeatPoints": [],
        }
    ), llm_meta
