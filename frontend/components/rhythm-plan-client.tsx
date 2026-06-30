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
import { BGM_RECOMMEND_LLM_STAGES, RHYTHM_LLM_STAGES } from "@/lib/llm-progress-stages";
import { getBgmPhaseLabel, isRhythmAnalyzed } from "@/lib/rhythm-workflow";
import { useLlmProgress } from "@/lib/use-llm-progress";
import {
  capcutBeatModeOptions,
  filterBeatsForCapcutMode,
  getCapcutBeatModeDescription
} from "@/lib/capcut-beat";
import type { BgmRecommendation, RhythmPlan } from "@/types/domain";

type RhythmPlanClientProps = {
  projectId: string;
  targetDurationSec: number;
  initialPlan: RhythmPlan;
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

export function RhythmPlanClient({
  projectId,
  targetDurationSec,
  initialPlan
}: RhythmPlanClientProps) {
  const router = useRouter();
  const [plan, setPlan] = useState(initialPlan);
  const [beatPointsText, setBeatPointsText] = useState(numberListToText(initialPlan.beatPoints));
  const [rhythmNotesText, setRhythmNotesText] = useState(listToText(initialPlan.rhythmNotes));
  const [darkCutsText, setDarkCutsText] = useState(numberListToText(initialPlan.darkCutSuggestions));
  const [photoText, setPhotoText] = useState(listToText(initialPlan.photoMotionSuggestions));
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
    setPlan(nextPlan);
    setBeatPointsText(numberListToText(nextPlan.beatPoints));
    setRhythmNotesText(listToText(nextPlan.rhythmNotes));
    setDarkCutsText(numberListToText(nextPlan.darkCutSuggestions));
    setPhotoText(listToText(nextPlan.photoMotionSuggestions));
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
        setBeatPointsText(numberListToText(filtered));
      }
      return nextPlan;
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
        state={
          llmProgress ?? {
            title: "",
            stages: BGM_RECOMMEND_LLM_STAGES,
            currentStage: "preparing",
            message: "",
            detail: "",
            progress: 0,
            startedAt: Date.now()
          }
        }
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
