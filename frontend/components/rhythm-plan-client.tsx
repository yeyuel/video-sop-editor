"use client";

import type { FormEvent } from "react";
import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { generateRhythmPlan, saveRhythmPlan, uploadRhythmAudio, deleteRhythmAudio } from "@/lib/browser-api";
import {
  capcutBeatModeOptions,
  filterBeatsForCapcutMode,
  getCapcutBeatModeDescription
} from "@/lib/capcut-beat";
import type { RhythmPlan } from "@/types/domain";

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
  if (source === "rule") {
    return "规则生成";
  }
  if (source === "rule_fallback") {
    return "识别失败回退";
  }
  return "手动编辑";
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
    tone?: "error" | "success";
  } | null>(null);
  const [isPending, startTransition] = useTransition();

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

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await generateRhythmPlan(projectId);
        syncFromPlan(nextPlan);
        router.refresh();
        setNotice({ title: "节奏规划已生成", message: "已按规则生成节拍点和节奏说明。" });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成节奏规划失败，请稍后重试。"
        );
      }
    });
  }

  function handleBeatModeChange(nextMode: string) {
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
    if (!audioFile) {
      setError("请先选择一个音频文件。");
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await uploadRhythmAudio(projectId, audioFile);
        syncFromPlan(nextPlan);
        setAudioFile(null);
        router.refresh();
        if (nextPlan.analysisSource === "rule_fallback") {
          setNotice({
            title: "已回退到规则生成",
            message: nextPlan.analysisNotes[0] ?? "音频识别失败，已改用规则节拍点。",
            tone: "error"
          });
        } else {
          setNotice({
            title: "音频识别完成",
            message: `识别 BPM ${nextPlan.detectedBpm || "—"}，原始节拍 ${nextPlan.rawBeatPoints.length || nextPlan.beatPoints.length} 个，当前模式输出 ${nextPlan.beatPoints.length} 个节拍点。`
          });
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "音频节拍识别失败，请稍后重试。"
        );
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
        setNotice({ title: "音频已移除", message: "当前节奏规划仍保留，可继续手工编辑或重新上传。" });
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
        visible={isPending}
      />
      <ToastNotice
        message={notice?.message ?? ""}
        title={notice?.title ?? ""}
        tone={notice?.tone}
        visible={Boolean(notice)}
      />
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "生成中..." : "根据项目生成节奏规划"}
        </button>
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "保存中..." : "保存节奏规划"}
        </button>
        <button
          type="button"
          onClick={handleAudioUpload}
          disabled={isPending || !audioFile}
          className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "识别中..." : "上传音频并识别节拍"}
        </button>
        {plan.audioFileName ? (
          <button
            type="button"
            onClick={handleDeleteAudio}
            disabled={isPending}
            className="inline-flex rounded-full border border-clay/25 bg-white px-5 py-3 text-sm font-medium text-clay transition hover:bg-[#fff1ea] disabled:cursor-not-allowed disabled:opacity-60"
          >
            移除已绑定音频
          </button>
        ) : null}
      </div>

      {plan.analysisSource === "rule_fallback" ? (
        <div className="rounded-2xl border border-clay/25 bg-[#fff7f2] px-4 py-3 text-sm leading-6 text-clay">
          {plan.analysisNotes[0] ?? "音频识别失败，当前显示的是规则生成的节拍点。"}
        </div>
      ) : null}

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-5 md:grid-cols-2">
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">
            音频上传（支持 WAV / MP3 / M4A / AAC / OGG / MGG / FLAC / WMA）
          </span>
          <input
            type="file"
            accept=".wav,.mp3,.m4a,.aac,.ogg,.mgg,.flac,.wma,audio/*"
            onChange={(event) => setAudioFile(event.target.files?.[0] ?? null)}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 text-sm outline-none transition focus:border-pine"
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

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">BGM 风格</span>
          <input
            required
            value={plan.bgmStyle}
            onChange={(event) => setPlan({ ...plan, bgmStyle: event.target.value })}
            placeholder="例如：冷感氛围电子 + 轻鼓点"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
          <p className="mt-2 text-xs text-ink/55">
            优先使用 librosa 识别真实节拍点；不可用时自动回退到能量起音检测。
          </p>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">参考曲目</span>
          <input
            required
            value={plan.selectedTrackName}
            onChange={(event) => setPlan({ ...plan, selectedTrackName: event.target.value })}
            placeholder="例如：snow-dream-demo"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节拍模式（对标剪映）</span>
          <select
            value={plan.beatMode}
            onChange={(event) => handleBeatModeChange(event.target.value)}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
          {plan.rawBeatPoints.length > 0 ? (
            <p className="mt-1 text-xs text-ink/55">
              已缓存细粒度 {plan.rawBeatPoints.length} 个
              {plan.coarseBeatPoints.length > 0
                ? `、粗粒度 ${plan.coarseBeatPoints.length} 个`
                : ""}
              节拍；切换模式会自动重新采点，保存后写入项目。
            </p>
          ) : null}
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">暗场建议点（秒）</span>
          <input
            value={darkCutsText}
            onChange={(event) => setDarkCutsText(event.target.value)}
            placeholder="例如：15, 30, 45"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">节拍点（秒）</span>
          <textarea
            required
            rows={4}
            value={beatPointsText}
            onChange={(event) => setBeatPointsText(event.target.value)}
            placeholder="例如：0, 0.5, 1, 1.5, 2"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
          <p className="mt-2 text-xs text-ink/55">
            分镜生成会优先参考这里的节拍点做卡点切镜，所以 workflow 顺序已调整为“节奏
            → 分镜”。
          </p>
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">节奏说明</span>
          <textarea
            rows={5}
            value={rhythmNotesText}
            onChange={(event) => setRhythmNotesText(event.target.value)}
            placeholder="每行一条，例如：前 3 秒保证强开头"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">照片素材动效建议</span>
          <textarea
            rows={4}
            value={photoText}
            onChange={(event) => setPhotoText(event.target.value)}
            placeholder="每行一条，例如：照片素材优先慢推，不和视频一起快切"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
      </div>
    </form>
  );
}
