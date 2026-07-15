import type { RhythmPlan } from "@/types/domain";

export function isRhythmAnalyzed(plan: RhythmPlan | null | undefined): boolean {
  if (!plan) {
    return false;
  }
  return (
    plan.bgmPhase === "analyzed" &&
    plan.analysisSource === "audio_upload" &&
    (plan.beatPoints?.length ?? 0) > 0 &&
    Boolean(plan.selectedBgmId) &&
    Boolean(plan.audioFileName)
  );
}

export function getBgmPhaseLabel(phase: RhythmPlan["bgmPhase"]): string {
  if (phase === "recommended") {
    return "已推荐，待选定并上传";
  }
  if (phase === "analyzed") {
    return "已上传并识别节拍";
  }
  return "待 LLM 推荐 BGM";
}
