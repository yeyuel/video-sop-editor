from __future__ import annotations

import os

from app.models.entities import ProjectEntity
from app.models.schemas import AssetRead, NarrativeThemeRead, RhythmPlanWriteRequest
from app.services.audio_analysis import BeatAnalysisResult
from app.services.beat_grid import filter_beats_for_capcut_mode, normalize_beat_times


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


def build_dark_cuts(target_duration_sec: int) -> list[float]:
    return [
        round(target_duration_sec * 0.25, 2),
        round(target_duration_sec * 0.5, 2),
        round(target_duration_sec * 0.75, 2),
    ]


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
) -> RhythmPlanWriteRequest:
    beat_mode = recommend_beat_mode(project.video_type)
    base_beats = build_beat_points(project.target_duration_sec, 0.25)
    raw_beats = normalize_beat_times(base_beats, float(project.target_duration_sec))
    beat_points = filter_beats_for_capcut_mode(
        raw_beats,
        beat_mode,
        float(project.target_duration_sec),
    )

    return RhythmPlanWriteRequest(
        bgmStyle=theme.rhythmProfile if theme else "快起快收，中段稳节奏",
        selectedTrackName=f"{project.id}-demo-track",
        audioFileName="",
        analysisSource="rule",
        analysisNotes=["当前为规则生成节拍点，依据项目时长、视频类型和剪映踩点语义进行估算。"],
        detectedBpm=0,
        audioDurationSec=0.0,
        rawBeatPoints=[],
        beatMode=beat_mode,
        beatPoints=beat_points,
        rhythmNotes=build_rhythm_notes(project, assets, theme),
        darkCutSuggestions=build_dark_cuts(project.target_duration_sec),
        photoMotionSuggestions=build_photo_motion_suggestions(assets),
    )


def build_audio_rhythm_payload(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    audio_file_name: str,
    analysis: BeatAnalysisResult,
) -> RhythmPlanWriteRequest:
    return RhythmPlanWriteRequest(
        bgmStyle=analysis.bgm_style,
        selectedTrackName=os.path.splitext(audio_file_name)[0],
        audioFileName=audio_file_name,
        analysisSource="audio_upload",
        analysisNotes=analysis.analysis_notes,
        detectedBpm=analysis.bpm,
        audioDurationSec=analysis.audio_duration_sec,
        rawBeatPoints=analysis.raw_beat_times,
        beatMode=analysis.beat_mode,
        beatPoints=analysis.beat_points,
        rhythmNotes=build_rhythm_notes(project, assets, theme)
        + [f"当前节拍点来自音频分析（{analysis.analysis_engine}），识别 BPM 为 {analysis.bpm}。"],
        darkCutSuggestions=analysis.dark_cut_suggestions,
        photoMotionSuggestions=build_photo_motion_suggestions(assets),
    )


def build_rule_fallback_rhythm_payload(
    project: ProjectEntity,
    assets: list[AssetRead],
    theme: NarrativeThemeRead | None,
    *,
    audio_file_name: str = "",
    failure_reason: str,
) -> RhythmPlanWriteRequest:
    payload = build_rule_rhythm_payload(project, assets, theme)
    return payload.model_copy(
        update={
            "audioFileName": "",
            "analysisSource": "rule_fallback",
            "analysisNotes": [
                f"音频识别失败（{audio_file_name or '未命名文件'}），已自动回退到规则生成：{failure_reason}",
                "你可以重新上传音频，或继续手工调整节拍点。",
            ],
            "detectedBpm": 0,
            "audioDurationSec": 0.0,
            "rawBeatPoints": [],
        }
    )
