from __future__ import annotations

from app.models.schemas import RhythmPlanRead


def rhythm_ready_for_storyboard(rhythm: RhythmPlanRead | None) -> bool:
    if not rhythm:
        return False
    return (
        rhythm.bgmPhase == "analyzed"
        and rhythm.analysisSource == "audio_upload"
        and bool(rhythm.selectedBgmId)
        and bool(rhythm.beatPoints)
        and bool(rhythm.audioFileName)
    )


def rhythm_requirement_message(rhythm: RhythmPlanRead | None) -> str:
    if not rhythm or rhythm.bgmPhase == "empty":
        return "请先在节奏页使用 LLM 推荐 BGM。"
    if not rhythm.selectedBgmId:
        return "请先从 BGM 推荐列表中选择一首曲目。"
    if rhythm.bgmPhase != "analyzed" or rhythm.analysisSource != "audio_upload":
        return "请下载所选 BGM 并上传音频，完成节拍识别后再进入分镜。"
    if not rhythm.beatPoints:
        return "当前节拍点为空，请重新上传 BGM 音频并完成识别。"
    return ""
