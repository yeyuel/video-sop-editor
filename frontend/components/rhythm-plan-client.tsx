"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import {
  deleteRhythmAudio,
  recommendBgm,
  saveRhythmPlan,
  selectBgmRecommendation,
  uploadRhythmAudio
} from "@/lib/browser-api";
import { describeLlmStatus, llmNoticeTone } from "@/lib/llm-status";
import {
  aiInputClassName,
  AiFieldLabel,
  AiSuggestHint,
  clearSuggestedField
} from "@/lib/ai-field-ui";
import {
  BGM_RECOMMEND_LLM_STAGES,
  RHYTHM_LLM_STAGES,
  type LlmProgressViewState
} from "@/lib/llm-progress-stages";
import { getBgmPhaseLabel, isRhythmAnalyzed } from "@/lib/rhythm-workflow";
import { useLlmProgress } from "@/lib/use-llm-progress";
import {
  applyBeatCalibration,
  capcutBeatModeOptions,
  filterBeatsForCapcutMode,
  getCapcutBeatModeDescription,
  getCapcutBeatModeLabel
} from "@/lib/capcut-beat";
import type { BgmRecommendation, RhythmPlan } from "@/types/domain";

type RhythmPlanClientProps = {
  projectId: string;
  targetDurationSec: number;
  initialPlan: RhythmPlan | null | undefined;
};

function listToText(value: string[]) {
  return value.join("\n");
}

function numberListToText(value: number[]) {
  return value.join(", ");
}

function parseTextList(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseNumberList(value: string) {
  return value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => !Number.isNaN(item));
}

function parseOptionalNumber(value: string) {
  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function clampBeatOffset(value: number) {
  return Math.min(0.5, Math.max(-0.5, value));
}

function formatBeatOffset(value: number) {
  const rounded = Math.round(value * 100) / 100;
  return Object.is(rounded, -0) ? "0" : String(rounded);
}

function formatBeatScale(value: number) {
  const rounded = Math.round(value * 10000) / 10000;
  return Object.is(rounded, -0) ? "1" : String(rounded || 1);
}

function shortFingerprint(value: string) {
  if (!value) {
    return "暂无";
  }
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

function summarizeBeatPoints(points: number[], limit = 18) {
  if (!points.length) {
    return "暂无";
  }
  const visible = points.slice(0, limit).map((point) => Number(point.toFixed(2)));
  const suffix = points.length > limit ? ` ... 共 ${points.length} 个` : ` 共 ${points.length} 个`;
  return `${visible.join(", ")}${suffix}`;
}

function estimateBeatOffsetFromReference(systemBeatPoints: number[], referenceBeatPoints: number[]) {
  if (!systemBeatPoints.length || !referenceBeatPoints.length) {
    return 0;
  }
  const offsets = referenceBeatPoints.map((reference) => {
    const nearest = systemBeatPoints.reduce((best, current) =>
      Math.abs(current - reference) < Math.abs(best - reference) ? current : best
    );
    return reference - nearest;
  });
  const sorted = [...offsets].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
  return clampBeatOffset(Math.round(median * 100) / 100);
}

function estimateBeatCalibrationFromReference(
  systemBeatPoints: number[],
  referenceBeatPoints: number[]
) {
  const offset = estimateBeatOffsetFromReference(systemBeatPoints, referenceBeatPoints);
  if (systemBeatPoints.length < 2 || referenceBeatPoints.length < 2) {
    return { offset, scale: 1 };
  }

  const pairs: Array<[number, number]> = [];
  const used = new Set<number>();
  for (const reference of [...referenceBeatPoints].sort((a, b) => a - b)) {
    const nearest = systemBeatPoints.reduce((best, current) =>
      Math.abs(current - reference) < Math.abs(best - reference) ? current : best
    );
    if (used.has(nearest)) {
      continue;
    }
    used.add(nearest);
    pairs.push([nearest, reference]);
  }
  if (pairs.length < 2) {
    return { offset, scale: 1 };
  }

  const meanSystem = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanReference = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  const denominator = pairs.reduce((sum, pair) => sum + (pair[0] - meanSystem) ** 2, 0);
  if (denominator <= 0) {
    return { offset, scale: 1 };
  }

  const rawScale =
    pairs.reduce(
      (sum, pair) => sum + (pair[0] - meanSystem) * (pair[1] - meanReference),
      0
    ) / denominator;
  const scale = Math.min(1.05, Math.max(0.95, rawScale));
  const scaledOffset = clampBeatOffset(meanReference - scale * meanSystem);
  return {
    offset: Math.round(scaledOffset * 100) / 100,
    scale: Math.round(scale * 10000) / 10000
  };
}

function beatReferenceMatchError(systemBeatPoints: number[], referenceBeatPoints: number[]) {
  if (!systemBeatPoints.length || !referenceBeatPoints.length) {
    return Number.POSITIVE_INFINITY;
  }
  const distances = referenceBeatPoints
    .map((reference) =>
      Math.min(...systemBeatPoints.map((system) => Math.abs(system - reference)))
    )
    .sort((a, b) => a - b);
  const middle = Math.floor(distances.length / 2);
  return distances.length % 2 === 0
    ? (distances[middle - 1] + distances[middle]) / 2
    : distances[middle];
}

function recommendBeatModeFromReference(
  rawBeatPoints: number[],
  coarseBeatPoints: number[],
  referenceBeatPoints: number[],
  targetDurationSec: number,
  currentMode: string
) {
  if (!rawBeatPoints.length || referenceBeatPoints.length < 2) {
    return currentMode;
  }
  let bestMode = currentMode && currentMode !== "none" ? currentMode : "beat_1";
  let bestScore = Number.POSITIVE_INFINITY;
  for (const mode of ["beat_1", "beat_2", "strong_weak"]) {
    const candidate = filterBeatsForCapcutMode(
      rawBeatPoints,
      mode,
      targetDurationSec,
      coarseBeatPoints
    );
    const calibration = estimateBeatCalibrationFromReference(candidate, referenceBeatPoints);
    const calibrated = applyBeatCalibration(
      candidate,
      targetDurationSec,
      calibration.offset,
      calibration.scale
    );
    const densityGap =
      Math.abs(calibrated.length - referenceBeatPoints.length) /
      Math.max(referenceBeatPoints.length, 1);
    const score = beatReferenceMatchError(calibrated, referenceBeatPoints) + densityGap * 0.03;
    if (score < bestScore) {
      bestScore = score;
      bestMode = mode;
    }
  }
  return bestMode;
}

function getAnalysisSourceLabel(source: string) {
  if (source === "audio_upload") {
    return "音频识别";
  }
  if (source === "rule_fallback") {
    return "识别失败回退";
  }
  return "待上传 BGM";
}

function formatTrackLabel(item: BgmRecommendation) {
  return item.artist ? `${item.artist} - ${item.title}` : item.title;
}

function getRhythmModeLabel(mode?: string) {
  const labels: Record<string, string> = {
    highlight_reel: "射门集锦型",
    seed_and_guide: "种草攻略型",
    chapter_explainer: "章节讲解型",
    emotional_vlog: "情绪 Vlog 型",
    stable_story: "稳定叙事型",
    chapter_story: "章节故事型"
  };
  return mode ? labels[mode] ?? mode : "未生成";
}

function getCutDensityLabel(value?: string) {
  const labels: Record<string, string> = {
    fast: "快切",
    medium_fast: "中快",
    medium: "中速",
    medium_slow: "中慢",
    chaptered: "章节化"
  };
  return value ? labels[value] ?? value : "未生成";
}

function getCalibrationLabel(source?: string) {
  const labels: Record<string, string> = {
    rule: "规则估算",
    bgm_recommend: "等待音频",
    audio_upload: "音频识别",
    manual: "手动调整"
  };
  return source ? labels[source] ?? source : "未校准";
}

type RhythmSuggestField =
  | "bgmStyle"
  | "selectedTrackName"
  | "beatMode"
  | "darkCuts"
  | "beatPoints"
  | "rhythmNotes"
  | "photoMotion";

type RhythmFormSnapshot = {
  bgmStyle: string;
  beatMode: string;
  beatPointsText: string;
  darkCutsText: string;
  photoText: string;
  rhythmNotesText: string;
  selectedTrackName: string;
};

function snapshotRhythmForm(
  plan: RhythmPlan,
  texts: Pick<
    RhythmFormSnapshot,
    "beatPointsText" | "darkCutsText" | "photoText" | "rhythmNotesText"
  >
): RhythmFormSnapshot {
  return {
    bgmStyle: plan.bgmStyle,
    selectedTrackName: plan.selectedTrackName,
    beatMode: plan.beatMode,
    beatPointsText: texts.beatPointsText,
    darkCutsText: texts.darkCutsText,
    rhythmNotesText: texts.rhythmNotesText,
    photoText: texts.photoText
  };
}

function detectRhythmSuggested(before: RhythmFormSnapshot, after: RhythmFormSnapshot) {
  const fields: RhythmSuggestField[] = [];
  if (after.bgmStyle.trim() && after.bgmStyle !== before.bgmStyle) {
    fields.push("bgmStyle");
  }
  if (after.selectedTrackName.trim() && after.selectedTrackName !== before.selectedTrackName) {
    fields.push("selectedTrackName");
  }
  if (after.beatMode.trim() && after.beatMode !== before.beatMode) {
    fields.push("beatMode");
  }
  if (after.darkCutsText.trim() && after.darkCutsText !== before.darkCutsText) {
    fields.push("darkCuts");
  }
  if (after.beatPointsText.trim() && after.beatPointsText !== before.beatPointsText) {
    fields.push("beatPoints");
  }
  if (after.rhythmNotesText.trim() && after.rhythmNotesText !== before.rhythmNotesText) {
    fields.push("rhythmNotes");
  }
  if (after.photoText.trim() && after.photoText !== before.photoText) {
    fields.push("photoMotion");
  }
  return fields;
}

function mergeSuggestedFields(current: RhythmSuggestField[], detected: RhythmSuggestField[]) {
  return [...new Set([...current, ...detected])];
}

function emptyRhythmPlan(): RhythmPlan {
  return {
    bgmStyle: "",
    selectedTrackName: "",
    audioFileName: "",
    audioFilePath: "",
    analysisSource: "manual",
    analysisNotes: [],
    detectedBpm: 0,
    audioDurationSec: 0,
    rawBeatPoints: [],
    coarseBeatPoints: [],
    beatMode: "none",
    beatPoints: [],
    rhythmNotes: [],
    darkCutSuggestions: [],
    photoMotionSuggestions: [],
    recommendedBgm: [],
    selectedBgmId: "",
    bgmPhase: "empty",
    rhythmProfile: {},
    attentionBeats: [],
    beatCalibration: {},
    audioFingerprint: "",
    audioAnalysisVersion: ""
  };
}

function asNumberList(value: unknown) {
  return Array.isArray(value)
    ? value.map((item) => Number(item)).filter((item) => Number.isFinite(item))
    : [];
}

function asStringList(value: unknown) {
  return Array.isArray(value)
    ? value.map((item) => String(item).trim()).filter(Boolean)
    : [];
}

function asObjectRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

const idleLlmProgressState: LlmProgressViewState = {
  title: "",
  stages: BGM_RECOMMEND_LLM_STAGES,
  currentStage: "preparing",
  message: "",
  detail: "",
  progress: 0,
  startedAt: 0
};

function normalizeRhythmPlan(plan: RhythmPlan | null | undefined): RhythmPlan {
  const source = plan ?? emptyRhythmPlan();
  return {
    ...emptyRhythmPlan(),
    ...source,
    analysisNotes: asStringList(source.analysisNotes),
    attentionBeats: Array.isArray(source.attentionBeats) ? source.attentionBeats : [],
    beatCalibration: asObjectRecord(source.beatCalibration) as RhythmPlan["beatCalibration"],
    beatPoints: asNumberList(source.beatPoints),
    coarseBeatPoints: asNumberList(source.coarseBeatPoints),
    darkCutSuggestions: asNumberList(source.darkCutSuggestions),
    photoMotionSuggestions: asStringList(source.photoMotionSuggestions),
    rawBeatPoints: asNumberList(source.rawBeatPoints),
    recommendedBgm: Array.isArray(source.recommendedBgm)
      ? source.recommendedBgm.map((item) => ({
          ...item,
          styleTags: asStringList(item.styleTags)
        }))
      : [],
    rhythmNotes: asStringList(source.rhythmNotes),
    rhythmProfile: asObjectRecord(source.rhythmProfile) as RhythmPlan["rhythmProfile"],
    audioFingerprint: source.audioFingerprint ?? "",
    audioAnalysisVersion: source.audioAnalysisVersion ?? ""
  };
}

export function RhythmPlanClient({
  projectId,
  targetDurationSec,
  initialPlan
}: RhythmPlanClientProps) {
  const router = useRouter();
  const normalizedInitialPlan = normalizeRhythmPlan(initialPlan);
  const [plan, setPlan] = useState(normalizedInitialPlan);
  const [beatPointsText, setBeatPointsText] = useState(
    numberListToText(normalizedInitialPlan.beatPoints)
  );
  const [beatOffsetText, setBeatOffsetText] = useState(
    String(normalizedInitialPlan.beatCalibration?.beatOffsetSec ?? 0)
  );
  const [beatScaleText, setBeatScaleText] = useState(
    String(normalizedInitialPlan.beatCalibration?.beatScale ?? 1)
  );
  const [referenceBeatPointsText, setReferenceBeatPointsText] = useState(
    numberListToText(normalizedInitialPlan.beatCalibration?.referenceBeatPoints ?? [])
  );
  const [rhythmNotesText, setRhythmNotesText] = useState(
    listToText(normalizedInitialPlan.rhythmNotes)
  );
  const [darkCutsText, setDarkCutsText] = useState(
    numberListToText(normalizedInitialPlan.darkCutSuggestions)
  );
  const [photoText, setPhotoText] = useState(
    listToText(normalizedInitialPlan.photoMotionSuggestions)
  );
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [isPending, startTransition] = useTransition();
  const { llmProgress, isLlmRunning, start, onProgress, finish } = useLlmProgress();
  const [llmSuggestedFields, setLlmSuggestedFields] = useState<RhythmSuggestField[]>([]);

  const rhythmAnalyzed = isRhythmAnalyzed(plan);
  const canUploadAudio = Boolean(plan.selectedBgmId);
  const canEditBeats = rhythmAnalyzed;
  const referenceBeatPoints = parseNumberList(referenceBeatPointsText);
  const currentOutputBeatPoints = parseNumberList(beatPointsText);
  const baseModeBeatPoints = useMemo(() => {
    if (plan.rawBeatPoints.length > 0 && plan.beatMode !== "none") {
      return filterBeatsForCapcutMode(
        plan.rawBeatPoints,
        plan.beatMode,
        targetDurationSec,
        plan.coarseBeatPoints
      );
    }
    return currentOutputBeatPoints;
  }, [
    currentOutputBeatPoints,
    plan.beatMode,
    plan.coarseBeatPoints,
    plan.rawBeatPoints,
    targetDurationSec
  ]);
  const calibratedPreviewBeatPoints = useMemo(
    () =>
      applyBeatCalibration(
        baseModeBeatPoints,
        targetDurationSec,
        parseOptionalNumber(beatOffsetText),
        parseOptionalNumber(beatScaleText) || 1
      ),
    [baseModeBeatPoints, beatOffsetText, beatScaleText, targetDurationSec]
  );

  const selectedRecommendation = useMemo(
    () => plan.recommendedBgm.find((item) => item.id === plan.selectedBgmId) ?? null,
    [plan.recommendedBgm, plan.selectedBgmId]
  );

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function showError(message: string) {
    setError(message);
    setNotice({ title: "操作失败", message, tone: "error" });
  }

  function syncFromPlan(nextPlan: RhythmPlan) {
    const normalizedPlan = normalizeRhythmPlan(nextPlan);
    setPlan(normalizedPlan);
    setBeatPointsText(numberListToText(normalizedPlan.beatPoints));
    setBeatOffsetText(String(normalizedPlan.beatCalibration?.beatOffsetSec ?? 0));
    setBeatScaleText(String(normalizedPlan.beatCalibration?.beatScale ?? 1));
    setReferenceBeatPointsText(
      numberListToText(normalizedPlan.beatCalibration?.referenceBeatPoints ?? [])
    );
    setRhythmNotesText(listToText(normalizedPlan.rhythmNotes));
    setDarkCutsText(numberListToText(normalizedPlan.darkCutSuggestions));
    setPhotoText(listToText(normalizedPlan.photoMotionSuggestions));
  }

  function handleRecommendBgm() {
    setError("");
    start("LLM 推荐 BGM", BGM_RECOMMEND_LLM_STAGES);
    startTransition(async () => {
      const before = snapshotRhythmForm(plan, {
        beatPointsText,
        darkCutsText,
        photoText,
        rhythmNotesText
      });
      try {
        const { data: nextPlan, meta } = await recommendBgm(projectId, onProgress);
        syncFromPlan(nextPlan);
        const after = snapshotRhythmForm(nextPlan, {
          beatPointsText: numberListToText(nextPlan.beatPoints),
          darkCutsText: numberListToText(nextPlan.darkCutSuggestions),
          photoText: listToText(nextPlan.photoMotionSuggestions),
          rhythmNotesText: listToText(nextPlan.rhythmNotes)
        });
        setLlmSuggestedFields((current) =>
          mergeSuggestedFields(current, detectRhythmSuggested(before, after))
        );
        router.refresh();
        const llmNotice = describeLlmStatus(meta);
        if (llmNotice) {
          setNotice({
            title: llmNotice.title,
            message: llmNotice.message,
            tone: llmNoticeTone(llmNotice.tone)
          });
        } else {
          setNotice({
            title: "BGM 推荐已生成",
            message: "请选定一首曲目，下载后上传音频以识别真实节拍。"
          });
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "BGM 推荐失败，请稍后重试。"
        );
      } finally {
        finish();
      }
    });
  }

  function handleSelectBgm(recommendationId: string) {
    setError("");
    startTransition(async () => {
      const before = snapshotRhythmForm(plan, {
        beatPointsText,
        darkCutsText,
        photoText,
        rhythmNotesText
      });
      try {
        const nextPlan = await selectBgmRecommendation(projectId, recommendationId);
        syncFromPlan(nextPlan);
        const after = snapshotRhythmForm(nextPlan, {
          beatPointsText: numberListToText(nextPlan.beatPoints),
          darkCutsText: numberListToText(nextPlan.darkCutSuggestions),
          photoText: listToText(nextPlan.photoMotionSuggestions),
          rhythmNotesText: listToText(nextPlan.rhythmNotes)
        });
        setLlmSuggestedFields((current) =>
          mergeSuggestedFields(current, detectRhythmSuggested(before, after))
        );
        router.refresh();
        setNotice({
          title: "已选定 BGM",
          message: "请到音乐平台搜索并下载该曲目，然后回到此页上传音频。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "选定 BGM 失败，请稍后重试。"
        );
      }
    });
  }

  async function handleCopySearchHint(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setNotice({ title: "已复制", message: "搜索关键词已复制到剪贴板。" });
    } catch {
      showError("复制失败，请手动复制搜索词。");
    }
  }

  function handleBeatModeChange(nextMode: string) {
    if (!canEditBeats) {
      return;
    }
    setPlan((current) => {
      const nextPlan = { ...current, beatMode: nextMode };
      if (current.rawBeatPoints.length > 0 && nextMode !== "none") {
        const filtered = filterBeatsForCapcutMode(
          current.rawBeatPoints,
          nextMode,
          targetDurationSec,
          current.coarseBeatPoints
        );
        setBeatPointsText(
          numberListToText(
            applyBeatCalibration(
              filtered,
              targetDurationSec,
              parseOptionalNumber(beatOffsetText),
              parseOptionalNumber(beatScaleText) || 1
            )
          )
        );
      }
      return nextPlan;
    });
  }

  function handleBeatOffsetChange(nextValue: string) {
    setBeatOffsetText(nextValue);
    applyBeatCalibrationPreview(parseOptionalNumber(nextValue), parseOptionalNumber(beatScaleText) || 1);
  }

  function handleBeatOffsetSliderChange(nextValue: string) {
    const offset = clampBeatOffset(Number(nextValue));
    setBeatOffsetText(formatBeatOffset(offset));
    applyBeatCalibrationPreview(offset, parseOptionalNumber(beatScaleText) || 1);
  }

  function applyBeatCalibrationPreview(offset: number, scale: number) {
    if (plan.rawBeatPoints.length > 0 && plan.beatMode !== "none") {
      const filtered = filterBeatsForCapcutMode(
        plan.rawBeatPoints,
        plan.beatMode,
        targetDurationSec,
        plan.coarseBeatPoints
      );
      setBeatPointsText(
        numberListToText(applyBeatCalibration(filtered, targetDurationSec, offset, scale))
      );
    } else {
      setBeatPointsText(
        numberListToText(
          applyBeatCalibration(parseNumberList(beatPointsText), targetDurationSec, offset, scale)
        )
      );
    }
  }

  function getBaseBeatPointsForCalibration() {
    if (plan.rawBeatPoints.length > 0 && plan.beatMode !== "none") {
      return filterBeatsForCapcutMode(
        plan.rawBeatPoints,
        plan.beatMode,
        targetDurationSec,
        plan.coarseBeatPoints
      );
    }
    return parseNumberList(beatPointsText);
  }

  function handleEstimateBeatOffsetFromReference() {
    if (!canEditBeats) {
      return;
    }
    const referencePoints = parseNumberList(referenceBeatPointsText);
    if (!referencePoints.length) {
      showError("请先填写剪映参考节拍点，例如：0.12, 0.62, 1.12。");
      return;
    }
    const recommendedMode = recommendBeatModeFromReference(
      plan.rawBeatPoints,
      plan.coarseBeatPoints,
      referencePoints,
      targetDurationSec,
      plan.beatMode
    );
    const baseBeatPoints =
      recommendedMode !== plan.beatMode && plan.rawBeatPoints.length > 0
        ? filterBeatsForCapcutMode(
            plan.rawBeatPoints,
            recommendedMode,
            targetDurationSec,
            plan.coarseBeatPoints
          )
        : getBaseBeatPointsForCalibration();
    const estimated = estimateBeatCalibrationFromReference(baseBeatPoints, referencePoints);
    if (recommendedMode !== plan.beatMode) {
      setPlan((current) => ({ ...current, beatMode: recommendedMode }));
    }
    setBeatOffsetText(formatBeatOffset(estimated.offset));
    setBeatScaleText(String(estimated.scale));
    setBeatPointsText(
      numberListToText(
        applyBeatCalibration(baseBeatPoints, targetDurationSec, estimated.offset, estimated.scale)
      )
    );
    setNotice({
      title: "已估算节拍校准",
      message: `推荐模式 ${recommendedMode}，偏移 ${formatBeatOffset(estimated.offset)}s，比例 ${estimated.scale}。保存后会用于分镜切点。`
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEditBeats) {
      showError("请先完成 BGM 推荐、选定曲目并上传音频识别节拍。");
      return;
    }
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await saveRhythmPlan(projectId, {
          ...plan,
          beatPoints: parseNumberList(beatPointsText),
          beatCalibration: {
            ...plan.beatCalibration,
            source: plan.analysisSource === "audio_upload" ? "manual" : plan.beatCalibration?.source,
            beatOffsetSec: parseOptionalNumber(beatOffsetText),
            beatScale: parseOptionalNumber(beatScaleText) || 1,
            densityMode: plan.beatMode,
            referenceBeatPoints: parseNumberList(referenceBeatPointsText)
          },
          rhythmNotes: parseTextList(rhythmNotesText),
          darkCutSuggestions: parseNumberList(darkCutsText),
          photoMotionSuggestions: parseTextList(photoText)
        });
        syncFromPlan(nextPlan);
        setLlmSuggestedFields([]);
        router.refresh();
        setNotice({ title: "节奏规划已保存", message: "当前节拍设置已写入项目。" });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "保存节奏规划失败，请稍后重试。"
        );
      }
    });
  }

  function handleAudioUpload() {
    if (!plan.selectedBgmId) {
      showError("请先从 BGM 推荐列表中选定一首曲目。");
      return;
    }
    if (!audioFile) {
      setError("请先选择一个音频文件。");
      return;
    }

    setError("");
    start("音频节拍识别", RHYTHM_LLM_STAGES);
    startTransition(async () => {
      const before = snapshotRhythmForm(plan, {
        beatPointsText,
        darkCutsText,
        photoText,
        rhythmNotesText
      });
      try {
        const { data: nextPlan, meta } = await uploadRhythmAudio(projectId, audioFile, onProgress);
        syncFromPlan(nextPlan);
        const after = snapshotRhythmForm(nextPlan, {
          beatPointsText: numberListToText(nextPlan.beatPoints),
          darkCutsText: numberListToText(nextPlan.darkCutSuggestions),
          photoText: listToText(nextPlan.photoMotionSuggestions),
          rhythmNotesText: listToText(nextPlan.rhythmNotes)
        });
        setLlmSuggestedFields((current) =>
          mergeSuggestedFields(current, detectRhythmSuggested(before, after))
        );
        setAudioFile(null);
        router.refresh();
        if (nextPlan.analysisSource === "rule_fallback") {
          setNotice({
            title: "音频识别失败",
            message:
              nextPlan.analysisNotes[0] ??
              "识别失败，请检查音频文件后重新上传。未完成识别前无法进入分镜。",
            tone: "error"
          });
        } else {
          const llmNotice = describeLlmStatus(meta);
          if (llmNotice && llmNotice.tone !== "success") {
            setNotice({
              title: llmNotice.title,
              message: llmNotice.message,
              tone: llmNoticeTone(llmNotice.tone)
            });
          } else {
            setNotice({
              title: "音频识别完成",
              message: `识别 BPM ${nextPlan.detectedBpm || "—"}，节拍点 ${nextPlan.beatPoints.length} 个。现在可以进入分镜。`
            });
          }
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "音频节拍识别失败，请稍后重试。"
        );
      } finally {
        finish();
      }
    });
  }

  function handleDeleteAudio() {
    if (!plan.audioFileName) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await deleteRhythmAudio(projectId);
        syncFromPlan(nextPlan);
        setAudioFile(null);
        router.refresh();
        setNotice({
          title: "音频已移除",
          message: "节拍点已清空，请重新上传所选 BGM 音频。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "移除音频失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      <BlockingNotice
        description="正在处理节奏相关操作，请稍候。"
        title="处理中"
        visible={isPending && !isLlmRunning}
      />
      <LlmProgressOverlay
        state={llmProgress ?? idleLlmProgressState}
        visible={isLlmRunning}
      />
      <ToastNotice
        message={notice?.message ?? ""}
        title={notice?.title ?? ""}
        tone={notice?.tone}
        visible={Boolean(notice)}
      />

      <div className="surface-ai px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-ink">BGM 工作流</p>
            <p className="mt-1 text-sm text-ink/65">
              ① LLM 推荐曲目 → ② 选定并自行下载 → ③ 上传音频识别节拍 → ④ 进入分镜
            </p>
          </div>
          <span className="badge-ai">当前：{getBgmPhaseLabel(plan.bgmPhase)}</span>
        </div>
      </div>

      <div className="surface-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-ink">平台节奏画像</h3>
            <p className="mt-1 text-sm text-ink/65">
              这里描述内容节奏结构；下方“节拍点”描述音乐卡点，两者会共同影响后续分镜。
            </p>
          </div>
          <span className="badge-ai">
            {getRhythmModeLabel(plan.rhythmProfile?.mode as string | undefined)}
          </span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="stat-cell">
            切镜密度：{getCutDensityLabel(plan.rhythmProfile?.cutDensity as string | undefined)}
          </div>
          <div className="stat-cell">
            字幕密度：{String(plan.rhythmProfile?.subtitleDensity ?? "未生成")}
          </div>
          <div className="stat-cell">
            校准状态：{getCalibrationLabel(plan.beatCalibration?.source)}
          </div>
        </div>
        {plan.rhythmProfile?.motionPolicy ? (
          <p className="mt-3 rounded-2xl bg-sand/60 px-4 py-3 text-sm leading-6 text-ink/70">
            动效策略：{String(plan.rhythmProfile.motionPolicy)}
          </p>
        ) : null}
        {plan.attentionBeats.length > 0 ? (
          <div className="mt-4 grid gap-2">
            <p className="text-sm font-medium text-ink/75">内容注意力点</p>
            <div className="flex flex-wrap gap-2">
              {plan.attentionBeats.map((beat, index) => (
                <span key={`${beat.time}-${beat.role}-${index}`} className="stat-pill">
                  {beat.time}s · {beat.label}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink/55">生成 BGM 推荐或上传音频后会同步生成注意力点。</p>
        )}
      </div>

      <div className="surface-panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-ink">BGM 推荐</h3>
            <p className="mt-1 text-sm text-ink/65">
              LLM 会推荐含真实歌名的候选曲目，并提供音乐平台搜索词（不提供下载链接）。
            </p>
          </div>
          <button
            type="button"
            onClick={handleRecommendBgm}
            disabled={isPending || isLlmRunning}
            className="btn-ai"
          >
            {isPending ? "推荐中..." : "LLM 推荐 BGM"}
          </button>
        </div>

        {plan.recommendedBgm.length > 0 ? (
          <div className="mt-4 grid gap-3">
            {plan.recommendedBgm.map((item) => (
              <div
                key={item.id}
                className={`rounded-2xl border px-4 py-4 transition ${
                  item.isSelected
                    ? "border-pine/30 bg-sand/60 shadow-soft"
                    : "border-line bg-white hover:border-pine/20"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-base font-semibold text-ink">{formatTrackLabel(item)}</p>
                      {item.isSelected ? <span className="badge-ai">已选定</span> : null}
                    </div>
                    <p className="mt-1 text-sm text-ink/65">
                      {item.mood} · BPM {item.bpmRange || "—"}
                      {item.styleTags.length > 0 ? ` · ${item.styleTags.join(" / ")}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => handleSelectBgm(item.id)}
                      disabled={isPending || item.isSelected}
                      className="btn-secondary px-4 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {item.isSelected ? "已选定" : "选这首"}
                    </button>
                    {item.searchHint ? (
                      <button
                        type="button"
                        onClick={() => handleCopySearchHint(item.searchHint)}
                        className="btn-ghost border border-line px-4 py-2 text-xs"
                      >
                        复制搜索词
                      </button>
                    ) : null}
                  </div>
                </div>
                {item.fitReason ? (
                  <p className="mt-3 text-sm leading-6 text-ink/70">{item.fitReason}</p>
                ) : null}
                {item.platformTips ? (
                  <p className="mt-2 text-xs text-ink/55">{item.platformTips}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-ink/55">尚未生成 BGM 推荐，请先点击上方按钮。</p>
        )}
      </div>

      <div className="surface-panel p-5">
        <h3 className="text-lg font-semibold text-ink">上传 BGM 并识别节拍</h3>
        <p className="mt-1 text-sm text-ink/65">
          {selectedRecommendation
            ? `当前选定：${formatTrackLabel(selectedRecommendation)}。请上传你下载的音频文件。`
            : "请先在上方推荐列表中选定一首 BGM。"}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleAudioUpload}
            disabled={isPending || isLlmRunning || !audioFile || !canUploadAudio}
            className="btn-primary"
          >
            {isPending ? "识别中..." : "上传音频并识别节拍"}
          </button>
          {plan.audioFileName ? (
            <button
              type="button"
              onClick={handleDeleteAudio}
              disabled={isPending || isLlmRunning}
              className="btn-danger"
            >
              移除已绑定音频
            </button>
          ) : null}
          <button
            type="submit"
            disabled={isPending || isLlmRunning || !canEditBeats}
            className="btn-secondary"
          >
            {isPending ? "保存中..." : "保存节奏规划"}
          </button>
        </div>

        <label className="mt-4 block">
          <span className="mb-2 block text-sm text-ink/75">
            音频上传（支持 WAV / MP3 / M4A / AAC / OGG / MGG / FLAC / WMA）
          </span>
          <input
            type="file"
            accept=".wav,.mp3,.m4a,.aac,.ogg,.mgg,.flac,.wma,audio/*"
            disabled={!canUploadAudio}
            onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
            className="input-field disabled:cursor-not-allowed disabled:bg-sand/40"
          />
          <p className="mt-2 text-xs text-ink/55">
            当前已绑定音频：{plan.audioFileName || "未上传"}，分析来源：
            {getAnalysisSourceLabel(plan.analysisSource)}
            {plan.detectedBpm > 0 ? `，识别 BPM：${plan.detectedBpm}` : ""}
            {plan.audioDurationSec > 0 ? `，音频时长：${plan.audioDurationSec}s` : ""}
            {plan.beatPoints.length > 0 ? `，节拍点：${plan.beatPoints.length} 个` : ""}
          </p>
          {plan.analysisNotes.length > 0 ? (
            <p className="mt-1 text-xs text-ink/55">{plan.analysisNotes.join(" / ")}</p>
          ) : null}
        </label>
      </div>

      {plan.analysisSource === "rule_fallback" ? (
        <div className="rounded-2xl border border-clay/25 bg-[#fff7f2] px-4 py-3 text-sm leading-6 text-clay">
          {plan.analysisNotes[0] ?? "音频识别失败，请重新上传 BGM 音频。"}
        </div>
      ) : null}

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {llmSuggestedFields.length > 0 ? (
        <AiSuggestHint count={llmSuggestedFields.length} />
      ) : null}

      <div className={`grid gap-5 md:grid-cols-2 ${canEditBeats ? "" : "opacity-60"}`}>
        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("bgmStyle")}>BGM 风格</AiFieldLabel>
          <input
            readOnly={!canEditBeats}
            value={plan.bgmStyle}
            onChange={(event) => {
              setPlan({ ...plan, bgmStyle: event.target.value });
              setLlmSuggestedFields((current) => clearSuggestedField(current, "bgmStyle"));
            }}
            placeholder="推荐 BGM 后自动填入"
            className={aiInputClassName(
              llmSuggestedFields.includes("bgmStyle"),
              "input-field disabled:bg-sand/40"
            )}
          />
        </label>

        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("selectedTrackName")}>
            参考曲目
          </AiFieldLabel>
          <input
            readOnly
            value={plan.selectedTrackName}
            placeholder="选定 BGM 后自动填入"
            className={aiInputClassName(
              llmSuggestedFields.includes("selectedTrackName"),
              "input-field bg-sand/30"
            )}
          />
        </label>

        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("beatMode")}>
            节拍模式（对标剪映）
          </AiFieldLabel>
          <select
            value={plan.beatMode}
            disabled={!canEditBeats}
            onChange={(event) => {
              handleBeatModeChange(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "beatMode"));
            }}
            className={aiInputClassName(
              llmSuggestedFields.includes("beatMode"),
              "input-field disabled:cursor-not-allowed disabled:bg-sand/40"
            )}
          >
            {capcutBeatModeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {getCapcutBeatModeDescription(plan.beatMode) ? (
            <p className="mt-2 text-xs text-ink/55">{getCapcutBeatModeDescription(plan.beatMode)}</p>
          ) : null}
        </label>

        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("darkCuts")}>
            暗场建议点（秒）
          </AiFieldLabel>
          <input
            readOnly={!canEditBeats}
            value={darkCutsText}
            onChange={(event) => {
              setDarkCutsText(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "darkCuts"));
            }}
            className={aiInputClassName(
              llmSuggestedFields.includes("darkCuts"),
              "input-field disabled:bg-sand/40"
            )}
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">整体节拍偏移（秒）</span>
          <div className="rounded-2xl border border-pine/20 bg-sand/30 px-4 py-4">
            <div className="flex items-center gap-4">
              <span className="text-xs text-ink/45">提前 -0.5s</span>
              <input
                type="range"
                min="-0.5"
                max="0.5"
                step="0.01"
                disabled={!canEditBeats}
                value={clampBeatOffset(parseOptionalNumber(beatOffsetText))}
                onChange={(event) => handleBeatOffsetSliderChange(event.target.value)}
                className="h-2 flex-1 cursor-pointer accent-pine disabled:cursor-not-allowed disabled:opacity-50"
              />
              <span className="text-xs text-ink/45">滞后 +0.5s</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <input
                readOnly={!canEditBeats}
                value={beatOffsetText}
                onChange={(event) => handleBeatOffsetChange(event.target.value)}
                onBlur={() =>
                  setBeatOffsetText(formatBeatOffset(clampBeatOffset(parseOptionalNumber(beatOffsetText))))
                }
                placeholder="例如：0.08 或 -0.12"
                className="w-36 rounded-full border border-pine/25 bg-white px-4 py-2 text-sm outline-none transition focus:border-pine disabled:bg-sand/40"
              />
              <span className="text-sm text-ink/60">
                当前偏移：{formatBeatOffset(clampBeatOffset(parseOptionalNumber(beatOffsetText)))}s
              </span>
              <button
                type="button"
                disabled={!canEditBeats}
                onClick={() => {
                  setBeatOffsetText("0");
                  setBeatScaleText("1");
                  applyBeatCalibrationPreview(0, 1);
                }}
                className="rounded-full border border-pine/20 bg-white px-3 py-2 text-xs font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-50"
              >
                归零
              </button>
            </div>
          </div>
          <p className="mt-2 text-xs text-ink/55">
            当系统节拍整体比剪映靠前或靠后时，在这里微调整体偏移；保存后分镜会使用校准后的节拍点。
          </p>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">剪映参考节拍点（可选）</span>
          <textarea
            readOnly={!canEditBeats}
            value={referenceBeatPointsText}
            onChange={(event) => setReferenceBeatPointsText(event.target.value)}
            placeholder="从剪映抄少量明显卡点，例如：0.12, 0.62, 1.12, 1.62"
            rows={4}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine disabled:bg-sand/40"
          />
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={!canEditBeats}
              onClick={handleEstimateBeatOffsetFromReference}
              className="rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-50"
            >
              根据参考点估算校准
            </button>
            <span className="text-xs text-ink/55">
              会估算节拍模式、整体偏移和轻微比例差，适合系统节拍与剪映密度或位置不一致的情况。
            </span>
          </div>
        </label>

        <div className="rounded-3xl border border-pine/15 bg-sand/25 p-4 md:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-ink">节拍校准追踪</h3>
              <p className="mt-1 text-xs leading-5 text-ink/55">
                用来对照“音频原始识别 → 当前剪映模式筛选 → 整体偏移校准 → 分镜实际使用”的变化。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-white px-3 py-1 text-xs text-ink/55">
                偏移 {formatBeatOffset(clampBeatOffset(parseOptionalNumber(beatOffsetText)))}s
              </span>
              <span className="rounded-full bg-white px-3 py-1 text-xs text-ink/55">
                比例 {formatBeatScale(parseOptionalNumber(beatScaleText) || 1)}
              </span>
            </div>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">节拍模式</span>
              {getCapcutBeatModeLabel(plan.beatMode)}
              {plan.beatCalibration?.densityMode ? ` / 推荐 ${getCapcutBeatModeLabel(plan.beatCalibration.densityMode)}` : ""}
            </div>
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">校准来源</span>
              {getCalibrationLabel(plan.beatCalibration?.source)}
              {plan.beatCalibration?.confidence ? ` / 可信度 ${plan.beatCalibration.confidence}` : ""}
            </div>
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">音频分析</span>
              {plan.audioAnalysisVersion || "未记录"} / {shortFingerprint(plan.audioFingerprint)}
            </div>
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">点位数量</span>
              原始 {plan.rawBeatPoints.length} / 粗拍 {plan.coarseBeatPoints.length} / 输出{" "}
              {currentOutputBeatPoints.length}
            </div>
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">模式筛选</span>
              筛选后 {baseModeBeatPoints.length} / 参考 {referenceBeatPoints.length} / 预览{" "}
              {calibratedPreviewBeatPoints.length}
            </div>
            <div className="rounded-2xl bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65">
              <span className="block font-medium text-ink">计算公式</span>
              筛选点 × {formatBeatScale(parseOptionalNumber(beatScaleText) || 1)} +{" "}
              {formatBeatOffset(clampBeatOffset(parseOptionalNumber(beatOffsetText)))}s
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl bg-white/80 p-3">
              <div className="text-xs font-medium text-ink/55">原始识别点</div>
              <p className="mt-2 text-sm leading-6 text-ink/75">
                {summarizeBeatPoints(plan.rawBeatPoints)}
              </p>
            </div>
            <div className="rounded-2xl bg-white/80 p-3">
              <div className="text-xs font-medium text-ink/55">当前模式筛选点</div>
              <p className="mt-2 text-sm leading-6 text-ink/75">
                {summarizeBeatPoints(baseModeBeatPoints)}
              </p>
            </div>
            <div className="rounded-2xl bg-white/80 p-3">
              <div className="text-xs font-medium text-ink/55">剪映参考点</div>
              <p className="mt-2 text-sm leading-6 text-ink/75">
                {summarizeBeatPoints(referenceBeatPoints)}
              </p>
            </div>
            <div className="rounded-2xl bg-white/80 p-3">
              <div className="text-xs font-medium text-ink/55">校准后预览点</div>
              <p className="mt-2 text-sm leading-6 text-ink/75">
                {summarizeBeatPoints(calibratedPreviewBeatPoints)}
              </p>
            </div>
          </div>
          <p className="mt-3 text-xs leading-5 text-ink/55">
            下方“节拍点（秒）”是当前会保存并给分镜使用的结果；如果预览点和下方不一致，点击保存后会以服务端重新计算结果为准。
          </p>
        </div>

        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("beatPoints")}>
            节拍点（秒）
          </AiFieldLabel>
          <textarea
            readOnly={!canEditBeats}
            rows={4}
            value={beatPointsText}
            onChange={(event) => {
              setBeatPointsText(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "beatPoints"));
            }}
            placeholder="上传 BGM 音频识别后自动生成"
            className={aiInputClassName(
              llmSuggestedFields.includes("beatPoints"),
              "input-field disabled:bg-sand/40"
            )}
          />
          <p className="mt-2 text-xs text-ink/55">
            分镜生成依赖真实 BGM 节拍点；未完成音频识别前无法进入分镜。
          </p>
        </label>

        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("rhythmNotes")}>
            节奏说明
          </AiFieldLabel>
          <textarea
            readOnly={!canEditBeats}
            rows={5}
            value={rhythmNotesText}
            onChange={(event) => {
              setRhythmNotesText(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "rhythmNotes"));
            }}
            className={aiInputClassName(
              llmSuggestedFields.includes("rhythmNotes"),
              "input-field disabled:bg-sand/40"
            )}
          />
        </label>

        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("photoMotion")}>
            照片素材动效建议
          </AiFieldLabel>
          <textarea
            readOnly={!canEditBeats}
            rows={4}
            value={photoText}
            onChange={(event) => {
              setPhotoText(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "photoMotion"));
            }}
            className={aiInputClassName(
              llmSuggestedFields.includes("photoMotion"),
              "input-field disabled:bg-sand/40"
            )}
          />
        </label>
      </div>
    </form>
  );
}
